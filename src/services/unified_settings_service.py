"""
Unified Settings Service - Single source of truth for all settings
Eliminates confusion between localStorage, SQLite, and memory cache
"""

import sqlite3
import json
from typing import Dict, Any, Optional
from datetime import datetime
import os
from threading import Lock

class UnifiedSettingsService:
    def __init__(self, db_path: str = 'data/trading_settings.db'):
        self.db_path = db_path
        self._lock = Lock()
        self._cache = {}
        self._cache_version = 0
        self._ensure_database()
    
    def _ensure_database(self):
        """Ensure database and table exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS UnifiedSettings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT,
                    category TEXT DEFAULT 'general',
                    version INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_unified_category 
                ON UnifiedSettings(category)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_unified_version 
                ON UnifiedSettings(version)
            """)
            conn.commit()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value with caching"""
        with self._lock:
            cache_key = f"{key}_v{self._cache_version}"
            
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT setting_value, version 
                    FROM UnifiedSettings 
                    WHERE setting_key = ?
                """, (key,))
                row = cursor.fetchone()
                
                if row:
                    value = self._deserialize(row[0])
                    self._cache[cache_key] = value
                    return value
                
                return default
    
    def set(self, key: str, value: Any, category: str = 'general') -> Dict[str, Any]:
        """Set a setting value and invalidate cache"""
        with self._lock:
            serialized_value = self._serialize(value)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT version FROM UnifiedSettings WHERE setting_key = ?
                """, (key,))
                row = cursor.fetchone()
                
                new_version = (row[0] + 1) if row else 1
                
                cursor.execute("""
                    INSERT OR REPLACE INTO UnifiedSettings 
                    (setting_key, setting_value, category, version, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (key, serialized_value, category, new_version))
                
                conn.commit()
            
            self._invalidate_cache(key)
            
            return {
                'key': key,
                'value': value,
                'category': category,
                'version': new_version,
                'updated_at': datetime.now().isoformat()
            }
    
    def get_all(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get all settings, optionally filtered by category"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if category:
                cursor.execute("""
                    SELECT setting_key, setting_value, version, updated_at
                    FROM UnifiedSettings
                    WHERE category = ?
                    ORDER BY setting_key
                """, (category,))
            else:
                cursor.execute("""
                    SELECT setting_key, setting_value, version, updated_at
                    FROM UnifiedSettings
                    ORDER BY category, setting_key
                """)
            
            settings = {}
            for row in cursor.fetchall():
                settings[row[0]] = {
                    'value': self._deserialize(row[1]),
                    'version': row[2],
                    'updated_at': row[3]
                }
            
            return settings
    
    def get_categories(self) -> list:
        """Get all unique categories"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT category 
                FROM UnifiedSettings 
                ORDER BY category
            """)
            return [row[0] for row in cursor.fetchall()]
    
    def delete(self, key: str) -> bool:
        """Delete a setting"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM UnifiedSettings WHERE setting_key = ?
                """, (key,))
                conn.commit()
                deleted = cursor.rowcount > 0
            
            if deleted:
                self._invalidate_cache(key)
            
            return deleted
    
    def bulk_update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update multiple settings atomically"""
        with self._lock:
            results = {}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                try:
                    for key, value in updates.items():
                        category = 'general'
                        if isinstance(value, dict) and 'category' in value:
                            category = value['category']
                            value = value['value']
                        
                        serialized_value = self._serialize(value)
                        
                        cursor.execute("""
                            SELECT version FROM UnifiedSettings WHERE setting_key = ?
                        """, (key,))
                        row = cursor.fetchone()
                        
                        new_version = (row[0] + 1) if row else 1
                        
                        cursor.execute("""
                            INSERT OR REPLACE INTO UnifiedSettings 
                            (setting_key, setting_value, category, version, updated_at)
                            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (key, serialized_value, category, new_version))
                        
                        results[key] = {
                            'value': value,
                            'version': new_version,
                            'category': category
                        }
                    
                    conn.commit()
                    
                    for key in updates.keys():
                        self._invalidate_cache(key)
                    
                except Exception as e:
                    conn.rollback()
                    raise e
            
            return results
    
    def get_version(self, key: str) -> Optional[int]:
        """Get the version number of a setting"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT version FROM UnifiedSettings WHERE setting_key = ?
            """, (key,))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def _serialize(self, value: Any) -> str:
        """Serialize value for storage"""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)
    
    def _deserialize(self, value: str) -> Any:
        """Deserialize value from storage"""
        if value is None:
            return None
        
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            try:
                return float(value) if '.' in value else int(value)
            except ValueError:
                return value
    
    def _invalidate_cache(self, key: Optional[str] = None):
        """Invalidate cache for a specific key or all keys"""
        if key:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{key}_")]
            for k in keys_to_remove:
                del self._cache[k]
        else:
            self._cache.clear()
        self._cache_version += 1
    
    def export_settings(self) -> Dict[str, Any]:
        """Export all settings for backup"""
        settings = self.get_all()
        categories = self.get_categories()
        
        return {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'categories': categories,
            'settings': settings
        }
    
    def import_settings(self, data: Dict[str, Any], overwrite: bool = False):
        """Import settings from backup"""
        if 'settings' not in data:
            raise ValueError("Invalid import data format")
        
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                try:
                    for key, setting_data in data['settings'].items():
                        if not overwrite:
                            cursor.execute("""
                                SELECT 1 FROM UnifiedSettings WHERE setting_key = ?
                            """, (key,))
                            if cursor.fetchone():
                                continue
                        
                        value = setting_data.get('value') if isinstance(setting_data, dict) else setting_data
                        category = setting_data.get('category', 'general') if isinstance(setting_data, dict) else 'general'
                        
                        self.set(key, value, category)
                    
                    conn.commit()
                    
                except Exception as e:
                    conn.rollback()
                    raise e
            
            self._invalidate_cache()

unified_settings = UnifiedSettingsService()