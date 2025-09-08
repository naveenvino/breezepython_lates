"""
Consolidated Settings Service
Single service for all settings operations using the unified schema
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConsolidatedSettingsService:
    def __init__(self, db_path: str = "data/trading_settings.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Ensure UnifiedSettings and SettingsAudit tables exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS UnifiedSettings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'default',
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    data_type TEXT DEFAULT 'string',
                    is_active BOOLEAN DEFAULT 1,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT DEFAULT 'system',
                    UNIQUE(user_id, namespace, key)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS SettingsAudit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    namespace TEXT,
                    key TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    action TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    performed_by TEXT DEFAULT 'system'
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_unified_user_namespace ON UnifiedSettings(user_id, namespace)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_unified_namespace_key ON UnifiedSettings(namespace, key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON SettingsAudit(timestamp)")
            
            conn.commit()
    
    def get_setting(
        self, 
        key: str, 
        namespace: str = "general", 
        user_id: str = "default",
        default: Any = None
    ) -> Any:
        """Get a single setting value"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value, data_type FROM UnifiedSettings 
                WHERE user_id = ? AND namespace = ? AND key = ? AND is_active = 1
            """, (user_id, namespace, key))
            
            row = cursor.fetchone()
            if row:
                return self._deserialize_value(row[0], row[1])
            return default
    
    def set_setting(
        self, 
        key: str, 
        value: Any,
        namespace: str = "general",
        user_id: str = "default",
        performed_by: str = "system"
    ) -> bool:
        """Set a single setting value"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get old value for audit
            cursor.execute("""
                SELECT value FROM UnifiedSettings 
                WHERE user_id = ? AND namespace = ? AND key = ?
            """, (user_id, namespace, key))
            old_row = cursor.fetchone()
            old_value = old_row[0] if old_row else None
            
            # Serialize value
            serialized_value = self._serialize_value(value)
            data_type = self._determine_data_type(value)
            
            # Insert or update setting
            cursor.execute("""
                INSERT INTO UnifiedSettings 
                (user_id, namespace, key, value, data_type, updated_at, created_by)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(user_id, namespace, key) 
                DO UPDATE SET 
                    value = excluded.value,
                    data_type = excluded.data_type,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, namespace, key, serialized_value, data_type, performed_by))
            
            # Add audit log
            action = 'UPDATE' if old_value is not None else 'CREATE'
            cursor.execute("""
                INSERT INTO SettingsAudit 
                (user_id, namespace, key, old_value, new_value, action, performed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, namespace, key, old_value, serialized_value, action, performed_by))
            
            conn.commit()
            return True
    
    def get_namespace_settings(
        self, 
        namespace: str, 
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Get all settings in a namespace"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT key, value, data_type FROM UnifiedSettings 
                WHERE user_id = ? AND namespace = ? AND is_active = 1
            """, (user_id, namespace))
            
            settings = {}
            for key, value, data_type in cursor.fetchall():
                settings[key] = self._deserialize_value(value, data_type)
            return settings
    
    def get_all_settings(self, user_id: str = "default") -> Dict[str, Dict[str, Any]]:
        """Get all settings for a user organized by namespace"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT namespace, key, value, data_type FROM UnifiedSettings 
                WHERE user_id = ? AND is_active = 1
                ORDER BY namespace, key
            """, (user_id,))
            
            settings = {}
            for namespace, key, value, data_type in cursor.fetchall():
                if namespace not in settings:
                    settings[namespace] = {}
                settings[namespace][key] = self._deserialize_value(value, data_type)
            return settings
    
    def bulk_update(
        self, 
        settings: Dict[str, Any], 
        namespace: str = "general",
        user_id: str = "default",
        performed_by: str = "system"
    ) -> bool:
        """Update multiple settings at once"""
        success = True
        for key, value in settings.items():
            if not self.set_setting(key, value, namespace, user_id, performed_by):
                success = False
        return success
    
    def delete_setting(
        self,
        key: str,
        namespace: str = "general",
        user_id: str = "default",
        performed_by: str = "system"
    ) -> bool:
        """Delete a setting (soft delete by marking inactive)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get old value for audit
            cursor.execute("""
                SELECT value FROM UnifiedSettings 
                WHERE user_id = ? AND namespace = ? AND key = ? AND is_active = 1
            """, (user_id, namespace, key))
            old_row = cursor.fetchone()
            
            if not old_row:
                return False
            
            # Soft delete
            cursor.execute("""
                UPDATE UnifiedSettings 
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND namespace = ? AND key = ?
            """, (user_id, namespace, key))
            
            # Add audit log
            cursor.execute("""
                INSERT INTO SettingsAudit 
                (user_id, namespace, key, old_value, new_value, action, performed_by)
                VALUES (?, ?, ?, ?, NULL, 'DELETE', ?)
            """, (user_id, namespace, key, old_row[0], performed_by))
            
            conn.commit()
            return True
    
    def get_trading_config(self, config_name: str = "default", user_id: str = "default") -> Dict[str, Any]:
        """Get a complete trading configuration"""
        config = {}
        
        # Get settings from different namespaces
        for namespace in ['trading', 'risk', 'hedge', 'signal', 'expiry']:
            namespace_settings = self.get_namespace_settings(namespace, user_id)
            
            # Filter by config_name if not default
            if config_name != "default":
                filtered = {}
                for key, value in namespace_settings.items():
                    if key.startswith(f"{config_name}_"):
                        # Remove config_name prefix
                        clean_key = key[len(config_name) + 1:]
                        filtered[clean_key] = value
                namespace_settings = filtered
            
            config.update(namespace_settings)
        
        return config
    
    def save_trading_config(
        self, 
        config_name: str,
        config_data: Dict[str, Any],
        user_id: str = "default",
        performed_by: str = "system"
    ) -> bool:
        """Save a complete trading configuration"""
        namespace_mapping = {
            'num_lots': 'trading',
            'entry_timing': 'trading',
            'auto_trade_enabled': 'trading',
            'position_size_mode': 'trading',
            'hedge_enabled': 'hedge',
            'hedge_method': 'hedge',
            'hedge_percent': 'hedge',
            'hedge_offset': 'hedge',
            'profit_lock_enabled': 'risk',
            'profit_target': 'risk',
            'profit_lock': 'risk',
            'trailing_stop_enabled': 'risk',
            'trail_percent': 'risk',
            'max_positions': 'risk',
            'daily_loss_limit': 'risk',
            'daily_profit_target': 'risk',
            'max_loss_per_trade': 'risk',
            'max_exposure': 'risk',
            'active_signals': 'signal',
            'selected_expiry': 'expiry',
            'exit_day_offset': 'expiry',
            'exit_time': 'expiry',
            'auto_square_off_enabled': 'expiry',
            'weekday_config': 'expiry'
        }
        
        success = True
        for key, value in config_data.items():
            namespace = namespace_mapping.get(key, 'general')
            
            # Add config_name prefix if not default
            save_key = f"{config_name}_{key}" if config_name != "default" else key
            
            if not self.set_setting(save_key, value, namespace, user_id, performed_by):
                success = False
        
        return success
    
    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        namespace: Optional[str] = None,
        key: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit log entries"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM SettingsAudit WHERE 1=1"
            params = []
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            if namespace:
                query += " AND namespace = ?"
                params.append(namespace)
            if key:
                query += " AND key = ?"
                params.append(key)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize a value to string for storage"""
        if value is None:
            return None
        elif isinstance(value, (dict, list)):
            return json.dumps(value)
        elif isinstance(value, bool):
            return '1' if value else '0'
        else:
            return str(value)
    
    def _deserialize_value(self, value: str, data_type: str) -> Any:
        """Deserialize a value from storage"""
        if value is None:
            return None
        
        if data_type == 'json':
            return json.loads(value)
        elif data_type == 'boolean':
            return value == '1' or value.lower() == 'true'
        elif data_type == 'integer':
            return int(value)
        elif data_type == 'float':
            return float(value)
        else:
            return value
    
    def _determine_data_type(self, value: Any) -> str:
        """Determine the data type of a value"""
        if isinstance(value, bool):
            return 'boolean'
        elif isinstance(value, int):
            return 'integer'
        elif isinstance(value, float):
            return 'float'
        elif isinstance(value, (dict, list)):
            return 'json'
        else:
            return 'string'
    
    def export_settings(self, user_id: str = "default") -> Dict[str, Any]:
        """Export all settings for backup or transfer"""
        settings = self.get_all_settings(user_id)
        return {
            'user_id': user_id,
            'exported_at': datetime.now().isoformat(),
            'settings': settings
        }
    
    def import_settings(
        self, 
        settings_data: Dict[str, Any], 
        user_id: Optional[str] = None,
        performed_by: str = "import"
    ) -> bool:
        """Import settings from backup"""
        if not user_id:
            user_id = settings_data.get('user_id', 'default')
        
        settings = settings_data.get('settings', {})
        success = True
        
        for namespace, namespace_settings in settings.items():
            if not self.bulk_update(namespace_settings, namespace, user_id, performed_by):
                success = False
        
        return success