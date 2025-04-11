import csv
import os
import threading
import shutil
import fcntl
import time
from datetime import datetime
import logging
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class CSVDatabaseError(Exception):
    """Base exception for CSV database errors"""
    pass

class CSVLockError(CSVDatabaseError):
    """Exception raised when lock cannot be acquired"""
    pass

class CSVTransaction:
    def __init__(self, db, isolation_level="READ_COMMITTED"):
        self.db = db
        self.isolation_level = isolation_level
        self.changes: List[Dict[str, Any]] = []
        self.is_active = False
        
    def begin(self):
        """Begin a transaction"""
        if self.is_active:
            raise CSVDatabaseError("Transaction already active")
        self.is_active = True
        self.changes = []
        
    def commit(self):
        """Commit all changes in the transaction"""
        if not self.is_active:
            raise CSVDatabaseError("No active transaction")
        try:
            # Apply all changes
            for change in self.changes:
                if change["type"] == "write":
                    self.db._write_all(change["data"], change["fieldnames"])
                elif change["type"] == "append":
                    self.db._append_records(change["records"])
            self.is_active = False
            self.changes = []
        except Exception as e:
            self.rollback()
            raise CSVDatabaseError(f"Failed to commit transaction: {str(e)}")
            
    def rollback(self):
        """Rollback all changes in the transaction"""
        self.is_active = False
        self.changes = []

class EnhancedCSVDatabase:
    """Thread-safe CSV database with file locking and transaction support"""
    
    def __init__(self, file_path: str, backup_dir: str, max_retries: int = 5, retry_delay: float = 0.1):
        self.file_path = file_path
        self.backup_dir = backup_dir
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.thread_lock = threading.Lock()
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create file if it doesn't exist
        if not os.path.exists(file_path):
            self._create_empty_file()
    
    def _create_empty_file(self):
        """Create an empty CSV file with default headers"""
        default_headers = [
            "id", "role", "name", "email", "phone", "company",
            "kit_type", "special_kit", "lunch_day1", "dinner_day1",
            "lunch_day2", "dinner_preconf", "arrival_date", "departure_date",
            "stay_arrangements", "paper_submission", "presentation_title",
            "moderator", "daily_attendance", "created_at", "updated_at"
        ]
        with open(self.file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(default_headers)
    
    @contextmanager
    def _file_lock(self, mode='r'):
        """Context manager for file locking using fcntl"""
        file = None
        for attempt in range(self.max_retries):
            try:
                file = open(self.file_path, mode, newline='', encoding='utf-8')
                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (IOError, OSError) as e:
                if file:
                    file.close()
                if attempt == self.max_retries - 1:
                    raise CSVLockError(f"Could not acquire lock after {self.max_retries} attempts")
                time.sleep(self.retry_delay)
        
        try:
            yield file
        finally:
            if file:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)
                file.close()
    
    def read_all(self) -> List[Dict[str, str]]:
        """Read all records with proper locking"""
        with self._file_lock('r') as file:
            reader = csv.DictReader(file)
            return list(reader)
    
    def write_all(self, data: List[Dict[str, str]], fieldnames: Optional[List[str]] = None):
        """Write all records with proper locking and backup"""
        self.create_backup()  # Create backup before writing
        
        if not fieldnames and data:
            fieldnames = list(data[0].keys())
        
        with self._file_lock('w') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    
    def append_records(self, records: List[Dict[str, str]]):
        """Append records to the CSV file"""
        existing_data = self.read_all()
        if not existing_data and not records:
            return
        
        fieldnames = list(records[0].keys()) if records else list(existing_data[0].keys())
        all_data = existing_data + records
        self.write_all(all_data, fieldnames)
    
    def create_backup(self, custom_name: Optional[str] = None) -> str:
        """Create a timestamped backup"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_name = custom_name or f"backup_{timestamp}.csv"
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        with self.thread_lock:
            shutil.copy2(self.file_path, backup_path)
        
        # Keep only last 10 backups
        self._cleanup_old_backups()
        
        return backup_path
    
    def _cleanup_old_backups(self, keep_last: int = 10):
        """Keep only the specified number of most recent backups"""
        backups = sorted([
            os.path.join(self.backup_dir, f)
            for f in os.listdir(self.backup_dir)
            if f.endswith('.csv')
        ], key=os.path.getmtime)
        
        for backup in backups[:-keep_last]:
            try:
                os.remove(backup)
            except OSError as e:
                logger.warning(f"Failed to remove old backup {backup}: {str(e)}")
    
    def begin_transaction(self, isolation_level="READ_COMMITTED") -> CSVTransaction:
        """Begin a new transaction"""
        return CSVTransaction(self, isolation_level) 