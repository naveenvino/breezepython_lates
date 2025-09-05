"""
Test saving configuration without daily_loss_limit field
"""

import requests
import json

# Test configuration without daily_loss_limit
test_config = {
    "num_lots": 10,
    "entry_timing": "immediate",
    "hedge_enabled": True,
    "hedge_method": "percentage",
    "hedge_percent": 30.0,
    "hedge_offset": 200,
    "profit_lock_enabled": True,
    "profit_target": 10.0,
    "profit_lock": 5.0,
    "trailing_stop_enabled": False,
    "trail_percent": 1.0,
    "auto_trade_enabled": False,
    "active_signals": ["S1", "S2"],
    "daily_profit_target": 100000,
    "max_loss_per_trade": 20000,
    "position_size_mode": "fixed"
}

print("Testing save configuration without daily_loss_limit...")
print(f"Config: {json.dumps(test_config, indent=2)}")

# Save configuration (wrapped in config object as expected by API)
url = "http://localhost:8000/api/trade-config/save"
wrapped_config = {
    "config": test_config,
    "user_id": "default",
    "config_name": "default"
}
response = requests.post(url, json=wrapped_config)

print(f"\nSave Response Status: {response.status_code}")
print(f"Save Response: {json.dumps(response.json(), ensure_ascii=True)}")

# Load configuration to verify
load_url = "http://localhost:8000/api/trade-config/load"
load_response = requests.get(load_url)

print(f"\nLoad Response Status: {load_response.status_code}")
loaded_config = load_response.json()

# Check if daily_loss_limit is absent
if 'daily_loss_limit' not in loaded_config:
    print("[OK] SUCCESS: daily_loss_limit is NOT in loaded configuration")
else:
    print("[FAIL] daily_loss_limit still exists in loaded configuration")

print(f"\nLoaded configuration keys: {list(loaded_config.keys())}")

# Verify mandatory fields
if loaded_config.get('num_lots') == 10:
    print("[OK] num_lots saved correctly")
if loaded_config.get('entry_timing') == 'immediate':
    print("[OK] entry_timing saved correctly")
if loaded_config.get('active_signals') == ["S1", "S2"]:
    print("[OK] active_signals saved correctly")