import requests
import json
import time

def test_config_persistence():
    """Test if configuration persists correctly"""
    
    BASE_URL = "http://localhost:8000"
    
    print("Testing Configuration Loading Fix")
    print("=" * 60)
    
    # Test configuration
    test_config = {
        "num_lots": 25,
        "entry_timing": "next_candle",
        "hedge_enabled": True,
        "hedge_method": "offset",
        "hedge_offset": 500,
        "profit_lock_enabled": True,
        "profit_target": 20.0,
        "profit_lock": 10.0,
        "selected_expiry": "2025-01-21",
        "exit_day_offset": 1,  # T+1
        "exit_time": "14:30",
        "auto_square_off_enabled": True,
        "weekday_config": {
            "monday": "next",
            "tuesday": "current",
            "wednesday": "month_end",
            "tuesday": "next",
            "friday": "current"
        }
    }
    
    print("\n1. Saving test configuration...")
    response = requests.post(
        f"{BASE_URL}/api/trade-config/save",
        json={
            "config_name": "default",
            "user_id": "default",
            "config": test_config
        }
    )
    
    if response.ok and response.json().get('success'):
        print("   [OK] Configuration saved")
    else:
        print(f"   [FAIL] Save failed: {response.text}")
        return False
    
    print("\n2. Loading configuration from API...")
    response = requests.get(f"{BASE_URL}/api/trade-config/load/default?user_id=default")
    
    if response.ok:
        result = response.json()
        if result.get('success') and result.get('config'):
            config = result['config']
            print("   [OK] Configuration loaded from API")
            
            print("\n3. Verifying loaded values:")
            
            # Check critical values
            checks = [
                ('num_lots', 25),
                ('entry_timing', 'next_candle'),
                ('exit_day_offset', 1),
                ('exit_time', '14:30'),
                ('hedge_offset', 500),
                ('profit_target', 20.0)
            ]
            
            all_ok = True
            for key, expected in checks:
                actual = config.get(key)
                if actual == expected:
                    print(f"   [OK] {key}: {actual}")
                else:
                    print(f"   [FAIL] {key}: Expected {expected}, got {actual}")
                    all_ok = False
            
            # Check weekday config
            if config.get('weekday_config'):
                wc = config['weekday_config']
                weekday_checks = [
                    ('monday', 'next'),
                    ('tuesday', 'current'),
                    ('wednesday', 'month_end'),
                    ('tuesday', 'next'),
                    ('friday', 'current')
                ]
                
                print("\n4. Verifying weekday configuration:")
                for day, expected in weekday_checks:
                    actual = wc.get(day)
                    if actual == expected:
                        print(f"   [OK] {day}: {actual}")
                    else:
                        print(f"   [FAIL] {day}: Expected {expected}, got {actual}")
                        all_ok = False
            
            print("\n" + "=" * 60)
            if all_ok:
                print("SUCCESS: Configuration persists correctly!")
                print("\nNOTE: The UI should now load these values when you refresh the page.")
                print("The following issues were fixed:")
                print("  1. Removed hardcoded 'selected' attributes from HTML")
                print("  2. Fixed 'monthend' vs 'month_end' mismatch")
                print("  3. Removed duplicate loadTradeConfig() calls")
                print("  4. Added updateWeekdayExpiryDates() function")
                return True
            else:
                print("FAILURE: Some values not persisting correctly")
                return False
    
    return False

if __name__ == "__main__":
    success = test_config_persistence()
    exit(0 if success else 1)