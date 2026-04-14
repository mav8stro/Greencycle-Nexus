from flask import Blueprint, request, jsonify
from app import db
from app.models import User, WasteEntry, Payment, Pickup
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import base64
import json

bp = Blueprint('main', __name__)

# ─── Helpers ────────────────────────────────────────────────────────────────

def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def make_token(user_id, role):
    payload = json.dumps({'user_id': user_id, 'role': role})
    return base64.b64encode(payload.encode()).decode()

def decode_token(token):
    try:
        payload = base64.b64decode(token.encode()).decode()
        return json.loads(payload)
    except Exception:
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = auth.replace('Bearer ', '').strip()
        data = decode_token(token)
        if not data:
            return jsonify({'error': 'Unauthorized'}), 401
        request.user_id = data['user_id']
        request.user_role = data['role']
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = auth.replace('Bearer ', '').strip()
        data = decode_token(token)
        if not data or data['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        request.user_id = data['user_id']
        request.user_role = data['role']
        return f(*args, **kwargs)
    return decorated


# ─── Auth ────────────────────────────────────────────────────────────────────

@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    phone = data.get('phone', '').strip()
    pin = data.get('pin', '').strip()
    role = data.get('role', 'citizen')

    if not phone or not pin or len(pin) != 4:
        return jsonify({'error': 'Phone and 4-digit PIN required'}), 400

    if role not in ('citizen', 'worker', 'admin'):
        return jsonify({'error': 'Invalid role'}), 400

    if User.query.filter_by(phone=phone).first():
        return jsonify({'error': 'Phone already registered'}), 409

    user = User(phone=phone, pin=hash_pin(pin), role=role)
    db.session.add(user)
    db.session.commit()

    # Create an initial pickup schedule for citizens
    if role == 'citizen':
        pickup = Pickup(
            user_id=user.id,
            date=datetime.utcnow() + timedelta(days=3),
            status='scheduled'
        )
        db.session.add(pickup)
        db.session.commit()

    token = make_token(user.id, user.role)
    return jsonify({'user_id': user.id, 'role': user.role, 'token': token}), 201


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    phone = data.get('phone', '').strip()
    pin = data.get('pin', '').strip()

    user = User.query.filter_by(phone=phone, pin=hash_pin(pin)).first()
    if not user:
        return jsonify({'error': 'Invalid phone or PIN'}), 401

    token = make_token(user.id, user.role)
    return jsonify({'user_id': user.id, 'role': user.role, 'token': token})


# ─── Waste ───────────────────────────────────────────────────────────────────

@bp.route('/waste', methods=['POST'])
@token_required
def log_waste():
    data = request.get_json()
    try:
        food = float(data.get('food', 0))
        plastic = float(data.get('plastic', 0))
        other = float(data.get('other', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid weight values'}), 400

    if food < 0 or plastic < 0 or other < 0:
        return jsonify({'error': 'Weights cannot be negative'}), 400

    entry = WasteEntry(
        user_id=request.user_id,
        food=food,
        plastic=plastic,
        other=other
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.to_dict()), 201


@bp.route('/history/<int:user_id>', methods=['GET'])
@token_required
def history(user_id):
    entries = WasteEntry.query.filter_by(user_id=user_id).order_by(WasteEntry.date.desc()).all()
    return jsonify([e.to_dict() for e in entries])


# ─── Admin ───────────────────────────────────────────────────────────────────

@bp.route('/pending', methods=['GET'])
@admin_required
def pending():
    entries = WasteEntry.query.filter_by(approved=False).order_by(WasteEntry.date.desc()).all()
    result = []
    for e in entries:
        d = e.to_dict()
        user = User.query.get(e.user_id)
        d['phone'] = user.phone if user else 'Unknown'
        result.append(d)
    return jsonify(result)


@bp.route('/approve/<int:entry_id>', methods=['POST'])
@admin_required
def approve(entry_id):
    entry = WasteEntry.query.get_or_404(entry_id)
    if entry.approved:
        return jsonify({'error': 'Already approved'}), 400

    entry.approved = True

    amount = entry.total_amount()
    payment = Payment(
        user_id=entry.user_id,
        amount=amount,
        due_date=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(payment)
    db.session.commit()
    return jsonify({'message': 'Approved', 'payment_created': payment.to_dict()})


# ─── Payments ────────────────────────────────────────────────────────────────

@bp.route('/payments/<int:user_id>', methods=['GET'])
@token_required
def payments(user_id):
    pays = Payment.query.filter_by(user_id=user_id).order_by(Payment.due_date.desc()).all()
    total_due = sum(p.amount for p in pays if not p.paid)
    return jsonify({'payments': [p.to_dict() for p in pays], 'total_due': total_due})


# ─── Schedule ────────────────────────────────────────────────────────────────

@bp.route('/schedule/<int:user_id>', methods=['GET'])
@token_required
def schedule(user_id):
    pickups = Pickup.query.filter_by(user_id=user_id).order_by(Pickup.date.asc()).all()
    return jsonify([p.to_dict() for p in pickups])


# ─── Worker ──────────────────────────────────────────────────────────────────

@bp.route('/pickups/<int:worker_id>', methods=['GET'])
@token_required
def worker_pickups(worker_id):
    pickups = Pickup.query.filter_by(worker_id=worker_id).order_by(Pickup.date.asc()).all()
    result = []
    for p in pickups:
        d = p.to_dict()
        user = User.query.get(p.user_id)
        d['citizen_phone'] = user.phone if user else 'Unknown'
        result.append(d)
    return jsonify(result)


@bp.route('/collect/<int:pickup_id>', methods=['POST'])
@token_required
def collect(pickup_id):
    pickup = Pickup.query.get_or_404(pickup_id)
    pickup.status = 'collected'
    db.session.commit()
    return jsonify({'message': 'Marked as collected', 'pickup': pickup.to_dict()})
