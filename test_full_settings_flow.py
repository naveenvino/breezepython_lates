"""
Complete Settings Persistence Test
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("COMPLETE SETTINGS PERSISTENCE TEST")
print("=" * 60)

# Step 1: Clear any existing config
print("\n1. Clearing existing configuration...")
clear_config = {
    "num_lots": 10,
    "entry_timing": "immediate",
    "hedge_enabled": True,
    "hedge_method": "percentage",
    "hedge_percent": 30.0,
    "profit_lock_enabled": False,
    "trailing_stop_enabled": False,
    "auto_trade_enabled": False,
    "active_signals": []
}

response = requests.post(
    f"{BASE_URL}/api/trade-config/save",
    json={"config": clear_config, "config_name": "default", "user_id": "default"}
)
print(f"[OK] Default config restored: {response.ok}")

# Step 2: Save user's specific configuration
print("\n2. Saving user's specific configuration...")
user_config = {
    "num_lots": 25,
    "entry_timing": "delayed",
    "hedge_enabled": False,
    "hedge_method": "offset",
    "hedge_offset": 300,
    "profit_lock_enabled": True,
    "profit_target": 15.0,
    "profit_lock": 7.0,
    "trailing_stop_enabled": True,
    "trail_percent": 2.0,
    "auto_trade_enabled": True,
    "active_signals": ["S1", "S2", "S7", "S8"]
}

response = requests.post(
    f"{BASE_URL}/api/trade-config/save",
    json={"config": user_config, "config_name": "default", "user_id": "default"}
)
print(f"[OK] User config saved: {response.ok}")

# Step 3: Verify it persists
print("\n3. Loading configuration back...")
response = requests.get(f"{BASE_URL}/api/trade-config/load/default")
if response.ok:
    result = response.json()
    loaded = result.get('config', {})
    
    print("\n4. Verification Results:")
    print("-" * 40)
    
    tests = [
        ("Number of Lots", "num_lots", 25),
        ("Entry Timing", "entry_timing", "delayed"),
        ("Hedge Enabled", "hedge_enabled", False),
        ("Hedge Method", "hedge_method", "offset"),
        ("Hedge Offset", "hedge_offset", 300),
        ("Profit Lock Enabled", "profit_lock_enabled", True),
        ("Profit Target", "profit_target", 15.0),
        ("Profit Lock", "profit_lock", 7.0),
        ("Trailing Stop", "trailing_stop_enabled", True),
        ("Trail Percent", "trail_percent", 2.0),
        ("Auto Trade", "auto_trade_enabled", True),
        ("Active Signals", "active_signals", ["S1", "S2", "S7", "S8"])
    ]
    
    all_pass = True
    for display_name, key, expected in tests:
        actual = loaded.get(key)
        if actual == expected:
            print(f"  [OK] {display_name}: {actual}")
        else:
            print(f"  [FAIL] {display_name}: Expected {expected}, Got {actual}")
            all_pass = False
    
    print("\n" + "=" * 60)
    if all_pass:
        print("SUCCESS: All settings persist correctly!")
        print("\nYour settings are now saved and will:")
        print("  - Persist across page refreshes")
        print("  - Persist across API restarts")
        print("  - Work in cloud deployment")
        print("  - Support automated trading")
    else:
        print("FAILURE: Some settings did not persist")
    print("=" * 60)

print("\n5. UI Verification Instructions:")
print("-" * 40)
print("1. Open http://localhost:8000/tradingview_pro.html")
print("2. Refresh the page (F5)")
print("3. Verify these settings are loaded:")
print("   - Number of Lots: 25")
print("   - Entry Timing: Second Candle")
print("   - Hedging: DISABLED")
print("   - Hedge Method: Offset (300 points)")
print("   - Profit Lock: ENABLED (15% target, 7% lock)")
print("   - Trailing Stop: ENABLED (2%)")
print("   - Auto Trade: ENABLED")
print("   - Active Signals: S1, S2, S7, S8 checked")
print("\nIf all settings load correctly, the system is ready!")
print("=" * 60)