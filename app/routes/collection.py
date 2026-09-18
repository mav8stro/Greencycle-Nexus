from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, date
from app.extensions import db
from app.models import CollectionSchedule, Pickup, PickupItem, CollectionRequest, User, Vehicle
from app.services.auth_service import token_required, admin_required, log_audit, create_notification

collection_bp = Blueprint('collection', __name__, url_prefix='/api/collection')

@collection_bp.route('/schedules', methods=['GET'])
@token_required
def get_schedules():
    lb_id = request.args.get('local_body_id', type=int)
    ward_id = request.args.get('ward_id', type=int)
    query = CollectionSchedule.query.filter_by(active=True)
    if lb_id: query = query.filter_by(local_body_id=lb_id)
    if ward_id: query = query.filter_by(ward_id=ward_id)
    schedules = query.all()
    return jsonify([s.to_dict() for s in schedules])

@collection_bp.route('/schedules', methods=['POST'])
@admin_required
def create_schedule():
    data = request.get_json() or {}
    lb_id = data.get('local_body_id')
    ward_id = data.get('ward_id')
    route_name = data.get('route_name', '').strip()
    cat_id = data.get('waste_category_id')
    day = data.get('collection_day', 'Monday')
    slot = data.get('time_slot', '08:00 AM - 11:00 AM')

    if not lb_id or not ward_id or not route_name or not cat_id:
        return jsonify({'error': 'Local body, ward, route, and category are required'}), 400

    sched = CollectionSchedule(
        local_body_id=lb_id,
        ward_id=ward_id,
        route_name=route_name,
        waste_category_id=cat_id,
        collection_day=day,
        time_slot=slot,
        collector_id=data.get('collector_id'),
        vehicle_id=data.get('vehicle_id'),
        active=True
    )
    db.session.add(sched)
    db.session.commit()
    log_audit('SCHEDULE_CREATE', 'CollectionSchedule', sched.id, None, {'route': route_name}, request.user_id, request.user_role)
    return jsonify(sched.to_dict()), 201

@collection_bp.route('/pickups', methods=['GET'])
@token_required
def get_all_pickups():
    status = request.args.get('status')
    collector_id = request.args.get('collector_id', type=int)
    
    query = Pickup.query
    if request.user_role == 'worker':
        query = query.filter_by(collector_id=request.user_id)
    elif request.user_role == 'citizen':
        query = query.filter_by(citizen_id=request.user_id)
    elif collector_id:
        query = query.filter_by(collector_id=collector_id)

    if status:
        query = query.filter_by(status=status)

    pickups = query.order_by(Pickup.scheduled_date.desc()).all()
    return jsonify([p.to_dict() for p in pickups])

@collection_bp.route('/pickups/<int:pickup_id>/assign', methods=['POST'])
@admin_required
def assign_pickup(pickup_id):
    pickup = db.get_or_404(Pickup, pickup_id)
    data = request.get_json() or {}
    collector_id = data.get('collector_id')
    vehicle_id = data.get('vehicle_id')

    if not collector_id:
        return jsonify({'error': 'Collector ID required'}), 400

    collector = db.get_or_404(User, collector_id)
    pickup.collector_id = collector.id
    if vehicle_id:
        pickup.vehicle_id = vehicle_id
    pickup.status = 'Assigned'

    if pickup.collection_request:
        pickup.collection_request.status = 'Assigned'

    db.session.commit()

    log_audit('PICKUP_ASSIGN', 'Pickup', pickup.id, None, {'collector_id': collector.id}, request.user_id, request.user_role)
    create_notification(collector.id, 'New Pickup Assigned', f"Pickup #{pickup.pickup_number} assigned to your route on {pickup.scheduled_date}.", 'schedule')
    create_notification(pickup.citizen_id, 'Collector Assigned', f"Collector {collector.full_name} has been assigned for your pickup on {pickup.scheduled_date}.", 'pickup')

    return jsonify({'message': f'Assigned to {collector.full_name}', 'pickup': pickup.to_dict()})

@collection_bp.route('/requests/<int:req_id>/schedule', methods=['POST'])
@admin_required
def schedule_request(req_id):
    """Admin schedules a citizen's collection request into an active Pickup."""
    req = db.get_or_404(CollectionRequest, req_id)
    data = request.get_json() or {}
    collector_id = data.get('collector_id')
    vehicle_id = data.get('vehicle_id')
    scheduled_date_str = data.get('scheduled_date')

    sched_date = datetime.strptime(scheduled_date_str, '%Y-%m-%d').date() if scheduled_date_str else req.requested_date

    p_count = Pickup.query.count() + 1
    p_num = f"GCN-PKP-2026-{p_count:05d}"

    total_est = sum(it.estimated_weight for it in req.items)

    pickup = Pickup(
        pickup_number=p_num,
        request_id=req.id,
        citizen_id=req.citizen_id,
        collector_id=collector_id,
        vehicle_id=vehicle_id,
        scheduled_date=sched_date,
        scheduled_slot=req.requested_slot,
        status='Assigned' if collector_id else 'Scheduled',
        total_estimated_weight=total_est
    )
    db.session.add(pickup)
    db.session.flush()

    for it in req.items:
        p_item = PickupItem(
            pickup_id=pickup.id,
            waste_category_id=it.waste_category_id,
            estimated_weight=it.estimated_weight
        )
        db.session.add(p_item)

    req.status = 'Assigned' if collector_id else 'Scheduled'
    db.session.commit()

    log_audit('REQUEST_SCHEDULED', 'Pickup', pickup.id, None, {'pickup_number': p_num}, request.user_id, request.user_role)
    create_notification(req.citizen_id, 'Pickup Scheduled', f"Your collection request #{req.req_number} has been scheduled for {sched_date}.", 'pickup')

    return jsonify({'message': 'Pickup scheduled successfully', 'pickup': pickup.to_dict()}), 201
