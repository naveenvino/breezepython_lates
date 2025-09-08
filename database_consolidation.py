"""
Database Consolidation Script
Consolidates multiple duplicate settings tables into a unified schema
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
import shutil
from typing import Dict, List, Any, Optional

class DatabaseConsolidator:
    def __init__(self):
        self.db_path = Path("data/trading_settings.db")
        self.backup_path = Path("data/backup")
        self.backup_path.mkdir(exist_ok=True)
        
    def backup_database(self):
        """Create backup of existing database"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_path / f"trading_settings_backup_{timestamp}.db"
        
        print(f"Creating backup at {backup_file}")
        shutil.copy2(self.db_path, backup_file)
        
        # Also backup other db files if they exist
        for db_file in ["test_settings.db", "test_audit.db"]:
            source = Path("data") / db_file
            if source.exists():
                dest = self.backup_path / f"{db_file.replace('.db', '')}_backup_{timestamp}.db"
                shutil.copy2(source, dest)
                print(f"Backed up {db_file} to {dest}")
        
        return backup_file
    
    def create_unified_schema(self, conn: sqlite3.Connection):
        """Create the unified settings tables"""
        cursor = conn.cursor()
        
        # Drop existing unified tables if they exist (for clean migration)
        cursor.execute("DROP TABLE IF EXISTS UnifiedSettings")
        cursor.execute("DROP TABLE IF EXISTS SettingsAudit")
        
        # Create UnifiedSettings table
        cursor.execute("""
            CREATE TABLE UnifiedSettings (
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
        
        # Create SettingsAudit table
        cursor.execute("""
            CREATE TABLE SettingsAudit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                namespace TEXT,
                key TEXT,
                old_value TEXT,
                new_value TEXT,
                action TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                performed_by TEXT DEFAULT 'migration'
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX idx_unified_user_namespace ON UnifiedSettings(user_id, namespace)")
        cursor.execute("CREATE INDEX idx_unified_namespace_key ON UnifiedSettings(namespace, key)")
        cursor.execute("CREATE INDEX idx_audit_timestamp ON SettingsAudit(timestamp)")
        
        conn.commit()
        print("Created unified schema")
    
    def migrate_user_settings(self, conn: sqlite3.Connection):
        """Migrate data from UserSettings table"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM UserSettings")
            rows = cursor.fetchall()
            
            for row in rows:
                user_id = row[1] or 'default'
                key = row[2]
                value = row[3]
                
                # Determine namespace based on key patterns
                namespace = self._determine_namespace(key)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO UnifiedSettings 
                    (user_id, namespace, key, value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, namespace, key, value, row[4], row[5]))
            
            print(f"Migrated {len(rows)} rows from UserSettings")
        except sqlite3.OperationalError as e:
            print(f"UserSettings table not found or error: {e}")
    
    def migrate_trade_configuration(self, conn: sqlite3.Connection):
        """Migrate data from TradeConfiguration table"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM TradeConfiguration")
            rows = cursor.fetchall()
            
            for row in rows:
                user_id = row[1] or 'default'
                config_name = row[2]
                
                # Map TradeConfiguration columns to settings
                config_mapping = {
                    'num_lots': ('trading', row[3]),
                    'entry_timing': ('trading', row[4]),
                    'hedge_enabled': ('hedge', row[5]),
                    'hedge_method': ('hedge', row[6]),
                    'hedge_percent': ('hedge', row[7]),
                    'hedge_offset': ('hedge', row[8]),
                    'profit_lock_enabled': ('risk', row[9]),
                    'profit_target': ('risk', row[10]),
                    'profit_lock': ('risk', row[11]),
                    'trailing_stop_enabled': ('risk', row[12]),
                    'trail_percent': ('risk', row[13]),
                    'auto_trade_enabled': ('trading', row[14]),
                    'active_signals': ('signal', row[15]),
                    'max_positions': ('risk', row[16]),
                    'daily_loss_limit': ('risk', row[17]),
                    'daily_profit_target': ('risk', row[18]),
                    'max_loss_per_trade': ('risk', row[19]),
                    'position_size_mode': ('trading', row[20]),
                    'is_active': ('system', row[21]),
                    'max_exposure': ('risk', row[24]),
                    'selected_expiry': ('expiry', row[25]),
                    'exit_day_offset': ('expiry', row[26]),
                    'exit_time': ('expiry', row[27]),
                    'auto_square_off_enabled': ('expiry', row[28]),
                    'weekday_config': ('expiry', row[29])
                }
                
                for key, (namespace, value) in config_mapping.items():
                    if value is not None:
                        # Add config_name as prefix for multiple configurations
                        full_key = f"{config_name}_{key}" if config_name != 'default' else key
                        data_type = self._determine_data_type(value)
                        
                        cursor.execute("""
                            INSERT OR REPLACE INTO UnifiedSettings 
                            (user_id, namespace, key, value, data_type, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (user_id, namespace, full_key, str(value), data_type, row[22], row[23]))
            
            print(f"Migrated {len(rows)} configurations from TradeConfiguration")
        except sqlite3.OperationalError as e:
            print(f"TradeConfiguration table not found or error: {e}")
    
    def migrate_system_settings(self, conn: sqlite3.Connection):
        """Migrate data from SystemSettings table"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM SystemSettings")
            rows = cursor.fetchall()
            
            for row in rows:
                key = row[0]
                value = row[1]
                category = row[2] or 'system'
                
                cursor.execute("""
                    INSERT OR IGNORE INTO UnifiedSettings 
                    (user_id, namespace, key, value, created_at, updated_at)
                    VALUES ('system', ?, ?, ?, ?, ?)
                """, (category, key, value, row[3], row[4]))
            
            print(f"Migrated {len(rows)} rows from SystemSettings")
        except sqlite3.OperationalError as e:
            print(f"SystemSettings table not found or error: {e}")
    
    def migrate_settings_table(self, conn: sqlite3.Connection):
        """Migrate data from Settings table"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM Settings")
            rows = cursor.fetchall()
            
            for row in rows:
                key = row[1]
                value = row[2]
                category = row[3] or 'general'
                
                cursor.execute("""
                    INSERT OR IGNORE INTO UnifiedSettings 
                    (user_id, namespace, key, value, created_at, updated_at)
                    VALUES ('default', ?, ?, ?, ?, ?)
                """, (category, key, value, row[4], row[5]))
            
            print(f"Migrated {len(rows)} rows from Settings")
        except sqlite3.OperationalError as e:
            print(f"Settings table not found or error: {e}")
    
    def migrate_signal_states(self, conn: sqlite3.Connection):
        """Migrate data from SignalStates table"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM SignalStates")
            rows = cursor.fetchall()
            
            for row in rows:
                signal_name = row[1]
                is_active = row[2]
                description = row[3]
                
                # Store signal state
                cursor.execute("""
                    INSERT OR IGNORE INTO UnifiedSettings 
                    (user_id, namespace, key, value, data_type, metadata, created_at, updated_at)
                    VALUES ('default', 'signal', ?, ?, 'boolean', ?, ?, ?)
                """, (f"{signal_name}_active", str(is_active), json.dumps({'description': description}), row[6], row[7]))
                
                # Store signal metadata
                if row[4]:  # last_triggered
                    cursor.execute("""
                        INSERT OR IGNORE INTO UnifiedSettings 
                        (user_id, namespace, key, value, data_type, created_at, updated_at)
                        VALUES ('default', 'signal', ?, ?, 'timestamp', ?, ?)
                    """, (f"{signal_name}_last_triggered", row[4], row[6], row[7]))
                
                if row[5]:  # trigger_count
                    cursor.execute("""
                        INSERT OR IGNORE INTO UnifiedSettings 
                        (user_id, namespace, key, value, data_type, created_at, updated_at)
                        VALUES ('default', 'signal', ?, ?, 'integer', ?, ?)
                    """, (f"{signal_name}_trigger_count", str(row[5]), row[6], row[7]))
            
            print(f"Migrated {len(rows)} signal states from SignalStates")
        except sqlite3.OperationalError as e:
            print(f"SignalStates table not found or error: {e}")
    
    def migrate_expiry_config(self, conn: sqlite3.Connection):
        """Migrate data from ExpiryConfig table"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM ExpiryConfig")
            rows = cursor.fetchall()
            
            for row in rows:
                weekday = row[1]
                config = {
                    'expiry_type': row[2],
                    'exit_day': row[3],
                    'exit_time': row[4],
                    'auto_square_off': row[5]
                }
                
                cursor.execute("""
                    INSERT OR IGNORE INTO UnifiedSettings 
                    (user_id, namespace, key, value, data_type, created_at, updated_at)
                    VALUES ('default', 'expiry', ?, ?, 'json', ?, ?)
                """, (f"weekday_{weekday.lower()}", json.dumps(config), row[6], row[7]))
            
            print(f"Migrated {len(rows)} expiry configurations from ExpiryConfig")
        except sqlite3.OperationalError as e:
            print(f"ExpiryConfig table not found or error: {e}")
    
    def migrate_audit_log(self, conn: sqlite3.Connection):
        """Migrate data from SettingsAuditLog table"""
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM SettingsAuditLog")
            rows = cursor.fetchall()
            
            for row in rows:
                cursor.execute("""
                    INSERT INTO SettingsAudit 
                    (user_id, namespace, key, old_value, new_value, action, timestamp, performed_by)
                    VALUES (?, 'legacy', ?, ?, ?, ?, ?, 'migration')
                """, (row[1], row[3], row[4], row[5], row[2], row[6]))
            
            print(f"Migrated {len(rows)} audit log entries")
        except sqlite3.OperationalError as e:
            print(f"SettingsAuditLog table not found or error: {e}")
    
    def _determine_namespace(self, key: str) -> str:
        """Determine namespace based on key patterns"""
        key_lower = key.lower()
        
        if any(x in key_lower for x in ['hedge', 'offset']):
            return 'hedge'
        elif any(x in key_lower for x in ['risk', 'loss', 'profit', 'exposure', 'stop']):
            return 'risk'
        elif any(x in key_lower for x in ['signal', 's1', 's2', 's3', 's4', 's5', 's6', 's7', 's8']):
            return 'signal'
        elif any(x in key_lower for x in ['expiry', 'exit', 'square']):
            return 'expiry'
        elif any(x in key_lower for x in ['trade', 'trading', 'lot', 'position', 'auto']):
            return 'trading'
        elif any(x in key_lower for x in ['system', 'debug', 'log']):
            return 'system'
        else:
            return 'general'
    
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
    
    def verify_migration(self, conn: sqlite3.Connection):
        """Verify the migration was successful"""
        cursor = conn.cursor()
        
        # Count records in unified table
        cursor.execute("SELECT COUNT(*) FROM UnifiedSettings")
        unified_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT namespace) FROM UnifiedSettings")
        namespace_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT namespace, COUNT(*) as cnt FROM UnifiedSettings GROUP BY namespace")
        namespace_stats = cursor.fetchall()
        
        print("\n=== Migration Verification ===")
        print(f"Total settings migrated: {unified_count}")
        print(f"Number of namespaces: {namespace_count}")
        print("\nSettings per namespace:")
        for ns, cnt in namespace_stats:
            print(f"  {ns}: {cnt}")
        
        return unified_count > 0
    
    def cleanup_old_tables(self, conn: sqlite3.Connection):
        """Optional: Remove old tables after successful migration"""
        cursor = conn.cursor()
        
        old_tables = [
            'UserSettings', 'TradeConfiguration', 'SessionSettings',
            'SystemSettings', 'Settings', 'SignalStates', 'ExpiryConfig',
            'exit_timing_settings', 'expiry_settings'
        ]
        
        print("\n=== Cleaning Up Old Tables ===")
        for table in old_tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}_old")
                cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
                print(f"Renamed {table} to {table}_old")
            except sqlite3.OperationalError:
                pass
        
        conn.commit()
    
    def run_consolidation(self, cleanup: bool = False):
        """Run the complete consolidation process"""
        print("=== Starting Database Consolidation ===\n")
        
        # Step 1: Backup
        backup_file = self.backup_database()
        print(f"Backup completed: {backup_file}\n")
        
        # Step 2: Connect to database
        with sqlite3.connect(self.db_path) as conn:
            # Step 3: Create unified schema
            self.create_unified_schema(conn)
            
            # Step 4: Migrate all data
            print("\n=== Migrating Data ===")
            self.migrate_user_settings(conn)
            self.migrate_trade_configuration(conn)
            self.migrate_system_settings(conn)
            self.migrate_settings_table(conn)
            self.migrate_signal_states(conn)
            self.migrate_expiry_config(conn)
            self.migrate_audit_log(conn)
            
            # Step 5: Verify migration
            success = self.verify_migration(conn)
            
            # Step 6: Optional cleanup
            if success and cleanup:
                self.cleanup_old_tables(conn)
            elif success:
                print("\n[INFO] Old tables preserved. Run with cleanup=True to remove them.")
            
            if success:
                print("\n[SUCCESS] Database consolidation completed successfully!")
                print(f"[INFO] Backup saved at: {backup_file}")
            else:
                print("\n[ERROR] Migration verification failed. Please check the backup.")
        
        return success


def main():
    consolidator = DatabaseConsolidator()
    
    # Run consolidation without cleanup first (safer)
    success = consolidator.run_consolidation(cleanup=False)
    
    if success:
        print("\n[NEXT STEPS]")
        print("1. Test the unified settings with your application")
        print("2. If everything works, run with cleanup=True to remove old tables")
        print("3. Update unified_api_correct.py to use the new UnifiedSettings table")
        print("4. Remove duplicate API endpoints and service code")


if __name__ == "__main__":
    main()