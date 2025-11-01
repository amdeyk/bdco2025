# Example of improved CSV database module (csv_db.py)
import csv
import os
import threading
import time
import shutil
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CSVDatabase:
    """Thread-safe CSV database operations with automatic backups"""
    
    def __init__(self, file_path, backup_dir):
        self.file_path = file_path
        self.backup_dir = backup_dir
        self.lock = threading.Lock()
        self.lock_file = f"{self.file_path}.lock"
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        os.makedirs(backup_dir, exist_ok=True)

    def _acquire_file_lock(self, timeout=3.0, poll=0.02):
        """Cross-process lock using a lock file. Returns True if acquired."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                # O_CREAT|O_EXCL ensures atomic creation; fails if exists
                fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                with os.fdopen(fd, 'w') as f:
                    f.write(f"locked {datetime.now().isoformat()}\n")
                return True
            except FileExistsError:
                time.sleep(poll)
            except Exception as e:
                logger.warning(f"Lock acquire unexpected error: {e}")
                time.sleep(poll)
        return False

    def _release_file_lock(self):
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception:
            pass
    
    def read_all(self):
        """Read all records from CSV file with proper error handling"""
        try:
            # If a writer holds lock, wait briefly to avoid partial reads
            start = time.time()
            while os.path.exists(self.lock_file) and (time.time() - start) < 1.0:
                time.sleep(0.02)
            with self.lock:
                if not os.path.exists(self.file_path):
                    return []
                with open(self.file_path, mode='r', newline='', encoding='utf-8-sig') as file:
                    reader = csv.DictReader(file)
                    return list(reader)
        except Exception as e:
            logger.error(f"Error reading from CSV: {str(e)}")
            raise
    
    def write_all(self, data, fieldnames=None):
        """Write all records to CSV file with backup creation"""
        try:
            # Try to acquire cross-process lock
            if not self._acquire_file_lock(timeout=3.0, poll=0.02):
                logger.warning("CSV lock busy: write_all timed out")
                raise TimeoutError("Database is busy. Please try again.")

            # Create backup first
            self.create_backup()
            with self.lock:
                if not fieldnames and data:
                    fieldnames = list(data[0].keys())
                temp_file = f"{self.file_path}.tmp"
                with open(temp_file, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
                os.replace(temp_file, self.file_path)
            return True
        except Exception as e:
            logger.error(f"Error writing to CSV: {str(e)}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise
        finally:
            self._release_file_lock()
    
    def create_backup(self, custom_name=None):
        """Create a timestamped backup of the CSV file"""
        try:
            if not os.path.exists(self.file_path):
                return None
                
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_name = custom_name or f"backup_{timestamp}.csv"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            with self.lock:
                shutil.copy2(self.file_path, backup_path)
                
            logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            raise
