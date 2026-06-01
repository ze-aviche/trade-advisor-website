#!/usr/bin/env python3
"""
Authentication System for Trading Advisor
Handles user registration, login, and session management using SQLite database
"""
import hashlib
import logging
import re
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, session, g
from database import db_manager

_auth_logger = logging.getLogger('auth')

class AuthManager:
    def __init__(self):
        # Migrate existing users from JSON to database
        db_manager.migrate_existing_users()
        self.session_timeout = 24 * 60 * 60  # 24 hours in seconds
    
    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def generate_session_token(self):
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)
    
    def register_user(self, username, email, password, first_name=None, last_name=None,
                       address=None, profession=None, annual_income_range=None):
        """Register a new user"""
        if not username or not email or not password:
            return False, "All fields are required"
        if len(username) < 8:
            return False, "Username must be at least 8 characters"
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return False, "Username may only contain letters, numbers, and underscores"
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        if '@' not in email:
            return False, "Invalid email format"

        password_hash = self.hash_password(password)
        success, message = db_manager.create_user(
            username, email, password_hash,
            first_name=first_name, last_name=last_name,
            address=address, profession=profession,
            annual_income_range=annual_income_range
        )
        if success:
            return True, message  # message is the verification token UUID
        return False, message
    
    def login_user(self, username, password):
        """Login a user"""
        if not username or not password:
            return False, "Username and password are required"
        
        # Get user from database
        user = db_manager.get_user_by_username(username)
        
        if not user:
            return False, "Invalid username or password"
        
        # Check password
        password_hash = self.hash_password(password)
        if user['password_hash'] != password_hash:
            return False, "Invalid username or password"

        # Check account is active
        if not user.get('is_active', 1):
            return False, "Account is deactivated. Contact an administrator."

        # Block login until email is verified
        if not user.get('email_verified', 0):
            return False, "EMAIL_NOT_VERIFIED"

        # Update last login
        db_manager.update_last_login(username)

        # Generate session token
        session_token = self.generate_session_token()
        expires_at = datetime.now() + timedelta(seconds=self.session_timeout)

        # Create session in database
        if db_manager.create_session(session_token, username, expires_at):
            return True, {
                'session_token': session_token,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'system_role': user.get('system_role'),
                    'subscription_tier': user.get('subscription_tier', 'basic'),
                    'subscription_status': user.get('subscription_status', 'active'),
                    'preferences': user.get('preferences', {})
                }
            }
        else:
            return False, "Failed to create session"
    
    def validate_session(self, session_token):
        """Validate a session token"""
        if not session_token:
            return False, None
        
        # Get session from database
        session_data = db_manager.get_session(session_token)
        
        if not session_data:
            return False, None
        
        # Check if session is expired
        if datetime.now() > session_data['expires_at']:
            # Session expired, remove it
            db_manager.delete_session(session_token)
            return False, None
        
        # Extend session
        new_expires_at = datetime.now() + timedelta(seconds=self.session_timeout)
        db_manager.update_session_expiry(session_token, new_expires_at)
        
        return True, session_data
    
    def logout_user(self, session_token):
        """Logout a user"""
        if session_token:
            db_manager.delete_session(session_token)
        return True, "Logged out successfully"
    
    def get_user_by_session(self, session_token):
        """Get user data by session token"""
        valid, session_data = self.validate_session(session_token)
        if not valid:
            return None
        
        username = session_data['username']
        user = db_manager.get_user_by_username(username)
        
        if user:
            # Don't return password hash
            user.pop('password_hash', None)
            return user
        
        return None
    
    def update_user_preferences(self, session_token, preferences):
        """Update user preferences"""
        user = self.get_user_by_session(session_token)
        if not user:
            return False, "Invalid session"
        
        username = user['username']
        current_preferences = user.get('preferences', {})
        current_preferences.update(preferences)
        
        if db_manager.update_user_preferences(username, current_preferences):
            return True, "Preferences updated successfully"
        else:
            return False, "Failed to update preferences"
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        return db_manager.cleanup_expired_sessions()

# Global auth manager instance
auth_manager = AuthManager()

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')

        if not session_token:
            session_token = request.cookies.get('session_token')

        valid, session_data = auth_manager.validate_session(session_token)
        if not valid:
            token_hint = ('…' + session_token[-6:]) if session_token else 'none'
            _POLLING_PATHS = {
                '/api/brown-bot/status', '/api/brown-bot/logs', '/api/brown-bot/risk-status',
                '/api/bot/status', '/api/entry-bot/status', '/api/session/ping', '/api/health',
            }
            log_fn = _auth_logger.debug if request.path in _POLLING_PATHS else _auth_logger.warning
            log_fn(
                f'401 {request.method} {request.path} '
                f'token={token_hint} ip={request.remote_addr}'
            )
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        request.user = auth_manager.get_user_by_session(session_token)
        _tag_request_context(request.user)
        return f(*args, **kwargs)

    return decorated_function


_TIER_ORDER = {'basic': 0, 'beginner': 1, 'advanced': 2, 'yogi': 3}


def _get_effective_tier(user: dict) -> str:
    """Return the user's effective subscription tier, honouring active free trials."""
    from datetime import datetime as _dt
    base = user.get('subscription_tier', 'basic') or 'basic'
    trial_raw = user.get('trial_expires_at')
    if trial_raw and base == 'basic':
        try:
            if _dt.fromisoformat(str(trial_raw)) > _dt.now():
                return 'yogi'
        except Exception:
            pass
    return base


def require_tier(*min_tiers):
    """Decorator: require the user to be on at least one of the given tiers (or higher).
    Staff accounts (system_role set) bypass the check.
    Usage: @require_tier('beginner')  or  @require_tier('yogi')
    """
    min_rank = min(_TIER_ORDER.get(t, 0) for t in min_tiers)

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = getattr(request, 'user', None)
            if not user:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            # Staff always bypass tier checks
            if user.get('system_role'):
                return f(*args, **kwargs)
            effective = _get_effective_tier(user)
            if _TIER_ORDER.get(effective, 0) < min_rank:
                return jsonify({
                    'success': False,
                    'error': f'This feature requires a {min_tiers[0].capitalize()} Trader subscription or higher.',
                    'upgrade_required': True,
                    'required_tier': min_tiers[0],
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(*system_roles):
    """Decorator to require one of the given system_roles (super_admin, dev_master)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not session_token:
                session_token = request.cookies.get('session_token')

            valid, _ = auth_manager.validate_session(session_token)
            if not valid:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401

            user = auth_manager.get_user_by_session(session_token)
            if not user:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401

            if user.get('system_role') not in system_roles:
                return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

            request.user = user
            _tag_request_context(user)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def _tag_request_context(user: dict) -> None:
    """Set Flask g and Sentry user context for the current request."""
    if not user:
        return
    uid = user.get('id')
    g.current_user_id = uid
    try:
        import sentry_sdk
        sentry_sdk.set_user({
            'id':       str(uid),
            'username': user.get('username'),
            'email':    user.get('email'),
        })
    except Exception:
        pass 