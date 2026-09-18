"""
Root models module for backwards compatibility.
Re-exports all models from app.models.
"""
from app.extensions import db
from app.models import (
    User, WasteEntry, Payment, Pickup, PickupItem,
    LocalBody, Ward, Address, WasteCategory, CollectionRequest, CollectionRequestItem,
    CollectionSchedule, Collector, Vehicle, Facility, MaterialMovement,
    UserFeeRule, MaterialRate, OperationalCost, Transaction, PaymentReceipt,
    Complaint, SystemConfig, Volunteer, Event, EventRegistration, Attendance, VolunteerReward,
    AuditLog, Notification
)

__all__ = [
    'db', 'User', 'WasteEntry', 'Payment', 'Pickup', 'PickupItem',
    'LocalBody', 'Ward', 'Address', 'WasteCategory', 'CollectionRequest', 'CollectionRequestItem',
    'CollectionSchedule', 'Collector', 'Vehicle', 'Facility', 'MaterialMovement',
    'UserFeeRule', 'MaterialRate', 'OperationalCost', 'Transaction', 'PaymentReceipt',
    'Complaint', 'SystemConfig', 'Volunteer', 'Event', 'EventRegistration', 'Attendance', 'VolunteerReward',
    'AuditLog', 'Notification'
]
