from datetime import datetime
from app.extensions import db
from sqlalchemy.ext.hybrid import hybrid_property
import json

class UserFeeRule(db.Model):
    __tablename__ = 'user_fee_rules'

    id = db.Column(db.Integer, primary_key=True)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=False, index=True)
    customer_type = db.Column(db.String(40), nullable=False)  # Household, Shop, Office, School/College, Institution, Other Commercial
    service_type = db.Column(db.String(50), default='Standard Household Collection')  # Standard Household Collection, Commercial Collection, Special Pickup, Extra Volume
    collection_frequency = db.Column(db.String(20), default='Monthly')  # Monthly, Per-Pickup, Quarterly, Annual
    base_fee = db.Column(db.Float, nullable=False, default=100.0)  # INR ₹
    additional_fee = db.Column(db.Float, default=0.0)  # Extra fee per additional kg / special item
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.String(255), default='[DEMO DATA] Configurable local tariff rule')

    def to_dict(self):
        return {
            'id': self.id,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else None,
            'customer_type': self.customer_type,
            'service_type': self.service_type,
            'collection_frequency': self.collection_frequency,
            'base_fee': self.base_fee,
            'additional_fee': self.additional_fee,
            'effective_from': self.effective_from.strftime('%Y-%m-%d') if self.effective_from else None,
            'effective_to': self.effective_to.strftime('%Y-%m-%d') if self.effective_to else None,
            'active': self.active,
            'notes': self.notes
        }


class MaterialRate(db.Model):
    __tablename__ = 'material_rates'

    id = db.Column(db.Integer, primary_key=True)
    waste_category_id = db.Column(db.Integer, db.ForeignKey('waste_categories.id'), nullable=False, index=True)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=True)
    buyer_name = db.Column(db.String(100), default='Clean Kerala Company / Authorized Recycler')
    purchase_rate = db.Column(db.Float, nullable=False, default=15.0)  # Realization rate ₹/kg received when selling to recycler
    buyback_rate = db.Column(db.Float, default=0.0)  # Optional payout rate ₹/kg paid to citizen (separate from fee)
    processing_cost = db.Column(db.Float, default=2.0)  # MCF/RRF sorting cost ₹/kg
    disposal_cost = db.Column(db.Float, default=1.0)  # Residue disposal cost ₹/kg
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)

    local_body = db.relationship('LocalBody')

    def to_dict(self):
        return {
            'id': self.id,
            'waste_category_id': self.waste_category_id,
            'category_name': self.category.name if self.category else None,
            'category_code': self.category.code if self.category else None,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else 'All Local Bodies',
            'buyer_name': self.buyer_name,
            'purchase_rate': self.purchase_rate,
            'buyback_rate': self.buyback_rate,
            'processing_cost': self.processing_cost,
            'disposal_cost': self.disposal_cost,
            'effective_from': self.effective_from.strftime('%Y-%m-%d') if self.effective_from else None,
            'effective_to': self.effective_to.strftime('%Y-%m-%d') if self.effective_to else None,
            'active': self.active
        }


class OperationalCost(db.Model):
    __tablename__ = 'operational_costs'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    # Categories: Labour Cost, Fuel Cost, Vehicle Maintenance, Collection Equipment, PPE, Sorting Cost,
    # Processing Cost, Storage Cost, Facility Cost, Transport to Recycler, Disposal Cost, Payment Gateway Cost, Communication Cost, Other
    amount = db.Column(db.Float, nullable=False)
    cost_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    local_body_id = db.Column(db.Integer, db.ForeignKey('local_bodies.id'), nullable=True)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=True)
    reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    local_body = db.relationship('LocalBody')
    ward = db.relationship('Ward')
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'amount': round(self.amount, 2),
            'cost_date': self.cost_date.strftime('%Y-%m-%d') if self.cost_date else None,
            'local_body_id': self.local_body_id,
            'local_body_name': self.local_body.name if self.local_body else 'General',
            'ward_id': self.ward_id,
            'ward_name': self.ward.ward_name if self.ward else None,
            'reference': self.reference,
            'notes': self.notes,
            'created_by': self.creator.full_name if self.creator else 'System',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    txn_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    transaction_type = db.Column(db.String(30), nullable=False)
    # Types: COLLECTION_FEE, MATERIAL_PAYOUT, REFUND, REWARD, PENALTY, OTHER
    direction = db.Column(db.String(30), nullable=False)
    # Directions: CUSTOMER_TO_GREENCYCLE, GREENCYCLE_TO_CUSTOMER
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Successful')
    reference_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', foreign_keys=[user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'txn_number': self.txn_number,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'transaction_type': self.transaction_type,
            'direction': self.direction,
            'amount': round(self.amount, 2),
            'status': self.status,
            'reference_id': self.reference_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey('collection_requests.id'), nullable=True)
    fee_rule_id = db.Column(db.Integer, db.ForeignKey('user_fee_rules.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    billing_period = db.Column(db.String(30), nullable=False)  # e.g., 'October 2026', 'Per-Pickup #102'
    status = db.Column(db.String(20), default='Pending', index=True)
    # Pending, Initiated, Successful, Failed, Cancelled, Refunded
    payment_method = db.Column(db.String(30), default='Online Payment')  # UPI, Online Payment, Cash, Offline
    due_date = db.Column(db.Date, nullable=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    collector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # if cash collected on doorstep
    approved_by_admin = db.Column(db.Boolean, default=False)  # for cash reconciliation
    cash_reconciled_at = db.Column(db.DateTime, nullable=True)
    cash_reconciled_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    collector = db.relationship('User', foreign_keys=[collector_id])
    receipt = db.relationship('PaymentReceipt', backref='payment', uselist=False, lazy=True)
    fee_rule = db.relationship('UserFeeRule')
    reconciled_admin = db.relationship('User', foreign_keys=[cash_reconciled_by])

    def __init__(self, **kwargs):
        if 'due_date' not in kwargs:
            from datetime import date, timedelta
            kwargs['due_date'] = date.today() + timedelta(days=7)
        elif hasattr(kwargs['due_date'], 'date'):
            kwargs['due_date'] = kwargs['due_date'].date()
        if 'payment_number' not in kwargs:
            import uuid
            kwargs['payment_number'] = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        if 'billing_period' not in kwargs:
            kwargs['billing_period'] = 'Current Billing'
        if 'paid' in kwargs:
            paid_val = kwargs.pop('paid')
            kwargs['status'] = 'Successful' if paid_val else 'Pending'
        super().__init__(**kwargs)

    @hybrid_property
    def paid(self):
        return self.status == 'Successful'

    @paid.setter
    def paid(self, value):
        self.status = 'Successful' if value else 'Pending'

    @paid.expression
    def paid(cls):
        return cls.status == 'Successful'

    def to_dict(self):
        return {
            'id': self.id,
            'payment_number': self.payment_number,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'user_phone': self.user.phone if self.user else None,
            'amount': round(self.amount, 2),
            'billing_period': self.billing_period,
            'status': self.status,
            'paid': self.paid,
            'payment_method': self.payment_method,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else None,
            'paid_at': self.paid_at.strftime('%Y-%m-%d %H:%M') if self.paid_at else None,
            'collector_id': self.collector_id,
            'collector_name': self.collector.full_name if self.collector else None,
            'approved_by_admin': self.approved_by_admin,
            'cash_reconciled_at': self.cash_reconciled_at.strftime('%Y-%m-%d %H:%M') if self.cash_reconciled_at else None,
            'cash_reconciled_by_name': self.reconciled_admin.full_name if self.reconciled_admin else None,
            'notes': self.notes,
            'receipt': self.receipt.to_dict() if self.receipt else None
        }


class PaymentReceipt(db.Model):
    __tablename__ = 'payment_receipts'

    id = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(35), unique=True, nullable=False, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(30), nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    receipt_data_json = db.Column(db.Text, nullable=True)

    user = db.relationship('User', foreign_keys=[user_id])
    transaction = db.relationship('Transaction')

    def to_dict(self):
        return {
            'id': self.id,
            'receipt_number': self.receipt_number,
            'payment_id': self.payment_id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'amount': round(self.amount, 2),
            'payment_method': self.payment_method,
            'issued_at': self.issued_at.strftime('%Y-%m-%d %H:%M:%S') if self.issued_at else None,
            'details': json.loads(self.receipt_data_json) if self.receipt_data_json else {}
        }
