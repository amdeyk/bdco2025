import time
from typing import Dict, Optional
from datetime import datetime, timedelta
import threading
from app.config import Config

config = Config()

class RateLimiter:
    """Rate limiter for API endpoints"""
    
    def __init__(self):
        self.rate_limit = config.getint('SECURITY', 'RateLimit', fallback=100)  # requests per minute
        self.window_size = 60  # seconds
        self.requests: Dict[str, list] = {}
        self.lock = threading.Lock()
    
    def is_allowed(self, user_id: str) -> bool:
        """Check if a user is allowed to make a request"""
        with self.lock:
            now = time.time()
            
            # Clean up old requests
            if user_id in self.requests:
                self.requests[user_id] = [
                    t for t in self.requests[user_id]
                    if now - t < self.window_size
                ]
            
            # Add new request
            if user_id not in self.requests:
                self.requests[user_id] = []
            
            # Check rate limit
            if len(self.requests[user_id]) >= self.rate_limit:
                return False
            
            self.requests[user_id].append(now)
            return True
    
    def get_remaining_requests(self, user_id: str) -> int:
        """Get number of remaining requests for a user"""
        with self.lock:
            now = time.time()
            
            if user_id not in self.requests:
                return self.rate_limit
            
            # Clean up old requests
            self.requests[user_id] = [
                t for t in self.requests[user_id]
                if now - t < self.window_size
            ]
            
            return self.rate_limit - len(self.requests[user_id])
    
    def reset(self, user_id: Optional[str] = None):
        """Reset rate limit for a user or all users"""
        with self.lock:
            if user_id:
                if user_id in self.requests:
                    del self.requests[user_id]
            else:
                self.requests.clear() 