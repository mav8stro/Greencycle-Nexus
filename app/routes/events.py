from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from app.extensions import db
from app.models import Event
from app.services.auth_service import token_required, admin_required, log_audit
import uuid

events_bp = Blueprint('events', __name__, url_prefix='/api/events')

@events_bp.route('', methods=['GET'])
def list_events():
    events = Event.query.order_by(Event.event_date.asc()).all()
    return jsonify([e.to_dict() for e in events])

@events_bp.route('/<int:event_id>', methods=['GET'])
def get_event(event_id):
    event = db.get_or_404(Event, event_id)
    return jsonify(event.to_dict())

@events_bp.route('', methods=['POST'])
@admin_required
def create_event():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    desc = data.get('description', '').strip()
    date_str = data.get('event_date')
    location = data.get('location', '').strip()

    if not title or not desc or not date_str or not location:
        return jsonify({'error': 'Title, description, event date, and location are required.'}), 400

    try:
        ev_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    ev_count = Event.query.count() + 1
    event_code = f"EVT-2026-{ev_count:04d}"

    # Generate QR attendance tokens
    token_in = f"GCN-{event_code}-IN-{uuid.uuid4().hex[:6].upper()}"
    token_out = f"GCN-{event_code}-OUT-{uuid.uuid4().hex[:6].upper()}"

    event = Event(
        event_code=event_code,
        title=title,
        description=desc,
        banner_url=data.get('banner_url'),
        event_date=ev_date,
        start_time=data.get('start_time', '08:00 AM'),
        end_time=data.get('end_time', '12:00 PM'),
        location=location,
        local_body_id=data.get('local_body_id'),
        ward_id=data.get('ward_id'),
        max_participants=int(data.get('max_participants', 50)),
        required_skills=data.get('required_skills', 'Segregation, General Volunteering'),
        status='Published',
        qr_checkin_token=token_in,
        qr_checkout_token=token_out
    )
    db.session.add(event)
    db.session.commit()

    log_audit('EVENT_CREATE', 'Event', event.id, None, {'title': title}, request.user_id, request.user_role)
    return jsonify(event.to_dict()), 201
