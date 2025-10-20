import re
from typing import Dict, List, Optional
from datetime import datetime
import logging
from app.models.faculty import Faculty
from app.models.guest import Guest

logger = logging.getLogger(__name__)

class DataValidator:
    """Service for validating data before database operations"""
    
    def __init__(self):
        self.email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        self.phone_regex = re.compile(r'^\+?[0-9]{10,15}$')
        self.date_format = '%Y-%m-%d'
    
    def validate_faculty(self, faculty_data: Dict) -> List[str]:
        """Validate faculty data"""
        errors = []
        
        # Required fields
        required_fields = ['name', 'email', 'phone', 'department', 'designation']
        for field in required_fields:
            if not faculty_data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Email validation
        if faculty_data.get('email') and not self.email_regex.match(faculty_data['email']):
            errors.append("Invalid email format")
        
        # Phone validation
        if faculty_data.get('phone') and not self.phone_regex.match(faculty_data['phone']):
            errors.append("Invalid phone number format")
        
        # Role validation
        valid_roles = ['faculty', 'admin', 'reviewer']
        if faculty_data.get('role') and faculty_data['role'] not in valid_roles:
            errors.append(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        
        return errors
    
    def validate_guest(self, guest_data: Dict) -> List[str]:
        """Validate guest data"""
        errors = []
        
        # Required fields
        required_fields = ['name', 'email', 'phone', 'role', 'purpose']
        for field in required_fields:
            if not guest_data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Email validation
        if guest_data.get('email') and not self.email_regex.match(guest_data['email']):
            errors.append("Invalid email format")
        
        # Phone validation
        if guest_data.get('phone') and not self.phone_regex.match(guest_data['phone']):
            errors.append("Invalid phone number format")
        
        # Role validation
        valid_roles = ['student', 'faculty', 'industry', 'government', 'other']
        if guest_data.get('role') and guest_data['role'] not in valid_roles:
            errors.append(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        
        # Date validation
        if guest_data.get('visit_date'):
            try:
                datetime.strptime(guest_data['visit_date'], self.date_format)
            except ValueError:
                errors.append("Invalid visit date format. Use YYYY-MM-DD")
        
        return errors
    
    def validate_presentation(self, presentation_data: Dict) -> List[str]:
        """Validate presentation data"""
        errors = []
        
        # Required fields
        required_fields = ['title', 'faculty_id', 'file_path']
        for field in required_fields:
            if not presentation_data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # File type validation
        if presentation_data.get('file_path'):
            valid_extensions = ['.pdf', '.ppt', '.pptx']
            if not any(presentation_data['file_path'].lower().endswith(ext) for ext in valid_extensions):
                errors.append(f"Invalid file type. Must be one of: {', '.join(valid_extensions)}")
        
        return errors
    
    def validate_journey(self, journey_data: Dict) -> List[str]:
        """Validate journey details"""
        errors = []
        
        # Required fields
        required_fields = ['faculty_id', 'arrival_date', 'departure_date', 'transport_mode']
        for field in required_fields:
            if not journey_data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Date validation
        for date_field in ['arrival_date', 'departure_date']:
            if journey_data.get(date_field):
                try:
                    datetime.strptime(journey_data[date_field], self.date_format)
                except ValueError:
                    errors.append(f"Invalid {date_field} format. Use YYYY-MM-DD")
        
        # Date range validation
        if journey_data.get('arrival_date') and journey_data.get('departure_date'):
            try:
                arrival = datetime.strptime(journey_data['arrival_date'], self.date_format)
                departure = datetime.strptime(journey_data['departure_date'], self.date_format)
                if departure < arrival:
                    errors.append("Departure date must be after arrival date")
            except ValueError:
                pass  # Already caught in date validation
        
        # Transport mode validation
        valid_modes = ['flight', 'train', 'bus', 'car']
        if journey_data.get('transport_mode') and journey_data['transport_mode'] not in valid_modes:
            errors.append(f"Invalid transport mode. Must be one of: {', '.join(valid_modes)}")
        
        return errors
    
    def validate_bulk_data(self, data_list: List[Dict], data_type: str) -> Dict[str, List[str]]:
        """Validate a list of data entries"""
        validation_results = {}
        
        for i, data in enumerate(data_list):
            if data_type == 'faculty':
                errors = self.validate_faculty(data)
            elif data_type == 'guest':
                errors = self.validate_guest(data)
            elif data_type == 'presentation':
                errors = self.validate_presentation(data)
            elif data_type == 'journey':
                errors = self.validate_journey(data)
            else:
                errors = ["Invalid data type"]
            
            if errors:
                validation_results[f"Entry {i+1}"] = errors
        
        return validation_results 