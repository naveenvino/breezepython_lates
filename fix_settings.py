import sqlite3
import json

# Connect to database
conn = sqlite3.connect('data/trading_settings.db')
cursor = conn.cursor()

# Proper weekday configuration  
weekday_config = {
    "monday": "next",  # Use next Tuesday
    "tuesday": "next",  # Use next Tuesday (since current expires today)
    "wednesday": "next",  # Use next Tuesday
    "thursday": "next",  # Use next Tuesday
    "friday": "next"  # Use next Tuesday
}

# Update the default configuration with correct values
cursor.execute("""
    UPDATE TradeConfiguration 
    SET weekday_config = ?,
        exit_time = '15:25',
        exit_day_offset = 0
    WHERE user_id = 'default' AND config_name = 'default'
""", (json.dumps(weekday_config),))

conn.commit()
print(f"Updated {cursor.rowcount} rows")

# Verify the update
cursor.execute("""
    SELECT num_lots, amo_enabled, profit_lock_enabled, 
           exit_day_offset, exit_time, weekday_config 
    FROM TradeConfiguration 
    WHERE user_id = 'default' AND config_name = 'default'
""")
row = cursor.fetchone()
print(f"\nCurrent settings:")
print(f"  Lots: {row[0]}")
print(f"  AMO: {row[1]}")
print(f"  Profit Lock: {row[2]}")
print(f"  Exit Day: T+{row[3]}")
print(f"  Exit Time: {row[4]}")
print(f"  Weekday Config: {row[5]}")

conn.close()
print("\nSettings fixed successfully!")