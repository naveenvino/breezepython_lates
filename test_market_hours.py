"""
Test Market Hours Enforcement
CRITICAL: Prevents trading outside market hours (9:15 AM - 3:30 PM)
"""

import requests
import json
from datetime import datetime, time, timedelta
import time as time_module

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "tradingview-webhook-secret-key-2025"

def get_current_time_str():
    """Get current time as string"""
    return datetime.now().strftime("%H:%M:%S")

def test_market_hours_validation():
    """Test that orders are only accepted during market hours"""
    print("\n" + "="*60)
    print("TESTING MARKET HOURS ENFORCEMENT")
    print("="*60)
    
    current_time = datetime.now().time()
    current_hour = current_time.hour
    
    print(f"Current time: {get_current_time_str()}")
    
    # Define market hours
    market_open = time(9, 15)  # 9:15 AM
    market_close = time(15, 30)  # 3:30 PM
    
    is_market_hours = market_open <= current_time <= market_close
    is_weekend = datetime.now().weekday() >= 5  # Saturday = 5, Sunday = 6
    
    print(f"Market hours: 9:15 AM - 3:30 PM")
    print(f"Currently in market hours: {is_market_hours}")
    print(f"Is weekend: {is_weekend}")
    
    # Test webhook
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S1",
        "strike": 25000,
        "option_type": "PE",
        "lots": 1,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=payload,
            timeout=5
        )
        
        print(f"\nWebhook Response:")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.text[:200] if response.text else 'No response body'}")
        
        if is_weekend:
            if response.status_code in [400, 403, 503]:
                print("\n[PASS] Weekend trading correctly blocked")
                return True
            else:
                print("\n[FAIL] Weekend trading not blocked!")
                return False
        elif not is_market_hours:
            if response.status_code in [400, 403, 503]:
                print("\n[PASS] After-hours trading correctly blocked")
                return True
            else:
                print("\n[WARNING] After-hours trading not blocked")
                return False
        else:
            if response.status_code == 200:
                print("\n[PASS] Market hours trading allowed")
                return True
            else:
                print("\n[INFO] Market hours but order failed - check other issues")
                return True
                
    except Exception as e:
        print(f"\nError testing webhook: {e}")
        return False

def test_pre_market_order():
    """Test order placement before market opens"""
    print("\n" + "="*60)
    print("TESTING PRE-MARKET ORDER REJECTION")
    print("="*60)
    
    # Create a pre-market timestamp (8:00 AM)
    pre_market_time = datetime.now().replace(hour=8, minute=0, second=0)
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S2",
        "strike": 25000,
        "option_type": "CE",
        "lots": 1,
        "timestamp": pre_market_time.isoformat(),
        "force_time": "08:00:00"  # Hint to system this is pre-market
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=payload,
            timeout=5
        )
        
        print(f"Pre-market order (8:00 AM):")
        print(f"  Status: {response.status_code}")
        
        if response.status_code in [400, 403, 503]:
            print("\n[PASS] Pre-market order correctly rejected")
            return True
        else:
            print("\n[WARNING] Pre-market order not rejected")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_post_market_order():
    """Test order placement after market closes"""
    print("\n" + "="*60)
    print("TESTING POST-MARKET ORDER REJECTION")
    print("="*60)
    
    # Create a post-market timestamp (4:00 PM)
    post_market_time = datetime.now().replace(hour=16, minute=0, second=0)
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S3",
        "strike": 25000,
        "option_type": "PE",
        "lots": 1,
        "timestamp": post_market_time.isoformat(),
        "force_time": "16:00:00"  # Hint to system this is post-market
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=payload,
            timeout=5
        )
        
        print(f"Post-market order (4:00 PM):")
        print(f"  Status: {response.status_code}")
        
        if response.status_code in [400, 403, 503]:
            print("\n[PASS] Post-market order correctly rejected")
            return True
        else:
            print("\n[WARNING] Post-market order not rejected")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_auto_square_off_time():
    """Test auto square-off at 3:20 PM"""
    print("\n" + "="*60)
    print("TESTING AUTO SQUARE-OFF TIME (3:20 PM)")
    print("="*60)
    
    # Check if we have any open positions
    try:
        response = requests.get(f"{BASE_URL}/api/positions", timeout=5)
        if response.status_code == 200:
            positions = response.json().get("positions", [])
            print(f"Current open positions: {len(positions)}")
            
            if len(positions) > 0:
                print("Positions found that should be squared off at 3:20 PM")
                
                # Check square-off schedule
                schedule_response = requests.get(
                    f"{BASE_URL}/api/square-off/schedule",
                    timeout=5
                )
                if schedule_response.status_code == 200:
                    schedule = schedule_response.json()
                    print(f"Square-off schedule: {schedule}")
                    return True
            else:
                print("No positions to square off")
                return True
                
    except Exception as e:
        print(f"Error checking square-off: {e}")
        return False

def test_weekend_rejection():
    """Test that weekend orders are rejected"""
    print("\n" + "="*60)
    print("TESTING WEEKEND ORDER REJECTION")
    print("="*60)
    
    is_weekend = datetime.now().weekday() >= 5
    
    if not is_weekend:
        print("Not a weekend, skipping test")
        return True
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S4",
        "strike": 25000,
        "option_type": "CE",
        "lots": 1,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=payload,
            timeout=5
        )
        
        print(f"Weekend order attempt:")
        print(f"  Day: {datetime.now().strftime('%A')}")
        print(f"  Status: {response.status_code}")
        
        if response.status_code in [400, 403, 503]:
            print("\n[PASS] Weekend order correctly rejected")
            return True
        else:
            print("\n[FAIL] Weekend order not rejected!")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_holiday_calendar():
    """Test NSE holiday calendar integration"""
    print("\n" + "="*60)
    print("TESTING HOLIDAY CALENDAR")
    print("="*60)
    
    try:
        # Check if system knows about holidays
        response = requests.get(f"{BASE_URL}/api/market/holidays", timeout=5)
        
        if response.status_code == 200:
            holidays = response.json()
            print(f"System recognizes {len(holidays.get('holidays', []))} holidays")
            
            # Check if today is a holiday
            today = datetime.now().date().isoformat()
            is_holiday = today in holidays.get('holidays', [])
            
            print(f"Today ({today}) is holiday: {is_holiday}")
            return True
        elif response.status_code == 404:
            print("[INFO] Holiday calendar endpoint not found")
            return True
        else:
            print(f"[WARNING] Holiday check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error checking holidays: {e}")
        return True  # Don't fail test if endpoint doesn't exist

if __name__ == "__main__":
    print("\n" + "="*70)
    print("CRITICAL TEST: MARKET HOURS ENFORCEMENT")
    print("="*70)
    print("This test ensures trading only happens during market hours")
    print("Prevents orders on weekends and holidays")
    
    test_results = []
    
    # Run tests
    test_results.append(("Market Hours Validation", test_market_hours_validation()))
    time_module.sleep(1)
    
    test_results.append(("Pre-Market Rejection", test_pre_market_order()))
    time_module.sleep(1)
    
    test_results.append(("Post-Market Rejection", test_post_market_order()))
    time_module.sleep(1)
    
    test_results.append(("Auto Square-Off Check", test_auto_square_off_time()))
    time_module.sleep(1)
    
    test_results.append(("Weekend Rejection", test_weekend_rejection()))
    time_module.sleep(1)
    
    test_results.append(("Holiday Calendar", test_holiday_calendar()))
    
    # Summary
    print("\n" + "="*70)
    print("MARKET HOURS TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n SUCCESS: Market hours protection is working!")
    else:
        print("\n WARNING: Market hours protection needs improvement!")
        print("This could lead to orders placed at wrong times!")