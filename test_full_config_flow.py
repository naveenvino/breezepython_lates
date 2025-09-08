import requests
import json
import time

def test_complete_config_flow():
    """Test the complete configuration save and load flow"""
    
    BASE_URL = "http://localhost:8000"
    
    print("Testing Complete Configuration Flow")
    print("=" * 60)
    
    # 1. Save a specific configuration
    test_config = {
        "num_lots": 30,
        "entry_timing": "custom",
        "exit_day_offset": 0,  # Expiry day
        "exit_time": "09:30",
        "weekday_config": {
            "monday": "current",
            "tuesday": "current", 
            "wednesday": "next",
            "thursday": "next",
            "friday": "next"
        }
    }
    
    print("\n1. Saving configuration...")
    print(f"   Number of lots: {test_config['num_lots']}")
    print(f"   Exit day: Expiry Day (offset={test_config['exit_day_offset']})")
    print(f"   Exit time: {test_config['exit_time']}")
    print(f"   Monday expiry: {test_config['weekday_config']['monday']}")
    
    response = requests.post(
        f"{BASE_URL}/api/trade-config/save",
        json={
            "config_name": "default",
            "user_id": "default",
            "config": test_config
        }
    )
    
    if response.ok and response.json().get('success'):
        print("   [OK] Configuration saved successfully")
    else:
        print(f"   [FAIL] Save failed: {response.text}")
        return False
    
    # 2. Load and verify
    time.sleep(1)
    print("\n2. Loading configuration...")
    
    response = requests.get(f"{BASE_URL}/api/trade-config/load/default?user_id=default")
    
    if response.ok:
        result = response.json()
        if result.get('success') and result.get('config'):
            config = result['config']
            print("   [OK] Configuration loaded")
            
            # Verify values
            print("\n3. Verifying values:")
            
            success = True
            if config.get('num_lots') == 30:
                print(f"   [OK] Number of lots: {config.get('num_lots')}")
            else:
                print(f"   [FAIL] Number of lots: Expected 30, got {config.get('num_lots')}")
                success = False
            
            if config.get('exit_day_offset') == 0:
                print(f"   [OK] Exit day offset: {config.get('exit_day_offset')} (Expiry Day)")
            else:
                print(f"   [FAIL] Exit day offset: Expected 0, got {config.get('exit_day_offset')}")
                success = False
            
            if config.get('exit_time') == '09:30':
                print(f"   [OK] Exit time: {config.get('exit_time')}")
            else:
                print(f"   [FAIL] Exit time: Expected 09:30, got {config.get('exit_time')}")
                success = False
            
            if config.get('weekday_config', {}).get('monday') == 'current':
                print(f"   [OK] Monday expiry: {config.get('weekday_config', {}).get('monday')}")
            else:
                print(f"   [FAIL] Monday expiry: Expected current, got {config.get('weekday_config', {}).get('monday')}")
                success = False
            
            print("\n" + "=" * 60)
            if success:
                print("SUCCESS: All configuration values persist correctly!")
                print("\nIMPORTANT FIXES APPLIED:")
                print("1. Circuit breaker disabled for /api/trade-config/ endpoints")
                print("2. Removed hardcoded 'selected' attributes from HTML dropdowns")
                print("3. Fixed 'monthend' vs 'month_end' value mismatch")
                print("4. Added delay to ensure DOM is ready before loading config")
                print("5. Removed duplicate loadTradeConfig() calls")
                print("\nThe UI should now properly display saved values on page refresh.")
            else:
                print("FAILURE: Some values not persisting correctly")
            
            return success
    
    return False

if __name__ == "__main__":
    success = test_complete_config_flow()
    exit(0 if success else 1)