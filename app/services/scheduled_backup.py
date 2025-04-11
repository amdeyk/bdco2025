import schedule
import time
import threading
import logging
from datetime import datetime
from app.config import Config
from app.services.enhanced_csv_db import EnhancedCSVDatabase
import os

logger = logging.getLogger(__name__)

class ScheduledBackup:
    """Service for scheduled database backups"""
    
    def __init__(self):
        self.config = Config()
        self.db = EnhancedCSVDatabase(
            self.config.get('DATABASE', 'CSVPath'),
            self.config.get('DATABASE', 'BackupDir')
        )
        self.backup_interval = self.config.getint('BACKUP', 'IntervalMinutes', fallback=60)
        self.keep_backups = self.config.getint('BACKUP', 'KeepBackups', fallback=10)
        self.is_running = False
        self.thread = None
    
    def start(self):
        """Start the backup scheduler"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Schedule backup job
        schedule.every(self.backup_interval).minutes.do(self._create_backup)
        
        # Start scheduler in a separate thread
        self.thread = threading.Thread(target=self._run_scheduler)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info(f"Started scheduled backups every {self.backup_interval} minutes")
    
    def stop(self):
        """Stop the backup scheduler"""
        self.is_running = False
        if self.thread:
            self.thread.join()
        logger.info("Stopped scheduled backups")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)
    
    def _create_backup(self):
        """Create a backup of the database"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}.csv"
            
            # Create backup
            backup_path = self.db.create_backup(backup_name)
            
            # Clean up old backups
            self._cleanup_old_backups()
            
            logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
    
    def _cleanup_old_backups(self):
        """Clean up old backups"""
        try:
            backup_dir = self.config.get('DATABASE', 'BackupDir')
            backups = sorted([
                f for f in os.listdir(backup_dir)
                if f.startswith('backup_') and f.endswith('.csv')
            ])
            
            # Remove old backups
            for backup in backups[:-self.keep_backups]:
                os.remove(os.path.join(backup_dir, backup))
                logger.info(f"Removed old backup: {backup}")
        except Exception as e:
            logger.error(f"Failed to clean up old backups: {str(e)}")
    
    def get_backup_status(self) -> dict:
        """Get backup status information"""
        try:
            backup_dir = self.config.get('DATABASE', 'BackupDir')
            backups = sorted([
                f for f in os.listdir(backup_dir)
                if f.startswith('backup_') and f.endswith('.csv')
            ])
            
            return {
                "is_running": self.is_running,
                "backup_interval": self.backup_interval,
                "keep_backups": self.keep_backups,
                "total_backups": len(backups),
                "last_backup": backups[-1] if backups else None,
                "next_backup": schedule.next_run().isoformat() if self.is_running else None
            }
        except Exception as e:
            logger.error(f"Failed to get backup status: {str(e)}")
            return {
                "is_running": self.is_running,
                "error": str(e)
            } 