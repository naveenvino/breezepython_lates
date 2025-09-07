"""
Simple endpoint test using requests instead of aiohttp
Tests all the newly added missing endpoints
"""
import requests
import json
import time
from datetime import datetime

# Test configuration
API_BASE_URL = "http://localhost:8000"
TEST_USER = "test_user"

def test_endpoint(method, url, data=None, description=""):
    """Test a single endpoint"""
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=5)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=5)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, timeout=5)
        elif method.upper() == "DELETE":
            response = requests.delete(url, timeout=5)
        
        print(f"[{method}] {description}")
        print(f"  URL: {url}")
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"  Response: {json.dumps(result, indent=2)}")
                print("  ✓ SUCCESS")
            except:
                print(f"  Response: {response.text[:100]}")
                print("  ✓ SUCCESS (non-JSON)")
        else:
            print(f"  Error: {response.text}")
            print("  ✗ FAILED")
        
        print("-" * 60)
        return response.status_code == 200
        
    except Exception as e:
        print(f"[{method}] {description}")
        print(f"  URL: {url}")
        print(f"  Exception: {str(e)}")
        print("  ✗ FAILED")
        print("-" * 60)
        return False

def main():
    print("=" * 60)
    print("ENDPOINT INTEGRATION TEST")
    print("=" * 60)
    print(f"Testing API at: {API_BASE_URL}")
    print(f"Started at: {datetime.now()}")
    print("=" * 60)
    
    results = []
    
    # Test 1: Health Check
    success = test_endpoint("GET", f"{API_BASE_URL}/health", description="Health Check")
    results.append(("Health Check", success))
    
    # Test 2: Settings CRUD
    test_key = "test_setting_123"
    test_value = {"test": "value", "timestamp": datetime.now().isoformat()}
    
    # Create setting
    success = test_endpoint("POST", f"{API_BASE_URL}/settings", 
                          {"key": test_key, "value": test_value, "category": "test"},
                          "Create Setting (POST /settings)")
    results.append(("Create Setting", success))
    
    # Get setting
    success = test_endpoint("GET", f"{API_BASE_URL}/settings/{test_key}", 
                          description="Get Setting (GET /settings/{key})")
    results.append(("Get Setting", success))
    
    # Update setting
    updated_value = {"test": "updated_value", "timestamp": datetime.now().isoformat()}
    success = test_endpoint("PUT", f"{API_BASE_URL}/settings/{test_key}", 
                          {"value": updated_value}, 
                          "Update Setting (PUT /settings/{key})")
    results.append(("Update Setting", success))
    
    # Delete setting
    success = test_endpoint("DELETE", f"{API_BASE_URL}/settings/{test_key}", 
                          description="Delete Setting (DELETE /settings/{key})")
    results.append(("Delete Setting", success))
    
    # Test 3: Trade Config
    trade_config = {
        "num_lots": 15,
        "max_loss_per_trade": 7500,
        "stop_loss_points": 250,
        "target_points": 500,
        "max_positions": 5
    }
    
    success = test_endpoint("POST", f"{API_BASE_URL}/save-trade-config", 
                          trade_config, "Save Trade Config")
    results.append(("Save Trade Config", success))
    
    success = test_endpoint("GET", f"{API_BASE_URL}/trade-config", 
                          description="Get Trade Config")
    results.append(("Get Trade Config", success))
    
    # Test 4: Signal States
    signal_states = {
        "S1": True, "S2": False, "S3": True, "S4": False,
        "S5": True, "S6": False, "S7": True, "S8": False
    }
    
    success = test_endpoint("POST", f"{API_BASE_URL}/save-signal-states", 
                          signal_states, "Save Signal States")
    results.append(("Save Signal States", success))
    
    success = test_endpoint("GET", f"{API_BASE_URL}/signal-states", 
                          description="Get Signal States")
    results.append(("Get Signal States", success))
    
    # Test 5: Expiry Config
    weekday_config = {
        "enabled": True,
        "exit_time": "15:10",
        "weekdays": ["monday", "tuesday", "wednesday", "thursday"]
    }
    
    success = test_endpoint("POST", f"{API_BASE_URL}/save-weekday-expiry-config", 
                          weekday_config, "Save Weekday Expiry Config")
    results.append(("Save Weekday Config", success))
    
    success = test_endpoint("GET", f"{API_BASE_URL}/weekday-expiry-config", 
                          description="Get Weekday Expiry Config")
    results.append(("Get Weekday Config", success))
    
    # Test 6: Exit Timing Config
    exit_config = {
        "auto_exit_enabled": True,
        "exit_time": "15:15",
        "buffer_minutes": 5
    }
    
    success = test_endpoint("POST", f"{API_BASE_URL}/save-exit-timing-config", 
                          exit_config, "Save Exit Timing Config")
    results.append(("Save Exit Timing Config", success))
    
    # Test 7: Market Data
    success = test_endpoint("GET", f"{API_BASE_URL}/nifty-spot", 
                          description="Get NIFTY Spot Price")
    results.append(("NIFTY Spot", success))
    
    success = test_endpoint("GET", f"{API_BASE_URL}/positions", 
                          description="Get Trading Positions")
    results.append(("Get Positions", success))
    
    # Summary
    print("=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    failed = len(results) - passed
    
    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{test_name:<25}: {status}")
    
    print("=" * 60)
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {passed/len(results)*100:.1f}%")
    
    if failed == 0:
        print("🎉 ALL ENDPOINTS WORKING!")
    else:
        print(f"⚠️  {failed} endpoints need attention")
    
    print("=" * 60)

if __name__ == "__main__":
    main()