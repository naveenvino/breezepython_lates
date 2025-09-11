"""
Test to show how exit configuration is stored with each trade
"""
import sqlite3
from datetime import datetime

print("=" * 60)
print("EXIT CONFIGURATION STORAGE TEST")
print("=" * 60)

# Connect to database
conn = sqlite3.connect('data/trading_settings.db')
cursor = conn.cursor()

# Show current exit timing settings
print("\n1. CURRENT EXIT TIMING CONFIGURATION:")
print("-" * 40)
cursor.execute("SELECT exit_day_offset, exit_time FROM exit_timing_settings ORDER BY updated_at DESC LIMIT 1")
result = cursor.fetchone()
if result:
    print(f"   Current setting: T+{result[0]} at {result[1]}")
else:
    print("   No active configuration")

# Show recent orders with their stored exit configuration
print("\n2. RECENT ORDERS WITH STORED EXIT CONFIG:")
print("-" * 40)
cursor.execute("""
    SELECT 
        webhook_id,
        signal,
        main_strike,
        created_at,
        exit_config_day,
        exit_config_time,
        status
    FROM OrderTracking
    ORDER BY created_at DESC
    LIMIT 5
""")

orders = cursor.fetchall()

if orders:
    for order in orders:
        webhook_id = order[0][:20] + "..." if len(order[0]) > 20 else order[0]
        signal = order[1]
        strike = order[2]
        created = order[3]
        exit_day = order[4]
        exit_time = order[5]
        status = order[6]
        
        print(f"\n   Order: {webhook_id}")
        print(f"   Signal: {signal}, Strike: {strike}")
        print(f"   Entry: {created}")
        if exit_day is not None and exit_time is not None:
            print(f"   Exit Config (stored at entry): T+{exit_day} at {exit_time}")
        else:
            print(f"   Exit Config: Not stored (old order)")
        print(f"   Status: {status}")
else:
    print("   No orders found")

# Demonstrate the scenario
print("\n3. SCENARIO DEMONSTRATION:")
print("-" * 40)
print("""
   BEFORE Trade Entry:
   - Exit config in UI: T+2 at 14:15
   - User places trade via webhook
   - System stores: exit_config_day=2, exit_config_time='14:15'
   
   AFTER Trade Entry:
   - User changes UI config to: Expiry at 15:15
   - This NEW config applies to NEW trades only
   - Existing trade still uses: T+2 at 14:15 (stored at entry)
   
   RESULT:
   - Each trade remembers its own exit configuration
   - Changes in UI don't affect existing positions
   - Prevents confusion and ensures consistency
""")

# Show how it works in the code
print("\n4. HOW IT WORKS IN THE CODE:")
print("-" * 40)
print("""
   A. At Entry (unified_api_correct.py line 6826):
      - Read current exit_timing_settings
      - Store in OrderTracking with the order:
        • exit_config_day (0=expiry, 1-7=T+N)
        • exit_config_time (HH:MM format)
   
   B. At Exit Check (live_stoploss_monitor.py):
      - Read exit config FROM OrderTracking (not settings)
      - Use stored values to calculate exit time
      - Trigger exit based on STORED config
   
   C. Key Benefits:
      - Trade-specific configuration
      - No retroactive changes
      - Clear audit trail
""")

conn.close()
print("=" * 60)