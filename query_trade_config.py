"""
Direct SQL query to fetch all data from TradeConfiguration table
"""
import sqlite3
from pathlib import Path
import json

db_path = Path("data/trading_settings.db")

# Connect to database
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row  # This enables column access by name
cursor = conn.cursor()

# Execute SELECT query
cursor.execute("SELECT * FROM TradeConfiguration")

# Fetch all rows
rows = cursor.fetchall()

print("=" * 80)
print("SELECT * FROM TradeConfiguration")
print("=" * 80)

for row in rows:
    print(f"\nRow {row['id']}:")
    print("-" * 40)
    
    # Convert row to dictionary and print each field
    row_dict = dict(row)
    for key, value in row_dict.items():
        # Format the output nicely
        if key in ['active_signals', 'weekday_config'] and value:
            try:
                # Parse JSON fields
                parsed = json.loads(value)
                print(f"  {key:30} = {parsed}")
            except:
                print(f"  {key:30} = {value}")
        else:
            print(f"  {key:30} = {value}")

# Also show as a table format
print("\n" + "=" * 80)
print("TABLE FORMAT:")
print("=" * 80)

# Get column names
column_names = [description[0] for description in cursor.description]

# Print header
print(" | ".join(f"{col:15}" for col in column_names[:5]))  # First 5 columns
print("-" * 80)

# Reset cursor
cursor.execute("SELECT * FROM TradeConfiguration")
for row in cursor.fetchall():
    print(" | ".join(f"{str(row[col])[:15]:15}" for col in column_names[:5]))

conn.close()

print("\n" + "=" * 80)
print("You can also use DB Browser for SQLite (GUI tool) to view this data")
print("Database location: data/trading_settings.db")
print("=" * 80)