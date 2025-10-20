# app/utils/validators.py
import re
from typing import Dict, List, Any, Optional, Tuple

def validate_email(email: str) -> bool:
    """
    Validate email format
    
    Args:
        email: Email to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
        
    # Simple regex for email validation
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """
    Validate phone number (10 digits)
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not phone:
        return False
        
    # Remove any non-digit characters
    phone_digits = re.sub(r'\D', '', phone)
    
    # Check if it's exactly 10 digits
    return len(phone_digits) == 10

def validate_date(date_str: str) -> bool:
    """
    Validate date format (YYYY-MM-DD)
    
    Args:
        date_str: Date string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not date_str:
        return False
        
    # Check basic format
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, date_str):
        return False
        
    # Check valid date values
    try:
        year, month, day = map(int, date_str.split('-'))
        
        # Basic validation
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return False
            
        # Specific month length validation
        if month in [4, 6, 9, 11] and day > 30:
            return False
            
        # February validation
        if month == 2:
            # Leap year check
            is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
            if day > 29 or (not is_leap and day > 28):
                return False
                
        return True
    except ValueError:
        return False

def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> List[str]:
    """
    Validate that required fields are present and not empty
    
    Args:
        data: Dictionary of data to validate
        required_fields: List of required field names
        
    Returns:
        List of missing field names
    """
    missing = []
    
    for field in required_fields:
        value = data.get(field, '')
        if not value and value != 0:  # Allow 0 as a valid value
            missing.append(field)
            
    return missing

def validate_min_length(text: str, min_length: int) -> bool:
    """
    Validate minimum text length
    
    Args:
        text: Text to validate
        min_length: Minimum allowed length
        
    Returns:
        True if valid, False otherwise
    """
    return len(text) >= min_length

def validate_max_length(text: str, max_length: int) -> bool:
    """
    Validate maximum text length
    
    Args:
        text: Text to validate
        max_length: Maximum allowed length
        
    Returns:
        True if valid, False otherwise
    """
    return len(text) <= max_length

def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
    """
    Validate file extension
    
    Args:
        filename: Filename to validate
        allowed_extensions: List of allowed extensions (without dot)
        
    Returns:
        True if valid, False otherwise
    """
    if not filename or '.' not in filename:
        return False
        
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in allowed_extensions

def validate_numeric(value: str) -> bool:
    """
    Validate numeric value (integer or float)
    
    Args:
        value: Value to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not value:
        return False
        
    # Allow floating point numbers with decimal point
    try:
        float(value)
        return True
    except ValueError:
        return False

def validate_integer(value: str) -> bool:
    """
    Validate integer value
    
    Args:
        value: Value to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not value:
        return False
        
    # Check if it's an integer
    try:
        int(value)
        return True
    except ValueError:
        return False

def validate_positive(value: str) -> bool:
    """
    Validate positive numeric value
    
    Args:
        value: Value to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not validate_numeric(value):
        return False
        
    return float(value) > 0