# app/utils/logging_utils.py
import os
import datetime
from app.config import Config
import logging

config = Config()

logger = logging.getLogger(__name__)

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

def get_recent_activity(limit: int = 50):
    """Get recent activity entries"""
    try:
        log_file = os.path.join(config.get('PATHS', 'LogsDir'), 'activity.log')
        
        if not os.path.exists(log_file):
            return []
            
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Return last 'limit' entries
        recent_lines = lines[-limit:] if len(lines) > limit else lines
        
        activities = []
        for line in recent_lines:
            line = line.strip()
            if line:
                parts = line.split(' - ', 3)
                if len(parts) >= 3:
                    activities.append({
                        'timestamp': parts[0],
                        'action': parts[1],
                        'entity_id': parts[2],
                        'details': parts[3] if len(parts) > 3 else ''
                    })
                    
        return list(reversed(activities))  # Most recent first
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        return []