"""
Create OrderTracking table for webhook position management
This table links main and hedge positions together for proper exit handling
"""
import sqlite3
from datetime import datetime

def create_order_tracking_table():
    conn = sqlite3.connect('data/trading_settings.db')
    cursor = conn.cursor()
    
    # Create OrderTracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS OrderTracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_id TEXT UNIQUE NOT NULL,
            signal TEXT NOT NULL,
            main_strike INTEGER NOT NULL,
            main_symbol TEXT NOT NULL,
            main_order_id TEXT,
            main_quantity INTEGER NOT NULL,
            hedge_strike INTEGER,
            hedge_symbol TEXT,
            hedge_order_id TEXT,
            hedge_quantity INTEGER,
            option_type TEXT NOT NULL,
            lots INTEGER NOT NULL,
            entry_time TIMESTAMP NOT NULL,
            exit_time TIMESTAMP,
            status TEXT DEFAULT 'pending',
            entry_price_main REAL,
            entry_price_hedge REAL,
            exit_price_main REAL,
            exit_price_hedge REAL,
            pnl REAL,
            exit_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_webhook_id ON OrderTracking(webhook_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_signal_strike ON OrderTracking(signal, main_strike)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON OrderTracking(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_entry_time ON OrderTracking(entry_time DESC)')
    
    conn.commit()
    print("OrderTracking table created successfully")
    
    # Verify table structure
    cursor.execute("PRAGMA table_info(OrderTracking)")
    columns = cursor.fetchall()
    
    print("\nTable structure:")
    print("-" * 60)
    for col in columns:
        print(f"  {col[1]:20} {col[2]:15} {'NOT NULL' if col[3] else 'NULL':10} {f'DEFAULT {col[4]}' if col[4] else ''}")
    
    conn.close()
    
    return True

if __name__ == "__main__":
    create_order_tracking_table()
    
    # Show existing data if any
    conn = sqlite3.connect('data/trading_settings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM OrderTracking")
    count = cursor.fetchone()[0]
    print(f"\nCurrent records in OrderTracking: {count}")
    
    if count > 0:
        cursor.execute("SELECT webhook_id, signal, main_strike, status, entry_time FROM OrderTracking ORDER BY entry_time DESC LIMIT 5")
        recent = cursor.fetchall()
        print("\nRecent orders:")
        for order in recent:
            print(f"  {order[0]}: {order[1]} @ {order[2]} - Status: {order[3]} - Time: {order[4]}")
    
    conn.close()