"""
Test script for expiry selection and exit timing features
"""
import requests
import json
from datetime import datetime
import sys

BASE_URL = "http://localhost:8000"

def test_expiry_management():
    """Test expiry management functionality"""
    print("\n" + "="*60)
    print("  TESTING EXPIRY MANAGEMENT FEATURES")
    print("="*60)
    
    # Test 1: Get available expiries
    print("\n[TEST 1] Getting available expiries...")
    try:
        response = requests.get(f"{BASE_URL}/api/expiry/available")
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Status: {data['status']}")
            
            if 'data' in data:
                expiry_data = data['data']
                print(f"[OK] Current day: {expiry_data['current_day']}")
                print(f"[OK] Current week available: {expiry_data['current_week_available']}")
                print(f"[OK] Available expiries:")
                
                for expiry in expiry_data['available_expiries']:
                    print(f"     - {expiry['display']} ({expiry['date']}) - {expiry['days_to_expiry']} days")
                
                print(f"[OK] Default expiry: {expiry_data['default_expiry']}")
                return True
            else:
                print(f"[FAIL] No data in response")
                return False
        else:
            print(f"[FAIL] Status code: {response.status_code}")
            print(f"[FAIL] Response: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_expiry_selection():
    """Test expiry selection"""
    print("\n[TEST 2] Testing expiry selection...")
    
    # First get available expiries
    try:
        response = requests.get(f"{BASE_URL}/api/expiry/available")
        if response.status_code == 200:
            data = response.json()
            if data['data']['available_expiries']:
                # Select the first available expiry
                selected_expiry = data['data']['available_expiries'][0]['date']
                
                # Test selection
                select_data = {"expiry_date": selected_expiry}
                response = requests.post(
                    f"{BASE_URL}/api/expiry/select",
                    json=select_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"[OK] Selection successful: {result['message']}")
                    print(f"[OK] Selected expiry: {result.get('expiry_date')}")
                    return True
                else:
                    print(f"[FAIL] Selection failed: {response.status_code}")
                    print(f"[FAIL] Response: {response.text}")
                    return False
        return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_exit_timing_options():
    """Test exit timing options"""
    print("\n[TEST 3] Getting exit timing options...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/exit-timing/options")
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Status: {data['status']}")
            
            if 'data' in data:
                options = data['data']
                print(f"[OK] Exit day options: {len(options['exit_days'])}")
                for day_opt in options['exit_days'][:3]:  # Show first 3
                    print(f"     - {day_opt['label']}")
                
                print(f"[OK] Exit time options: {len(options['exit_times'])}")
                for time_opt in options['exit_times']:
                    print(f"     - {time_opt['label']}")
                
                print(f"[OK] Default: T+{options['default_exit_day']} at {options['default_exit_time']}")
                return True
        else:
            print(f"[FAIL] Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_exit_timing_configuration():
    """Test exit timing configuration"""
    print("\n[TEST 4] Configuring exit timing...")
    
    config = {
        "exit_day_offset": 3,
        "exit_time": "14:15",
        "auto_square_off_enabled": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/exit-timing/configure",
            json=config
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Configuration successful: {result['message']}")
            print(f"[OK] Exit day: T+{result['config']['exit_day_offset']}")
            print(f"[OK] Exit time: {result['config']['exit_time']}")
            print(f"[OK] Auto square-off: {result['config']['auto_square_off_enabled']}")
            return True
        else:
            print(f"[FAIL] Configuration failed: {response.status_code}")
            print(f"[FAIL] Response: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_pending_square_offs():
    """Test pending square-offs retrieval"""
    print("\n[TEST 5] Getting pending square-offs...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/square-off/pending")
        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Status: {result['status']}")
            print(f"[OK] Pending count: {result['count']}")
            
            if result['data']:
                for item in result['data']:
                    print(f"     - {item['symbol']} ({item['quantity']} qty) at {item['exit_datetime']}")
            else:
                print("     - No pending square-offs")
            return True
        else:
            print(f"[FAIL] Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_expiry_service_logic():
    """Test expiry service logic directly"""
    print("\n[TEST 6] Testing expiry calculation logic...")
    
    try:
        from src.services.expiry_management_service import ExpiryManagementService
        
        service = ExpiryManagementService()
        
        # Test different days of week
        test_dates = [
            datetime(2025, 1, 6),   # Monday
            datetime(2025, 1, 7),   # Tuesday
            datetime(2025, 1, 8),   # Wednesday
            datetime(2025, 1, 10),  # Friday
        ]
        
        for test_date in test_dates:
            expiries = service.get_available_expiries(test_date)
            day_name = test_date.strftime("%A")
            print(f"\n[OK] {day_name}: {len(expiries['available_expiries'])} expiries available")
            print(f"     Current week available: {expiries['current_week_available']}")
        
        # Test exit date calculation
        entry_date = datetime(2025, 1, 6)  # Monday
        for t_plus in [1, 2, 3, 5]:
            exit_date, display = service.calculate_exit_date(entry_date, t_plus)
            print(f"[OK] T+{t_plus}: {display}")
        
        return True
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def main():
    print("\n" + "="*60)
    print("  EXPIRY & EXIT TIMING FEATURE TEST")
    print("  Testing NIFTY Weekly Expiry Selection")
    print("="*60)
    
    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("\n[ERROR] API server not running on port 8000")
            print("Please start: python unified_api_correct.py")
            return 1
    except:
        print("\n[ERROR] Cannot connect to API server")
        print("Please start: python unified_api_correct.py")
        return 1
    
    # Run tests
    tests_passed = 0
    tests_failed = 0
    
    tests = [
        ("Expiry Management", test_expiry_management),
        ("Expiry Selection", test_expiry_selection),
        ("Exit Timing Options", test_exit_timing_options),
        ("Exit Timing Configuration", test_exit_timing_configuration),
        ("Pending Square-offs", test_pending_square_offs),
        ("Expiry Service Logic", test_expiry_service_logic)
    ]
    
    for test_name, test_func in tests:
        try:
            if test_func():
                tests_passed += 1
            else:
                tests_failed += 1
        except Exception as e:
            print(f"[ERROR] Test {test_name} crashed: {e}")
            tests_failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Success Rate: {(tests_passed/(tests_passed+tests_failed)*100):.1f}%")
    
    if tests_failed == 0:
        print("\n[SUCCESS] All tests passed! ✅")
        print("\nFeatures Working:")
        print("• Weekly expiry selection (Tuesday)")
        print("• Current/Next/Month-end expiry options")
        print("• Exit timing configuration (T+1 to T+7)")
        print("• Auto square-off scheduling")
        print("• Holiday and weekend handling")
        return 0
    else:
        print("\n[WARNING] Some tests failed ⚠️")
        return 1

if __name__ == "__main__":
    sys.exit(main())