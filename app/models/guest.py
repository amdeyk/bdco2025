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
        self.badge_given = "False"
        self.badge_printed_date = ""
        self.badge_given_date = ""
        self.kit_received_date = ""
        self.check_in_time = ""
        self.payment_status = "Pending"
        self.payment_amount = "0"
        self.payment_date = ""
        self.payment_method = ""
        self.organization = ""
        self.kmc_number = ""
        self.notes = ""
        # New fields
        self.journey_details_updated = "False"
        self.journey_completed = "False"
        self.food_coupons_day1 = "False"
        self.food_coupons_day2 = "False"
        self.gifts_given = "False"
        self.gift_given_date = ""
        self.food_coupons_day1_date = ""
        self.food_coupons_day2_date = ""
        self.gift_notes = ""
        self.food_notes = ""
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'Guest':
        """Create a guest instance from dictionary data"""
        instance = cls()
        
        # Map dictionary fields to object attributes
        for key, value in data.items():
            # Convert to standard object attribute names (camelCase to snake_case)
            attr_name = key[0].lower() + key[1:]
            
            # Special cases for fields that don't map directly
            if key == "ID":
                attr_name = "id"
            elif key == "KMCNumber":
                attr_name = "kmc_number"
            
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
            "BadgeGiven": self.badge_given,
            "BadgePrintedDate": self.badge_printed_date,
            "BadgeGivenDate": self.badge_given_date,
            "KitReceivedDate": self.kit_received_date,
            "CheckInTime": self.check_in_time,
            "PaymentStatus": self.payment_status,
            "PaymentAmount": self.payment_amount,
            "PaymentDate": self.payment_date,
            "PaymentMethod": self.payment_method,
            "Organization": self.organization,
            "KMCNumber": self.kmc_number,
            "Notes": self.notes,
            "JourneyDetailsUpdated": self.journey_details_updated,
            "JourneyCompleted": self.journey_completed,
            "FoodCouponsDay1": self.food_coupons_day1,
            "FoodCouponsDay2": self.food_coupons_day2,
            "FoodCouponsDay1Date": self.food_coupons_day1_date,
            "FoodCouponsDay2Date": self.food_coupons_day2_date,
            "GiftsGiven": self.gifts_given,
            "GiftGivenDate": self.gift_given_date,
            "GiftNotes": self.gift_notes,
            "FoodNotes": self.food_notes
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

        if self.kmc_number and not self.kmc_number.isdigit():
            errors.append("KMC number must be numeric")

        return errors
