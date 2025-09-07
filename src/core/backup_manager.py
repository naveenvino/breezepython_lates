"""
Comprehensive backup and recovery system for trading data
"""
import os
import shutil
import gzip
import json
import logging
import threading
import schedule
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import tempfile
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BackupInfo:
    """Backup information"""
    backup_id: str
    backup_type: str  # full, incremental, config, data
    file_path: str
    size_bytes: int
    created_at: datetime
    source: str
    compressed: bool
    metadata: Dict[str, Any]

class BackupManager:
    """Comprehensive backup and recovery system"""
    
    def __init__(self):
        self.backup_root = Path(os.getenv('BACKUP_PATH', 'backups'))
        self.retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
        self.enable_compression = os.getenv('BACKUP_COMPRESSION', 'true').lower() == 'true'
        self.enable_encryption = os.getenv('BACKUP_ENCRYPTION', 'false').lower() == 'true'
        
        # Create backup directory structure
        self.backup_root.mkdir(exist_ok=True)
        (self.backup_root / 'daily').mkdir(exist_ok=True)
        (self.backup_root / 'weekly').mkdir(exist_ok=True)
        (self.backup_root / 'monthly').mkdir(exist_ok=True)
        (self.backup_root / 'config').mkdir(exist_ok=True)
        (self.backup_root / 'data').mkdir(exist_ok=True)
        
        # Backup registry
        self.backup_registry = []
        self._load_backup_registry()
        
        # Thread lock
        self._lock = threading.Lock()
        
        # Schedule automated backups
        self._schedule_backups()
        
        logger.info(f"Backup manager initialized: {self.backup_root}")
    
    def _load_backup_registry(self):
        """Load backup registry from file"""
        registry_file = self.backup_root / 'backup_registry.json'
        
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    registry_data = json.load(f)
                
                self.backup_registry = [
                    BackupInfo(
                        backup_id=item['backup_id'],
                        backup_type=item['backup_type'],
                        file_path=item['file_path'],
                        size_bytes=item['size_bytes'],
                        created_at=datetime.fromisoformat(item['created_at']),
                        source=item['source'],
                        compressed=item['compressed'],
                        metadata=item.get('metadata', {})
                    )
                    for item in registry_data
                ]
                
                logger.info(f"Loaded {len(self.backup_registry)} backup entries from registry")
                
            except Exception as e:
                logger.error(f"Failed to load backup registry: {e}")
                self.backup_registry = []
    
    def _save_backup_registry(self):
        """Save backup registry to file"""
        registry_file = self.backup_root / 'backup_registry.json'
        
        try:
            registry_data = [
                {
                    'backup_id': backup.backup_id,
                    'backup_type': backup.backup_type,
                    'file_path': backup.file_path,
                    'size_bytes': backup.size_bytes,
                    'created_at': backup.created_at.isoformat(),
                    'source': backup.source,
                    'compressed': backup.compressed,
                    'metadata': backup.metadata
                }
                for backup in self.backup_registry
            ]
            
            with open(registry_file, 'w') as f:
                json.dump(registry_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save backup registry: {e}")
    
    def _schedule_backups(self):
        """Schedule automated backups"""
        # Daily database backup at 2 AM
        schedule.every().day.at("02:00").do(self._daily_backup_job)
        
        # Weekly full backup on Sunday at 3 AM
        schedule.every().sunday.at("03:00").do(self._weekly_backup_job)
        
        # Monthly backup on 1st day at 4 AM
        schedule.every().month.do(self._monthly_backup_job)
        
        # Start scheduler thread
        scheduler_thread = threading.Thread(target=self._run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        
        logger.info("Backup scheduler started")
    
    def _run_scheduler(self):
        """Run the backup scheduler"""
        while True:
            try:
                schedule.run_pending()
                threading.Event().wait(60)  # Check every minute
            except Exception as e:
                logger.error(f"Backup scheduler error: {e}")
    
    def _daily_backup_job(self):
        """Daily backup job"""
        try:
            # Backup databases
            self.backup_sqlite_database('trading_settings')
            self.backup_sqlite_database('audit_log')
            
            # Backup configuration files
            self.backup_configuration()
            
            # Backup trade data
            self.backup_trade_data()
            
            logger.info("Daily backup completed successfully")
            
        except Exception as e:
            logger.error(f"Daily backup failed: {e}")
    
    def _weekly_backup_job(self):
        """Weekly backup job"""
        try:
            # Full system backup
            self.create_full_backup()
            
            # Clean up old backups
            self.cleanup_old_backups()
            
            logger.info("Weekly backup completed successfully")
            
        except Exception as e:
            logger.error(f"Weekly backup failed: {e}")
    
    def _monthly_backup_job(self):
        """Monthly backup job"""
        try:
            # Create archive backup
            self.create_archive_backup()
            
            logger.info("Monthly backup completed successfully")
            
        except Exception as e:
            logger.error(f"Monthly backup failed: {e}")
    
    def backup_sqlite_database(self, db_name: str) -> str:
        """Backup SQLite database"""
        try:
            db_path = Path(f"data/{db_name}.db")
            
            if not db_path.exists():
                logger.warning(f"Database {db_name} not found for backup")
                return None
            
            # Create backup filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{db_name}_{timestamp}.db"
            
            if self.enable_compression:
                backup_filename += ".gz"
            
            backup_path = self.backup_root / 'data' / backup_filename
            
            # Create backup
            if self.enable_compression:
                with open(db_path, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(db_path, backup_path)
            
            # Register backup
            backup_info = BackupInfo(
                backup_id=f"{db_name}_{timestamp}",
                backup_type='data',
                file_path=str(backup_path),
                size_bytes=backup_path.stat().st_size,
                created_at=datetime.utcnow(),
                source=str(db_path),
                compressed=self.enable_compression,
                metadata={'database': db_name}
            )
            
            with self._lock:
                self.backup_registry.append(backup_info)
                self._save_backup_registry()
            
            logger.info(f"Database backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to backup database {db_name}: {e}")
            return None
    
    def backup_configuration(self) -> str:
        """Backup configuration files"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"config_{timestamp}.tar.gz"
            backup_path = self.backup_root / 'config' / backup_filename
            
            # Files to backup
            config_files = [
                '.env.example',
                'requirements.txt',
                'requirements-prod.txt',
                'Dockerfile',
                'docker-compose.yml',
                'CLAUDE.md',
                'README.md'
            ]
            
            # Create temporary directory for staging
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Copy configuration files
                for config_file in config_files:
                    src_path = Path(config_file)
                    if src_path.exists():
                        dst_path = temp_path / config_file
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dst_path)
                
                # Copy configuration directories
                config_dirs = ['config', 'src/config']
                for config_dir in config_dirs:
                    src_dir = Path(config_dir)
                    if src_dir.exists():
                        dst_dir = temp_path / config_dir
                        shutil.copytree(src_dir, dst_dir, ignore_dangling_symlinks=True)
                
                # Create compressed archive
                shutil.make_archive(
                    str(backup_path.with_suffix('')),
                    'gztar',
                    temp_dir
                )
            
            # Register backup
            backup_info = BackupInfo(
                backup_id=f"config_{timestamp}",
                backup_type='config',
                file_path=str(backup_path),
                size_bytes=backup_path.stat().st_size,
                created_at=datetime.utcnow(),
                source='configuration',
                compressed=True,
                metadata={'files': config_files}
            )
            
            with self._lock:
                self.backup_registry.append(backup_info)
                self._save_backup_registry()
            
            logger.info(f"Configuration backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to backup configuration: {e}")
            return None
    
    def backup_trade_data(self) -> str:
        """Backup trade data and positions"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"trade_data_{timestamp}.json"
            
            if self.enable_compression:
                backup_filename += ".gz"
            
            backup_path = self.backup_root / 'data' / backup_filename
            
            # Collect trade data
            trade_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'positions': {},
                'risk_status': {},
                'settings': {}
            }
            
            # Get risk manager data
            try:
                from src.core.risk_manager import get_risk_manager
                risk_manager = get_risk_manager()
                trade_data['risk_status'] = risk_manager.get_risk_status()
                trade_data['positions'] = risk_manager.get_position_details()
            except Exception as e:
                logger.warning(f"Could not backup risk manager data: {e}")
            
            # Get settings data
            try:
                from src.infrastructure.database.connection_pool import get_sqlite_session
                with get_sqlite_session() as cursor:
                    cursor.execute("SELECT key, value, category FROM settings")
                    settings = cursor.fetchall()
                    trade_data['settings'] = {
                        row[0]: {'value': json.loads(row[1]), 'category': row[2]}
                        for row in settings
                    }
            except Exception as e:
                logger.warning(f"Could not backup settings data: {e}")
            
            # Write backup file
            if self.enable_compression:
                with gzip.open(backup_path, 'wt') as f:
                    json.dump(trade_data, f, indent=2, default=str)
            else:
                with open(backup_path, 'w') as f:
                    json.dump(trade_data, f, indent=2, default=str)
            
            # Register backup
            backup_info = BackupInfo(
                backup_id=f"trade_data_{timestamp}",
                backup_type='data',
                file_path=str(backup_path),
                size_bytes=backup_path.stat().st_size,
                created_at=datetime.utcnow(),
                source='trade_data',
                compressed=self.enable_compression,
                metadata={
                    'positions_count': len(trade_data['positions']),
                    'settings_count': len(trade_data['settings'])
                }
            )
            
            with self._lock:
                self.backup_registry.append(backup_info)
                self._save_backup_registry()
            
            logger.info(f"Trade data backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to backup trade data: {e}")
            return None
    
    def create_full_backup(self) -> str:
        """Create full system backup"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"full_backup_{timestamp}.tar.gz"
            backup_path = self.backup_root / 'weekly' / backup_filename
            
            # Directories to include in full backup
            backup_dirs = [
                'data',
                'logs',
                'src',
                'static',
                'config'
            ]
            
            # Files to include
            backup_files = [
                'unified_api_correct.py',
                'clean_unified_api.py',
                'requirements.txt',
                'requirements-prod.txt',
                'Dockerfile',
                'docker-compose.yml',
                'CLAUDE.md',
                'README.md'
            ]
            
            # Create temporary directory for staging
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / 'full_backup'
                temp_path.mkdir()
                
                # Copy directories
                for backup_dir in backup_dirs:
                    src_dir = Path(backup_dir)
                    if src_dir.exists():
                        dst_dir = temp_path / backup_dir
                        shutil.copytree(src_dir, dst_dir, ignore_dangling_symlinks=True)
                
                # Copy files
                for backup_file in backup_files:
                    src_file = Path(backup_file)
                    if src_file.exists():
                        dst_file = temp_path / backup_file
                        shutil.copy2(src_file, dst_file)
                
                # Create compressed archive
                shutil.make_archive(
                    str(backup_path.with_suffix('')),
                    'gztar',
                    temp_path.parent,
                    'full_backup'
                )
            
            # Register backup
            backup_info = BackupInfo(
                backup_id=f"full_{timestamp}",
                backup_type='full',
                file_path=str(backup_path),
                size_bytes=backup_path.stat().st_size,
                created_at=datetime.utcnow(),
                source='full_system',
                compressed=True,
                metadata={
                    'directories': backup_dirs,
                    'files': backup_files
                }
            )
            
            with self._lock:
                self.backup_registry.append(backup_info)
                self._save_backup_registry()
            
            logger.info(f"Full backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to create full backup: {e}")
            return None
    
    def create_archive_backup(self) -> str:
        """Create monthly archive backup"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m")
            backup_filename = f"archive_{timestamp}.tar.gz"
            backup_path = self.backup_root / 'monthly' / backup_filename
            
            # Archive entire backup directory (except monthly to avoid recursion)
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / 'archive'
                temp_path.mkdir()
                
                # Copy all backup data except monthly archives
                for item in self.backup_root.iterdir():
                    if item.name != 'monthly' and item.is_dir():
                        shutil.copytree(item, temp_path / item.name)
                    elif item.is_file():
                        shutil.copy2(item, temp_path / item.name)
                
                # Create compressed archive
                shutil.make_archive(
                    str(backup_path.with_suffix('')),
                    'gztar',
                    temp_path.parent,
                    'archive'
                )
            
            # Register backup
            backup_info = BackupInfo(
                backup_id=f"archive_{timestamp}",
                backup_type='archive',
                file_path=str(backup_path),
                size_bytes=backup_path.stat().st_size,
                created_at=datetime.utcnow(),
                source='backup_archive',
                compressed=True,
                metadata={'archive_month': timestamp}
            )
            
            with self._lock:
                self.backup_registry.append(backup_info)
                self._save_backup_registry()
            
            logger.info(f"Archive backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to create archive backup: {e}")
            return None
    
    def restore_database(self, backup_id: str, target_db: str = None) -> bool:
        """Restore database from backup"""
        try:
            # Find backup
            backup = None
            for b in self.backup_registry:
                if b.backup_id == backup_id:
                    backup = b
                    break
            
            if not backup:
                logger.error(f"Backup {backup_id} not found")
                return False
            
            backup_path = Path(backup.file_path)
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            # Determine target database
            if not target_db:
                target_db = backup.metadata.get('database', 'trading_settings')
            
            target_path = Path(f"data/{target_db}.db")
            
            # Create backup of current database
            if target_path.exists():
                backup_current = f"data/{target_db}.db.backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(target_path, backup_current)
                logger.info(f"Current database backed up to: {backup_current}")
            
            # Restore database
            target_path.parent.mkdir(exist_ok=True)
            
            if backup.compressed:
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(target_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(backup_path, target_path)
            
            logger.info(f"Database restored from backup: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Clean up old backups based on retention policy"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            backups_to_remove = [
                backup for backup in self.backup_registry
                if backup.created_at < cutoff_date and backup.backup_type != 'archive'
            ]
            
            for backup in backups_to_remove:
                try:
                    # Remove backup file
                    backup_path = Path(backup.file_path)
                    if backup_path.exists():
                        backup_path.unlink()
                    
                    # Remove from registry
                    self.backup_registry.remove(backup)
                    
                except Exception as e:
                    logger.error(f"Failed to remove backup {backup.backup_id}: {e}")
            
            if backups_to_remove:
                with self._lock:
                    self._save_backup_registry()
                
                logger.info(f"Cleaned up {len(backups_to_remove)} old backups")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get backup system status"""
        with self._lock:
            total_backups = len(self.backup_registry)
            total_size = sum(backup.size_bytes for backup in self.backup_registry)
            
            # Group by type
            by_type = {}
            for backup in self.backup_registry:
                backup_type = backup.backup_type
                if backup_type not in by_type:
                    by_type[backup_type] = {'count': 0, 'size': 0}
                by_type[backup_type]['count'] += 1
                by_type[backup_type]['size'] += backup.size_bytes
            
            # Recent backups (last 7 days)
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            recent_backups = [
                backup for backup in self.backup_registry
                if backup.created_at > recent_cutoff
            ]
            
            return {
                'total_backups': total_backups,
                'total_size_gb': round(total_size / (1024**3), 2),
                'by_type': by_type,
                'recent_backups': len(recent_backups),
                'retention_days': self.retention_days,
                'compression_enabled': self.enable_compression,
                'last_backup': max(
                    (b.created_at for b in self.backup_registry),
                    default=None
                ),
                'backup_root': str(self.backup_root),
                'status': 'operational'
            }
    
    def list_backups(self, backup_type: str = None, limit: int = 50) -> List[BackupInfo]:
        """List available backups"""
        with self._lock:
            backups = self.backup_registry.copy()
        
        # Filter by type if specified
        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x.created_at, reverse=True)
        
        return backups[:limit]

# Global backup manager
_backup_manager: Optional[BackupManager] = None

def get_backup_manager() -> BackupManager:
    """Get global backup manager instance"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager