"""
Ensure SQLite settings table exists with proper schema
"""

import sqlite3
import os
from datetime import datetime

def ensure_settings_table():
    db_path = 'data/trading_settings.db'
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create settings table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SystemSettings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create index for better performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_category 
        ON SystemSettings(category)
    """)
    
    # Insert default settings if not exist
    default_settings = [
        ('trading_auto_trade_enabled', 'false', 'trading'),
        ('trading_default_lots', '10', 'trading'),
        ('trading_default_strike_offset', '200', 'trading'),
        ('risk_max_loss_per_day', '50000', 'risk'),
        ('risk_max_positions', '5', 'risk'),
        ('risk_stop_loss_percent', '30', 'risk'),
        ('webhook_secret', 'tradingview-webhook-secret-key-2025', 'webhook'),
        ('expiry_exit_enabled', 'true', 'expiry'),
        ('expiry_exit_time', '15:15', 'expiry'),
        ('kill_switch_enabled', 'true', 'safety'),
        ('kill_switch_state', 'READY', 'safety')
    ]
    
    for key, value, category in default_settings:
        cursor.execute("""
            INSERT OR IGNORE INTO SystemSettings (setting_key, setting_value, category)
            VALUES (?, ?, ?)
        """, (key, value, category))
    
    conn.commit()
    
    # Verify table structure
    cursor.execute("PRAGMA table_info(SystemSettings)")
    columns = cursor.fetchall()
    
    print("SQLite Settings Table Schema:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Show current settings
    cursor.execute("SELECT category, COUNT(*) FROM SystemSettings GROUP BY category")
    counts = cursor.fetchall()
    
    print("\nSettings by Category:")
    for category, count in counts:
        print(f"  - {category}: {count} settings")
    
    conn.close()
    print("\n✅ SQLite settings table ready!")

if __name__ == "__main__":
    ensure_settings_table()