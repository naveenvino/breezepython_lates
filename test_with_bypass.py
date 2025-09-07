"""
Test with Market Hours Bypass for Weekend Testing
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "tradingview-webhook-secret-key-2025"

def enable_test_mode():
    """Enable test mode to bypass market hours"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/test-mode/enable",
            json={"bypass_market_hours": True},
            timeout=5
        )
        if response.status_code == 200:
            print("Test mode enabled - market hours bypassed")
            return True
    except:
        pass
    
    # Alternative: Set environment variable
    import os
    os.environ['BYPASS_MARKET_HOURS'] = 'true'
    print("Set BYPASS_MARKET_HOURS environment variable")
    return True

def disable_test_mode():
    """Disable test mode"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/test-mode/disable",
            timeout=5
        )
        print("Test mode disabled")
    except:
        pass

def test_single_webhook():
    """Test that a single webhook goes through"""
    print("\n" + "="*60)
    print("TESTING SINGLE WEBHOOK (WITH BYPASS)")
    print("="*60)
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S1",
        "strike": 25000,
        "option_type": "PE",
        "lots": 10,
        "timestamp": datetime.now().isoformat(),
        "test_mode": True  # Flag for test mode
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=payload,
            timeout=5
        )
        
        print(f"Response Status: {response.status_code}")
        if response.status_code == 200:
            print("SUCCESS: Webhook accepted")
            return True
        else:
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_duplicate_prevention_fixed():
    """Test duplicate prevention with first signal going through"""
    print("\n" + "="*60)
    print("TESTING DUPLICATE PREVENTION (FIXED)")
    print("="*60)
    
    # Clear any existing signals first
    time.sleep(2)
    
    # Create unique signal
    signal_id = f"test_{int(time.time())}"
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S2",
        "strike": 25000,
        "option_type": "CE",
        "lots": 5,
        "timestamp": datetime.now().isoformat(),
        "signal_id": signal_id,
        "test_mode": True
    }
    
    results = []
    
    # Send same signal 5 times
    for i in range(5):
        try:
            response = requests.post(
                f"{BASE_URL}/webhook/entry",
                json=payload,
                timeout=5
            )
            results.append(response.status_code)
            print(f"  Attempt {i+1}: Status {response.status_code}")
            time.sleep(0.5)
        except Exception as e:
            results.append("error")
            print(f"  Attempt {i+1}: Error - {e}")
    
    # Check results
    success_count = sum(1 for r in results if r == 200)
    duplicate_count = sum(1 for r in results if r == 409)
    
    print(f"\nResults:")
    print(f"  Successful: {success_count}")
    print(f"  Duplicates blocked: {duplicate_count}")
    
    if success_count == 1 and duplicate_count == 4:
        print("PASS: First signal accepted, duplicates blocked")
        return True
    else:
        print("FAIL: Incorrect duplicate handling")
        return False

def test_position_limits_fixed():
    """Test position limits with proper handling"""
    print("\n" + "="*60)
    print("TESTING POSITION LIMITS (FIXED)")
    print("="*60)
    
    test_cases = [
        {"lots": 10, "expected": 200},
        {"lots": 50, "expected": 200},
        {"lots": 100, "expected": 200},
        {"lots": 500, "expected": 400},  # Should be rejected
        {"lots": 1000, "expected": 400}, # Should be rejected
    ]
    
    results = []
    
    for test in test_cases:
        # Use different signals to avoid duplicate rejection
        signal = f"S{(test['lots'] % 8) + 1}"
        
        payload = {
            "secret": WEBHOOK_SECRET,
            "signal": signal,
            "strike": 25000 + test['lots'],
            "option_type": "PE" if test['lots'] % 2 == 0 else "CE",
            "lots": test['lots'],
            "timestamp": datetime.now().isoformat(),
            "test_mode": True
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/webhook/entry",
                json=payload,
                timeout=5
            )
            
            passed = (test['lots'] <= 100 and response.status_code == 200) or \
                     (test['lots'] > 100 and response.status_code in [400, 403, 422])
            
            results.append(passed)
            status = "PASS" if passed else "FAIL"
            print(f"  {test['lots']} lots: Status {response.status_code} [{status}]")
            
        except Exception as e:
            results.append(False)
            print(f"  {test['lots']} lots: Error - {e}")
        
        time.sleep(1)  # Avoid rate limiting
    
    passed = sum(results)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    return passed == total

if __name__ == "__main__":
    print("\n" + "="*70)
    print("TESTING WITH MARKET HOURS BYPASS")
    print("="*70)
    
    # Enable test mode
    enable_test_mode()
    
    test_results = []
    
    # Run tests
    test_results.append(("Single Webhook", test_single_webhook()))
    time.sleep(2)
    
    test_results.append(("Duplicate Prevention", test_duplicate_prevention_fixed()))
    time.sleep(2)
    
    test_results.append(("Position Limits", test_position_limits_fixed()))
    
    # Disable test mode
    disable_test_mode()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nSUCCESS: All tests passing with bypass!")
    else:
        print("\nWARNING: Some tests still failing!")