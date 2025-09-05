"""
Test Risk Management Settings Persistence
"""

import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("TESTING RISK MANAGEMENT PERSISTENCE")
print("=" * 60)

# Step 1: Save configuration with specific risk settings
config = {
    "num_lots": 15,
    "entry_timing": "immediate",
    "daily_loss_limit": 75000,  # Changed from default 50000
    "max_positions": 8,          # Changed from default 5
    "max_exposure": 300000,      # Changed from default 200000
    "hedge_enabled": True
}

print("\n1. Saving Risk Management Settings:")
print("-" * 40)
print(f"  Daily Loss Limit: {config['daily_loss_limit']}")
print(f"  Max Positions: {config['max_positions']}")
print(f"  Max Exposure: {config['max_exposure']}")

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
    
    print(f"  Loaded Daily Loss: {loaded.get('daily_loss_limit')}")
    print(f"  Loaded Max Positions: {loaded.get('max_positions')}")
    print(f"  Loaded Max Exposure: {loaded.get('max_exposure')}")
    
    # Verify values match
    print("\n3. Verification:")
    print("-" * 40)
    
    tests = [
        ("Daily Loss Limit", config['daily_loss_limit'], loaded.get('daily_loss_limit')),
        ("Max Positions", config['max_positions'], loaded.get('max_positions')),
        ("Max Exposure", config['max_exposure'], loaded.get('max_exposure'))
    ]
    
    all_pass = True
    for field, expected, actual in tests:
        if expected == actual:
            print(f"  [OK] {field}: {actual}")
        else:
            print(f"  [FAIL] {field}: Expected {expected}, Got {actual}")
            all_pass = False
    
    print("\n" + "=" * 60)
    if all_pass:
        print("SUCCESS: Risk Management settings persist correctly!")
        print("\nFrontend should now show:")
        print("  - Max Daily Loss: 75,000")
        print("  - Max Positions: 8")
        print("  - Max Exposure: 300,000")
        print("\nRefresh the page and verify these values load!")
    else:
        print("FAILURE: Some settings not persisting")
    print("=" * 60)
else:
    print(f"[FAIL] Load failed: {response.status_code}")