# app/utils/logging_utils.py
import os
import datetime
from app.config import Config

config = Config()

def log_activity(activity_type, description):
    """Log an activity to the activity log file"""
    try:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"{timestamp} - {activity_type} - {description}\n"
        
        log_file = os.path.join(config.get('PATHS', 'LogsDir'), 'activity.log')
        
        # Create log directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Append to log file
        with open(log_file, 'a') as f:
            f.write(log_entry)
            
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error logging activity: {str(e)}")
        return False

def log_checkin(guest_id, name, role):
    """Log a check-in to the check-in log file"""
    try:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"{guest_id},{name},{role},{timestamp}\n"
        
        log_file = os.path.join(config.get('PATHS', 'LogsDir'), 'checkin.log')
        
        # Create log directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Append to log file
        with open(log_file, 'a') as f:
            f.write(log_entry)
            
        # Also log to activity log
        log_activity("Check-in", f"Guest {name} ({guest_id}) checked in")
        
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error logging check-in: {str(e)}")
        return False