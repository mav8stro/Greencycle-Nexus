from datetime import datetime
from app.extensions import db
from sqlalchemy.orm import synonym
from sqlalchemy.ext.hybrid import hybrid_property
import json

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='citizen')  # citizen, worker, volunteer, admin
    full_name = db.Column(db.String(100), nullable=False, default='Civic User')
    must_change_password = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    addresses = db.relationship('Address', backref='user', lazy=True, cascade="all, delete-orphan")
    collection_requests = db.relationship('CollectionRequest', backref='citizen', lazy=True, foreign_keys='CollectionRequest.citizen_id')
    pickups_as_citizen = db.relationship('Pickup', backref='citizen', lazy=True, foreign_keys='Pickup.citizen_id')
    pickups_as_collector = db.relationship('Pickup', backref='collector', lazy=True, foreign_keys='Pickup.collector_id')
    payments = db.relationship('Payment', backref='user', lazy=True, foreign_keys='Payment.user_id')
    complaints = db.relationship('Complaint', backref='citizen', lazy=True, foreign_keys='Complaint.citizen_id')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")
    volunteer_profile = db.relationship('Volunteer', foreign_keys='Volunteer.user_id', back_populates='user', uselist=False, lazy=True)
    collector_profile = db.relationship('Collector', foreign_keys='Collector.user_id', backref='user', uselist=False, lazy=True)

    def __init__(self, **kwargs):
        if 'pin' in kwargs and 'password_hash' not in kwargs:
            raw = kwargs.pop('pin')
            if raw and (raw.startswith(('scrypt:', 'pbkdf2:')) or (len(raw) == 64 and all(c in '0123456789abcdefABCDEF' for c in raw))):
                kwargs['password_hash'] = raw
            else:
                from app.services.auth_service import hash_password
                kwargs['password_hash'] = hash_password(raw)
        super().__init__(**kwargs)

    @hybrid_property
    def pin(self):
        return self.password_hash

    @pin.setter
    def pin(self, val):
        from app.services.auth_service import hash_password
        if val and (val.startswith(('scrypt:', 'pbkdf2:')) or (len(val) == 64 and all(c in '0123456789abcdefABCDEF' for c in val))):
            self.password_hash = val
        else:
            self.password_hash = hash_password(val)

    @pin.expression
    def pin(cls):
        return cls.password_hash

    pickups_as_worker = synonym('pickups_as_collector')

    def to_dict(self, include_sensitive=False):
        d = {
            'id': self.id,
            'phone': self.phone,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'must_change_password': self.must_change_password,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }
        if self.addresses and len(self.addresses) > 0:
            primary_addr = self.addresses[0]
            d['address'] = primary_addr.to_dict()
        if self.volunteer_profile:
            d['volunteer_profile'] = self.volunteer_profile.to_dict()
        if self.collector_profile:
            d['collector_profile'] = self.collector_profile.to_dict()
        return d


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    actor_role = db.Column(db.String(20), nullable=True)
    action = db.Column(db.String(80), nullable=False)  # LOGIN, USER_CREATE, WASTE_VERIFY, CASH_APPROVE, etc.
    entity_type = db.Column(db.String(50), nullable=False)  # User, Pickup, Payment, FeeRule, etc.
    entity_id = db.Column(db.String(50), nullable=True)
    old_values = db.Column(db.Text, nullable=True)  # JSON string
    new_values = db.Column(db.Text, nullable=True)  # JSON string
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    actor = db.relationship('User', foreign_keys=[actor_id])

    def to_dict(self):
        return {
            'id': self.id,
            'actor_id': self.actor_id,
            'actor_name': self.actor.full_name if self.actor else 'System',
            'actor_role': self.actor_role or (self.actor.role if self.actor else 'System'),
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'old_values': json.loads(self.old_values) if self.old_values else None,
            'new_values': json.loads(self.new_values) if self.new_values else None,
            'ip_address': self.ip_address,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(40), default='general')  # request, pickup, payment, complaint, event
    is_read = db.Column(db.Boolean, default=False, index=True)
    link_url = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type,
            'is_read': self.is_read,
            'link_url': self.link_url,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }
