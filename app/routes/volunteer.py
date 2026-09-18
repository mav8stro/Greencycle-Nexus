from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from app.extensions import db
from app.models import Volunteer, Event, EventRegistration, Attendance, VolunteerReward, User
from app.services.auth_service import token_required, role_required, log_audit, create_notification

volunteer_bp = Blueprint('volunteer', __name__, url_prefix='/api/volunteer')

@volunteer_bp.route('/profile', methods=['GET'])
@role_required(['volunteer', 'admin'])
def get_volunteer_profile():
    user = request.current_user
    vol = user.volunteer_profile
    if not vol:
        return jsonify({'error': 'Volunteer profile not found'}), 404
    return jsonify(vol.to_dict())

@volunteer_bp.route('/events', methods=['GET'])
@token_required
def get_available_events():
    events = Event.query.filter(Event.status.in_(['Published', 'Ongoing'])).order_by(Event.event_date.asc()).all()
    user_vol = request.current_user.volunteer_profile
    
    result = []
    for ev in events:
        d = ev.to_dict()
        d['is_registered'] = False
        if user_vol:
            reg = EventRegistration.query.filter_by(event_id=ev.id, volunteer_id=user_vol.id).first()
            if reg:
                d['is_registered'] = True
                d['registration_status'] = reg.status
        result.append(d)
    return jsonify(result)

@volunteer_bp.route('/events/<int:event_id>/register', methods=['POST'])
@role_required(['volunteer', 'admin'])
def register_for_event(event_id):
    vol = request.current_user.volunteer_profile
    if not vol or vol.status != 'Approved':
        return jsonify({'error': 'Volunteer account must be approved by Admin to register for events.'}), 403

    event = db.get_or_404(Event, event_id)
    if event.status != 'Published':
        return jsonify({'error': 'Event is not open for registration.'}), 400

    existing = EventRegistration.query.filter_by(event_id=event.id, volunteer_id=vol.id).first()
    if existing:
        return jsonify({'message': 'Already registered for this event.', 'registration': existing.to_dict()})

    reg = EventRegistration(
        event_id=event.id,
        volunteer_id=vol.id,
        status='Approved',
        registered_at=datetime.now(timezone.utc),
        approved_at=datetime.now(timezone.utc)
    )
    db.session.add(reg)
    db.session.commit()

    log_audit('EVENT_REGISTER', 'EventRegistration', reg.id, None, {'event_id': event.id}, request.user_id, request.user_role)
    create_notification(request.user_id, 'Event Registration Confirmed', f"You are registered for {event.title} on {event.event_date}.", 'event')

    return jsonify({'message': 'Successfully registered for event!', 'registration': reg.to_dict()}), 201

@volunteer_bp.route('/my-registrations', methods=['GET'])
@role_required(['volunteer', 'admin'])
def get_my_registrations():
    vol = request.current_user.volunteer_profile
    if not vol:
        return jsonify([])
    regs = EventRegistration.query.filter_by(volunteer_id=vol.id).all()
    return jsonify([r.to_dict() for r in regs])

@volunteer_bp.route('/attendance/qr-checkin', methods=['POST'])
@role_required(['volunteer', 'admin'])
def qr_checkin():
    """
    QR Attendance Check-in:
    Volunteer enters or scans QR token. System verifies and prevents duplicate check-in.
    """
    vol = request.current_user.volunteer_profile
    if not vol:
        return jsonify({'error': 'Volunteer profile not found'}), 404

    data = request.get_json() or {}
    qr_token = data.get('qr_token', '').strip()
    if not qr_token:
        return jsonify({'error': 'Please provide the Event QR Check-in token.'}), 400

    event = Event.query.filter_by(qr_checkin_token=qr_token).first()
    if not event:
        return jsonify({'error': 'Invalid QR check-in token.'}), 404

    # Prevent duplicate check-in
    existing = Attendance.query.filter_by(event_id=event.id, volunteer_id=vol.id).first()
    if existing and existing.status in ('Checked In', 'Completed'):
        return jsonify({'error': f'Already checked in at {existing.check_in_time.strftime("%H:%M")}.'}), 400

    att = Attendance(
        event_id=event.id,
        volunteer_id=vol.id,
        check_in_time=datetime.now(timezone.utc),
        status='Checked In',
        verified_by=request.user_id
    )
    db.session.add(att)
    db.session.commit()

    log_audit('QR_CHECKIN', 'Attendance', att.id, None, {'event_id': event.id}, request.user_id, request.user_role)
    return jsonify({
        'message': f'✓ Checked in successfully for "{event.title}"!',
        'attendance': att.to_dict()
    })

@volunteer_bp.route('/attendance/qr-checkout', methods=['POST'])
@role_required(['volunteer', 'admin'])
def qr_checkout():
    """
    QR Attendance Check-out:
    Volunteer enters or scans check-out QR token.
    Calculates hours spent and automatically awards points and updates reward badges!
    """
    vol = request.current_user.volunteer_profile
    if not vol:
        return jsonify({'error': 'Volunteer profile not found'}), 404

    data = request.get_json() or {}
    qr_token = data.get('qr_token', '').strip()
    if not qr_token:
        return jsonify({'error': 'Please provide the Event QR Check-out token.'}), 400

    event = Event.query.filter_by(qr_checkout_token=qr_token).first()
    if not event:
        return jsonify({'error': 'Invalid QR check-out token.'}), 404

    att = Attendance.query.filter_by(event_id=event.id, volunteer_id=vol.id, status='Checked In').first()
    if not att:
        return jsonify({'error': 'No active check-in found for this event. Please check in first.'}), 400

    checkout_time = datetime.now(timezone.utc).replace(tzinfo=None)
    checkin_time = att.check_in_time.replace(tzinfo=None) if att.check_in_time and att.check_in_time.tzinfo else att.check_in_time
    duration_seconds = (checkout_time - checkin_time).total_seconds()
    # If checked out immediately in demo, grant minimum 2.0 hours credit
    hours = max(2.0, round(duration_seconds / 3600.0, 1))

    att.check_out_time = checkout_time
    att.hours_spent = hours
    att.status = 'Completed'

    # Award Points — read from SystemConfig (configurable by Admin)
    from app.models.feedback import SystemConfig
    pts_cfg = SystemConfig.query.filter_by(config_key='VOLUNTEER_POINTS_PER_HOUR').first()
    points_per_hour = int(pts_cfg.config_value) if pts_cfg else 15
    waste_cfg = SystemConfig.query.filter_by(config_key='VOLUNTEER_WASTE_KG_PER_EVENT').first()
    waste_per_event = float(waste_cfg.config_value) if waste_cfg else 20.0

    points_earned = int(hours * points_per_hour)
    reward = vol.rewards
    if not reward:
        reward = VolunteerReward(volunteer_id=vol.id)
        db.session.add(reward)

    reward.total_hours += hours
    reward.points += points_earned
    reward.events_completed += 1
    reward.waste_collected_kg += waste_per_event

    db.session.commit()

    log_audit('QR_CHECKOUT', 'Attendance', att.id, None, {'hours': hours, 'points': points_earned}, request.user_id, request.user_role)
    create_notification(request.user_id, 'Volunteer Hours Awarded', f"Event completed! You earned {hours} hours and {points_earned} points.", 'event')

    return jsonify({
        'message': f'✓ Checked out successfully! Earned {hours} hours and {points_earned} points.',
        'attendance': att.to_dict(),
        'rewards': reward.to_dict()
    })

@volunteer_bp.route('/rewards', methods=['GET'])
@role_required(['volunteer', 'admin'])
def get_rewards():
    vol = request.current_user.volunteer_profile
    if not vol or not vol.rewards:
        return jsonify({'points': 0, 'total_hours': 0, 'events_completed': 0, 'waste_collected_kg': 0, 'badges': []})
    return jsonify(vol.rewards.to_dict())
