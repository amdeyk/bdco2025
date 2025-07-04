# app/utils/helpers.py
import os
import random
import string
import datetime
import re
from typing import Dict, List, Any, Optional
import unicodedata
import logging

logger = logging.getLogger(__name__)

def generate_random_id(length: int = 8) -> str:
    """
    Generate a random alphanumeric ID
    
    Args:
        length: Length of the ID
        
    Returns:
        Random ID string
    """
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_unique_id(existing_ids: List[str], length: int = 4) -> str:
    """Generate a unique alphanumeric ID not present in existing_ids."""
    if existing_ids is None:
        existing_ids = []

    attempt = generate_random_id(length)
    while attempt in existing_ids:
        attempt = generate_random_id(length)
    return attempt

def slugify(value: str) -> str:
    """
    Convert a string to a slug - lowercase, with spaces and special chars replaced by hyphens
    
    Args:
        value: String to slugify
        
    Returns:
        Slugified string
    """
    # Normalize unicode characters
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    # Convert to lowercase and remove leading/trailing whitespace
    value = value.lower().strip()
    # Replace spaces and other chars with hyphens
    value = re.sub(r'[^\w\s-]', '', value)
    value = re.sub(r'[\s_-]+', '-', value)
    return value

def format_date(date_string: str) -> str:
    """
    Format a date string (YYYY-MM-DD) to a more readable format (Month Day, Year)
    
    Args:
        date_string: Date string in YYYY-MM-DD format
        
    Returns:
        Formatted date string
    """
    if not date_string:
        return ""
        
    try:
        date_obj = datetime.datetime.strptime(date_string, "%Y-%m-%d")
        return date_obj.strftime("%B %d, %Y")
    except ValueError:
        return date_string

def ensure_dir_exists(directory: str) -> None:
    """
    Ensure a directory exists, creating it if necessary
    
    Args:
        directory: Directory path to check/create
    """
    os.makedirs(directory, exist_ok=True)

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing special characters
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Keep only alphanumeric chars, spaces, hyphens, underscores, and periods
    sanitized = re.sub(r'[^\w\s.-]', '', filename)
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    return sanitized

def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to a maximum length, adding ellipsis if needed
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
        
    return text[:max_length-3] + '...'

def parse_boolean(value: Any) -> bool:
    """
    Parse various string representations of boolean values
    
    Args:
        value: Value to parse
        
    Returns:
        Boolean interpretation of the value
    """
    if isinstance(value, bool):
        return value
        
    if isinstance(value, str):
        value = value.lower().strip()
        return value in ('true', 'yes', 'y', '1', 'on')
        
    if isinstance(value, (int, float)):
        return bool(value)
        
    return False