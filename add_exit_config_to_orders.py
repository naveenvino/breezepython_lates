"""
Add exit configuration columns to OrderTracking table
This ensures each trade remembers its own exit configuration
"""
import sqlite3

# Connect to database
conn = sqlite3.connect('data/trading_settings.db')
cursor = conn.cursor()

print("=" * 60)
print("ADDING EXIT CONFIGURATION TO ORDERTRACKING TABLE")
print("=" * 60)

# Check current columns
cursor.execute("PRAGMA table_info(OrderTracking)")
existing_columns = [col[1] for col in cursor.fetchall()]
print(f"Current columns: {existing_columns}")

# Add new columns if they don't exist
columns_to_add = [
    ("exit_config_day", "INTEGER", "NULL"),  # 0=expiry, 1-7=T+N days
    ("exit_config_time", "TEXT", "NULL"),    # HH:MM format
]

for col_name, col_type, default in columns_to_add:
    if col_name not in existing_columns:
        try:
            alter_sql = f"ALTER TABLE OrderTracking ADD COLUMN {col_name} {col_type} DEFAULT {default}"
            cursor.execute(alter_sql)
            print(f"Added column: {col_name}")
        except Exception as e:
            print(f"Error adding {col_name}: {e}")
    else:
        print(f"Column {col_name} already exists")

# Commit changes
conn.commit()

# Verify the changes
cursor.execute("PRAGMA table_info(OrderTracking)")
final_columns = [col[1] for col in cursor.fetchall()]
print(f"\nFinal columns: {final_columns}")

# Check if new columns were added
if 'exit_config_day' in final_columns and 'exit_config_time' in final_columns:
    print("\nSUCCESS: Exit configuration columns added to OrderTracking")
    print("Each trade will now store its own exit timing configuration")
else:
    print("\nERROR: Failed to add all columns")

conn.close()
print("=" * 60)