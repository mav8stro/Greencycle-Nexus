from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import User, Address, LocalBody, Ward, Volunteer, VolunteerReward
from app.services.auth_service import hash_password, verify_password, make_token, token_required, log_audit
from datetime import datetime, timezone, date

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip() or None
    pin_or_pass = data.get('pin', '').strip() or data.get('password', '').strip()
    full_name = data.get('full_name', '').strip()
    role = data.get('role', 'citizen').lower()

    if not phone or len(phone) < 10:
        return jsonify({'error': 'Valid 10-digit mobile number required'}), 400
    if not pin_or_pass or len(pin_or_pass) < 4:
        return jsonify({'error': 'PIN or Password must be at least 4 characters'}), 400

    # CRITICAL SECURITY RULE: Public users cannot register as Admin
    if role == 'admin':
        return jsonify({'error': 'Admin accounts can only be created by existing authorized administrators'}), 403

    if role not in ('citizen', 'worker', 'volunteer'):
        return jsonify({'error': 'Invalid role specified'}), 400

    if User.query.filter((User.phone == phone) | (User.email == email if email else False)).first():
        return jsonify({'error': 'Phone number or email is already registered'}), 409

    # Create User
    user = User(
        phone=phone,
        email=email,
        password_hash=hash_password(pin_or_pass),
        role=role,
        full_name=full_name or ('Citizen' if role == 'citizen' else ('Worker' if role == 'worker' else 'Volunteer')),
        is_active=True
    )
    db.session.add(user)
    db.session.flush()

    # If Citizen: capture comprehensive Kerala civic details
    if role == 'citizen':
        local_body_id = data.get('local_body_id')
        ward_id = data.get('ward_id')
        house_no = data.get('house_number', 'Not provided').strip()
        street_address = data.get('street_address', 'Door-to-door route').strip()
        district = data.get('district', 'Ernakulam').strip()
        pincode = data.get('pincode', '682001').strip()
        customer_type = data.get('customer_type', 'Household').strip()
        resident_count = int(data.get('resident_count', 4))
        preferred_day = data.get('preferred_day', 'Monday').strip()
        preferred_slot = data.get('preferred_slot', '08:00 AM - 11:00 AM').strip()

        # Fallback to first local body and ward if none supplied
        if not local_body_id:
            lb = LocalBody.query.first()
            local_body_id = lb.id if lb else 1
        if not ward_id:
            w = Ward.query.filter_by(local_body_id=local_body_id).first()
            ward_id = w.id if w else 1

        addr = Address(
            user_id=user.id,
            house_number=house_no,
            street_address=street_address,
            local_body_id=local_body_id,
            ward_id=ward_id,
            district=district,
            pincode=pincode,
            customer_type=customer_type,
            resident_count=resident_count,
            preferred_day=preferred_day,
            preferred_slot=preferred_slot,
            is_primary=True
        )
        db.session.add(addr)

    # If Volunteer: create pending volunteer profile
    elif role == 'volunteer':
        vol_count = Volunteer.query.count() + 1
        vol_code = f"GCN-VOL-2026-{vol_count:05d}"
        vol = Volunteer(
            volunteer_id_code=vol_code,
            user_id=user.id,
            full_name=user.full_name,
            email=email or f"{phone}@volunteer.greencycle.in",
            phone=phone,
            address=data.get('address', 'Kerala, India'),
            district=data.get('district', 'Ernakulam'),
            local_body_id=data.get('local_body_id'),
            skills=data.get('skills', 'Community Engagement'),
            availability=data.get('availability', 'Weekends'),
            status='Pending Approval'
        )
        db.session.add(vol)
        db.session.flush()
        reward = VolunteerReward(volunteer_id=vol.id, points=10, total_hours=0.0)
        db.session.add(reward)

    db.session.commit()
    log_audit('USER_REGISTER', 'User', user.id, None, {'phone': user.phone, 'role': user.role}, user.id, user.role)

    token = make_token(user.id, user.role)
    return jsonify({
        'message': 'Account registered successfully',
        'token': token,
        'user': user.to_dict()
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    identifier = data.get('phone', '').strip() or data.get('email', '').strip()
    pin_or_pass = data.get('pin', '').strip() or data.get('password', '').strip()

    if not identifier or not pin_or_pass:
        return jsonify({'error': 'Please provide Mobile/Email and PIN/Password'}), 400

    user = User.query.filter((User.phone == identifier) | (User.email == identifier)).first()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'This account has been deactivated. Contact Admin.'}), 403

    if not verify_password(pin_or_pass, user.password_hash):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = make_token(user.id, user.role)
    log_audit('LOGIN', 'User', user.id, None, {'login_time': datetime.now(timezone.utc).isoformat()}, user.id, user.role)

    return jsonify({
        'token': token,
        'user': user.to_dict(),
        'must_change_password': user.must_change_password
    })

@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password():
    data = request.get_json() or {}
    old_pin = data.get('old_password', '').strip() or data.get('old_pin', '').strip()
    new_pin = data.get('new_password', '').strip() or data.get('new_pin', '').strip()

    if not new_pin or len(new_pin) < 4:
        return jsonify({'error': 'New password/PIN must be at least 4 characters'}), 400

    user = request.current_user
    if old_pin and not verify_password(old_pin, user.password_hash):
        return jsonify({'error': 'Current password does not match'}), 400

    user.password_hash = hash_password(new_pin)
    user.must_change_password = False
    db.session.commit()

    log_audit('CHANGE_PASSWORD', 'User', user.id, None, None, user.id, user.role)
    return jsonify({'message': 'Password updated successfully'})

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_me():
    return jsonify({
        'user': request.current_user.to_dict()
    })
