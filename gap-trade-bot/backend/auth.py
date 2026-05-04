#!/usr/bin/env python3
"""
Authentication System for Trading Advisor
Handles user registration, login, and session management using SQLite database
"""
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, session
from database import db_manager

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
    
    def register_user(self, username, email, password):
        """Register a new user"""
        # Validate input
        if not username or not email or not password:
            return False, "All fields are required"
        
        if len(username) < 3:
            return False, "Username must be at least 3 characters"
        
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        
        if not '@' in email:
            return False, "Invalid email format"
        
        # Hash password
        password_hash = self.hash_password(password)
        
        # Create user in database
        success, message = db_manager.create_user(username, email, password_hash)
        
        if success:
            return True, "User registered successfully"
        else:
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
        db_manager.create_session(session_token, session_data['username'], new_expires_at)
        
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
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        request.user = auth_manager.get_user_by_session(session_token)
        return f(*args, **kwargs)

    return decorated_function


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
            return f(*args, **kwargs)
        return decorated_function
    return decorator 