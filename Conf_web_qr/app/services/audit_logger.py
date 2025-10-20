import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
import os
from app.config import Config

config = Config()

class AuditLogger:
    """Service for logging database operations and security events"""
    
    def __init__(self):
        self.log_dir = config.get('PATHS', 'LogsDir')
        self.audit_log_file = os.path.join(self.log_dir, 'audit.log')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Configure audit logger
        self.logger = logging.getLogger('audit')
        self.logger.setLevel(logging.INFO)
        
        # Create file handler
        fh = logging.FileHandler(self.audit_log_file)
        fh.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(fh)
    
    def log_operation(self, 
                     operation: str,
                     user_id: str,
                     details: Dict[str, Any],
                     status: str = "success",
                     error: Optional[str] = None):
        """Log a database operation"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "user_id": user_id,
            "details": details,
            "status": status,
            "error": error
        }
        
        self.logger.info(json.dumps(log_entry))
    
    def log_security_event(self,
                          event_type: str,
                          user_id: str,
                          details: Dict[str, Any],
                          severity: str = "info"):
        """Log a security-related event"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "details": details,
            "severity": severity
        }
        
        self.logger.info(json.dumps(log_entry))
    
    def get_recent_logs(self, limit: int = 100) -> list:
        """Get recent audit logs"""
        logs = []
        try:
            with open(self.audit_log_file, 'r') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            return []
        
        return logs[-limit:] 