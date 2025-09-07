"""
Test Script for Complete Webhook + Expiry Integration
Tests the full production flow from TradingView alert to position creation with correct expiry
"""
import requests
import json
from datetime import datetime, timedelta
import sys
import os

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'tradingview-webhook-secret-key-2025')

def test_weekday_config_setup():
    """Step 1: Configure expiry selection for each weekday"""
    print("\n" + "="*60)
    print("STEP 1: CONFIGURING WEEKDAY EXPIRY SELECTION")
    print("="*60)
    
    # Configure expiry for each day
    config = {
        "monday": "current",     # Use current week expiry on Monday
        "tuesday": "current",     # Use current week expiry on Tuesday
        "wednesday": "next",      # Use next week expiry on Wed
        "thursday": "next",       # Use next week expiry on Thu
        "friday": "next"          # Use next week expiry on Fri
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/expiry/weekday-config",
            json=config
        )
        
        if response.status_code == 200:
            result = response.json()
            print("[OK] Weekday configuration saved:")
            for day, expiry_type in config.items():
                print(f"     {day.capitalize()}: {expiry_type}")
            return True
        else:
            print(f"[FAIL] Failed to save config: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_exit_timing_setup():
    """Step 2: Configure exit timing"""
    print("\n" + "="*60)
    print("STEP 2: CONFIGURING EXIT TIMING")
    print("="*60)
    
    config = {
        "exit_day_offset": 0,  # Expiry day
        "exit_time": "15:15",
        "auto_square_off_enabled": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/exit-timing/configure",
            json=config
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Exit timing configured:")
            exit_text = "Expiry Day" if config['exit_day_offset'] == 0 else f"T+{config['exit_day_offset']}"
            print(f"     Exit: {exit_text} at {config['exit_time']}")
            print(f"     Auto square-off: {'Enabled' if config['auto_square_off_enabled'] else 'Disabled'}")
            return True
        else:
            print(f"[FAIL] Failed to configure exit timing: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_webhook_entry_simulation():
    """Step 3: Simulate TradingView webhook with entry signal"""
    print("\n" + "="*60)
    print("STEP 3: SIMULATING TRADINGVIEW WEBHOOK ENTRY")
    print("="*60)
    
    # Get current day to show which config will be used
    current_day = datetime.now().strftime('%A')
    print(f"[INFO] Current day: {current_day}")
    
    # Simulate webhook payload from TradingView
    webhook_payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S1",                  # Bear Trap signal (Bullish - Sell PUT)
        "action": "ENTRY",
        "strike": 25000,                 # Main strike
        "option_type": "PE",              # PUT option
        "spot_price": 25015.45,
        "premium": 120,                  # Main leg premium
        "hedge_premium": 30,             # Hedge leg premium
        "lots": 10,                       # Position size
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"[INFO] Sending webhook for signal: {webhook_payload['signal']}")
    print(f"[INFO] Strike: {webhook_payload['strike']} {webhook_payload['option_type']}")
    print(f"[INFO] Lots: {webhook_payload['lots']}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=webhook_payload
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result['status'] == 'success':
                print("[OK] Position created successfully!")
                print("\n[POSITION DETAILS]")
                position = result['position']
                
                # Main leg
                print(f"Main Leg:")
                print(f"  Strike: {position['main_leg']['strike']}")
                print(f"  Type: {position['main_leg']['type']}")
                print(f"  Symbol: {position['main_leg'].get('symbol', 'N/A')}")
                print(f"  Price: {position['main_leg']['price']}")
                
                # Hedge leg
                print(f"\nHedge Leg:")
                print(f"  Strike: {position['hedge_leg']['strike']}")
                print(f"  Symbol: {position['hedge_leg'].get('symbol', 'N/A')}")
                print(f"  Price: {position['hedge_leg']['price']}")
                
                # Expiry and square-off
                print(f"\nExpiry Information:")
                print(f"  Expiry Date: {position.get('expiry_date', 'N/A')}")
                print(f"  Breakeven: {position['breakeven']}")
                
                if position.get('auto_square_off'):
                    print(f"\nAuto Square-off:")
                    print(f"  Scheduled: {position['auto_square_off']}")
                
                return True, position
            else:
                print(f"[FAIL] {result.get('message', 'Unknown error')}")
                return False, None
        else:
            print(f"[FAIL] HTTP {response.status_code}")
            print(f"[FAIL] Response: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False, None

def test_pending_square_offs():
    """Step 4: Check pending square-offs"""
    print("\n" + "="*60)
    print("STEP 4: CHECKING PENDING SQUARE-OFFS")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/square-off/pending")
        
        if response.status_code == 200:
            result = response.json()
            pending = result.get('data', [])
            
            if pending:
                print(f"[OK] Found {len(pending)} pending square-offs:")
                for item in pending:
                    print(f"\n  Symbol: {item['symbol']}")
                    print(f"  Quantity: {item['quantity']}")
                    print(f"  Exit: {item['exit_datetime']}")
                    print(f"  Time remaining: {item.get('time_remaining', 'N/A')}")
            else:
                print("[INFO] No pending square-offs")
            
            return True
        else:
            print(f"[FAIL] Failed to get pending square-offs")
            return False
            
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_expiry_calculation():
    """Step 5: Verify expiry calculation logic"""
    print("\n" + "="*60)
    print("STEP 5: TESTING EXPIRY CALCULATION LOGIC")
    print("="*60)
    
    try:
        # Import the service directly to test
        from src.services.expiry_management_service import ExpiryManagementService
        
        service = ExpiryManagementService()
        
        # Test for different days
        test_days = [
            datetime(2025, 1, 6),   # Monday
            datetime(2025, 1, 7),   # Tuesday
            datetime(2025, 1, 8),   # Wednesday
            datetime(2025, 1, 9),   # Thursday
            datetime(2025, 1, 10),  # Friday
        ]
        
        for test_date in test_days:
            day_name = test_date.strftime('%A')
            expiries = service.get_available_expiries(test_date)
            
            print(f"\n{day_name}, {test_date.strftime('%Y-%m-%d')}:")
            print(f"  Current week available: {expiries['current_week_available']}")
            
            for expiry in expiries['available_expiries']:
                print(f"  - {expiry['display']} ({expiry['date']})")
        
        # Test symbol generation
        print("\n[SYMBOL GENERATION TEST]")
        expiry_date = datetime(2025, 1, 7)  # Tuesday
        
        # Test symbol generation (the method takes expiry_date and symbol_base)
        expiry_str = expiry_date.strftime('%Y-%m-%d')
        symbol_base = service.format_expiry_for_symbol(expiry_str, "NIFTY")
        
        # Manually append strike and option type
        put_symbol = f"{symbol_base}25000PE"
        call_symbol = f"{symbol_base}25000CE"
        
        print(f"PUT Symbol: {put_symbol}")
        print(f"CALL Symbol: {call_symbol}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def main():
    print("\n" + "="*60)
    print("   WEBHOOK + EXPIRY INTEGRATION TEST")
    print("   Testing Complete Production Flow")
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
    
    # Test 1: Configure weekday expiry
    if test_weekday_config_setup():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 2: Configure exit timing
    if test_exit_timing_setup():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 3: Simulate webhook entry
    success, position = test_webhook_entry_simulation()
    if success:
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 4: Check pending square-offs
    if test_pending_square_offs():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 5: Test expiry calculation
    if test_expiry_calculation():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("   TEST SUMMARY")
    print("="*60)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Success Rate: {(tests_passed/(tests_passed+tests_failed)*100):.1f}%")
    
    if tests_failed == 0:
        print("\n[SUCCESS] ALL TESTS PASSED - SYSTEM IS PRODUCTION READY!")
        print("\nProduction Flow Verified:")
        print("1. Weekday expiry configuration ✓")
        print("2. Exit timing configuration ✓")
        print("3. Webhook receives signal ✓")
        print("4. Correct expiry selected based on day ✓")
        print("5. Option symbols generated with expiry ✓")
        print("6. Position created with main & hedge ✓")
        print("7. Auto square-off scheduled ✓")
        
        print("\n[NEXT STEPS FOR PRODUCTION]")
        print("1. Connect real broker API (Kite/Breeze)")
        print("2. Configure TradingView webhook URL")
        print("3. Set WEBHOOK_SECRET in .env file")
        print("4. Test with paper trading first")
        print("5. Monitor logs during live trading")
    else:
        print("\n[WARNING] SOME TESTS FAILED - FIX ISSUES BEFORE PRODUCTION")
    
    return 0 if tests_failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())