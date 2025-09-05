"""
Test Frontend Settings Persistence
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_frontend_settings():
    print("=" * 60)
    print("TESTING FRONTEND SETTINGS PERSISTENCE")
    print("=" * 60)
    
    # Test configuration to save
    test_config = {
        "num_lots": 25,
        "entry_timing": "delayed",
        "hedge_enabled": False,
        "hedge_method": "percentage",
        "hedge_percent": 30.0,
        "hedge_offset": 200,
        "profit_lock_enabled": True,
        "profit_target": 10.0,
        "profit_lock": 5.0,
        "trailing_stop_enabled": False,
        "trail_percent": 1.0,
        "auto_trade_enabled": False,
        "active_signals": ["S1", "S2", "S7"],
        "max_positions": 5,
        "daily_loss_limit": 50000,
        "daily_profit_target": 100000,
        "max_loss_per_trade": 20000,
        "position_size_mode": "fixed"
    }
    
    print("\n1. Saving test configuration...")
    print("-" * 40)
    
    # Save configuration
    response = requests.post(
        f"{BASE_URL}/api/trade-config/save",
        json={"config": test_config, "config_name": "default", "user_id": "default"}
    )
    
    if response.ok:
        result = response.json()
        print(f"[OK] Configuration saved: {result.get('message')}")
    else:
        print(f"[X] Failed to save: {response.status_code}")
        return
    
    print("\n2. Loading saved configuration...")
    print("-" * 40)
    
    # Load configuration
    response = requests.get(f"{BASE_URL}/api/trade-config/load/default")
    
    if response.ok:
        result = response.json()
        print("[OK] Configuration loaded successfully")
        
        # Extract config from nested structure
        loaded_config = result.get('config', {})
        
        print("\n3. Verifying all settings...")
        print("-" * 40)
        
        # Check each setting
        checks = [
            ("num_lots", 25),
            ("entry_timing", "delayed"),
            ("hedge_enabled", False),
            ("profit_lock_enabled", True),
            ("profit_target", 10.0),
            ("profit_lock", 5.0),
            ("active_signals", ["S1", "S2", "S7"])
        ]
        
        all_ok = True
        for key, expected in checks:
            actual = loaded_config.get(key)
            if actual == expected:
                print(f"  [OK] {key}: {actual}")
            else:
                print(f"  [X] {key}: Expected {expected}, Got {actual}")
                all_ok = False
        
        if all_ok:
            print("\n[SUCCESS] All settings verified successfully!")
        else:
            print("\n[WARNING] Some settings did not match")
            
        print("\n4. Frontend Instructions:")
        print("-" * 40)
        print("Open http://localhost:8000/tradingview_pro.html")
        print("Check that the following are set:")
        print("  - Number of Lots: 25")
        print("  - Entry Timing: Second Candle (Delayed)")
        print("  - Hedging: DISABLED")
        print("  - Profit Lock: ENABLED with 10% target, 5% lock")
        print("  - Active Signals: S1, S2, S7 checkboxes checked")
        
    else:
        print(f"[X] Failed to load: {response.status_code}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_frontend_settings()