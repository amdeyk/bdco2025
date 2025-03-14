# Example of improved auth service (auth.py)
import secrets
from datetime import datetime, timedelta

class AuthService:
    """Authentication and authorization service"""
    
    def __init__(self, admin_password):
        self.admin_password = admin_password
        self.sessions = {}  # In-memory session store
    
    def create_session(self, user_id, role):
        """Create a new session for a user"""
        session_id = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(hours=12)
        
        self.sessions[session_id] = {
            "user_id": user_id,
            "role": role,
            "expires": expiry
        }
        
        return session_id
    
    def validate_session(self, session_id):
        """Validate a session and return user information"""
        if not session_id or session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # Check expiry
        if datetime.now() > session["expires"]:
            del self.sessions[session_id]
            return None
        
        return session
    
    def require_admin(self, session_id):
        """Check if the session has admin privileges"""
        session = self.validate_session(session_id)
        if not session or session["role"] != "admin":
            return False
        return True
        
    def require_faculty(self, session_id):
        """Check if the session has faculty privileges"""
        session = self.validate_session(session_id)
        if not session or session["role"] not in ["admin", "faculty"]:
            return False
        return True