from datetime import datetime
from app.extensions import db

class Collector(db.Model):
    __tablename__ = 'collectors'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=True)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=True)
    route_name = db.Column(db.String(100), nullable=True)
    employment_type = db.Column(db.String(50), default='Haritha Karma Sena')  # Haritha Karma Sena, Municipal Staff, Contract
    salary_or_rate = db.Column(db.Float, default=450.0)  # Daily rate / hourly rate / per-pickup rate
    rate_type = db.Column(db.String(20), default='Daily')  # Daily, Hourly, Per-Pickup
    status = db.Column(db.String(20), default='Active')

    local_body = db.relationship('LocalBody')
    ward = db.relationship('Ward')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.user.full_name if self.user else None,
            'phone': self.user.phone if self.user else None,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else None,
            'ward_id': self.ward_id,
            'ward_name': self.ward.ward_name if self.ward else None,
            'route_name': self.route_name,
            'employment_type': self.employment_type,
            'salary_or_rate': self.salary_or_rate,
            'rate_type': self.rate_type,
            'status': self.status
        }


class Vehicle(db.Model):
    __tablename__ = 'vehicles'

    id = db.Column(db.Integer, primary_key=True)
    reg_number = db.Column(db.String(30), unique=True, nullable=False, index=True)  # KL-07-CD-1024
    vehicle_type = db.Column(db.String(50), nullable=False)  # Electric Mini-Tipper, Diesel Truck, Auto-Tipper
    fuel_type = db.Column(db.String(20), default='Electric')  # Electric, Diesel, Petrol, CNG
    mileage_kml = db.Column(db.Float, default=12.0)  # km/L or km/kWh for EV
    capacity_kg = db.Column(db.Float, default=1000.0)
    assigned_route = db.Column(db.String(100), nullable=True)
    assigned_collector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    active = db.Column(db.Boolean, default=True)

    assigned_collector = db.relationship('User', foreign_keys=[assigned_collector_id])

    def to_dict(self):
        return {
            'id': self.id,
            'reg_number': self.reg_number,
            'vehicle_type': self.vehicle_type,
            'fuel_type': self.fuel_type,
            'mileage_kml': self.mileage_kml,
            'capacity_kg': self.capacity_kg,
            'assigned_route': self.assigned_route,
            'assigned_collector_id': self.assigned_collector_id,
            'assigned_collector_name': self.assigned_collector.full_name if self.assigned_collector else None,
            'active': self.active
        }


class Facility(db.Model):
    __tablename__ = 'facilities'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    facility_type = db.Column(db.String(50), nullable=False)  # Mini-MCF, MCF, RRF, Compost Facility, Authorized Recycler, Disposal Facility
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=True)
    location = db.Column(db.String(150), nullable=False)
    capacity_kg = db.Column(db.Float, default=5000.0)
    contact = db.Column(db.String(30), nullable=True)
    manager_name = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(20), default='Operational')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'facility_type': self.facility_type,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else None,
            'location': self.location,
            'capacity_kg': self.capacity_kg,
            'contact': self.contact,
            'manager_name': self.manager_name,
            'status': self.status
        }


class MaterialMovement(db.Model):
    __tablename__ = 'material_movements'

    id = db.Column(db.Integer, primary_key=True)
    movement_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    pickup_id = db.Column(db.Integer, db.ForeignKey('pickups.id'), nullable=True)
    waste_category_id = db.Column(db.Integer, db.ForeignKey('waste_categories.id'), nullable=False)
    source_type = db.Column(db.String(40), nullable=False)  # Household, Mini-MCF, MCF, RRF
    source_name = db.Column(db.String(100), nullable=False)
    destination_type = db.Column(db.String(40), nullable=False)  # Mini-MCF, MCF, RRF, Recycler, Disposal
    destination_name = db.Column(db.String(100), nullable=False)
    weight_kg = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='Dispatched')  # Dispatched, In Transit, Received, Processed
    handler_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    movement_date = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('WasteCategory')
    handler = db.relationship('User', foreign_keys=[handler_id])

    def to_dict(self):
        return {
            'id': self.id,
            'movement_code': self.movement_code,
            'pickup_id': self.pickup_id,
            'waste_category_id': self.waste_category_id,
            'category_name': self.category.name if self.category else None,
            'source_type': self.source_type,
            'source_name': self.source_name,
            'destination_type': self.destination_type,
            'destination_name': self.destination_name,
            'weight_kg': round(self.weight_kg, 2),
            'status': self.status,
            'handler_name': self.handler.full_name if self.handler else None,
            'movement_date': self.movement_date.strftime('%Y-%m-%d %H:%M') if self.movement_date else None
        }
