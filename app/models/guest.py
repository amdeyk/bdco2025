# app/models/guest.py
from typing import Dict, Optional, List
from datetime import datetime
import uuid

class Guest:
    """Model for guest records"""
    
    def __init__(
        self, 
        name: str = "", 
        phone: str = "", 
        email: str = "", 
        guest_role: str = "Delegate"
    ):
        """
        Initialize a new guest
        
        Args:
            name: Guest's full name
            phone: Contact phone number
            email: Email address
            guest_role: Role at the conference (Delegate, Faculty, Staff, etc.)
        """
        self.id = str(uuid.uuid4())[:8].upper()  # Short ID for convenience
        self.name = name
        self.phone = phone
        self.email = email
        self.guest_role = guest_role
        self.registration_date = datetime.now().isoformat()
        self.daily_attendance = "False"
        self.is_active = True
        self.kit_received = "False"
        self.badge_printed = "False"
        self.payment_status = "Pending"
        self.payment_amount = "0"
        self.organization = ""
        self.notes = ""
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'Guest':
        """Create a guest instance from dictionary data"""
        instance = cls()
        
        # Map dictionary fields to object attributes
        for key, value in data.items():
            # Convert to standard object attribute names (camelCase to snake_case)
            attr_name = key[0].lower() + key[1:]
            
            # Special case for ID
            if key == "ID":
                attr_name = "id"
            
            # Check if attribute exists and set value
            if hasattr(instance, attr_name):
                setattr(instance, attr_name, value)
                
        return instance
        
    def to_dict(self) -> Dict:
        """Convert to dictionary representation (for CSV storage)"""
        return {
            "ID": self.id,
            "Name": self.name,
            "Phone": self.phone,
            "Email": self.email,
            "GuestRole": self.guest_role,
            "RegistrationDate": self.registration_date,
            "DailyAttendance": self.daily_attendance,
            "IsActive": str(self.is_active),
            "KitReceived": self.kit_received,
            "BadgePrinted": self.badge_printed,
            "PaymentStatus": self.payment_status,
            "PaymentAmount": self.payment_amount,
            "Organization": self.organization,
            "Notes": self.notes
        }
        
    def validate(self) -> List[str]:
        """Validate guest data and return list of errors"""
        errors = []
        
        if not self.name or len(self.name) < 3:
            errors.append("Name is required and must be at least 3 characters")
            
        if not self.phone or not self.phone.isdigit() or len(self.phone) != 10:
            errors.append("Phone number must be exactly 10 digits")
            
        if self.email and "@" not in self.email:
            errors.append("Invalid email format")
            
        if self.guest_role not in ["Delegate", "Faculty", "Staff", "Sponsor", "Guest"]:
            errors.append("Invalid guest role")
            
        return errors