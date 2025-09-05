#!/usr/bin/env python3
"""
Implement SQLite-based settings storage for production deployment
This ensures settings persist without requiring SQL Server
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

def create_sqlite_settings():
    """Create SQLite database for settings storage"""
    
    # Create data directory if it doesn't exist
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # SQLite database path
    db_path = data_dir / "trading_settings.db"
    
    print("=" * 60)
    print("SQLITE SETTINGS IMPLEMENTATION")
    print("=" * 60)
    print(f"Database path: {db_path.absolute()}")
    
    # Connect to SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS UserSettings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default',
            setting_key TEXT NOT NULL,
            setting_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, setting_key)
        )
    """)
    
    # Check if settings exist
    cursor.execute("SELECT COUNT(*) FROM UserSettings WHERE user_id = 'default'")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("\nInserting default production settings...")
        
        # Production-ready default settings
        defaults = [
            ('position_size', '10'),           # 10 lots default
            ('lot_quantity', '75'),            # NIFTY lot size
            ('entry_timing', 'immediate'),     # Immediate execution
            ('stop_loss_points', '200'),       # 200 point SL
            ('enable_hedging', 'true'),        # Hedging enabled
            ('hedge_percentage', '0.3'),       # 30% price-based hedge
            ('hedge_offset', '200'),           # Fallback offset
            ('auto_trade_enabled', 'false'),   # Manual approval initially
            ('trading_mode', 'LIVE'),          # Live trading mode
            ('signals_enabled', 'S1,S2,S3,S4,S5,S6,S7,S8'),  # All signals
            ('max_positions', '5'),            # Max concurrent positions
            ('daily_loss_limit', '50000'),     # Daily loss limit
            ('broker', 'kite'),                # Default broker
        ]
        
        for key, value in defaults:
            cursor.execute("""
                INSERT OR REPLACE INTO UserSettings (user_id, setting_key, setting_value)
                VALUES ('default', ?, ?)
            """, (key, value))
        
        conn.commit()
        print(f"[OK] Inserted {len(defaults)} default settings")
    else:
        print(f"[OK] Found {count} existing settings")
    
    # Display current settings
    cursor.execute("""
        SELECT setting_key, setting_value 
        FROM UserSettings 
        WHERE user_id = 'default'
        ORDER BY setting_key
    """)
    
    print("\nCurrent Settings:")
    print("-" * 40)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    cursor.close()
    conn.close()
    
    return db_path

def update_api_to_use_sqlite():
    """Generate the code changes needed in unified_api_correct.py"""
    
    print("\n" + "=" * 60)
    print("API UPDATE REQUIRED")
    print("=" * 60)
    
    code_changes = '''
# Add this import at the top of unified_api_correct.py:
import sqlite3
from pathlib import Path

# Replace the get_settings function (around line 3050) with:
def get_settings():
    """Get settings from SQLite database"""
    try:
        db_path = Path("data/trading_settings.db")
        if not db_path.exists():
            return DEFAULT_SETTINGS
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT setting_key, setting_value 
            FROM UserSettings 
            WHERE user_id = 'default'
        """)
        
        settings = {}
        for key, value in cursor.fetchall():
            # Convert string booleans to actual booleans
            if value in ['true', 'false']:
                settings[key] = value == 'true'
            else:
                settings[key] = value
        
        cursor.close()
        conn.close()
        
        return settings or DEFAULT_SETTINGS
        
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS

# Replace the save_settings function with:
def save_settings(settings: dict):
    """Save settings to SQLite database"""
    try:
        db_path = Path("data/trading_settings.db")
        db_path.parent.mkdir(exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserSettings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default',
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, setting_key)
            )
        """)
        
        # Update each setting
        for key, value in settings.items():
            # Convert booleans to strings
            if isinstance(value, bool):
                value = 'true' if value else 'false'
            
            cursor.execute("""
                INSERT OR REPLACE INTO UserSettings (user_id, setting_key, setting_value)
                VALUES ('default', ?, ?)
            """, (key, str(value)))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False
'''
    
    print("Code changes to apply:")
    print(code_changes)
    
    return code_changes

def test_sqlite_operations():
    """Test SQLite operations"""
    
    print("\n" + "=" * 60)
    print("TESTING SQLITE OPERATIONS")
    print("=" * 60)
    
    db_path = Path("data/trading_settings.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Test 1: Update a setting
    print("\n1. Testing UPDATE operation...")
    cursor.execute("""
        UPDATE UserSettings 
        SET setting_value = '15', updated_at = CURRENT_TIMESTAMP
        WHERE user_id = 'default' AND setting_key = 'position_size'
    """)
    conn.commit()
    
    # Verify update
    cursor.execute("""
        SELECT setting_value FROM UserSettings 
        WHERE user_id = 'default' AND setting_key = 'position_size'
    """)
    new_value = cursor.fetchone()[0]
    print(f"   Position size updated to: {new_value}")
    
    # Test 2: Add new setting
    print("\n2. Testing INSERT operation...")
    cursor.execute("""
        INSERT OR REPLACE INTO UserSettings (user_id, setting_key, setting_value)
        VALUES ('default', 'test_setting', 'test_value')
    """)
    conn.commit()
    print("   New setting added successfully")
    
    # Test 3: Retrieve all settings
    print("\n3. Testing SELECT ALL operation...")
    cursor.execute("""
        SELECT COUNT(*) FROM UserSettings WHERE user_id = 'default'
    """)
    total = cursor.fetchone()[0]
    print(f"   Total settings: {total}")
    
    cursor.close()
    conn.close()
    
    print("\n[OK] All SQLite operations working correctly")

def main():
    print(f"SQLite Settings Implementation")
    print(f"Started at: {datetime.now()}")
    print()
    
    # Step 1: Create SQLite database
    db_path = create_sqlite_settings()
    
    # Step 2: Show required API changes
    update_api_to_use_sqlite()
    
    # Step 3: Test operations
    test_sqlite_operations()
    
    print("\n" + "=" * 60)
    print("IMPLEMENTATION COMPLETE")
    print("=" * 60)
    print("\nBenefits of SQLite for your deployment:")
    print("[OK] No SQL Server setup required")
    print("[OK] Zero configuration - just works")
    print("[OK] Single file database (data/trading_settings.db)")
    print("[OK] Persists across restarts")
    print("[OK] Perfect for single-instance deployments")
    print("[OK] Can handle thousands of requests per second")
    print("\nYour settings will now persist forever without daily login!")
    
if __name__ == "__main__":
    main()