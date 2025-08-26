# app/models/journey.py
from typing import Dict, Optional, List
from datetime import datetime
import uuid

class Journey:
    """Model for guest travel journey details"""
    
    def __init__(self, guest_id: str = ""):
        """
        Initialize journey details for a guest
        
        Args:
            guest_id: ID of the guest
        """
        self.guest_id = guest_id
        self.inward_date = None
        self.inward_origin = ""
        self.inward_destination = ""  # Usually the conference venue city
        self.inward_transport_mode = ""  # Flight, Train, Bus, Car, etc.
        self.inward_transport_details = ""  # Flight number, train number, etc.
        self.inward_remarks = ""
        
        self.outward_date = None
        self.outward_origin = ""  # Usually the conference venue city
        self.outward_destination = ""
        self.outward_transport_mode = ""
        self.outward_transport_details = ""
        self.outward_remarks = ""
        
        self.pickup_required = False
        self.pickup_location = ""
        self.pickup_confirmed = False
        
        self.drop_required = False
        self.drop_location = ""
        self.drop_confirmed = False

        # Ground transport details
        self.day1_pickup_location = ""
        self.day1_pickup_time = ""
        self.day1_drop_location = ""
        self.day1_drop_time = ""
        self.day2_pickup_location = ""
        self.day2_pickup_time = ""
        self.day2_drop_location = ""
        self.day2_drop_time = ""

        self.updated_at = datetime.now().isoformat()
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'Journey':
        """Create a journey instance from dictionary data"""
        instance = cls()
        
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
                
        return instance
        
    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "guest_id": self.guest_id,
            "inward_date": self.inward_date,
            "inward_origin": self.inward_origin,
            "inward_destination": self.inward_destination,
            "inward_transport_mode": self.inward_transport_mode,
            "inward_transport_details": self.inward_transport_details,
            "inward_remarks": self.inward_remarks,
            
            "outward_date": self.outward_date,
            "outward_origin": self.outward_origin,
            "outward_destination": self.outward_destination,
            "outward_transport_mode": self.outward_transport_mode,
            "outward_transport_details": self.outward_transport_details,
            "outward_remarks": self.outward_remarks,
            
            "pickup_required": str(self.pickup_required),
            "pickup_location": self.pickup_location,
            "pickup_confirmed": str(self.pickup_confirmed),
            
            "drop_required": str(self.drop_required),
            "drop_location": self.drop_location,
            "drop_confirmed": str(self.drop_confirmed),
            "day1_pickup_location": self.day1_pickup_location,
            "day1_pickup_time": self.day1_pickup_time,
            "day1_drop_location": self.day1_drop_location,
            "day1_drop_time": self.day1_drop_time,
            "day2_pickup_location": self.day2_pickup_location,
            "day2_pickup_time": self.day2_pickup_time,
            "day2_drop_location": self.day2_drop_location,
            "day2_drop_time": self.day2_drop_time,

            "updated_at": self.updated_at
        }
        
    def validate(self) -> List[str]:
        """Validate journey data"""
        errors = []
        
        if not self.guest_id:
            errors.append("Guest ID is required")
            
        if self.pickup_required and not self.pickup_location:
            errors.append("Pickup location is required when pickup is requested")
            
        if self.drop_required and not self.drop_location:
            errors.append("Drop location is required when drop is requested")
            
        # If inward journey details are provided, ensure they are complete
        if any([self.inward_date, self.inward_origin, self.inward_destination]) and not all([self.inward_date, self.inward_origin, self.inward_destination]):
            errors.append("Complete inward journey details are required")
            
        # If outward journey details are provided, ensure they are complete
        if any([self.outward_date, self.outward_origin, self.outward_destination]) and not all([self.outward_date, self.outward_origin, self.outward_destination]):
            errors.append("Complete outward journey details are required")
            
        return errors