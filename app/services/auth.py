# Example of improved auth service (auth.py)
import secrets
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from app.config import Config

# First, define the class
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

# Then, instantiate it
config = Config()
auth_service = AuthService(config.get('DEFAULT', 'AdminPassword'))

# Finally, add the missing function
async def get_current_admin(request: Request):
    """Verify admin is authenticated and return admin data"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = auth_service.validate_session(session_id)
    if not session or session["role"] != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
        
    return {"user_id": session["user_id"], "role": session["role"]}