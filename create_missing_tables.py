"""
Create missing database tables for complete integration
"""

import sqlite3
from pathlib import Path
import json
from datetime import datetime

def create_missing_tables():
    """Create the missing Settings, SignalStates, and ExpiryConfig tables"""
    
    db_path = Path("data/trading_settings.db")
    db_path.parent.mkdir(exist_ok=True)
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Create Settings table for general settings storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created Settings table")
        
        # Create SignalStates table for signal configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SignalStates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_name TEXT NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT 0,
                description TEXT,
                last_triggered TIMESTAMP,
                trigger_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created SignalStates table")
        
        # Create ExpiryConfig table for expiry configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ExpiryConfig (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekday TEXT NOT NULL UNIQUE,
                expiry_type TEXT DEFAULT 'current',
                exit_day TEXT DEFAULT 'expiry',
                exit_time TEXT DEFAULT '15:15',
                auto_square_off BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created ExpiryConfig table")
        
        # Insert default signal states
        signals = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
        for signal in signals:
            cursor.execute("""
                INSERT OR IGNORE INTO SignalStates (signal_name, is_active, description)
                VALUES (?, ?, ?)
            """, (signal, 1, f"Signal {signal} - Auto-generated"))
        print(f"[OK] Inserted {len(signals)} default signal states")
        
        # Insert default expiry config for weekdays
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Tuesday', 'Friday']
        for weekday in weekdays:
            cursor.execute("""
                INSERT OR IGNORE INTO ExpiryConfig (weekday, expiry_type)
                VALUES (?, ?)
            """, (weekday, 'current' if weekday != 'Friday' else 'next'))
        print(f"[OK] Inserted {len(weekdays)} default expiry configurations")
        
        # Insert some default settings
        default_settings = [
            ('tradingMode', 'LIVE', 'trading'),
            ('autoTradeEnabled', 'false', 'trading'),
            ('numLots', '1', 'trading'),
            ('entryTiming', 'immediate', 'trading'),
            ('maxLossPerDay', '50000', 'risk'),
            ('maxPositions', '5', 'risk'),
            ('stopLossPercent', '30', 'risk'),
            ('maxLossPerTrade', '20000', 'risk'),
            ('maxExposure', '200000', 'risk'),
            ('hedgeEnabled', 'true', 'hedge'),
            ('hedgeMethod', 'percentage', 'hedge'),
            ('hedgePercent', '30', 'hedge'),
            ('hedgeOffset', '200', 'hedge')
        ]
        
        for key, value, category in default_settings:
            cursor.execute("""
                INSERT OR IGNORE INTO Settings (key, value, category)
                VALUES (?, ?, ?)
            """, (key, value, category))
        print(f"[OK] Inserted {len(default_settings)} default settings")
        
        conn.commit()
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print("\n[INFO] Database tables now available:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table}: {count} records")
    
    print("\n[SUCCESS] All missing tables created successfully!")
    return True

if __name__ == "__main__":
    try:
        create_missing_tables()
    except Exception as e:
        print(f"[ERROR] Error creating tables: {str(e)}")
        import traceback
        traceback.print_exc()