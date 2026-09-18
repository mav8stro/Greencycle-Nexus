from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, date, timedelta
from app.extensions import db
from app.models import (
    User, Address, LocalBody, Ward, WasteCategory,
    UserFeeRule, MaterialRate, OperationalCost, Transaction, Payment, PaymentReceipt,
    Collector, Vehicle, Facility, MaterialMovement, CollectionSchedule, Pickup, PickupItem,
    CollectionRequest, Complaint, SystemConfig, Volunteer, Event, Attendance, AuditLog
)
from app.services.auth_service import admin_required, log_audit, create_notification, hash_password
from app.services.finance_engine import get_business_economics_summary, calculate_environmental_impact
import json

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def admin_dashboard():
    """
    CRITICAL REQUIREMENT:
    All metrics are computed from live database records, not hardcoded dummy data.
    """
    today = date.today()

    households = Address.query.filter_by(customer_type='Household').count()
    commercial = Address.query.filter(Address.customer_type != 'Household').count()
    active_collectors = Collector.query.filter_by(status='Active').count()
    
    scheduled_today = Pickup.query.filter_by(scheduled_date=today).count()
    completed_today = Pickup.query.filter(
        Pickup.scheduled_date == today,
        Pickup.status.in_(['Completed', 'Collected', 'Verified'])
    ).count()
    missed_today = max(0, scheduled_today - completed_today)

    total_waste_kg = sum(p.total_verified_weight or p.total_actual_weight for p in Pickup.query.all())

    # User Fees
    collected_fees = sum(p.amount for p in Payment.query.filter_by(status='Successful').all())
    pending_fees = sum(p.amount for p in Payment.query.filter_by(status='Pending').all())

    # Business Economics
    economics = get_business_economics_summary()
    impact = calculate_environmental_impact()

    # Category Breakdown for Charts
    categories = WasteCategory.query.filter_by(active=True).all()
    category_chart = []
    for cat in categories:
        items = PickupItem.query.filter_by(waste_category_id=cat.id).all()
        w = sum(it.verified_weight or it.actual_weight for it in items)
        category_chart.append({
            'name': cat.name,
            'code': cat.code,
            'weight_kg': round(w, 2)
        })

    # Recent activity
    recent_audit = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()

    return jsonify({
        'registered_households': households,
        'commercial_customers': commercial,
        'active_collectors': active_collectors,
        'today_scheduled_pickups': scheduled_today,
        'today_completed_pickups': completed_today,
        'today_missed_pickups': missed_today,
        'total_waste_collected_kg': round(total_waste_kg, 2),
        'pending_user_fees': round(pending_fees, 2),
        'collected_user_fees': round(collected_fees, 2),
        'material_revenue': economics['material_revenue'],
        'operating_cost': economics['total_operating_cost'],
        'net_operating_result': economics['net_operating_result'],
        'revenue_per_pickup': economics['revenue_per_pickup'],
        'cost_per_pickup': economics['cost_per_pickup'],
        'net_per_pickup': economics['net_per_pickup'],
        'revenue_per_kg': economics['revenue_per_kg'],
        'cost_per_kg': economics['cost_per_kg'],
        'net_per_kg': economics['net_per_kg'],
        'category_breakdown': category_chart,
        'environmental_impact': impact,
        'cost_breakdown': economics['cost_breakdown'],
        'recent_activity': [a.to_dict() for a in recent_audit]
    })

@admin_bp.route('/ward-analytics', methods=['GET'])
@admin_required
def get_ward_analytics():
    """Returns granular analytics filtered by Local Body and Ward."""
    local_body_id = request.args.get('local_body_id', type=int)
    ward_id = request.args.get('ward_id', type=int)

    addr_query = Address.query
    if local_body_id:
        addr_query = addr_query.filter(Address.local_body_id == local_body_id)
    if ward_id:
        addr_query = addr_query.filter(Address.ward_id == ward_id)

    addresses = addr_query.all()
    user_ids = [a.user_id for a in addresses]

    households = sum(1 for a in addresses if a.customer_type == 'Household')
    commercial = sum(1 for a in addresses if a.customer_type != 'Household')

    pickups = Pickup.query.filter(Pickup.citizen_id.in_(user_ids)).all() if user_ids else []
    completed_pickups = [p for p in pickups if p.status in ('Completed', 'Collected', 'Verified')]
    total_kg = sum(p.total_verified_weight or p.total_actual_weight for p in completed_pickups)

    # Fees in ward
    payments = Payment.query.filter(Payment.user_id.in_(user_ids)).all() if user_ids else []
    fees_collected = sum(p.amount for p in payments if p.status == 'Successful')
    fees_pending = sum(p.amount for p in payments if p.status == 'Pending')

    # Costs in ward
    cost_query = OperationalCost.query
    if local_body_id: cost_query = cost_query.filter(OperationalCost.local_body_id == local_body_id)
    if ward_id: cost_query = cost_query.filter(OperationalCost.ward_id == ward_id)
    operating_costs = sum(c.amount for c in cost_query.all())

    # Material value in ward
    material_val = 0.0
    for p in completed_pickups:
        for it in p.items:
            w = it.verified_weight or it.actual_weight
            rate = MaterialRate.query.filter_by(waste_category_id=it.waste_category_id, active=True).first()
            pr = rate.purchase_rate if rate else 10.0
            material_val += (w * pr)

    return jsonify({
        'local_body_id': local_body_id,
        'ward_id': ward_id,
        'registered_households': households,
        'commercial_customers': commercial,
        'total_pickups': len(pickups),
        'completed_pickups': len(completed_pickups),
        'missed_pickups': max(0, len(pickups) - len(completed_pickups)),
        'total_kg_collected': round(total_kg, 2),
        'user_fee_revenue': round(fees_collected, 2),
        'user_fee_pending': round(fees_pending, 2),
        'material_value': round(material_val, 2),
        'operating_cost': round(operating_costs, 2),
        'net_result': round((fees_collected + material_val) - operating_costs, 2)
    })

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    role = request.args.get('role')
    query = User.query
    if role:
        query = query.filter_by(role=role)
    users = query.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users])

@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    user = db.get_or_404(User, user_id)
    user.is_active = not user.is_active
    db.session.commit()
    log_audit('USER_TOGGLE_STATUS', 'User', user.id, None, {'is_active': user.is_active}, request.user_id, request.user_role)
    return jsonify({'message': f"User account {'activated' if user.is_active else 'deactivated'}.", 'user': user.to_dict()})

@admin_bp.route('/volunteers', methods=['GET'])
@admin_required
def get_volunteers():
    vols = Volunteer.query.order_by(Volunteer.created_at.desc()).all()
    return jsonify([v.to_dict() for v in vols])

@admin_bp.route('/volunteers/<int:vol_id>/approve', methods=['POST'])
@admin_required
def approve_volunteer(vol_id):
    """
    CRITICAL WORKFLOW TEST D:
    Admin approves volunteer -> Automatically generates:
    - Unique Volunteer ID (e.g. GCN-VOL-2026-00002)
    - Temporary password (e.g. Temp@2026)
    - Sets must_change_password = True
    - Creates VolunteerReward record
    """
    vol = db.get_or_404(Volunteer, vol_id)
    vol.status = 'Approved'
    vol.approved_at = datetime.now(timezone.utc)
    vol.approved_by = request.user_id

    # Ensure unique official ID code
    if not vol.volunteer_id_code or vol.volunteer_id_code.startswith('PENDING'):
        vol.volunteer_id_code = f"GCN-VOL-2026-{vol.id:05d}"

    # Generate temporary password for first login
    temp_pass = f"Vol@{vol.phone[-4:]}"
    user = vol.user
    user.password_hash = hash_password(temp_pass)
    user.must_change_password = True

    if not vol.rewards:
        reward = VolunteerReward(volunteer_id=vol.id, points=25, total_hours=0.0)
        db.session.add(reward)

    db.session.commit()

    log_audit('VOLUNTEER_APPROVE', 'Volunteer', vol.id, None, {'volunteer_id_code': vol.volunteer_id_code}, request.user_id, request.user_role)
    create_notification(user.id, 'Volunteer Application Approved', f"Welcome to GreenCycle Volunteers! Your Volunteer ID is {vol.volunteer_id_code}. Please sign in and update your password.", 'event')

    return jsonify({
        'message': f"Volunteer {vol.full_name} approved successfully.",
        'volunteer': vol.to_dict(),
        'generated_volunteer_id': vol.volunteer_id_code,
        'temporary_password': temp_pass,
        'notice': 'Temporary password generated. Volunteer must change password on first login.'
    })

@admin_bp.route('/cash-reconciliation', methods=['GET'])
@admin_required
def get_cash_reconciliation_queue():
    """Lists all cash payments awaiting municipal approval and reconciliation."""
    cash_payments = Payment.query.filter_by(
        payment_method='Cash'
    ).order_by(Payment.approved_by_admin.asc(), Payment.paid_at.desc()).all()

    # Collector-wise totals
    collectors = Collector.query.all()
    collector_totals = []
    for c in collectors:
        pending_sum = sum(p.amount for p in Payment.query.filter_by(collector_id=c.user_id, payment_method='Cash', approved_by_admin=False).all())
        total_collected = sum(p.amount for p in Payment.query.filter_by(collector_id=c.user_id, payment_method='Cash').all())
        collector_totals.append({
            'collector_id': c.user_id,
            'collector_name': c.user.full_name if c.user else 'Collector',
            'phone': c.user.phone if c.user else None,
            'ward_name': c.ward.ward_name if c.ward else None,
            'unreconciled_cash': round(pending_sum, 2),
            'lifetime_cash_collected': round(total_collected, 2)
        })

    return jsonify({
        'queue': [p.to_dict() for p in cash_payments],
        'collector_summaries': collector_totals
    })

@admin_bp.route('/cash-reconciliation/<int:payment_id>/approve', methods=['POST'])
@admin_required
def approve_cash_payment(payment_id):
    """
    CRITICAL WORKFLOW TEST C:
    Admin reviews and approves cash transaction:
    - Marks payment Successful
    - Sets approved_by_admin = True
    - Generates official PaymentReceipt
    - Creates formal Transaction audit record
    """
    payment = db.get_or_404(Payment, payment_id)
    if payment.approved_by_admin:
        return jsonify({'error': 'Payment has already been reconciled and approved'}), 400

    payment.approved_by_admin = True
    payment.status = 'Successful'
    payment.cash_reconciled_at = datetime.now(timezone.utc)
    payment.cash_reconciled_by = request.user_id

    # Create Transaction record
    txn_count = Transaction.query.count() + 1
    txn = Transaction(
        txn_number=f"TXN-CASH-{txn_count:07d}",
        user_id=payment.user_id,
        transaction_type='COLLECTION_FEE',
        direction='CUSTOMER_TO_GREENCYCLE',
        amount=payment.amount,
        status='Successful',
        reference_id=payment.payment_number,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(txn)
    db.session.flush()

    # Generate Official Receipt
    rcpt_count = PaymentReceipt.query.count() + 1
    rcpt = PaymentReceipt(
        receipt_number=f"RCPT-CASH-2026-{rcpt_count:05d}",
        payment_id=payment.id,
        transaction_id=txn.id,
        user_id=payment.user_id,
        amount=payment.amount,
        payment_method='Cash (Doorstep)',
        issued_at=datetime.now(timezone.utc),
        receipt_data_json=json.dumps({
            'customer_name': payment.user.full_name,
            'amount': payment.amount,
            'billing_period': payment.billing_period,
            'collector': payment.collector.full_name if payment.collector else 'Collector',
            'reconciled_by': request.current_user.full_name,
            'reconciled_at': payment.cash_reconciled_at.strftime('%d-%m-%Y %H:%M')
        })
    )
    db.session.add(rcpt)
    db.session.commit()

    log_audit('CASH_RECONCILIATION_APPROVE', 'Payment', payment.id, None, {'amount': payment.amount, 'receipt': rcpt.receipt_number}, request.user_id, request.user_role)
    create_notification(payment.user_id, 'Cash Payment Reconciled', f"Official receipt #{rcpt.receipt_number} issued for ₹{payment.amount:.2f} ({payment.billing_period}).", 'payment')

    return jsonify({
        'message': f"Cash payment of ₹{payment.amount:.2f} successfully reconciled.",
        'payment': payment.to_dict(),
        'receipt': rcpt.to_dict()
    })

# ── Civic Configuration (Local Bodies & Wards) ──
@admin_bp.route('/local-bodies', methods=['GET', 'POST'])
@admin_required
def handle_local_bodies():
    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        district = data.get('district', '').strip()
        body_type = data.get('body_type', 'Municipality')
        if not name or not district:
            return jsonify({'error': 'Name and district are required'}), 400
        lb = LocalBody(name=name, district=district, body_type=body_type, pincode=data.get('pincode'), service_area=data.get('service_area'))
        db.session.add(lb)
        db.session.commit()
        log_audit('LOCAL_BODY_CREATE', 'LocalBody', lb.id, None, {'name': name}, request.user_id, request.user_role)
        return jsonify(lb.to_dict()), 201

    lbs = LocalBody.query.all()
    return jsonify([lb.to_dict() for lb in lbs])

@admin_bp.route('/wards', methods=['GET', 'POST'])
@admin_required
def handle_wards():
    if request.method == 'POST':
        data = request.get_json() or {}
        lb_id = data.get('local_body_id')
        ward_num = int(data.get('ward_number', 1))
        ward_name = data.get('ward_name', '').strip()
        if not lb_id or not ward_name:
            return jsonify({'error': 'Local body and ward name required'}), 400
        ward = Ward(local_body_id=lb_id, ward_number=ward_num, ward_name=ward_name, pincode=data.get('pincode'))
        db.session.add(ward)
        db.session.commit()
        log_audit('WARD_CREATE', 'Ward', ward.id, None, {'name': ward_name}, request.user_id, request.user_role)
        return jsonify(ward.to_dict()), 201

    lb_id = request.args.get('local_body_id', type=int)
    query = Ward.query
    if lb_id: query = query.filter_by(local_body_id=lb_id)
    return jsonify([w.to_dict() for w in query.all()])

# ── User Fee Rules Engine ──
@admin_bp.route('/fee-rules', methods=['GET', 'POST'])
@admin_required
def handle_fee_rules():
    if request.method == 'POST':
        data = request.get_json() or {}
        lb_id = data.get('local_body_id')
        cust_type = data.get('customer_type', 'Household')
        service_type = data.get('service_type', 'Standard Household Collection')
        base_fee = float(data.get('base_fee', 100.0))
        freq = data.get('collection_frequency', 'Monthly')
        notes = data.get('notes', '[DEMO DATA] Tariff rule')

        rule = UserFeeRule(
            local_body_id=lb_id,
            customer_type=cust_type,
            service_type=service_type,
            collection_frequency=freq,
            base_fee=base_fee,
            additional_fee=float(data.get('additional_fee', 0.0)),
            effective_from=date.today(),
            active=True,
            notes=notes
        )
        db.session.add(rule)
        db.session.commit()
        log_audit('FEE_RULE_CREATE', 'UserFeeRule', rule.id, None, {'base_fee': base_fee}, request.user_id, request.user_role)
        return jsonify(rule.to_dict()), 201

    rules = UserFeeRule.query.order_by(UserFeeRule.id.desc()).all()
    return jsonify([r.to_dict() for r in rules])

# ── Material Rates Engine ──
@admin_bp.route('/material-rates', methods=['GET', 'POST'])
@admin_required
def handle_material_rates():
    if request.method == 'POST':
        data = request.get_json() or {}
        cat_id = data.get('waste_category_id')
        buyer = data.get('buyer_name', 'Authorized Recycler')
        purchase_rate = float(data.get('purchase_rate', 10.0))
        buyback_rate = float(data.get('buyback_rate', 0.0))

        rate = MaterialRate(
            waste_category_id=cat_id,
            local_body_id=data.get('local_body_id'),
            buyer_name=buyer,
            purchase_rate=purchase_rate,
            buyback_rate=buyback_rate,
            processing_cost=float(data.get('processing_cost', 2.0)),
            disposal_cost=float(data.get('disposal_cost', 1.0)),
            effective_from=date.today(),
            active=True
        )
        db.session.add(rate)
        db.session.commit()
        log_audit('MATERIAL_RATE_CREATE', 'MaterialRate', rate.id, None, {'rate': purchase_rate}, request.user_id, request.user_role)
        return jsonify(rate.to_dict()), 201

    rates = MaterialRate.query.order_by(MaterialRate.id.desc()).all()
    return jsonify([r.to_dict() for r in rates])

# ── Operational Costs Engine ──
@admin_bp.route('/operational-costs', methods=['GET', 'POST'])
@admin_required
def handle_operational_costs():
    if request.method == 'POST':
        data = request.get_json() or {}
        cat = data.get('category', 'Other')
        amount = float(data.get('amount', 0.0))
        ref = data.get('reference', '')
        notes = data.get('notes', '')

        cost = OperationalCost(
            category=cat,
            amount=amount,
            cost_date=date.today(),
            local_body_id=data.get('local_body_id'),
            ward_id=data.get('ward_id'),
            reference=ref,
            notes=notes,
            created_by=request.user_id
        )
        db.session.add(cost)
        db.session.commit()
        log_audit('OPERATIONAL_COST_LOG', 'OperationalCost', cost.id, None, {'amount': amount, 'category': cat}, request.user_id, request.user_role)
        return jsonify(cost.to_dict()), 201

    costs = OperationalCost.query.order_by(OperationalCost.cost_date.desc()).all()
    return jsonify([c.to_dict() for c in costs])

# ── Complaints Desk ──
@admin_bp.route('/complaints', methods=['GET'])
@admin_required
def get_complaints():
    comps = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return jsonify([c.to_dict() for c in comps])

@admin_bp.route('/complaints/<int:comp_id>/resolve', methods=['POST'])
@admin_required
def resolve_complaint(comp_id):
    comp = db.get_or_404(Complaint, comp_id)
    data = request.get_json() or {}
    comp.status = 'Resolved'
    comp.resolution_notes = data.get('resolution_notes', 'Issue resolved by civic operator.')
    comp.resolved_at = datetime.now(timezone.utc)
    comp.assigned_admin_id = request.user_id
    db.session.commit()

    log_audit('COMPLAINT_RESOLVE', 'Complaint', comp.id, None, {'notes': comp.resolution_notes}, request.user_id, request.user_role)
    create_notification(comp.citizen_id, 'Complaint Resolved', f"Your complaint #{comp.comp_number} was resolved: {comp.resolution_notes}", 'complaint')

    return jsonify({'message': 'Complaint marked as resolved', 'complaint': comp.to_dict()})

# ── Audit Logs ──
@admin_bp.route('/audit-logs', methods=['GET'])
@admin_required
def get_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return jsonify([l.to_dict() for l in logs])

# ── System Settings / Configurations ──
@admin_bp.route('/config', methods=['GET', 'POST'])
@admin_required
def system_configs():
    if request.method == 'POST':
        data = request.get_json() or {}
        for k, v in data.items():
            cfg = SystemConfig.query.filter_by(config_key=k).first()
            if cfg:
                cfg.config_value = str(v)
            else:
                db.session.add(SystemConfig(config_key=k, config_value=str(v)))
        db.session.commit()
        log_audit('SYSTEM_CONFIG_UPDATE', 'SystemConfig', None, None, data, request.user_id, request.user_role)
        return jsonify({'message': 'System configuration updated successfully'})

    cfgs = SystemConfig.query.all()
    return jsonify({c.config_key: c.config_value for c in cfgs})


# ── Collectors Management ──
@admin_bp.route('/collectors', methods=['GET'])
@admin_required
def get_collectors():
    collectors = Collector.query.all()
    return jsonify([c.to_dict() for c in collectors])


@admin_bp.route('/collectors', methods=['POST'])
@admin_required
def create_collector():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    user = db.get_or_404(User, user_id)
    if user.collector_profile:
        return jsonify({'error': 'Collector profile already exists for this user'}), 409
    col = Collector(
        user_id=user_id,
        local_body_id=data.get('local_body_id'),
        ward_id=data.get('ward_id'),
        route_name=data.get('route_name', ''),
        employment_type=data.get('employment_type', 'Haritha Karma Sena'),
        salary_or_rate=float(data.get('salary_or_rate', 450.0)),
        rate_type=data.get('rate_type', 'Daily'),
        status=data.get('status', 'Active')
    )
    db.session.add(col)
    # Update user role to worker if not already
    if user.role not in ('worker', 'admin'):
        user.role = 'worker'
    db.session.commit()
    log_audit('COLLECTOR_CREATE', 'Collector', col.id, None, {'user_id': user_id}, request.user_id, request.user_role)
    return jsonify(col.to_dict()), 201


# ── Vehicles Management ──
@admin_bp.route('/vehicles', methods=['GET'])
@admin_required
def get_vehicles():
    vehicles = Vehicle.query.all()
    return jsonify([v.to_dict() for v in vehicles])


@admin_bp.route('/vehicles', methods=['POST'])
@admin_required
def create_vehicle():
    data = request.get_json() or {}
    reg = data.get('reg_number', '').strip()
    vtype = data.get('vehicle_type', '').strip()
    if not reg or not vtype:
        return jsonify({'error': 'Registration number and vehicle type are required'}), 400
    if Vehicle.query.filter_by(reg_number=reg).first():
        return jsonify({'error': 'Vehicle with this registration number already exists'}), 409
    v = Vehicle(
        reg_number=reg,
        vehicle_type=vtype,
        fuel_type=data.get('fuel_type', 'Electric'),
        mileage_kml=float(data.get('mileage_kml', 12.0)),
        capacity_kg=float(data.get('capacity_kg', 1000.0)),
        assigned_route=data.get('assigned_route'),
        assigned_collector_id=data.get('assigned_collector_id'),
        active=True
    )
    db.session.add(v)
    db.session.commit()
    log_audit('VEHICLE_CREATE', 'Vehicle', v.id, None, {'reg': reg}, request.user_id, request.user_role)
    return jsonify(v.to_dict()), 201


# ── Facilities Management ──
@admin_bp.route('/facilities', methods=['GET'])
@admin_required
def get_facilities():
    facilities = Facility.query.all()
    return jsonify([f.to_dict() for f in facilities])


@admin_bp.route('/facilities', methods=['POST'])
@admin_required
def create_facility():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    ftype = data.get('facility_type', '').strip()
    location = data.get('location', '').strip()
    if not name or not ftype or not location:
        return jsonify({'error': 'Name, type, and location are required'}), 400
    fac = Facility(
        name=name,
        facility_type=ftype,
        local_body_id=data.get('local_body_id'),
        location=location,
        capacity_kg=float(data.get('capacity_kg', 5000.0)),
        contact=data.get('contact'),
        manager_name=data.get('manager_name'),
        status=data.get('status', 'Operational')
    )
    db.session.add(fac)
    db.session.commit()
    log_audit('FACILITY_CREATE', 'Facility', fac.id, None, {'name': name}, request.user_id, request.user_role)
    return jsonify(fac.to_dict()), 201


# ── Collection Requests Queue (Admin View) ──
@admin_bp.route('/collection-requests', methods=['GET'])
@admin_required
def get_all_collection_requests():
    status_filter = request.args.get('status')
    lb_id = request.args.get('local_body_id', type=int)
    ward_id = request.args.get('ward_id', type=int)
    query = CollectionRequest.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if lb_id:
        query = query.filter_by(local_body_id=lb_id)
    if ward_id:
        query = query.filter_by(ward_id=ward_id)
    reqs = query.order_by(CollectionRequest.created_at.desc()).all()
    return jsonify([r.to_dict() for r in reqs])


# ── Pickup Complete / Fail by Admin ──
@admin_bp.route('/pickups/<int:pickup_id>/complete', methods=['POST'])
@admin_required
def admin_complete_pickup(pickup_id):
    pickup = db.get_or_404(Pickup, pickup_id)
    data = request.get_json() or {}
    pickup.status = 'Completed'
    pickup.completed_at = datetime.now(timezone.utc)
    if pickup.collection_request:
        pickup.collection_request.status = 'Completed'
    db.session.commit()
    log_audit('PICKUP_COMPLETE', 'Pickup', pickup.id, None, {'status': 'Completed'}, request.user_id, request.user_role)
    create_notification(pickup.citizen_id, 'Collection Completed', f'Pickup #{pickup.pickup_number} has been marked as completed.', 'pickup')
    return jsonify({'message': 'Pickup marked completed', 'pickup': pickup.to_dict()})


@admin_bp.route('/pickups/<int:pickup_id>/fail', methods=['POST'])
@admin_required
def admin_fail_pickup(pickup_id):
    pickup = db.get_or_404(Pickup, pickup_id)
    data = request.get_json() or {}
    reason = data.get('reason', 'Marked as failed by Admin')
    pickup.status = 'Failed'
    pickup.notes = reason
    if pickup.collection_request:
        pickup.collection_request.status = 'Failed'
    db.session.commit()
    log_audit('PICKUP_FAIL', 'Pickup', pickup.id, None, {'reason': reason}, request.user_id, request.user_role)
    create_notification(pickup.citizen_id, 'Collection Failed', f'Pickup #{pickup.pickup_number} could not be completed. Reason: {reason}', 'pickup')
    return jsonify({'message': 'Pickup marked failed', 'pickup': pickup.to_dict()})


# ── Admin: Get All Pickups ──
@admin_bp.route('/pickups', methods=['GET'])
@admin_required
def get_all_pickups_admin():
    status = request.args.get('status')
    lb_id = request.args.get('local_body_id', type=int)
    date_str = request.args.get('date')
    query = Pickup.query
    if status:
        query = query.filter_by(status=status)
    if date_str:
        try:
            from datetime import datetime, timezone as dt
            d = dt.strptime(date_str, '%Y-%m-%d').date()
            query = query.filter_by(scheduled_date=d)
        except ValueError:
            pass
    pickups = query.order_by(Pickup.scheduled_date.desc()).all()
    return jsonify([p.to_dict() for p in pickups])


# ── Admin: Create User (Worker / Admin) ──
@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    from app.services.auth_service import hash_password as hp
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip() or None
    full_name = data.get('full_name', '').strip()
    role = data.get('role', 'worker').lower()
    password = data.get('password', '').strip()

    if not phone or len(phone) < 10:
        return jsonify({'error': 'Valid 10-digit mobile number required'}), 400
    if not password or len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    if role not in ('worker', 'admin', 'citizen', 'volunteer'):
        return jsonify({'error': 'Invalid role'}), 400
    if User.query.filter_by(phone=phone).first():
        return jsonify({'error': 'Phone number already registered'}), 409

    user = User(
        phone=phone,
        email=email,
        password_hash=hp(password),
        role=role,
        full_name=full_name or role.capitalize(),
        is_active=True,
        must_change_password=data.get('must_change_password', False)
    )
    db.session.add(user)
    db.session.commit()
    log_audit('USER_CREATE_ADMIN', 'User', user.id, None, {'phone': phone, 'role': role}, request.user_id, request.user_role)
    return jsonify({'message': f'{role.capitalize()} account created', 'user': user.to_dict()}), 201


# ── Admin: Schedule Management ──
@admin_bp.route('/schedules', methods=['GET'])
@admin_required
def get_all_schedules():
    lb_id = request.args.get('local_body_id', type=int)
    ward_id = request.args.get('ward_id', type=int)
    query = CollectionSchedule.query
    if lb_id:
        query = query.filter_by(local_body_id=lb_id)
    if ward_id:
        query = query.filter_by(ward_id=ward_id)
    scheds = query.order_by(CollectionSchedule.id.asc()).all()
    return jsonify([s.to_dict() for s in scheds])


# ── Admin: Events Management ──
@admin_bp.route('/events', methods=['GET'])
@admin_required
def admin_get_events():
    events = Event.query.order_by(Event.event_date.asc()).all()
    return jsonify([e.to_dict() for e in events])


# ── Admin: Attendance / Volunteer Summary ──
@admin_bp.route('/attendance', methods=['GET'])
@admin_required
def admin_get_attendance():
    from app.models.volunteer import Attendance as AttModel
    event_id = request.args.get('event_id', type=int)
    query = AttModel.query
    if event_id:
        query = query.filter_by(event_id=event_id)
    records = query.order_by(AttModel.check_in_time.desc()).all()
    return jsonify([r.to_dict() for r in records])

