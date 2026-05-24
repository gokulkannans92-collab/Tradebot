"""
Automated Backup System

Handles daily backups of critical database and log files.
Enforces retention policies to prevent disk space exhaustion.
"""

import os
import glob
import shutil
import logging
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED

logger = logging.getLogger(__name__)

class BackupManager:
    """Manages automated backups for TradeBot data."""
    
    def __init__(self, data_dir: str, retention_days: int = 7):
        self.data_dir = data_dir
        self.backup_dir = os.path.join(data_dir, "backups")
        self.retention_days = retention_days
        
        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)
        
    def perform_backup(self) -> bool:
        """
        Executes a backup of the database and logs.
        Creates a ZIP archive in the backups folder.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"tradebot_backup_{timestamp}.zip"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Files to backup
            targets = []
            
            # 1. Database
            db_path = os.path.join(self.data_dir, "tradebot.db")
            if os.path.exists(db_path):
                targets.append(db_path)
                
            # 2. Logs
            log_files = glob.glob(os.path.join(self.data_dir, "*.log*"))
            targets.extend(log_files)
            
            # 3. Session Caches & Configs (excluding .env for security)
            for file in ["users.json", ".session_cache"]:
                f_path = os.path.join(self.data_dir, file)
                if os.path.exists(f_path):
                    targets.append(f_path)
            
            if not targets:
                logger.warning("No files found to backup.")
                return False
                
            logger.info(f"Starting automated backup of {len(targets)} files...")
            
            # Create ZIP
            with ZipFile(backup_path, 'w', ZIP_DEFLATED) as zipf:
                for file_path in targets:
                    # Store file with relative name in ZIP
                    arcname = os.path.basename(file_path)
                    try:
                        zipf.write(file_path, arcname)
                    except PermissionError:
                        logger.warning(f"Could not backup {arcname} (file locked).")
                    except Exception as e:
                        logger.warning(f"Error backing up {arcname}: {e}")
                        
            logger.info(f"✅ Backup completed successfully: {backup_filename}")
            
            # Cleanup old backups
            self._enforce_retention()
            return True
            
        except Exception as e:
            logger.error(f"❌ Backup process failed: {e}", exc_info=True)
            return False
            
    def _enforce_retention(self):
        """Deletes backups older than retention_days."""
        try:
            now = datetime.now().timestamp()
            retention_seconds = self.retention_days * 86400
            
            backups = glob.glob(os.path.join(self.backup_dir, "*.zip"))
            deleted_count = 0
            
            for backup in backups:
                if os.path.isfile(backup):
                    file_time = os.path.getmtime(backup)
                    if (now - file_time) > retention_seconds:
                        try:
                            os.remove(backup)
                            deleted_count += 1
                        except OSError as e:
                            logger.error(f"Failed to delete old backup {backup}: {e}")
                            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old backups (older than {self.retention_days} days).")
                
        except Exception as e:
            logger.error(f"Error enforcing backup retention policy: {e}")
