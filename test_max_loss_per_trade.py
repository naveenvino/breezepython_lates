"""
Test max_loss_per_trade field persistence
"""

import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("TESTING MAX LOSS PER TRADE PERSISTENCE")
print("=" * 60)

# Step 1: Save configuration with max_loss_per_trade
config = {
    "num_lots": 15,
    "daily_loss_limit": 75000,
    "max_loss_per_trade": 30000,  # Changed from default 20000
    "max_positions": 8,
    "max_exposure": 300000,
}

print("\n1. Saving Configuration with max_loss_per_trade:")
print("-" * 40)
print(f"  Max Loss Per Trade: Rs.{config['max_loss_per_trade']:,}")

response = requests.post(
    f"{BASE_URL}/api/trade-config/save",
    json={"config": config}
)

if response.ok:
    print("\n[OK] Settings saved successfully")
else:
    print(f"\n[FAIL] Save failed: {response.json()}")
    exit(1)

# Step 2: Load configuration back
print("\n2. Loading Settings Back:")
print("-" * 40)

response = requests.get(f"{BASE_URL}/api/trade-config/load/default")
if response.ok:
    result = response.json()
    loaded = result.get('config', {})
    
    print(f"  Loaded Max Loss Per Trade: Rs.{loaded.get('max_loss_per_trade', 0):,}")
    
    # Verify value matches
    print("\n3. Verification:")
    print("-" * 40)
    
    expected = config['max_loss_per_trade']
    actual = loaded.get('max_loss_per_trade')
    
    if expected == actual:
        print(f"  [OK] Max Loss Per Trade: Rs.{actual:,}")
        print("\n" + "=" * 60)
        print("SUCCESS: max_loss_per_trade persists correctly!")
        print("\nFrontend should now show:")
        print(f"  - Max Loss Per Trade: Rs.30,000")
        print("  - This will auto-exit positions exceeding this loss")
        print("\nRefresh the page and verify this value loads!")
    else:
        print(f"  [FAIL] Expected Rs.{expected:,}, Got Rs.{actual:,}")
        print("\nFAILURE: max_loss_per_trade not persisting")
    print("=" * 60)
else:
    print(f"[FAIL] Load failed: {response.status_code}")