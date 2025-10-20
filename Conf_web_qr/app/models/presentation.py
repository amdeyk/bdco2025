# app/models/presentation.py
from typing import Dict, Optional, List
from datetime import datetime
import uuid

class Presentation:
    """Model for faculty presentations"""
    
    def __init__(
        self, 
        guest_id: str = "", 
        title: str = "", 
        description: str = "", 
        file_path: str = ""
    ):
        """
        Initialize a new presentation
        
        Args:
            guest_id: ID of the faculty/guest who submitted the presentation
            title: Title of the presentation
            description: Brief description of the content
            file_path: Path to the uploaded file
        """
        self.id = str(uuid.uuid4())
        self.guest_id = guest_id
        self.title = title
        self.description = description
        self.file_path = file_path
        self.file_type = self._determine_file_type()
        self.upload_date = datetime.now().isoformat()
        self.scheduled_date = None
        self.scheduled_time = None
        self.scheduled_venue = None
        self.duration_minutes = 30
        self.status = "Submitted"  # Submitted, Approved, Rejected, Scheduled
        self.review_comments = ""
        
    def _determine_file_type(self) -> str:
        """Determine the file type from the file path extension"""
        if not self.file_path:
            return "unknown"
            
        ext = self.file_path.lower().split('.')[-1]
        
        if ext in ["pdf"]:
            return "pdf"
        elif ext in ["ppt", "pptx"]:
            return "ppt"
        elif ext in ["doc", "docx"]:
            return "doc"
        elif ext in ["mp4", "avi", "mov", "webm"]:
            return "video"
        else:
            return "other"
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Presentation':
        """Create a presentation instance from dictionary data"""
        instance = cls()
        
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
                
        return instance
        
    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "guest_id": self.guest_id,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "upload_date": self.upload_date,
            "scheduled_date": self.scheduled_date,
            "scheduled_time": self.scheduled_time,
            "scheduled_venue": self.scheduled_venue,
            "duration_minutes": str(self.duration_minutes),
            "status": self.status,
            "review_comments": self.review_comments
        }
        
    def validate(self) -> List[str]:
        """Validate presentation data"""
        errors = []
        
        if not self.guest_id:
            errors.append("Guest ID is required")
            
        if not self.title:
            errors.append("Title is required")
            
        if not self.file_path:
            errors.append("Presentation file is required")
            
        return errors