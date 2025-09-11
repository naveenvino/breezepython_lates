"""
Remove daily_loss_limit and max_loss_per_trade columns from database
"""
import sqlite3

# Connect to database
conn = sqlite3.connect('data/trading_settings.db')
cursor = conn.cursor()

print("=" * 60)
print("REMOVING UNWANTED COLUMNS FROM DATABASE")
print("=" * 60)

# Check if columns exist in TradeConfiguration
try:
    cursor.execute("PRAGMA table_info(TradeConfiguration)")
    columns = cursor.fetchall()
    
    existing_columns = [col[1] for col in columns]
    print(f"\nCurrent columns in TradeConfiguration: {existing_columns}")
    
    columns_to_remove = ['daily_loss_limit', 'max_loss_per_trade']
    columns_present = [col for col in columns_to_remove if col in existing_columns]
    
    if columns_present:
        print(f"\nColumns to remove: {columns_present}")
        
        # SQLite doesn't support DROP COLUMN directly, need to recreate table
        # First, get the current table structure
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='TradeConfiguration'")
        create_sql = cursor.fetchone()[0]
        print(f"\nCurrent table structure:\n{create_sql}")
        
        # Create new table without the unwanted columns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TradeConfiguration_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default',
                config_name TEXT NOT NULL DEFAULT 'default',
                num_lots INTEGER DEFAULT 5,
                max_positions INTEGER DEFAULT 10,
                trailing_stop_enabled INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Copy data from old table to new table (excluding unwanted columns)
        cursor.execute("""
            INSERT INTO TradeConfiguration_new (
                id, user_id, config_name, num_lots, max_positions, 
                trailing_stop_enabled, is_active, created_at, updated_at
            )
            SELECT 
                id, user_id, config_name, num_lots, max_positions,
                trailing_stop_enabled, is_active, created_at, updated_at
            FROM TradeConfiguration
        """)
        
        # Drop old table and rename new table
        cursor.execute("DROP TABLE TradeConfiguration")
        cursor.execute("ALTER TABLE TradeConfiguration_new RENAME TO TradeConfiguration")
        
        conn.commit()
        print("\n✓ Successfully removed columns from TradeConfiguration")
        
    else:
        print(f"\nColumns {columns_to_remove} not found in TradeConfiguration - already removed")
        
except Exception as e:
    print(f"Error modifying TradeConfiguration: {e}")
    conn.rollback()

# Also remove from UnifiedSettings if present
print("\n" + "=" * 60)
print("CHECKING UNIFIEDSETTINGS TABLE")
print("=" * 60)

try:
    # Remove entries from UnifiedSettings
    cursor.execute("""
        DELETE FROM UnifiedSettings 
        WHERE key IN ('daily_loss_limit', 'max_loss_per_trade')
    """)
    
    deleted_count = cursor.rowcount
    
    if deleted_count > 0:
        conn.commit()
        print(f"✓ Removed {deleted_count} entries from UnifiedSettings")
    else:
        print("No entries found in UnifiedSettings to remove")
        
except Exception as e:
    print(f"Error cleaning UnifiedSettings: {e}")

# Also remove from Settings table if present
print("\n" + "=" * 60)
print("CHECKING SETTINGS TABLE")
print("=" * 60)

try:
    cursor.execute("""
        DELETE FROM Settings 
        WHERE key IN ('maxLossPerDay', 'maxLossPerTrade', 'daily_loss_limit', 'max_loss_per_trade')
    """)
    
    deleted_count = cursor.rowcount
    
    if deleted_count > 0:
        conn.commit()
        print(f"✓ Removed {deleted_count} entries from Settings")
    else:
        print("No entries found in Settings to remove")
        
except Exception as e:
    print(f"Error cleaning Settings: {e}")

# Verify changes
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)

try:
    cursor.execute("PRAGMA table_info(TradeConfiguration)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    print(f"Final columns in TradeConfiguration: {column_names}")
    
    if 'daily_loss_limit' not in column_names and 'max_loss_per_trade' not in column_names:
        print("\n✅ SUCCESS: Unwanted columns have been removed from database")
    else:
        print("\n❌ WARNING: Some columns may still exist")
        
except Exception as e:
    print(f"Error during verification: {e}")

conn.close()
print("\n" + "=" * 60)