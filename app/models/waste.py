from datetime import datetime
from app.extensions import db

class WasteEntry(db.Model):
    __tablename__ = 'waste_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    food = db.Column(db.Float, default=0.0)
    plastic = db.Column(db.Float, default=0.0)
    other = db.Column(db.Float, default=0.0)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    approved = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref=db.backref('waste_entries', lazy=True))

    def total_amount(self):
        return (self.food * 2) + (self.plastic * 3) + (self.other * 1)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'food': self.food,
            'plastic': self.plastic,
            'other': self.other,
            'date': self.date.strftime('%Y-%m-%d %H:%M') if self.date else None,
            'approved': self.approved,
            'amount': self.total_amount()
        }


class WasteCategory(db.Model):
    __tablename__ = 'waste_categories'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)  # PLASTIC, PAPER, E-WASTE, etc.
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=True)
    collection_type = db.Column(db.String(50), default='Door-to-door dry')  # Door-to-door dry, Door-to-door wet, Special On-demand, Drop-off
    is_recyclable = db.Column(db.Boolean, default=True)
    requires_special_handling = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    sorting_instructions = db.Column(db.Text, nullable=True)
    disposal_route = db.Column(db.String(150), nullable=True)  # e.g., 'MCF -> RRF -> Clean Kerala Company'

    # Relationships
    material_rates = db.relationship('MaterialRate', backref='category', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'collection_type': self.collection_type,
            'is_recyclable': self.is_recyclable,
            'requires_special_handling': self.requires_special_handling,
            'active': self.active,
            'sorting_instructions': self.sorting_instructions,
            'disposal_route': self.disposal_route
        }


class CollectionRequest(db.Model):
    __tablename__ = 'collection_requests'

    id = db.Column(db.Integer, primary_key=True)
    req_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=False)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=False)
    address_id = db.Column(db.Integer, db.ForeignKey('addresses.id'), nullable=False)
    requested_date = db.Column(db.Date, nullable=False)
    requested_slot = db.Column(db.String(30), nullable=False)  # Morning (08:00 - 11:00), Afternoon (14:00 - 17:00)
    notes = db.Column(db.Text, nullable=True)
    photo_url = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default='Requested', index=True)
    # Statuses: Requested, Scheduled, Assigned, En Route, Arrived, Collected, Verified, Completed, Cancelled, Failed, Rescheduled
    is_special_waste = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    items = db.relationship('CollectionRequestItem', backref='request', lazy=True, cascade="all, delete-orphan")
    pickup = db.relationship('Pickup', backref='collection_request', uselist=False, lazy=True)
    address = db.relationship('Address')
    local_body = db.relationship('LocalBody')
    ward = db.relationship('Ward')

    def total_estimated_weight(self):
        return sum(item.estimated_weight for item in self.items)

    def to_dict(self):
        return {
            'id': self.id,
            'req_number': self.req_number,
            'citizen_id': self.citizen_id,
            'citizen_name': self.citizen.full_name if self.citizen else 'Citizen',
            'citizen_phone': self.citizen.phone if self.citizen else None,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else None,
            'ward_id': self.ward_id,
            'ward_number': self.ward.ward_number if self.ward else None,
            'ward_name': self.ward.ward_name if self.ward else None,
            'address': self.address.to_dict() if self.address else None,
            'requested_date': self.requested_date.strftime('%Y-%m-%d') if self.requested_date else None,
            'requested_slot': self.requested_slot,
            'notes': self.notes,
            'photo_url': self.photo_url,
            'status': self.status,
            'is_special_waste': self.is_special_waste,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'items': [item.to_dict() for item in self.items],
            'total_estimated_weight': round(self.total_estimated_weight(), 2),
            'pickup': self.pickup.to_dict() if self.pickup else None
        }


class CollectionRequestItem(db.Model):
    __tablename__ = 'collection_request_items'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('collection_requests.id'), nullable=False, index=True)
    waste_category_id = db.Column(db.Integer, db.ForeignKey('waste_categories.id'), nullable=False)
    estimated_weight = db.Column(db.Float, default=0.0)

    category = db.relationship('WasteCategory')

    def to_dict(self):
        return {
            'id': self.id,
            'waste_category_id': self.waste_category_id,
            'category_name': self.category.name if self.category else 'Unknown',
            'category_code': self.category.code if self.category else 'UNKNOWN',
            'is_special_handling': self.category.requires_special_handling if self.category else False,
            'estimated_weight': self.estimated_weight
        }
