"""
Trade Configuration Settings Service
Handles persistent storage of trading configuration settings for cloud deployment
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TradeConfigService:
    def __init__(self, db_path: str = "data/trading_settings.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Trade configuration settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS TradeConfiguration (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    config_name TEXT NOT NULL,
                    
                    -- Position Settings
                    num_lots INTEGER DEFAULT 10,
                    entry_timing TEXT DEFAULT 'immediate',
                    
                    -- Hedge Configuration
                    hedge_enabled BOOLEAN DEFAULT 1,
                    hedge_method TEXT DEFAULT 'percentage',
                    hedge_percent REAL DEFAULT 30.0,
                    hedge_offset INTEGER DEFAULT 200,
                    
                    -- Stop Loss Settings
                    profit_lock_enabled BOOLEAN DEFAULT 0,
                    profit_target REAL DEFAULT 10.0,
                    profit_lock REAL DEFAULT 5.0,
                    trailing_stop_enabled BOOLEAN DEFAULT 0,
                    trail_percent REAL DEFAULT 1.0,
                    
                    -- Auto Trading Settings
                    auto_trade_enabled BOOLEAN DEFAULT 0,
                    active_signals TEXT DEFAULT '[]',  -- JSON array of active signals
                    daily_profit_target REAL DEFAULT 100000,
                    
                    -- Position Settings
                    position_size_mode TEXT DEFAULT 'fixed',  -- fixed or dynamic
                    
                    -- Metadata
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(user_id, config_name)
                )
            """)
            
            # Session settings for quick access
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS SessionSettings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    setting_key TEXT NOT NULL,
                    setting_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, setting_key)
                )
            """)
            
            # Audit log for tracking changes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS SettingsAuditLog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    config_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def save_trade_config(self, config: Dict[str, Any], user_id: str = 'default', config_name: str = 'default') -> Dict[str, Any]:
        """Save trade configuration to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if configuration exists
                cursor.execute("""
                    SELECT id FROM TradeConfiguration 
                    WHERE user_id = ? AND config_name = ?
                """, (user_id, config_name))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing configuration
                    cursor.execute("""
                        UPDATE TradeConfiguration SET
                            num_lots = ?,
                            entry_timing = ?,
                            hedge_enabled = ?,
                            hedge_method = ?,
                            hedge_percent = ?,
                            hedge_offset = ?,
                            profit_lock_enabled = ?,
                            profit_target = ?,
                            profit_lock = ?,
                            trailing_stop_enabled = ?,
                            trail_percent = ?,
                            auto_trade_enabled = ?,
                            active_signals = ?,
                            daily_profit_target = ?,
                            position_size_mode = ?,
                            max_positions = ?,
                            max_loss_per_trade = ?,
                            max_exposure = ?,
                            selected_expiry = ?,
                            exit_day_offset = ?,
                            exit_time = ?,
                            auto_square_off_enabled = ?,
                            weekday_config = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND config_name = ?
                    """, (
                        config.get('num_lots', 10),
                        config.get('entry_timing', 'immediate'),
                        config.get('hedge_enabled', True),
                        config.get('hedge_method', 'percentage'),
                        config.get('hedge_percent', 30.0),
                        config.get('hedge_offset', 200),
                        config.get('profit_lock_enabled', False),
                        config.get('profit_target', 10.0),
                        config.get('profit_lock', 5.0),
                        config.get('trailing_stop_enabled', False),
                        config.get('trail_percent', 1.0),
                        config.get('auto_trade_enabled', False),
                        json.dumps(config.get('active_signals', [])),
                        config.get('daily_profit_target', 100000),
                        config.get('position_size_mode', 'fixed'),
                        config.get('max_positions', 5),
                        config.get('max_loss_per_trade', 20000),
                        config.get('max_exposure', 200000),
                        config.get('selected_expiry'),
                        config.get('exit_day_offset', 2),
                        config.get('exit_time', '15:15'),
                        config.get('auto_square_off_enabled', True),
                        json.dumps(config.get('weekday_config', {})),
                        user_id, config_name
                    ))
                    
                    # Log the update
                    self._log_audit(cursor, user_id, 'UPDATE', config_name, None, json.dumps(config))
                    
                else:
                    # Insert new configuration
                    cursor.execute("""
                        INSERT INTO TradeConfiguration (
                            user_id, config_name, num_lots, entry_timing,
                            hedge_enabled, hedge_method, hedge_percent, hedge_offset,
                            profit_lock_enabled, profit_target, profit_lock,
                            trailing_stop_enabled, trail_percent,
                            auto_trade_enabled, active_signals,
                            daily_profit_target, position_size_mode,
                            max_positions, max_loss_per_trade, max_exposure,
                            selected_expiry, exit_day_offset, exit_time,
                            auto_square_off_enabled, weekday_config
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user_id, config_name,
                        config.get('num_lots', 10),
                        config.get('entry_timing', 'immediate'),
                        config.get('hedge_enabled', True),
                        config.get('hedge_method', 'percentage'),
                        config.get('hedge_percent', 30.0),
                        config.get('hedge_offset', 200),
                        config.get('profit_lock_enabled', False),
                        config.get('profit_target', 10.0),
                        config.get('profit_lock', 5.0),
                        config.get('trailing_stop_enabled', False),
                        config.get('trail_percent', 1.0),
                        config.get('auto_trade_enabled', False),
                        json.dumps(config.get('active_signals', [])),
                        config.get('daily_profit_target', 100000),
                        config.get('position_size_mode', 'fixed'),
                        config.get('max_positions', 5),
                        config.get('max_loss_per_trade', 20000),
                        config.get('max_exposure', 200000),
                        config.get('selected_expiry'),
                        config.get('exit_day_offset', 2),
                        config.get('exit_time', '15:15'),
                        config.get('auto_square_off_enabled', True),
                        json.dumps(config.get('weekday_config', {}))
                    ))
                    
                    # Log the insert
                    self._log_audit(cursor, user_id, 'INSERT', config_name, None, json.dumps(config))
                
                conn.commit()
                
                return {
                    'success': True,
                    'message': 'Configuration saved successfully',
                    'config_name': config_name
                }
                
        except Exception as e:
            logger.error(f"Error saving trade config: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to save configuration: {str(e)}'
            }
    
    def load_trade_config(self, user_id: str = 'default', config_name: str = 'default') -> Optional[Dict[str, Any]]:
        """Load trade configuration from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM TradeConfiguration
                    WHERE user_id = ? AND config_name = ? AND is_active = 1
                """, (user_id, config_name))
                
                row = cursor.fetchone()
                
                if row:
                    config = dict(row)
                    # Parse JSON fields
                    config['active_signals'] = json.loads(config.get('active_signals', '[]'))
                    # Parse weekday_config JSON
                    if config.get('weekday_config'):
                        try:
                            config['weekday_config'] = json.loads(config['weekday_config'])
                        except:
                            config['weekday_config'] = {}
                    # Convert boolean values
                    for key in ['hedge_enabled', 'profit_lock_enabled', 'trailing_stop_enabled', 
                                'auto_trade_enabled', 'auto_square_off_enabled']:
                        if key in config:
                            config[key] = bool(config[key])
                    
                    return config
                else:
                    # Return default configuration
                    return self.get_default_config()
                    
        except Exception as e:
            logger.error(f"Error loading trade config: {str(e)}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default trade configuration"""
        return {
            'num_lots': 10,
            'entry_timing': 'immediate',
            'hedge_enabled': True,
            'hedge_method': 'percentage',
            'hedge_percent': 30.0,
            'hedge_offset': 200,
            'profit_lock_enabled': False,
            'profit_target': 10.0,
            'profit_lock': 5.0,
            'trailing_stop_enabled': False,
            'trail_percent': 1.0,
            'auto_trade_enabled': False,
            'active_signals': [],
            'daily_profit_target': 100000,
            'position_size_mode': 'fixed',
            'max_positions': 5,
            'max_loss_per_trade': 20000,
            'max_exposure': 200000,
            'selected_expiry': None,
            'exit_day_offset': 2,
            'exit_time': '15:15',
            'auto_square_off_enabled': True,
            'weekday_config': {
                'monday': 'current',
                'tuesday': 'current',
                'wednesday': 'next',
                'thursday': 'next',
                'friday': 'next'
            }
        }
    
    def save_session_setting(self, key: str, value: Any, user_id: str = 'default') -> bool:
        """Save a single session setting"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO SessionSettings (user_id, setting_key, setting_value)
                    VALUES (?, ?, ?)
                """, (user_id, key, json.dumps(value) if not isinstance(value, str) else value))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving session setting: {str(e)}")
            return False
    
    def get_session_setting(self, key: str, user_id: str = 'default', default: Any = None) -> Any:
        """Get a single session setting"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT setting_value FROM SessionSettings
                    WHERE user_id = ? AND setting_key = ?
                """, (user_id, key))
                
                row = cursor.fetchone()
                
                if row:
                    try:
                        return json.loads(row[0])
                    except:
                        return row[0]
                        
                return default
                
        except Exception as e:
            logger.error(f"Error getting session setting: {str(e)}")
            return default
    
    def list_configurations(self, user_id: str = 'default') -> list:
        """List all configurations for a user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT config_name, created_at, updated_at, is_active
                    FROM TradeConfiguration
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                """, (user_id,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error listing configurations: {str(e)}")
            return []
    
    def duplicate_config(self, source_name: str, target_name: str, user_id: str = 'default') -> Dict[str, Any]:
        """Duplicate an existing configuration"""
        try:
            config = self.load_trade_config(user_id, source_name)
            if config:
                return self.save_trade_config(config, user_id, target_name)
            else:
                return {'success': False, 'message': 'Source configuration not found'}
                
        except Exception as e:
            logger.error(f"Error duplicating config: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def delete_config(self, config_name: str, user_id: str = 'default') -> Dict[str, Any]:
        """Soft delete a configuration"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE TradeConfiguration 
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND config_name = ?
                """, (user_id, config_name))
                
                conn.commit()
                
                return {'success': True, 'message': 'Configuration deleted'}
                
        except Exception as e:
            logger.error(f"Error deleting config: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _log_audit(self, cursor, user_id: str, action: str, config_name: str, old_value: Any, new_value: Any):
        """Log configuration changes for audit"""
        try:
            cursor.execute("""
                INSERT INTO SettingsAuditLog (user_id, action, config_name, old_value, new_value)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, action, config_name, 
                  json.dumps(old_value) if old_value else None,
                  json.dumps(new_value) if new_value else None))
        except Exception as e:
            logger.error(f"Error logging audit: {str(e)}")

# Singleton instance
_trade_config_service = None

def get_trade_config_service() -> TradeConfigService:
    """Get singleton instance of trade config service"""
    global _trade_config_service
    if _trade_config_service is None:
        _trade_config_service = TradeConfigService()
    return _trade_config_service