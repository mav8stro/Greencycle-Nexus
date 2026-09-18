from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, date
from app.extensions import db
from app.models import (
    Pickup, PickupItem, CollectionRequest, User, Address,
    Payment, Transaction, PaymentReceipt, MaterialMovement,
    Collector, WasteCategory
)
from app.services.auth_service import token_required, role_required, log_audit, create_notification
from app.services.finance_engine import get_applicable_user_fee

worker_bp = Blueprint('worker', __name__, url_prefix='/api/worker')

@worker_bp.route('/dashboard', methods=['GET'])
@role_required(['worker', 'admin'])
def worker_dashboard():
    worker_id = request.user_id
    today = date.today()

    assigned_today = Pickup.query.filter_by(collector_id=worker_id, scheduled_date=today).count()
    completed_today = Pickup.query.filter(
        Pickup.collector_id == worker_id,
        Pickup.scheduled_date == today,
        Pickup.status.in_(['Completed', 'Collected', 'Verified'])
    ).count()
    pending_today = assigned_today - completed_today

    # Total weight collected by this worker today
    today_pickups = Pickup.query.filter(
        Pickup.collector_id == worker_id,
        Pickup.scheduled_date == today,
        Pickup.status.in_(['Completed', 'Collected', 'Verified'])
    ).all()
    weight_collected_today = sum(p.total_actual_weight for p in today_pickups)

    # Cash collected awaiting reconciliation
    pending_cash = Payment.query.filter_by(
        collector_id=worker_id,
        payment_method='Cash',
        approved_by_admin=False
    ).all()
    cash_in_hand = sum(p.amount for p in pending_cash)

    return jsonify({
        'today_pickups_count': assigned_today,
        'completed_today_count': completed_today,
        'pending_today_count': max(0, pending_today),
        'weight_collected_kg': round(weight_collected_today, 2),
        'cash_in_hand': round(cash_in_hand, 2),
        'unreconciled_cash_count': len(pending_cash)
    })

@worker_bp.route('/pickups', methods=['GET'])
@role_required(['worker', 'admin'])
def get_worker_pickups():
    worker_id = request.user_id
    status_filter = request.args.get('status')
    
    query = Pickup.query.filter_by(collector_id=worker_id)
    if status_filter:
        query = query.filter_by(status=status_filter)

    pickups = query.order_by(Pickup.scheduled_date.asc(), Pickup.id.asc()).all()
    return jsonify([p.to_dict() for p in pickups])

@worker_bp.route('/pickups/<int:pickup_id>/status', methods=['POST'])
@role_required(['worker', 'admin'])
def update_pickup_status(pickup_id):
    pickup = db.get_or_404(Pickup, pickup_id)
    if pickup.collector_id != request.user_id and request.user_role != 'admin':
        return jsonify({'error': 'Unauthorized to modify this pickup'}), 403

    data = request.get_json() or {}
    new_status = data.get('status')
    if new_status not in ('En Route', 'Arrived', 'Failed', 'Rescheduled'):
        return jsonify({'error': 'Invalid status progression'}), 400

    old_status = pickup.status
    pickup.status = new_status
    now = datetime.now(timezone.utc)

    if new_status == 'En Route' and not pickup.started_at:
        pickup.started_at = now
        create_notification(pickup.citizen_id, 'Collector En Route', f"Haritha Karma Sena collector is on the way to your address.", 'pickup')
    elif new_status == 'Arrived' and not pickup.arrived_at:
        pickup.arrived_at = now
        create_notification(pickup.citizen_id, 'Collector Arrived', f"Collector has arrived at your doorstep. Please present segregated waste.", 'pickup')

    if pickup.collection_request:
        pickup.collection_request.status = new_status

    db.session.commit()
    log_audit('PICKUP_STATUS_UPDATE', 'Pickup', pickup.id, {'status': old_status}, {'status': new_status}, request.user_id, request.user_role)
    return jsonify({'message': f'Status updated to {new_status}', 'pickup': pickup.to_dict()})

@worker_bp.route('/pickups/<int:pickup_id>/verify', methods=['POST'])
@role_required(['worker', 'admin'])
def verify_pickup_waste(pickup_id):
    """
    CRITICAL TWO-STAGE WEIGHT WORKFLOW:
    Worker enters ACTUAL weights per category, confirms segregation,
    attaches photo proof, and marks pickup Collected/Verified.
    Automatically generates traceability MaterialMovement record.
    """
    pickup = db.get_or_404(Pickup, pickup_id)
    if pickup.collector_id != request.user_id and request.user_role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    items_weights = data.get('items', [])  # [{'waste_category_id': 1, 'actual_weight': 4.5}]
    proof_photo = data.get('proof_photo')
    notes = data.get('notes', '')

    total_actual = 0.0
    for it in items_weights:
        cat_id = it.get('waste_category_id')
        act_w = float(it.get('actual_weight', 0.0))
        total_actual += act_w

        # Match or create PickupItem
        p_item = PickupItem.query.filter_by(pickup_id=pickup.id, waste_category_id=cat_id).first()
        if p_item:
            p_item.actual_weight = act_w
            p_item.verified_weight = act_w  # Collector verifies at scale
        else:
            p_item = PickupItem(
                pickup_id=pickup.id,
                waste_category_id=cat_id,
                estimated_weight=act_w,
                actual_weight=act_w,
                verified_weight=act_w
            )
            db.session.add(p_item)

        # Create MaterialMovement record (Household -> Mini-MCF)
        cat = db.session.get(WasteCategory, cat_id)
        mov_count = MaterialMovement.query.count() + 1
        mov = MaterialMovement(
            movement_code=f"MOV-2026-{mov_count:05d}",
            pickup_id=pickup.id,
            waste_category_id=cat_id,
            source_type='Household',
            source_name=pickup.citizen.full_name,
            destination_type='Mini-MCF',
            destination_name='Ward Mini-MCF',
            weight_kg=act_w,
            status='Received',
            handler_id=request.user_id
        )
        db.session.add(mov)

    pickup.total_actual_weight = total_actual
    pickup.total_verified_weight = total_actual
    pickup.weighed_by = request.current_user.full_name
    pickup.weighed_at = datetime.now(timezone.utc)
    pickup.completed_at = datetime.now(timezone.utc)
    pickup.status = 'Completed'
    pickup.proof_photo = proof_photo
    pickup.notes = notes

    if pickup.collection_request:
        pickup.collection_request.status = 'Completed'

    db.session.commit()

    log_audit('WASTE_VERIFICATION', 'Pickup', pickup.id, None, {'total_actual_weight': total_actual}, request.user_id, request.user_role)
    create_notification(pickup.citizen_id, 'Waste Collected & Weighed', f"Your waste was weighed and collected: {total_actual:.2f} kg total verified.", 'pickup')

    return jsonify({
        'message': 'Waste verified and collection completed successfully!',
        'pickup': pickup.to_dict()
    })

@worker_bp.route('/cash', methods=['POST'])
@role_required(['worker', 'admin'])
def record_cash_collection():
    """
    Collector records cash user-fee received on doorstep from citizen.
    Creates a pending cash payment record awaiting Admin reconciliation.
    """
    worker = request.current_user
    data = request.get_json() or {}

    citizen_id = data.get('citizen_id')
    amount = float(data.get('amount', 0.0))
    billing_period = data.get('billing_period', datetime.now().strftime('%B %Y'))
    notes = data.get('notes', f'Doorstep cash received by {worker.full_name}')

    if not citizen_id or amount <= 0:
        return jsonify({'error': 'Valid citizen and positive amount required'}), 400

    citizen = db.get_or_404(User, citizen_id)

    pay_count = Payment.query.count() + 1
    pay_number = f"PAY-CASH-2026-{pay_count:05d}"

    payment = Payment(
        payment_number=pay_number,
        user_id=citizen.id,
        amount=amount,
        billing_period=billing_period,
        status='Pending',  # Pending admin cash reconciliation
        payment_method='Cash',
        due_date=date.today(),
        paid_at=datetime.now(timezone.utc),
        collector_id=worker.id,
        approved_by_admin=False,
        notes=notes
    )
    db.session.add(payment)
    db.session.commit()

    log_audit('CASH_COLLECTED_DOORSTEP', 'Payment', payment.id, None, {'amount': amount, 'collector_id': worker.id}, worker.id, worker.role)
    create_notification(citizen.id, 'Cash Payment Acknowledged', f"Collector {worker.full_name} received ₹{amount:.2f} for {billing_period}. Awaiting municipal clearance.", 'payment')

    return jsonify({
        'message': f'Cash payment of ₹{amount:.2f} recorded. Awaiting admin reconciliation.',
        'payment': payment.to_dict()
    }), 201

@worker_bp.route('/cash-summary', methods=['GET'])
@role_required(['worker', 'admin'])
def get_cash_summary():
    worker_id = request.user_id
    pending_payments = Payment.query.filter_by(
        collector_id=worker_id,
        payment_method='Cash',
        approved_by_admin=False
    ).order_by(Payment.paid_at.desc()).all()

    total_unreconciled = sum(p.amount for p in pending_payments)
    return jsonify({
        'collector_id': worker_id,
        'collector_name': request.current_user.full_name,
        'total_unreconciled_cash': round(total_unreconciled, 2),
        'pending_transactions': [p.to_dict() for p in pending_payments]
    })

@worker_bp.route('/citizens', methods=['GET'])
@role_required(['worker', 'admin'])
def get_ward_citizens():
    # Return citizens in this collector's assigned ward
    col_profile = request.current_user.collector_profile
    ward_id = col_profile.ward_id if col_profile else None

    query = User.query.filter_by(role='citizen')
    if ward_id:
        query = query.join(Address).filter(Address.ward_id == ward_id)

    citizens = query.all()
    return jsonify([c.to_dict() for c in citizens])
