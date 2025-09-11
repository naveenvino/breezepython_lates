import requests
import json
import time

def test_save_and_load_config():
    """Test saving and loading configuration including expiry and exit timing"""
    
    BASE_URL = "http://localhost:8000"
    
    print("Testing Configuration Persistence")
    print("=" * 60)
    
    # Test configuration with expiry day exit
    test_config = {
        "num_lots": 15,
        "entry_timing": "second_candle",
        "hedge_enabled": True,
        "hedge_method": "percentage",
        "hedge_percent": 30.0,
        "hedge_offset": 200,
        "profit_lock_enabled": True,
        "profit_target": 15.0,
        "profit_lock": 7.0,
        "trailing_stop_enabled": False,
        "trail_percent": 1.0,
        "auto_trade_enabled": True,
        "active_signals": ["S1", "S2", "S7"],
        "max_positions": 3,
        "daily_profit_target": 50000,
        "max_loss_per_trade": 15000,
        "max_exposure": 150000,
        "position_size_mode": "fixed",
        
        # Expiry and Exit Timing - THIS IS WHAT WE'RE TESTING
        "selected_expiry": "2025-01-14",
        "exit_day_offset": 0,  # Expiry day
        "exit_time": "14:15",
        "auto_square_off_enabled": True,
        
        # Weekday Configuration
        "weekday_config": {
            "monday": "current",
            "tuesday": "current", 
            "wednesday": "next",
            "tuesday": "month_end",
            "friday": "next"
        }
    }
    
    print("\n1. Saving Configuration...")
    print(f"   Exit Day: {'Expiry Day' if test_config['exit_day_offset'] == 0 else f'T+{test_config['exit_day_offset']}'}")
    print(f"   Exit Time: {test_config['exit_time']}")
    print(f"   Monday Config: {test_config['weekday_config']['monday']}")
    print(f"   Tuesday Config: {test_config['weekday_config']['tuesday']}")
    
    # Save configuration
    try:
        response = requests.post(
            f"{BASE_URL}/api/trade-config/save",
            json={
                "config_name": "default",
                "user_id": "default",
                "config": test_config
            }
        )
        
        if response.ok:
            result = response.json()
            if result.get('success'):
                print("   [OK] Configuration saved successfully")
            else:
                print(f"   [FAIL] Save failed: {result.get('message')}")
                return False
        else:
            print(f"   [FAIL] HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   [FAIL] Error saving config: {e}")
        return False
    
    # Wait a moment
    time.sleep(1)
    
    print("\n2. Loading Configuration...")
    
    # Load configuration
    try:
        response = requests.get(
            f"{BASE_URL}/api/trade-config/load/default?user_id=default"
        )
        
        if response.ok:
            result = response.json()
            if result.get('success') and result.get('config'):
                loaded_config = result['config']
                print("   [OK] Configuration loaded successfully")
                
                # Verify expiry and exit timing
                print("\n3. Verifying Loaded Settings:")
                
                # Check exit timing
                if loaded_config.get('exit_day_offset') == 0:
                    print("   [OK] Exit Day: Expiry Day (correctly loaded)")
                else:
                    print(f"   [FAIL] Exit Day: Expected 0, got {loaded_config.get('exit_day_offset')}")
                
                if loaded_config.get('exit_time') == '14:15':
                    print("   [OK] Exit Time: 14:15 (correctly loaded)")
                else:
                    print(f"   [FAIL] Exit Time: Expected 14:15, got {loaded_config.get('exit_time')}")
                
                # Check weekday config
                weekday_ok = True
                if loaded_config.get('weekday_config'):
                    wc = loaded_config['weekday_config']
                    if wc.get('monday') == 'current':
                        print("   [OK] Monday: current (correctly loaded)")
                    else:
                        print(f"   [FAIL] Monday: Expected current, got {wc.get('monday')}")
                        weekday_ok = False
                        
                    if wc.get('tuesday') == 'month_end':
                        print("   [OK] Tuesday: month_end (correctly loaded)")
                    else:
                        print(f"   [FAIL] Tuesday: Expected month_end, got {wc.get('tuesday')}")
                        weekday_ok = False
                else:
                    print("   [FAIL] Weekday config not found in loaded config")
                    weekday_ok = False
                
                # Check other settings
                if loaded_config.get('num_lots') == 15:
                    print("   [OK] Number of lots: 15 (correctly loaded)")
                else:
                    print(f"   [FAIL] Number of lots: Expected 15, got {loaded_config.get('num_lots')}")
                
                print("\n" + "=" * 60)
                if (loaded_config.get('exit_day_offset') == 0 and 
                    loaded_config.get('exit_time') == '14:15' and 
                    weekday_ok):
                    print("SUCCESS: Expiry and exit timing settings persist correctly!")
                    return True
                else:
                    print("FAILURE: Some settings did not persist correctly")
                    return False
                    
            else:
                print(f"   [FAIL] No config returned: {result}")
                return False
        else:
            print(f"   [FAIL] HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   [FAIL] Error loading config: {e}")
        return False

if __name__ == "__main__":
    success = test_save_and_load_config()
    exit(0 if success else 1)