from datetime import datetime
from app.extensions import db
import json

class Volunteer(db.Model):
    __tablename__ = 'volunteers'

    id = db.Column(db.Integer, primary_key=True)
    volunteer_id_code = db.Column(db.String(30), unique=True, nullable=False, index=True)  # e.g. GCN-VOL-2026-00001
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    district = db.Column(db.String(60), nullable=False)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=True)
    skills = db.Column(db.String(200), default='Community Outreach, Waste Auditing')
    availability = db.Column(db.String(100), default='Weekends')
    emergency_contact = db.Column(db.String(50), nullable=True)
    profile_photo = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default='Pending Approval')  # Pending Approval, Approved, Inactive
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    local_body = db.relationship('LocalBody')
    user = db.relationship('User', foreign_keys=[user_id], back_populates='volunteer_profile')
    approver = db.relationship('User', foreign_keys=[approved_by])
    rewards = db.relationship('VolunteerReward', backref='volunteer', uselist=False, lazy=True, cascade="all, delete-orphan")
    registrations = db.relationship('EventRegistration', backref='volunteer', lazy=True)
    attendances = db.relationship('Attendance', backref='volunteer', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'volunteer_id_code': self.volunteer_id_code,
            'user_id': self.user_id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'district': self.district,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else None,
            'skills': self.skills,
            'availability': self.availability,
            'emergency_contact': self.emergency_contact,
            'profile_photo': self.profile_photo,
            'status': self.status,
            'approved_at': self.approved_at.strftime('%Y-%m-%d %H:%M') if self.approved_at else None,
            'rewards': self.rewards.to_dict() if self.rewards else {
                'points': 0, 'total_hours': 0, 'events_completed': 0, 'waste_collected_kg': 0, 'badges': []
            }
        }


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    event_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    banner_url = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(20), nullable=False)  # 08:00 AM
    end_time = db.Column(db.String(20), nullable=False)    # 12:00 PM
    location = db.Column(db.String(200), nullable=False)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=True)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=True)
    max_participants = db.Column(db.Integer, default=50)
    registration_deadline = db.Column(db.Date, nullable=True)
    required_skills = db.Column(db.String(150), default='Segregation, General Volunteering')
    status = db.Column(db.String(30), default='Published')  # Draft, Published, Ongoing, Completed, Cancelled
    qr_checkin_token = db.Column(db.String(64), unique=True, nullable=False)
    qr_checkout_token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    local_body = db.relationship('LocalBody')
    ward = db.relationship('Ward')
    registrations = db.relationship('EventRegistration', backref='event', lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship('Attendance', backref='event', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        reg_count = len(self.registrations) if self.registrations else 0
        return {
            'id': self.id,
            'event_code': self.event_code,
            'title': self.title,
            'description': self.description,
            'banner_url': self.banner_url,
            'event_date': self.event_date.strftime('%Y-%m-%d') if self.event_date else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'location': self.location,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else 'District-wide',
            'ward_id': self.ward_id,
            'ward_name': self.ward.ward_name if self.ward else None,
            'max_participants': self.max_participants,
            'registered_count': reg_count,
            'registration_deadline': self.registration_deadline.strftime('%Y-%m-%d') if self.registration_deadline else None,
            'required_skills': self.required_skills,
            'status': self.status,
            'qr_checkin_token': self.qr_checkin_token,
            'qr_checkout_token': self.qr_checkout_token
        }


class EventRegistration(db.Model):
    __tablename__ = 'event_registrations'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteers.id'), nullable=False, index=True)
    status = db.Column(db.String(30), default='Registered')  # Registered, Approved, Cancelled
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'event_title': self.event.title if self.event else None,
            'event_date': self.event.event_date.strftime('%Y-%m-%d') if self.event and self.event.event_date else None,
            'event_location': self.event.location if self.event else None,
            'volunteer_id': self.volunteer_id,
            'volunteer_name': self.volunteer.full_name if self.volunteer else None,
            'volunteer_code': self.volunteer.volunteer_id_code if self.volunteer else None,
            'status': self.status,
            'registered_at': self.registered_at.strftime('%Y-%m-%d %H:%M') if self.registered_at else None
        }


class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteers.id'), nullable=False, index=True)
    check_in_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    check_out_time = db.Column(db.DateTime, nullable=True)
    hours_spent = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default='Checked In')  # Checked In, Completed, Absent
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    verifier = db.relationship('User', foreign_keys=[verified_by])

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'event_title': self.event.title if self.event else None,
            'volunteer_id': self.volunteer_id,
            'volunteer_name': self.volunteer.full_name if self.volunteer else None,
            'volunteer_code': self.volunteer.volunteer_id_code if self.volunteer else None,
            'check_in_time': self.check_in_time.strftime('%Y-%m-%d %H:%M:%S') if self.check_in_time else None,
            'check_out_time': self.check_out_time.strftime('%Y-%m-%d %H:%M:%S') if self.check_out_time else None,
            'hours_spent': round(self.hours_spent, 1),
            'status': self.status
        }


class VolunteerReward(db.Model):
    __tablename__ = 'volunteer_rewards'

    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteers.id'), nullable=False, unique=True, index=True)
    points = db.Column(db.Integer, default=0)
    total_hours = db.Column(db.Float, default=0.0)
    events_completed = db.Column(db.Integer, default=0)
    waste_collected_kg = db.Column(db.Float, default=0.0)
    badges_json = db.Column(db.Text, default='["Eco-Pioneer", "Clean Kerala Champion"]')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'points': self.points,
            'total_hours': round(self.total_hours, 1),
            'events_completed': self.events_completed,
            'waste_collected_kg': round(self.waste_collected_kg, 1),
            'badges': json.loads(self.badges_json) if self.badges_json else []
        }
