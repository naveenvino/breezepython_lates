"""
Check Entry Timing Field
"""

import sqlite3
import json

# Check database structure
conn = sqlite3.connect('data/trading_settings.db')
cursor = conn.cursor()

print("=" * 60)
print("CHECKING ENTRY TIMING FIELD")
print("=" * 60)

print("\n1. Database Table Structure:")
print("-" * 40)
cursor.execute('PRAGMA table_info(TradeConfiguration)')
columns = cursor.fetchall()
for col in columns:
    if 'entry' in col[1].lower() or 'timing' in col[1].lower():
        print(f"  Column: {col[1]} - Type: {col[2]} - Default: {col[4]}")

print("\n2. Current Saved Configuration:")
print("-" * 40)
cursor.execute("""
    SELECT num_lots, entry_timing, hedge_enabled, profit_lock_enabled 
    FROM TradeConfiguration 
    WHERE user_id = 'default' AND config_name = 'default'
""")
row = cursor.fetchone()
if row:
    print(f"  Lots: {row[0]}")
    print(f"  Entry Timing: {row[1]} <-- THIS IS IMPORTANT!")
    print(f"  Hedge Enabled: {row[2]}")
    print(f"  Profit Lock: {row[3]}")
else:
    print("  No saved configuration found")

print("\n3. What Entry Timing Means:")
print("-" * 40)
print("  'immediate': Enter trade as soon as signal arrives")
print("  'delayed': Wait for second candle after signal (typically 11:15 AM)")
print("  - This is CRITICAL for backtest accuracy")
print("  - Affects entry price and timing")

print("\n4. Verification:")
print("-" * 40)

# Test save and load
from src.services.trade_config_service import get_trade_config_service

service = get_trade_config_service()

# Save with entry_timing
test_config = {
    'num_lots': 15,
    'entry_timing': 'delayed',  # Testing delayed entry
    'hedge_enabled': True
}

result = service.save_trade_config(test_config)
print(f"  Save result: {result['success']}")

# Load it back
loaded = service.load_trade_config()
print(f"  Loaded entry_timing: {loaded.get('entry_timing')}")

if loaded.get('entry_timing') == 'delayed':
    print("\n[OK] Entry timing is properly saved and loaded!")
else:
    print("\n[FAIL] Entry timing not working correctly!")

print("\n5. Impact if Not Saved:")
print("-" * 40)
print("  - Always defaults to 'immediate'")
print("  - May enter trades too early")
print("  - Backtest results won't match live trading")
print("  - CRITICAL for accurate signal execution")

conn.close()

print("\n" + "=" * 60)
print("ENTRY TIMING IS MANDATORY FOR ACCURATE TRADING")
print("=" * 60)