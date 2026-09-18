from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, date, timedelta
from app.extensions import db
from app.models import (
    User, Address, CollectionRequest, CollectionRequestItem, Pickup,
    WasteCategory, Payment, PaymentReceipt, Complaint, Notification,
    CollectionSchedule, LocalBody, Ward
)
from app.services.auth_service import token_required, role_required, log_audit, create_notification
from app.services.finance_engine import get_applicable_user_fee

citizen_bp = Blueprint('citizen', __name__, url_prefix='/api/citizen')

@citizen_bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    # IDOR Protection: Always returns authenticated user's profile
    user = request.current_user
    addr = user.addresses[0] if user.addresses else None
    return jsonify({
        'user': user.to_dict(),
        'address': addr.to_dict() if addr else None
    })

@citizen_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile():
    user = request.current_user
    data = request.get_json() or {}

    if 'full_name' in data:
        user.full_name = data['full_name'].strip()
    if 'email' in data and data['email']:
        user.email = data['email'].strip()

    addr = user.addresses[0] if user.addresses else None
    if addr:
        if 'house_number' in data: addr.house_number = data['house_number'].strip()
        if 'street_address' in data: addr.street_address = data['street_address'].strip()
        if 'preferred_day' in data: addr.preferred_day = data['preferred_day']
        if 'preferred_slot' in data: addr.preferred_slot = data['preferred_slot']
        if 'resident_count' in data: addr.resident_count = int(data['resident_count'])
        if 'pincode' in data: addr.pincode = data['pincode'].strip()

    db.session.commit()
    log_audit('UPDATE_PROFILE', 'User', user.id, None, {'phone': user.phone}, user.id, user.role)
    return jsonify({'message': 'Profile updated successfully', 'user': user.to_dict()})

@citizen_bp.route('/fee-card', methods=['GET'])
@token_required
def get_fee_card():
    """Generates the official Kerala-style digital User Fee Card data."""
    user = request.current_user
    addr = user.addresses[0] if user.addresses else None

    local_body_id = addr.local_body_id if addr else 1
    cust_type = addr.customer_type if addr else 'Household'

    # Get applicable configured tariff rule
    tariff = get_applicable_user_fee(local_body_id, cust_type)

    # Latest payment record
    latest_pay = Payment.query.filter_by(user_id=user.id).order_by(Payment.due_date.desc()).first()

    current_month_str = datetime.now().strftime('%B %Y')
    next_month_due = (datetime.now().replace(day=28) + timedelta(days=5)).strftime('%Y-%m-%d')

    fee_status = 'Paid' if latest_pay and latest_pay.status == 'Successful' and latest_pay.billing_period == current_month_str else 'Due'

    return jsonify({
        'citizen_id': f"GCN-CIT-{user.id:05d}",
        'customer_name': user.full_name,
        'mobile_number': user.phone,
        'local_body': addr.local_body.name if addr and addr.local_body else 'Kochi Municipal Corporation',
        'local_body_type': addr.local_body.body_type if addr and addr.local_body else 'Corporation',
        'ward': f"Ward {addr.ward.ward_number}: {addr.ward.ward_name}" if addr and addr.ward else 'Ward 12',
        'house_building_number': addr.house_number if addr else 'Flat 4B',
        'street_address': addr.street_address if addr else 'Marine Drive',
        'customer_type': cust_type,
        'service_type': tariff['service_type'],
        'applicable_fee': tariff['base_fee'],
        'billing_period': current_month_str,
        'payment_status': fee_status,
        'receipt_number': latest_pay.receipt.receipt_number if (latest_pay and latest_pay.receipt) else 'N/A',
        'collector_operator': latest_pay.collector.full_name if (latest_pay and latest_pay.collector) else 'Haritha Karma Sena (HKS)',
        'last_payment_date': latest_pay.paid_at.strftime('%d-%m-%Y') if (latest_pay and latest_pay.paid_at) else 'None Recorded',
        'next_due_date': next_month_due,
        'tariff_notes': tariff['notes']
    })

@citizen_bp.route('/requests', methods=['POST'])
@token_required
def submit_collection_request():
    """
    Submits a collection request:
    - Checks categories
    - Flags special waste handling (E-Waste, Sanitary, Hazardous)
    - Saves estimated weights
    - Auto-generates unique request number
    """
    user = request.current_user
    data = request.get_json() or {}

    addr = user.addresses[0] if user.addresses else None
    if not addr:
        return jsonify({'error': 'Please register or update your address first.'}), 400

    items_data = data.get('items', [])
    if not items_data:
        return jsonify({'error': 'Please select at least one waste category with estimated weight.'}), 400

    req_date_str = data.get('requested_date')
    try:
        req_date = datetime.strptime(req_date_str, '%Y-%m-%d').date() if req_date_str else (date.today() + timedelta(days=2))
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    req_slot = data.get('requested_slot', addr.preferred_slot or '08:00 AM - 11:00 AM')
    notes = data.get('notes', '').strip()
    photo_url = data.get('photo_url')

    # Verify categories and flag special waste
    has_special_waste = False
    special_guidelines = []

    req_count = CollectionRequest.query.count() + 1
    req_number = f"GCN-REQ-2026-{req_count:05d}"

    col_req = CollectionRequest(
        req_number=req_number,
        citizen_id=user.id,
        local_body_id=addr.local_body_id,
        ward_id=addr.ward_id,
        address_id=addr.id,
        requested_date=req_date,
        requested_slot=req_slot,
        notes=notes,
        photo_url=photo_url,
        status='Requested',
        is_special_waste=False
    )
    db.session.add(col_req)
    db.session.flush()

    total_est = 0.0
    for it in items_data:
        cat_id = it.get('waste_category_id')
        est_weight = float(it.get('estimated_weight', 0.0))
        if est_weight <= 0:
            continue
        cat = db.session.get(WasteCategory, cat_id)
        if not cat:
            continue

        if cat.requires_special_handling:
            has_special_waste = True
            special_guidelines.append(f"{cat.name}: {cat.sorting_instructions or 'Requires special segregated packaging'}")

        total_est += est_weight
        req_item = CollectionRequestItem(
            request_id=col_req.id,
            waste_category_id=cat.id,
            estimated_weight=est_weight
        )
        db.session.add(req_item)

    col_req.is_special_waste = has_special_waste
    db.session.commit()

    log_audit('COLLECTION_REQUEST_CREATE', 'CollectionRequest', col_req.id, None, {'req_number': req_number, 'is_special': has_special_waste}, user.id, user.role)
    create_notification(user.id, 'Collection Request Received', f"Request #{req_number} received for {req_date}. Status: Requested.", 'request')

    return jsonify({
        'message': 'Collection request submitted successfully!',
        'request': col_req.to_dict(),
        'special_waste_alert': has_special_waste,
        'special_guidelines': special_guidelines
    }), 201

@citizen_bp.route('/requests', methods=['GET'])
@token_required
def get_my_requests():
    # IDOR Protection: returns only the authenticated citizen's requests
    user = request.current_user
    reqs = CollectionRequest.query.filter_by(citizen_id=user.id).order_by(CollectionRequest.created_at.desc()).all()
    return jsonify([r.to_dict() for r in reqs])

@citizen_bp.route('/requests/<int:req_id>', methods=['GET'])
@token_required
def get_request_detail(req_id):
    col_req = db.get_or_404(CollectionRequest, req_id)
    # IDOR Protection: Prevent citizen from viewing other citizens' requests
    if col_req.citizen_id != request.user_id and request.user_role not in ('admin', 'worker'):
        return jsonify({'error': 'Unauthorized to access this collection request'}), 403
    return jsonify(col_req.to_dict())

@citizen_bp.route('/pickups', methods=['GET'])
@token_required
def get_my_pickups():
    # IDOR Protection
    user = request.current_user
    pickups = Pickup.query.filter_by(citizen_id=user.id).order_by(Pickup.scheduled_date.desc()).all()
    return jsonify([p.to_dict() for p in pickups])

@citizen_bp.route('/payments', methods=['GET'])
@token_required
def get_my_payments():
    # IDOR Protection
    user = request.current_user
    pays = Payment.query.filter_by(user_id=user.id).order_by(Payment.due_date.desc()).all()
    total_due = sum(p.amount for p in pays if p.status == 'Pending')
    return jsonify({
        'payments': [p.to_dict() for p in pays],
        'total_due': round(total_due, 2)
    })

@citizen_bp.route('/complaints', methods=['POST'])
@token_required
def submit_complaint():
    user = request.current_user
    data = request.get_json() or {}

    category = data.get('category', 'Other')
    description = data.get('description', '').strip()
    pickup_id = data.get('pickup_id')
    priority = data.get('priority', 'Medium')
    evidence = data.get('evidence_photo')

    if not description:
        return jsonify({'error': 'Please provide details for the complaint.'}), 400

    comp_count = Complaint.query.count() + 1
    comp_number = f"CMP-2026-{comp_count:05d}"

    complaint = Complaint(
        comp_number=comp_number,
        citizen_id=user.id,
        pickup_id=pickup_id,
        category=category,
        description=description,
        evidence_photo=evidence,
        priority=priority,
        status='Open'
    )
    db.session.add(complaint)
    db.session.commit()

    log_audit('COMPLAINT_CREATE', 'Complaint', complaint.id, None, {'category': category}, user.id, user.role)
    create_notification(user.id, 'Complaint Registered', f"Complaint #{comp_number} has been registered and forwarded to Local Body Admin.", 'complaint')

    return jsonify({
        'message': 'Complaint registered successfully',
        'complaint': complaint.to_dict()
    }), 201

@citizen_bp.route('/complaints', methods=['GET'])
@token_required
def get_my_complaints():
    user = request.current_user
    comps = Complaint.query.filter_by(citizen_id=user.id).order_by(Complaint.created_at.desc()).all()
    return jsonify([c.to_dict() for c in comps])

@citizen_bp.route('/notifications', methods=['GET'])
@token_required
def get_notifications():
    user = request.current_user
    notifs = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(30).all()
    unread_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return jsonify({
        'notifications': [n.to_dict() for n in notifs],
        'unread_count': unread_count
    })

@citizen_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@token_required
def mark_notification_read(notif_id):
    notif = db.get_or_404(Notification, notif_id)
    if notif.user_id != request.user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    notif.is_read = True
    db.session.commit()
    return jsonify({'message': 'Notification marked as read'})

@citizen_bp.route('/schedules', methods=['GET'])
@token_required
def get_ward_schedules():
    user = request.current_user
    addr = user.addresses[0] if user.addresses else None
    if not addr:
        scheds = CollectionSchedule.query.filter_by(active=True).all()
    else:
        scheds = CollectionSchedule.query.filter_by(ward_id=addr.ward_id, active=True).all()
    return jsonify([s.to_dict() for s in scheds])
