# app/utils/changelog.py
import os
import json
from datetime import datetime
from app.config import Config

config = Config()

class ChangelogManager:
    """Manages system changelog"""
    
    def __init__(self):
        self.log_dir = config.get('PATHS', 'LogsDir')
        self.changelog_file = os.path.join(self.log_dir, 'changelog.json')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create changelog file if it doesn't exist
        if not os.path.exists(self.changelog_file):
            with open(self.changelog_file, 'w') as f:
                json.dump([], f)
    
    def add_entry(self, title, description, author="admin", changes=None):
        """Add a new changelog entry"""
        if changes is None:
            changes = []
            
        entry = {
            "timestamp": datetime.now().isoformat(),
            "title": title,
            "description": description,
            "author": author,
            "changes": changes
        }
        
        # Read existing entries
        try:
            with open(self.changelog_file, 'r') as f:
                entries = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            entries = []
        
        # Add new entry and write back
        entries.append(entry)
        with open(self.changelog_file, 'w') as f:
            json.dump(entries, f, indent=2)
            
        return entry
    
    def get_entries(self, limit=None):
        """Get changelog entries, optionally limited"""
        try:
            with open(self.changelog_file, 'r') as f:
                entries = json.load(f)
                
            # Sort by timestamp (newest first)
            entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            if limit:
                return entries[:limit]
            return entries
        except (json.JSONDecodeError, FileNotFoundError):
            return []