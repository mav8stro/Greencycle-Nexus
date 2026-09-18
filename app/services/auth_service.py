from functools import wraps
from flask import request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import hmac
import hashlib
import base64
import json
import time
from app.extensions import db
from app.models.user import User, AuditLog, Notification

def hash_password(password: str) -> str:
    """Secure password hashing using Werkzeug (PBKDF2/scrypt with random salt)."""
    return generate_password_hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """Verifies plaintext against hash. Also supports legacy sha256 hashes during migration."""
    if hashed and hashed.startswith(('scrypt:', 'pbkdf2:')):
        return check_password_hash(hashed, password)
    # Legacy fallback for old 4-digit PINs (sha256 hex)
    if hashed == hashlib.sha256(password.encode()).hexdigest():
        return True
    return False

def make_token(user_id: int, role: str) -> str:
    """Generates cryptographically signed HMAC-SHA256 session token."""
    secret = current_app.config.get('SECRET_KEY', 'greencycle-nexus-secret-kerala-2026').encode('utf-8')
    expiry_hours = current_app.config.get('TOKEN_EXPIRY_HOURS', 48)
    exp = int(time.time()) + (expiry_hours * 3600)
    
    payload = {
        'user_id': user_id,
        'role': role,
        'iat': int(time.time()),
        'exp': exp
    }
    raw_payload = json.dumps(payload, separators=(',', ':'))
    b64_payload = base64.urlsafe_b64encode(raw_payload.encode('utf-8')).decode('utf-8').rstrip('=')
    signature = hmac.new(secret, b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{signature}"

def decode_token(token: str):
    """Verifies signature and expiration of session token."""
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        b64_payload, signature = parts
        secret = current_app.config.get('SECRET_KEY', 'greencycle-nexus-secret-kerala-2026').encode('utf-8')
        expected_sig = hmac.new(secret, b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Pad base64 if needed
        padding = 4 - (len(b64_payload) % 4)
        if padding != 4:
            b64_payload += '=' * padding

        raw_payload = base64.urlsafe_b64decode(b64_payload.encode('utf-8')).decode('utf-8')
        data = json.loads(raw_payload)

        # Check expiration
        if 'exp' in data and data['exp'] < int(time.time()):
            return None

        return data
    except Exception:
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        token = auth.replace('Bearer ', '').strip()
        data = decode_token(token)
        if not data:
            return jsonify({'error': 'Token invalid or expired. Please sign in again.'}), 401

        user = db.session.get(User, data['user_id'])
        if not user or not user.is_active:
            return jsonify({'error': 'User account inactive or not found'}), 401

        # Securely set verified user info on request
        request.user_id = user.id
        request.user_role = user.role
        request.current_user = user
        return f(*args, **kwargs)
    return decorated

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                return jsonify({'error': 'Unauthorized'}), 401
            token = auth.replace('Bearer ', '').strip()
            data = decode_token(token)
            if not data:
                return jsonify({'error': 'Token invalid or expired'}), 401

            user = db.session.get(User, data['user_id'])
            if not user or not user.is_active:
                return jsonify({'error': 'User account inactive or not found'}), 401

            if user.role not in allowed_roles:
                return jsonify({'error': f'Access forbidden: requires one of {allowed_roles}'}), 403

            request.user_id = user.id
            request.user_role = user.role
            request.current_user = user
            return f(*args, **kwargs)
        return decorated
    return decorator

def admin_required(f):
    return role_required(['admin'])(f)

def log_audit(action, entity_type, entity_id=None, old_values=None, new_values=None, actor_id=None, actor_role=None):
    """Creates a persistent audit log record."""
    try:
        log = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            ip_address=request.remote_addr if request else '127.0.0.1'
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Audit log failed: {e}")

def create_notification(user_id, title, message, notif_type='general', link_url=None):
    """Creates an in-app notification for a user."""
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notif_type,
            link_url=link_url
        )
        db.session.add(notif)
        db.session.commit()
        return notif
    except Exception as e:
        db.session.rollback()
        print(f"Notification creation failed: {e}")
        return None
