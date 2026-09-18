from datetime import datetime
from app.extensions import db
from sqlalchemy.orm import synonym

class CollectionSchedule(db.Model):
    __tablename__ = 'collection_schedules'

    id = db.Column(db.Integer, primary_key=True)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=False, index=True)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=False, index=True)
    route_name = db.Column(db.String(100), nullable=False)
    waste_category_id = db.Column(db.Integer, db.ForeignKey('waste_categories.id'), nullable=False)
    collection_day = db.Column(db.String(20), nullable=False)  # Monday, Tuesday, etc.
    time_slot = db.Column(db.String(50), nullable=False)  # 08:00 AM - 11:00 AM
    collector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=True)
    active = db.Column(db.Boolean, default=True)

    local_body = db.relationship('LocalBody')
    ward = db.relationship('Ward')
    category = db.relationship('WasteCategory')
    collector_user = db.relationship('User', foreign_keys=[collector_id])
    vehicle = db.relationship('Vehicle')

    def to_dict(self):
        return {
            'id': self.id,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else None,
            'ward_id': self.ward_id,
            'ward_number': self.ward.ward_number if self.ward else None,
            'ward_name': self.ward.ward_name if self.ward else None,
            'route_name': self.route_name,
            'waste_category_id': self.waste_category_id,
            'category_name': self.category.name if self.category else None,
            'collection_day': self.collection_day,
            'time_slot': self.time_slot,
            'collector_id': self.collector_id,
            'collector_name': self.collector_user.full_name if self.collector_user else None,
            'collector_phone': self.collector_user.phone if self.collector_user else None,
            'vehicle_id': self.vehicle_id,
            'vehicle_reg': self.vehicle.reg_number if self.vehicle else None,
            'active': self.active
        }


class Pickup(db.Model):
    __tablename__ = 'pickups'

    id = db.Column(db.Integer, primary_key=True)
    pickup_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey('collection_requests.id'), nullable=True, index=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    collector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=True)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    scheduled_slot = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(30), default='Scheduled', index=True)
    # Scheduled, Assigned, En Route, Arrived, Collected, Verified, Completed, Failed, Rescheduled
    started_at = db.Column(db.DateTime, nullable=True)
    arrived_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Weight tracking (Estimated -> Actual -> Verified)
    total_estimated_weight = db.Column(db.Float, default=0.0)
    total_actual_weight = db.Column(db.Float, default=0.0)
    total_verified_weight = db.Column(db.Float, default=0.0)
    weighed_by = db.Column(db.String(80), nullable=True)
    weighed_at = db.Column(db.DateTime, nullable=True)
    proof_photo = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    items = db.relationship('PickupItem', backref='pickup', lazy=True, cascade="all, delete-orphan")
    vehicle = db.relationship('Vehicle')
    movements = db.relationship('MaterialMovement', backref='pickup', lazy=True)

    def __init__(self, **kwargs):
        if 'user_id' in kwargs and 'citizen_id' not in kwargs:
            kwargs['citizen_id'] = kwargs.pop('user_id')
        if 'worker_id' in kwargs and 'collector_id' not in kwargs:
            kwargs['collector_id'] = kwargs.pop('worker_id')
        if 'date' in kwargs and 'scheduled_date' not in kwargs:
            val = kwargs.pop('date')
            kwargs['scheduled_date'] = val.date() if hasattr(val, 'date') else val
        if 'scheduled_date' not in kwargs:
            from datetime import date, timedelta
            kwargs['scheduled_date'] = date.today() + timedelta(days=3)
        elif hasattr(kwargs['scheduled_date'], 'date'):
            kwargs['scheduled_date'] = kwargs['scheduled_date'].date()
        if 'pickup_number' not in kwargs:
            import uuid
            kwargs['pickup_number'] = f"PCK-2026-{uuid.uuid4().hex[:6].upper()}"
        super().__init__(**kwargs)

    user_id = synonym('citizen_id')
    worker_id = synonym('collector_id')
    date = synonym('scheduled_date')

    def to_dict(self):
        req = self.collection_request
        addr = req.address if req else (self.citizen.addresses[0] if self.citizen and self.citizen.addresses else None)
        return {
            'id': self.id,
            'pickup_number': self.pickup_number,
            'request_id': self.request_id,
            'request_number': req.req_number if req else None,
            'citizen_id': self.citizen_id,
            'citizen_name': self.citizen.full_name if self.citizen else 'Citizen',
            'citizen_phone': self.citizen.phone if self.citizen else None,
            'user_id': self.citizen_id,
            'worker_id': self.collector_id,
            'date': self.scheduled_date.strftime('%Y-%m-%d %H:%M') if self.scheduled_date else None,
            'address': addr.to_dict() if addr else None,
            'collector_id': self.collector_id,
            'collector_name': self.collector.full_name if self.collector else None,
            'collector_phone': self.collector.phone if self.collector else None,
            'vehicle_id': self.vehicle_id,
            'vehicle_reg': self.vehicle.reg_number if self.vehicle else None,
            'scheduled_date': self.scheduled_date.strftime('%Y-%m-%d') if self.scheduled_date else None,
            'scheduled_slot': self.scheduled_slot,
            'status': self.status,
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M') if self.started_at else None,
            'arrived_at': self.arrived_at.strftime('%Y-%m-%d %H:%M') if self.arrived_at else None,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M') if self.completed_at else None,
            'total_estimated_weight': round(self.total_estimated_weight or 0.0, 2),
            'total_actual_weight': round(self.total_actual_weight or 0.0, 2),
            'total_verified_weight': round(self.total_verified_weight or 0.0, 2),
            'weighed_by': self.weighed_by,
            'weighed_at': self.weighed_at.strftime('%Y-%m-%d %H:%M') if self.weighed_at else None,
            'proof_photo': self.proof_photo,
            'notes': self.notes,
            'items': [item.to_dict() for item in self.items]
        }


class PickupItem(db.Model):
    __tablename__ = 'pickup_items'

    id = db.Column(db.Integer, primary_key=True)
    pickup_id = db.Column(db.Integer, db.ForeignKey('pickups.id'), nullable=False, index=True)
    waste_category_id = db.Column(db.Integer, db.ForeignKey('waste_categories.id'), nullable=False)
    estimated_weight = db.Column(db.Float, default=0.0)
    actual_weight = db.Column(db.Float, default=0.0)
    verified_weight = db.Column(db.Float, default=0.0)

    category = db.relationship('WasteCategory')

    def to_dict(self):
        return {
            'id': self.id,
            'waste_category_id': self.waste_category_id,
            'category_name': self.category.name if self.category else 'Unknown',
            'category_code': self.category.code if self.category else 'UNKNOWN',
            'is_special_handling': self.category.requires_special_handling if self.category else False,
            'estimated_weight': round(self.estimated_weight, 2),
            'actual_weight': round(self.actual_weight, 2),
            'verified_weight': round(self.verified_weight, 2)
        }
