# app/models/faculty.py
from typing import Dict, Optional, List
from datetime import datetime
import uuid
from app.templates import templates
class Faculty:
    """Model for faculty records"""
    
    def __init__(self, guest_id: str = None):
        self.id = str(uuid.uuid4())
        self.guest_id = guest_id
        self.is_active = True
        self.created_at = datetime.now().isoformat()
        self.last_login = None
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'Faculty':
        """Create a faculty instance from dictionary data"""
        instance = cls()
        
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
                
        return instance
        
    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "guest_id": self.guest_id,
            "is_active": str(self.is_active),
            "created_at": self.created_at,
            "last_login": self.last_login
        }
        
    def validate(self) -> List[str]:
        """Validate faculty data"""
        errors = []
        
        if not self.guest_id:
            errors.append("Guest ID is required")
            
        return errors