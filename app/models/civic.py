from datetime import datetime
from app.extensions import db

class LocalBody(db.Model):
    __tablename__ = 'local_bodies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(60), nullable=False)  # Ernakulam, Thiruvananthapuram, Kozhikode, etc.
    body_type = db.Column(db.String(40), nullable=False)  # Grama Panchayat, Municipality, Corporation
    pincode = db.Column(db.String(10), nullable=True)
    service_area = db.Column(db.String(150), nullable=True)
    status = db.Column(db.String(20), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    wards = db.relationship('Ward', backref='local_body', lazy=True, cascade="all, delete-orphan")
    fee_rules = db.relationship('UserFeeRule', backref='local_body', lazy=True)
    facilities = db.relationship('Facility', backref='local_body', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'district': self.district,
            'body_type': self.body_type,
            'pincode': self.pincode,
            'service_area': self.service_area,
            'status': self.status,
            'ward_count': len(self.wards) if self.wards else 0
        }


class Ward(db.Model):
    __tablename__ = 'wards'

    id = db.Column(db.Integer, primary_key=True)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=False, index=True)
    ward_number = db.Column(db.Integer, nullable=False)
    ward_name = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(10), nullable=True)
    status = db.Column(db.String(20), default='Active')

    # Relationships
    addresses = db.relationship('Address', backref='ward', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else None,
            'ward_number': self.ward_number,
            'ward_name': self.ward_name,
            'display_name': f"Ward {self.ward_number}: {self.ward_name}",
            'pincode': self.pincode,
            'status': self.status
        }


class Address(db.Model):
    __tablename__ = 'addresses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    house_number = db.Column(db.String(50), nullable=False)
    street_address = db.Column(db.String(255), nullable=False)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=False)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=False)
    district = db.Column(db.String(60), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    customer_type = db.Column(db.String(40), nullable=False, default='Household')
    # Types: Household, Shop, Office, School/College, Institution, Other Commercial
    resident_count = db.Column(db.Integer, default=4)
    preferred_day = db.Column(db.String(20), default='Monday')
    preferred_slot = db.Column(db.String(30), default='08:00 AM - 11:00 AM')
    is_primary = db.Column(db.Boolean, default=True)

    local_body = db.relationship('LocalBody')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'house_number': self.house_number,
            'street_address': self.street_address,
            'district': self.district,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else None,
            'local_body_type': self.local_body.body_type if self.local_body else None,
            'ward_id': self.ward_id,
            'ward_number': self.ward.ward_number if self.ward else None,
            'ward_name': self.ward.ward_name if self.ward else None,
            'pincode': self.pincode,
            'customer_type': self.customer_type,
            'resident_count': self.resident_count,
            'preferred_day': self.preferred_day,
            'preferred_slot': self.preferred_slot,
            'full_address': f"{self.house_number}, {self.street_address}, Ward {self.ward.ward_number if self.ward else ''}, {self.local_body.name if self.local_body else ''} - {self.pincode}"
        }
