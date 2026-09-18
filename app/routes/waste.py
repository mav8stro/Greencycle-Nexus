from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import WasteCategory, MaterialMovement, Pickup
from app.services.auth_service import token_required, admin_required, log_audit

waste_bp = Blueprint('waste', __name__, url_prefix='/api/waste')

@waste_bp.route('/categories', methods=['GET'])
def get_categories():
    categories = WasteCategory.query.filter_by(active=True).all()
    return jsonify([c.to_dict() for c in categories])

@waste_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    data = request.get_json() or {}
    code = data.get('code', '').strip().upper()
    name = data.get('name', '').strip()
    if not code or not name:
        return jsonify({'error': 'Code and Name required'}), 400

    cat = WasteCategory(
        code=code,
        name=name,
        description=data.get('description'),
        collection_type=data.get('collection_type', 'Door-to-door dry'),
        is_recyclable=bool(data.get('is_recyclable', True)),
        requires_special_handling=bool(data.get('requires_special_handling', False)),
        sorting_instructions=data.get('sorting_instructions'),
        disposal_route=data.get('disposal_route'),
        active=True
    )
    db.session.add(cat)
    db.session.commit()
    log_audit('WASTE_CATEGORY_CREATE', 'WasteCategory', cat.id, None, {'code': code}, request.user_id, request.user_role)
    return jsonify(cat.to_dict()), 201

@waste_bp.route('/movements', methods=['GET'])
@token_required
def get_material_movements():
    pickup_id = request.args.get('pickup_id', type=int)
    query = MaterialMovement.query
    if pickup_id:
        query = query.filter_by(pickup_id=pickup_id)
    movements = query.order_by(MaterialMovement.movement_date.desc()).all()
    return jsonify([m.to_dict() for m in movements])

@waste_bp.route('/movements', methods=['POST'])
@token_required
def create_material_movement():
    """Records traceability movement: Mini-MCF -> MCF -> RRF -> Recycler."""
    data = request.get_json() or {}
    pickup_id = data.get('pickup_id')
    cat_id = data.get('waste_category_id')
    source_type = data.get('source_type', 'Mini-MCF')
    source_name = data.get('source_name', 'Ward Mini-MCF')
    dest_type = data.get('destination_type', 'RRF')
    dest_name = data.get('destination_name', 'Central RRF')
    weight_kg = float(data.get('weight_kg', 0.0))

    if not cat_id or weight_kg <= 0:
        return jsonify({'error': 'Category and positive weight required'}), 400

    mov_count = MaterialMovement.query.count() + 1
    mov = MaterialMovement(
        movement_code=f"MOV-2026-{mov_count:05d}",
        pickup_id=pickup_id,
        waste_category_id=cat_id,
        source_type=source_type,
        source_name=source_name,
        destination_type=dest_type,
        destination_name=dest_name,
        weight_kg=weight_kg,
        status='Dispatched',
        handler_id=request.user_id
    )
    db.session.add(mov)
    db.session.commit()
    log_audit('MATERIAL_MOVEMENT_CREATE', 'MaterialMovement', mov.id, None, {'code': mov.movement_code}, request.user_id, request.user_role)
    return jsonify(mov.to_dict()), 201
