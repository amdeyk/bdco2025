# app/services/validator.py
import re
from typing import Dict, List, Tuple, Union, Any
import logging

logger = logging.getLogger(__name__)

class Validator:
    """Form validation service"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email format
        
        Args:
            email: Email address to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not email:
            return False
            
        pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return bool(re.match(pattern, email))
        
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """
        Validate phone number format (10 digits)
        
        Args:
            phone: Phone number to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not phone:
            return False
            
        # Remove spaces, dashes, etc.
        clean_phone = re.sub(r'\D', '', phone)
        
        # Check if it's a 10-digit number
        return len(clean_phone) == 10 and clean_phone.isdigit()
        
    @staticmethod
    def validate_required(value: Any, field_name: str) -> Tuple[bool, str]:
        """
        Validate required field
        
        Args:
            value: Field value
            field_name: Name of the field for error message
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return False, f"{field_name} is required"
        return True, ""
        
    @staticmethod
    def validate_min_length(value: str, min_length: int, field_name: str) -> Tuple[bool, str]:
        """
        Validate minimum length
        
        Args:
            value: Field value
            min_length: Minimum required length
            field_name: Name of the field for error message
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or len(value) < min_length:
            return False, f"{field_name} must be at least {min_length} characters"
        return True, ""
        
    @staticmethod
    def validate_max_length(value: str, max_length: int, field_name: str) -> Tuple[bool, str]:
        """
        Validate maximum length
        
        Args:
            value: Field value
            max_length: Maximum allowed length
            field_name: Name of the field for error message
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value and len(value) > max_length:
            return False, f"{field_name} must be at most {max_length} characters"
        return True, ""
        
    @staticmethod
    def validate_numeric(value: str, field_name: str) -> Tuple[bool, str]:
        """
        Validate numeric value
        
        Args:
            value: Field value
            field_name: Name of the field for error message
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return True, ""  # Empty is valid (unless required is checked separately)
            
        if not value.replace('.', '', 1).isdigit():
            return False, f"{field_name} must be a number"
        return True, ""
        
    @staticmethod
    def validate_date_format(value: str, field_name: str) -> Tuple[bool, str]:
        """
        Validate date format (YYYY-MM-DD)
        
        Args:
            value: Field value
            field_name: Name of the field for error message
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return True, ""  # Empty is valid (unless required is checked separately)
            
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(pattern, value):
            return False, f"{field_name} must be in YYYY-MM-DD format"
        
        # Check valid month and day
        try:
            year, month, day = map(int, value.split('-'))
            if not (1 <= month <= 12 and 1 <= day <= 31):
                return False, f"{field_name} contains invalid month or day"
        except ValueError:
            return False, f"{field_name} contains invalid values"
            
        return True, ""
        
    @staticmethod
    def validate_allowed_values(value: str, allowed_values: List[str], field_name: str) -> Tuple[bool, str]:
        """
        Validate value is in allowed list
        
        Args:
            value: Field value
            allowed_values: List of allowed values
            field_name: Name of the field for error message
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return True, ""  # Empty is valid (unless required is checked separately)
            
        if value not in allowed_values:
            return False, f"{field_name} must be one of: {', '.join(allowed_values)}"
        return True, ""
        
    @staticmethod
    def validate_form(form_data: Dict[str, Any], validators: Dict[str, List[callable]]) -> Dict[str, List[str]]:
        """
        Validate multiple form fields
        
        Args:
            form_data: Dictionary of form field values
            validators: Dictionary mapping field names to lists of validator functions
            
        Returns:
            Dictionary of field names to lists of error messages
        """
        errors = {}
        
        for field_name, field_validators in validators.items():
            field_errors = []
            field_value = form_data.get(field_name, "")
            
            for validator in field_validators:
                is_valid, error_message = validator(field_value)
                if not is_valid:
                    field_errors.append(error_message)
                    
            if field_errors:
                errors[field_name] = field_errors
                
        return errors