"""
Check stop loss configuration in database
"""
import sqlite3

# Connect to database
conn = sqlite3.connect('data/trading_settings.db')
cursor = conn.cursor()

print("=" * 60)
print("STOP LOSS CONFIGURATION IN DATABASE")
print("=" * 60)

# Check TradeConfiguration table
try:
    cursor.execute("""
        SELECT * FROM TradeConfiguration 
        WHERE is_active = 1
    """)
    config = cursor.fetchone()
    
    if config:
        columns = [description[0] for description in cursor.description]
        print("\nActive Trade Configuration:")
        for i, col in enumerate(columns):
            if 'stop' in col.lower() or 'loss' in col.lower() or 'sl' in col.lower():
                print(f"  {col}: {config[i]}")
    else:
        print("No active configuration found")
        
except Exception as e:
    print(f"Error checking TradeConfiguration: {e}")

# Check for stop loss related columns
print("\n" + "=" * 60)
print("CHECKING FOR STOP LOSS COLUMNS:")
print("=" * 60)

try:
    cursor.execute("PRAGMA table_info(TradeConfiguration)")
    columns = cursor.fetchall()
    
    stop_loss_columns = []
    for col in columns:
        col_name = col[1]
        if 'stop' in col_name.lower() or 'loss' in col_name.lower() or 'sl' in col_name.lower():
            stop_loss_columns.append(col_name)
    
    if stop_loss_columns:
        print(f"Found stop loss columns: {stop_loss_columns}")
        
        # Get values for these columns
        for col in stop_loss_columns:
            cursor.execute(f"SELECT {col} FROM TradeConfiguration WHERE is_active = 1")
            value = cursor.fetchone()
            if value:
                print(f"  {col} = {value[0]}")
    else:
        print("No stop loss columns found in TradeConfiguration")
        
except Exception as e:
    print(f"Error: {e}")

# Check OrderTracking table for stop loss info
print("\n" + "=" * 60)
print("CHECKING ORDER TRACKING FOR STOP LOSS:")
print("=" * 60)

try:
    cursor.execute("""
        SELECT webhook_id, signal, main_strike, stop_loss_price, status
        FROM OrderTracking
        ORDER BY created_at DESC
        LIMIT 5
    """)
    orders = cursor.fetchall()
    
    if orders:
        print("Recent orders with stop loss info:")
        for order in orders:
            print(f"  ID: {order[0][:20]}... Signal: {order[1]}, Strike: {order[2]}, SL: {order[3]}, Status: {order[4]}")
    else:
        print("No orders found in OrderTracking")
        
except Exception as e:
    print(f"OrderTracking table might not exist or error: {e}")

# Check for any settings table
print("\n" + "=" * 60)
print("CHECKING FOR SETTINGS TABLES:")
print("=" * 60)

cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name LIKE '%setting%'
""")
settings_tables = cursor.fetchall()

if settings_tables:
    for table in settings_tables:
        print(f"Found settings table: {table[0]}")
        try:
            cursor.execute(f"SELECT * FROM {table[0]} WHERE key LIKE '%stop%' OR key LIKE '%loss%' LIMIT 5")
            settings = cursor.fetchall()
            if settings:
                for setting in settings:
                    print(f"  {setting}")
        except:
            pass

conn.close()
print("\n" + "=" * 60)