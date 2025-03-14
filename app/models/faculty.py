# app/models/faculty.py
from typing import Dict, Optional, List
from datetime import datetime
import uuid

class Faculty:
    """Model for faculty records"""
    
    def __init__(self, guest_id: str = None):
        """
        Initialize a new faculty member
        
        Args:
            guest_id: ID of the associated guest record
        """
        self.id = str(uuid.uuid4())
        self.guest_id = guest_id
        self.is_active = True
        self.created_at = datetime.now().isoformat()
        self.last_login = None
        self.designation = ""
        self.institution = ""
        self.specialty = ""
        self.bio = ""
        self.presentation_topics = ""
        self.accommodation_required = False
        self.arrival_date = None
        self.departure_date = None
        self.travel_arranged = False
        
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
            "last_login": self.last_login,
            "designation": self.designation,
            "institution": self.institution,
            "specialty": self.specialty,
            "bio": self.bio,
            "presentation_topics": self.presentation_topics,
            "accommodation_required": str(self.accommodation_required),
            "arrival_date": self.arrival_date,
            "departure_date": self.departure_date,
            "travel_arranged": str(self.travel_arranged)
        }
        
    def validate(self) -> List[str]:
        """Validate faculty data"""
        errors = []
        
        if not self.guest_id:
            errors.append("Guest ID is required")
            
        if not self.designation:
            errors.append("Designation is required")
            
        if not self.institution:
            errors.append("Institution is required")
            
        if not self.specialty:
            errors.append("Specialty is required")
            
        if self.accommodation_required and (not self.arrival_date or not self.departure_date):
            errors.append("Arrival and departure dates are required when accommodation is needed")
            
        return errors