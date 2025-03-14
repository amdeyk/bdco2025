# app/services/backup.py
from datetime import datetime
import os
import shutil
import logging
import glob
from typing import List, Optional

logger = logging.getLogger(__name__)

class BackupManager:
    """Handles automatic backups and recovery of data files"""
    
    def __init__(self, backup_dir: str, max_backups: int = 10):
        """
        Initialize backup manager
        
        Args:
            backup_dir: Directory to store backups
            max_backups: Maximum number of backups to keep per file
        """
        self.backup_dir = backup_dir
        self.max_backups = max_backups
        
        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self, file_path: str, custom_name: Optional[str] = None) -> str:
        """
        Create a timestamped backup of a file
        
        Args:
            file_path: Path to the file to backup
            custom_name: Optional custom name for the backup
            
        Returns:
            Path to the created backup file
            
        Raises:
            FileNotFoundError: If the source file doesn't exist
            Exception: For other errors
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Source file not found: {file_path}")
            
            # Generate backup filename
            filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            
            if custom_name:
                backup_name = custom_name
            else:
                name, ext = os.path.splitext(filename)
                backup_name = f"{name}_backup_{timestamp}{ext}"
            
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # Create backup
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            
            # Clean up old backups
            self._cleanup_old_backups(filename)
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            raise
    
    def _cleanup_old_backups(self, filename: str) -> None:
        """
        Remove old backups exceeding the maximum limit
        
        Args:
            filename: Base filename to match backups
        """
        try:
            name, ext = os.path.splitext(filename)
            pattern = os.path.join(self.backup_dir, f"{name}_backup_*{ext}")
            
            # Get all matching backups
            backups = sorted(
                glob.glob(pattern),
                key=os.path.getmtime
            )
            
            # Remove oldest backups if exceeding limit
            if len(backups) > self.max_backups:
                for old_backup in backups[:-self.max_backups]:
                    os.remove(old_backup)
                    logger.info(f"Removed old backup: {old_backup}")
                    
        except Exception as e:
            logger.warning(f"Error cleaning up old backups: {str(e)}")
    
    def list_backups(self, filename: str) -> List[str]:
        """
        List all backups for a specific file
        
        Args:
            filename: Base filename to match backups
            
        Returns:
            List of backup file paths
        """
        try:
            name, ext = os.path.splitext(filename)
            pattern = os.path.join(self.backup_dir, f"{name}_backup_*{ext}")
            
            # Get all matching backups sorted by modification time
            backups = sorted(
                glob.glob(pattern),
                key=os.path.getmtime,
                reverse=True
            )
            
            return backups
            
        except Exception as e:
            logger.error(f"Error listing backups: {str(e)}")
            return []
    
    def restore_backup(self, backup_path: str, target_path: str) -> bool:
        """
        Restore a file from backup
        
        Args:
            backup_path: Path to the backup file
            target_path: Path where to restore the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            # Create backup of current file if it exists
            if os.path.exists(target_path):
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                pre_restore_backup = os.path.join(
                    self.backup_dir,
                    f"pre_restore_{timestamp}_{os.path.basename(target_path)}"
                )
                shutil.copy2(target_path, pre_restore_backup)
                logger.info(f"Created pre-restore backup: {pre_restore_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, target_path)
            logger.info(f"Restored from backup: {backup_path} -> {target_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error restoring from backup: {str(e)}")
            return False