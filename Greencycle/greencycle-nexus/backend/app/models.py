from app import db
from datetime import datetime


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    pin = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(10), default='citizen')  # citizen, worker, admin

    waste_entries = db.relationship('WasteEntry', backref='user', lazy=True, foreign_keys='WasteEntry.user_id')
    payments = db.relationship('Payment', backref='user', lazy=True)
    pickups_as_citizen = db.relationship('Pickup', backref='citizen', lazy=True, foreign_keys='Pickup.user_id')
    pickups_as_worker = db.relationship('Pickup', backref='worker', lazy=True, foreign_keys='Pickup.worker_id')

    def to_dict(self):
        return {'id': self.id, 'phone': self.phone, 'role': self.role}


class WasteEntry(db.Model):
    __tablename__ = 'waste_entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    food = db.Column(db.Float, default=0.0)
    plastic = db.Column(db.Float, default=0.0)
    other = db.Column(db.Float, default=0.0)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    approved = db.Column(db.Boolean, default=False)

    def total_amount(self):
        return (self.food * 2) + (self.plastic * 3) + (self.other * 1)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'food': self.food,
            'plastic': self.plastic,
            'other': self.other,
            'date': self.date.strftime('%Y-%m-%d %H:%M'),
            'approved': self.approved,
            'amount': self.total_amount()
        }


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    paid = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'due_date': self.due_date.strftime('%Y-%m-%d'),
            'paid': self.paid
        }


class Pickup(db.Model):
    __tablename__ = 'pickups'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, collected

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'worker_id': self.worker_id,
            'date': self.date.strftime('%Y-%m-%d %H:%M'),
            'status': self.status
        }
