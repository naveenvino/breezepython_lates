"""
Database repository for system configuration management
"""
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
import pyodbc
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class SystemConfig:
    id: str
    config_type: str
    config_key: str
    config_value: Any
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str]
    is_active: bool
    version: int

class ConfigRepository:
    def __init__(self):
        self.connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')};"
            f"DATABASE={os.getenv('DB_NAME', 'KiteConnectApi')};"
            f"Trusted_Connection=yes;"
        )
    
    def _get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def get_config(
        self,
        config_type: str,
        config_key: str
    ) -> Optional[SystemConfig]:
        """Get a specific configuration value"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    id, config_type, config_key, config_value,
                    description, created_at, updated_at,
                    updated_by, is_active, version
                FROM SystemConfigurations
                WHERE config_type = ? AND config_key = ? AND is_active = 1
            """, (config_type, config_key))
            
            row = cursor.fetchone()
            if row:
                # Try to parse as JSON, otherwise keep as string
                try:
                    value = json.loads(row[3])
                except:
                    value = row[3]
                
                return SystemConfig(
                    id=str(row[0]),
                    config_type=row[1],
                    config_key=row[2],
                    config_value=value,
                    description=row[4],
                    created_at=row[5],
                    updated_at=row[6],
                    updated_by=row[7],
                    is_active=bool(row[8]),
                    version=row[9]
                )
            return None
            
        finally:
            cursor.close()
            conn.close()
    
    def set_config(
        self,
        config_type: str,
        config_key: str,
        config_value: Any,
        description: Optional[str] = None,
        updated_by: Optional[str] = None
    ) -> bool:
        """Set or update a configuration value"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Convert value to JSON string if needed
            if isinstance(config_value, (dict, list)):
                value_str = json.dumps(config_value)
            else:
                value_str = str(config_value)
            
            # Check if config exists
            cursor.execute("""
                SELECT id, version FROM SystemConfigurations
                WHERE config_type = ? AND config_key = ?
            """, (config_type, config_key))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing config
                cursor.execute("""
                    UPDATE SystemConfigurations
                    SET config_value = ?,
                        description = COALESCE(?, description),
                        updated_at = GETDATE(),
                        updated_by = ?,
                        is_active = 1,
                        version = version + 1
                    WHERE config_type = ? AND config_key = ?
                """, (
                    value_str, description, updated_by,
                    config_type, config_key
                ))
            else:
                # Insert new config
                cursor.execute("""
                    INSERT INTO SystemConfigurations (
                        config_type, config_key, config_value,
                        description, created_at, updated_at,
                        updated_by, is_active, version
                    ) VALUES (?, ?, ?, ?, GETDATE(), GETDATE(), ?, 1, 1)
                """, (
                    config_type, config_key, value_str,
                    description, updated_by
                ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def get_configs_by_type(
        self,
        config_type: str
    ) -> List[SystemConfig]:
        """Get all configurations of a specific type"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    id, config_type, config_key, config_value,
                    description, created_at, updated_at,
                    updated_by, is_active, version
                FROM SystemConfigurations
                WHERE config_type = ? AND is_active = 1
                ORDER BY config_key
            """, config_type)
            
            configs = []
            for row in cursor.fetchall():
                # Try to parse as JSON, otherwise keep as string
                try:
                    value = json.loads(row[3])
                except:
                    value = row[3]
                
                configs.append(SystemConfig(
                    id=str(row[0]),
                    config_type=row[1],
                    config_key=row[2],
                    config_value=value,
                    description=row[4],
                    created_at=row[5],
                    updated_at=row[6],
                    updated_by=row[7],
                    is_active=bool(row[8]),
                    version=row[9]
                ))
            
            return configs
            
        finally:
            cursor.close()
            conn.close()
    
    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get all active configurations grouped by type"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    config_type, config_key, config_value
                FROM SystemConfigurations
                WHERE is_active = 1
                ORDER BY config_type, config_key
            """)
            
            configs = {}
            for row in cursor.fetchall():
                config_type = row[0]
                config_key = row[1]
                
                # Try to parse as JSON, otherwise keep as string
                try:
                    value = json.loads(row[2])
                except:
                    value = row[2]
                
                if config_type not in configs:
                    configs[config_type] = {}
                
                configs[config_type][config_key] = value
            
            return configs
            
        finally:
            cursor.close()
            conn.close()
    
    def deactivate_config(
        self,
        config_type: str,
        config_key: str
    ) -> bool:
        """Deactivate a configuration"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE SystemConfigurations
                SET is_active = 0, updated_at = GETDATE()
                WHERE config_type = ? AND config_key = ?
            """, (config_type, config_key))
            
            conn.commit()
            return cursor.rowcount > 0
            
        finally:
            cursor.close()
            conn.close()
    
    def get_scheduler_config(self) -> Dict[str, Any]:
        """Get scheduler configuration from database"""
        configs = self.get_configs_by_type('scheduler')
        
        result = {
            'breeze': {
                'enabled': False,
                'times': [],
                'weekdays_only': True,
                'headless': True
            },
            'kite': {
                'enabled': False,
                'times': [],
                'weekdays_only': True,
                'headless': True
            },
            'notifications': {
                'enabled': False
            }
        }
        
        for config in configs:
            if config.config_key == 'breeze_login_times':
                result['breeze']['times'] = config.config_value
                result['breeze']['enabled'] = True
            elif config.config_key == 'kite_login_times':
                result['kite']['times'] = config.config_value
                result['kite']['enabled'] = True
            elif config.config_key == 'weekdays_only':
                weekdays = config.config_value == 'true' if isinstance(config.config_value, str) else config.config_value
                result['breeze']['weekdays_only'] = weekdays
                result['kite']['weekdays_only'] = weekdays
        
        return result
    
    def save_scheduler_config(self, config: Dict[str, Any]) -> bool:
        """Save scheduler configuration to database"""
        try:
            # Save Breeze config
            if 'breeze' in config:
                breeze = config['breeze']
                if breeze.get('enabled'):
                    self.set_config(
                        'scheduler',
                        'breeze_login_times',
                        breeze.get('times', []),
                        'Breeze auto-login schedule'
                    )
            
            # Save Kite config
            if 'kite' in config:
                kite = config['kite']
                if kite.get('enabled'):
                    self.set_config(
                        'scheduler',
                        'kite_login_times',
                        kite.get('times', []),
                        'Kite auto-login schedule'
                    )
            
            # Save common settings
            weekdays_only = config.get('breeze', {}).get('weekdays_only', True)
            self.set_config(
                'scheduler',
                'weekdays_only',
                'true' if weekdays_only else 'false',
                'Run scheduler only on weekdays'
            )
            
            return True
            
        except Exception as e:
            print(f"Error saving scheduler config: {e}")
            return False

# Singleton instance
_config_repository = None

def get_config_repository() -> ConfigRepository:
    global _config_repository
    if _config_repository is None:
        _config_repository = ConfigRepository()
    return _config_repository