# app/models/faculty.py
from typing import Dict, Optional, List
from datetime import datetime
import uuid
from pydantic import BaseModel, EmailStr, Field
from enum import Enum

class FacultyRole(str, Enum):
    REVIEWER = "reviewer"
    LECTURER = "lecturer"
    MODERATOR = "moderator"

class JourneyDetails(BaseModel):
    """Model for faculty journey details"""
    arrival_date: datetime
    departure_date: datetime
    origin_city: str
    destination_city: str
    remarks: Optional[str] = None

class Presentation(BaseModel):
    """Model for faculty presentations"""
    title: str
    description: Optional[str] = None
    file_path: str
    file_type: str  # pdf, ppt, video
    upload_date: datetime = Field(default_factory=datetime.now)
    session_type: str  # keynote, technical, workshop, etc.

class FacultyProfile(BaseModel):
    """Model for faculty profile"""
    id: str
    name: str
    email: EmailStr
    phone: str
    kmc_number: Optional[str] = None
    photo_path: Optional[str] = None
    roles: List[FacultyRole]
    kit_faculty: bool = False
    special_kit_faculty: bool = False
    lunch_day1: bool = False
    dinner_day1: bool = False
    lunch_day2: bool = False
    dinner_preconf: bool = False
    journey_details: Optional[JourneyDetails] = None
    presentations: List[Presentation] = []
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True

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