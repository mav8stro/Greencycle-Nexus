"""
Root routes module for backwards compatibility.
Provides full backwards-compatible endpoints for legacy clients, API consumers,
and the GreenCycle Nexus web application.
"""
from datetime import datetime, timedelta, date, timezone
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import User, WasteEntry, Payment, Pickup, Address, LocalBody, Ward
from app.services.auth_service import (
    token_required, admin_required, make_token, hash_password, verify_password, log_audit
)

bp = Blueprint('main', __name__)

# ─── 1. Auth: Registration ───────────────────────────────────────────────────

@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    pin = data.get('pin', '').strip() or data.get('password', '').strip()
    role = data.get('role', 'citizen').strip().lower()
    full_name = data.get('full_name', '').strip()

    if not phone or len(phone) < 4:
        return jsonify({'error': 'Valid phone number required'}), 400

    if not pin or len(pin) < 4:
        return jsonify({'error': '4-digit PIN or password required'}), 400

    if role not in ('citizen', 'worker', 'volunteer', 'admin'):
        return jsonify({'error': 'Invalid role specified'}), 400

    # Public users cannot register as Admin if an admin already exists
    if role == 'admin' and not request.headers.get('Authorization'):
        if User.query.filter_by(role='admin').first():
            return jsonify({'error': 'Admin accounts can only be created by existing authorized administrators'}), 403

    if User.query.filter_by(phone=phone).first():
        return jsonify({'error': 'Phone already registered'}), 409

    user = User(
        phone=phone,
        password_hash=hash_password(pin),
        role=role,
        full_name=full_name or (role.capitalize() if role else 'Citizen'),
        is_active=True
    )
    db.session.add(user)
    db.session.flush()

    # Create address & initial scheduled pickup for citizen
    if role == 'citizen':
        local_body_id = data.get('local_body_id') or 1
        ward_id = data.get('ward_id') or 1
        addr = Address(
            user_id=user.id,
            house_number=data.get('house_number', '1/A'),
            street_address=data.get('street_address', 'Main Road'),
            local_body_id=local_body_id,
            ward_id=ward_id,
            district=data.get('district', 'Ernakulam'),
            pincode=data.get('pincode', '682001'),
            customer_type=data.get('customer_type', 'Household'),
            is_primary=True
        )
        db.session.add(addr)

        pickup = Pickup(
            citizen_id=user.id,
            scheduled_date=(datetime.now(timezone.utc) + timedelta(days=3)).date(),
            status='Scheduled',
            scheduled_slot='08:00 AM - 11:00 AM'
        )
        db.session.add(pickup)

    db.session.commit()
    token = make_token(user.id, user.role)
    return jsonify({
        'user_id': user.id,
        'role': user.role,
        'token': token,
        'user': user.to_dict()
    }), 201


# ─── 2. Auth: Login ──────────────────────────────────────────────────────────

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    phone = data.get('phone', '').strip() or data.get('email', '').strip()
    pin = data.get('pin', '').strip() or data.get('password', '').strip()

    if not phone or not pin:
        return jsonify({'error': 'Phone and PIN required'}), 400

    user = User.query.filter((User.phone == phone) | (User.email == phone)).first()
    if not user:
        return jsonify({'error': 'Invalid phone or PIN'}), 401

    if not user.is_active:
        return jsonify({'error': 'This account has been deactivated. Contact Admin.'}), 403

    if not verify_password(pin, user.password_hash):
        return jsonify({'error': 'Invalid phone or PIN'}), 401

    token = make_token(user.id, user.role)
    return jsonify({
        'user_id': user.id,
        'role': user.role,
        'token': token,
        'user': user.to_dict()
    })


# ─── 3. Waste: Log Waste Entry ───────────────────────────────────────────────

@bp.route('/waste', methods=['POST'])
@token_required
def log_waste():
    data = request.get_json() or {}
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
        other=other,
        date=datetime.now(timezone.utc),
        approved=False
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.to_dict()), 201


# ─── 4. Waste: User History ──────────────────────────────────────────────────

@bp.route('/history/<int:user_id>', methods=['GET'])
@token_required
def history(user_id):
    # IDOR Protection
    if request.user_role != 'admin' and request.user_id != user_id:
        return jsonify({'error': 'Access forbidden: You cannot view another citizen\'s history'}), 403

    entries = WasteEntry.query.filter_by(user_id=user_id).order_by(WasteEntry.date.desc()).all()
    return jsonify([e.to_dict() for e in entries])


# ─── 5. Admin: Pending Approvals ─────────────────────────────────────────────

@bp.route('/pending', methods=['GET'])
@admin_required
def pending():
    entries = WasteEntry.query.filter_by(approved=False).order_by(WasteEntry.date.desc()).all()
    result = []
    for e in entries:
        d = e.to_dict()
        user = db.session.get(User, e.user_id)
        d['phone'] = user.phone if user else 'Unknown'
        result.append(d)
    return jsonify(result)


# ─── 6. Admin: Approve Waste Entry ───────────────────────────────────────────

@bp.route('/approve/<int:entry_id>', methods=['POST'])
@admin_required
def approve(entry_id):
    entry = db.session.get(WasteEntry, entry_id)
    if not entry:
        return jsonify({'error': 'Waste entry not found'}), 404
    if entry.approved:
        return jsonify({'error': 'Already approved'}), 400

    entry.approved = True
    amount = entry.total_amount()
    due_date = (datetime.now(timezone.utc) + timedelta(days=7)).date()

    payment = Payment(
        user_id=entry.user_id,
        amount=amount,
        billing_period=f'Waste Collection #{entry.id}',
        due_date=due_date,
        status='Pending'
    )
    db.session.add(payment)
    db.session.commit()
    return jsonify({'message': 'Approved', 'payment_created': payment.to_dict()})


# ─── 7. Payments: User Payments ──────────────────────────────────────────────

@bp.route('/payments/<int:user_id>', methods=['GET'])
@token_required
def payments(user_id):
    # IDOR Protection
    if request.user_role != 'admin' and request.user_id != user_id:
        return jsonify({'error': 'Access forbidden: You cannot view another citizen\'s payments'}), 403

    pays = Payment.query.filter_by(user_id=user_id).order_by(Payment.due_date.desc()).all()
    total_due = sum(p.amount for p in pays if not p.paid)
    return jsonify({'payments': [p.to_dict() for p in pays], 'total_due': round(total_due, 2)})


# ─── 8. Schedule: User Schedule ──────────────────────────────────────────────

@bp.route('/schedule/<int:user_id>', methods=['GET'])
@token_required
def schedule(user_id):
    # IDOR Protection
    if request.user_role != 'admin' and request.user_id != user_id:
        return jsonify({'error': 'Access forbidden: You cannot view another citizen\'s schedule'}), 403

    pickups = Pickup.query.filter_by(user_id=user_id).order_by(Pickup.date.asc()).all()
    return jsonify([p.to_dict() for p in pickups])


# ─── 9. Worker: Worker Pickups ───────────────────────────────────────────────

@bp.route('/pickups/<int:worker_id>', methods=['GET'])
@token_required
def worker_pickups(worker_id):
    # IDOR Protection
    if request.user_role != 'admin' and request.user_id != worker_id:
        return jsonify({'error': 'Access forbidden: You cannot view another worker\'s pickups'}), 403

    pickups = Pickup.query.filter_by(worker_id=worker_id).order_by(Pickup.date.asc()).all()
    result = []
    for p in pickups:
        d = p.to_dict()
        user = db.session.get(User, p.citizen_id)
        d['citizen_phone'] = user.phone if user else 'Unknown'
        result.append(d)
    return jsonify(result)


# ─── 10. Worker: Mark Pickup Collected ───────────────────────────────────────

@bp.route('/collect/<int:pickup_id>', methods=['POST'])
@token_required
def collect(pickup_id):
    pickup = db.session.get(Pickup, pickup_id)
    if not pickup:
        return jsonify({'error': 'Pickup not found'}), 404

    # If worker, ensure pickup belongs to them (or is unassigned)
    if request.user_role == 'worker' and pickup.collector_id and pickup.collector_id != request.user_id:
        return jsonify({'error': 'Access forbidden: This pickup is not assigned to you'}), 403

    pickup.status = 'Collected'
    pickup.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'message': 'Marked as collected', 'pickup': pickup.to_dict()})
