from datetime import datetime
from app.extensions import db

class Complaint(db.Model):
    __tablename__ = 'complaints'

    id = db.Column(db.Integer, primary_key=True)
    comp_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    pickup_id = db.Column(db.Integer, db.ForeignKey('pickups.id'), nullable=True)
    category = db.Column(db.String(50), nullable=False)
    # Categories: Missed Collection, Late Collection, Wrong User Fee, Payment Problem, Waste Not Accepted,
    # Incorrect Waste Classification, Collector Issue, Damaged Property, Address Problem, Other
    description = db.Column(db.Text, nullable=False)
    evidence_photo = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default='Medium')  # Low, Medium, High, Urgent
    status = db.Column(db.String(25), default='Open', index=True)  # Open, Assigned, In Progress, Resolved, Reopened, Closed
    assigned_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    pickup = db.relationship('Pickup')
    assigned_admin = db.relationship('User', foreign_keys=[assigned_admin_id])

    def to_dict(self):
        return {
            'id': self.id,
            'comp_number': self.comp_number,
            'citizen_id': self.citizen_id,
            'citizen_name': self.citizen.full_name if self.citizen else None,
            'citizen_phone': self.citizen.phone if self.citizen else None,
            'pickup_id': self.pickup_id,
            'pickup_number': self.pickup.pickup_number if self.pickup else None,
            'category': self.category,
            'description': self.description,
            'evidence_photo': self.evidence_photo,
            'priority': self.priority,
            'status': self.status,
            'assigned_admin_id': self.assigned_admin_id,
            'assigned_admin_name': self.assigned_admin.full_name if self.assigned_admin else 'Unassigned',
            'resolution_notes': self.resolution_notes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'resolved_at': self.resolved_at.strftime('%Y-%m-%d %H:%M') if self.resolved_at else None
        }


class SystemConfig(db.Model):
    __tablename__ = 'system_configs'

    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(60), unique=True, nullable=False, index=True)
    config_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'key': self.config_key,
            'value': self.config_value,
            'description': self.description,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None
        }
