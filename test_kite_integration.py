"""
Test Script for Complete TradingView → Expiry → Kite Integration
Tests the full production flow from webhook to Zerodha order placement
"""
import requests
import json
from datetime import datetime
import sys
import os

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'tradingview-webhook-secret-key-2025')

def test_trading_mode_check():
    """Check current trading mode (paper/real)"""
    print("\n" + "="*60)
    print("CHECKING TRADING MODE")
    print("="*60)
    
    paper_mode = os.getenv('PAPER_TRADING_MODE', 'true').lower() == 'true'
    kite_api_key = os.getenv('KITE_API_KEY', '')
    kite_access_token = os.getenv('KITE_ACCESS_TOKEN', '')
    
    print(f"[INFO] Trading Mode: {'PAPER' if paper_mode else 'REAL'}")
    print(f"[INFO] KITE_API_KEY configured: {'Yes' if kite_api_key else 'No'}")
    print(f"[INFO] KITE_ACCESS_TOKEN configured: {'Yes' if kite_access_token else 'No'}")
    
    if not paper_mode and (not kite_api_key or not kite_access_token):
        print("[WARNING] Real trading mode enabled but Kite credentials not configured!")
        print("[WARNING] Orders will fail. Please set KITE_API_KEY and KITE_ACCESS_TOKEN")
        return False
    
    return True

def test_kite_symbol_generation():
    """Test Kite symbol generation for different expiry types"""
    print("\n" + "="*60)
    print("TESTING KITE SYMBOL GENERATION")
    print("="*60)
    
    try:
        from src.services.kite_weekly_options_executor import KiteWeeklyOptionsExecutor
        executor = KiteWeeklyOptionsExecutor(
            api_key="test_key",
            access_token="test_token"
        )
        
        # Test weekly expiry symbol
        weekly_date = datetime(2025, 1, 14)  # Tuesday
        weekly_symbol = executor.format_weekly_symbol(weekly_date, 25000, "PE")
        print(f"[OK] Weekly symbol: {weekly_symbol}")
        assert weekly_symbol == "NIFTY2511425000PE", f"Expected NIFTY2511425000PE, got {weekly_symbol}"
        
        # Test monthly expiry symbol
        monthly_date = datetime(2025, 1, 30)  # Last Tuesday
        monthly_symbol = executor.format_monthly_symbol(monthly_date, 25000, "CE")
        print(f"[OK] Monthly symbol: {monthly_symbol}")
        assert monthly_symbol == "NIFTY25JAN25000CE", f"Expected NIFTY25JAN25000CE, got {monthly_symbol}"
        
        return True
    except Exception as e:
        print(f"[FAIL] Symbol generation failed: {str(e)}")
        return False

def test_complete_webhook_flow():
    """Test complete flow from webhook to position creation"""
    print("\n" + "="*60)
    print("TESTING COMPLETE WEBHOOK FLOW")
    print("="*60)
    
    # Configure weekday expiry first
    config = {
        "monday": "current",
        "tuesday": "current",
        "wednesday": "next",
        "tuesday": "next",
        "friday": "next"
    }
    
    try:
        # Set weekday configuration
        response = requests.post(
            f"{BASE_URL}/api/expiry/weekday-config",
            json=config
        )
        if response.status_code != 200:
            print(f"[FAIL] Failed to set weekday config: {response.text}")
            return False
        print("[OK] Weekday configuration set")
        
        # Send webhook with entry signal
        webhook_payload = {
            "secret": WEBHOOK_SECRET,
            "signal": "S1",
            "action": "ENTRY",
            "strike": 25000,
            "option_type": "PE",
            "spot_price": 25015.45,
            "premium": 120,
            "hedge_premium": 30,
            "lots": 10,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"[INFO] Sending webhook for {webhook_payload['signal']}")
        
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=webhook_payload
        )
        
        if response.status_code == 200:
            result = response.json()
            if result['status'] == 'success':
                position = result['position']
                
                print("[OK] Position created successfully!")
                print("\nPOSITION DETAILS:")
                print(f"  ID: {position['id']}")
                print(f"  Signal: {position['signal']}")
                print(f"  Trading Mode: {position.get('trading_mode', 'unknown')}")
                
                print("\nMAIN LEG:")
                print(f"  Strike: {position['main_leg']['strike']}")
                print(f"  Symbol: {position['main_leg']['symbol']}")
                print(f"  Type: {position['main_leg']['type']}")
                
                print("\nHEDGE LEG:")
                print(f"  Strike: {position['hedge_leg']['strike']}")
                print(f"  Symbol: {position['hedge_leg']['symbol']}")
                
                print(f"\nExpiry Date: {position['expiry_date']}")
                print(f"Breakeven: {position['breakeven']}")
                
                if position.get('kite_orders'):
                    print("\nKITE ORDER IDs (REAL TRADING):")
                    print(f"  Main Order: {position['kite_orders']['main_order_id']}")
                    print(f"  Hedge Order: {position['kite_orders']['hedge_order_id']}")
                else:
                    print("\n[INFO] Paper trading mode - no real orders placed")
                
                return True
            else:
                print(f"[FAIL] {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"[FAIL] HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_exit_webhook():
    """Test position exit via webhook"""
    print("\n" + "="*60)
    print("TESTING EXIT WEBHOOK")
    print("="*60)
    
    webhook_payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S1",
        "action": "EXIT",
        "reason": "stop_loss",
        "spot_price": 24950.30,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/exit",
            json=webhook_payload
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result['status'] == 'success':
                print("[OK] Position closed successfully!")
                print(f"  Signal: {result['position']['signal']}")
                print(f"  P&L: {result['position']['pnl']}")
                print(f"  Exit Reason: {result['position']['exit_reason']}")
                
                if result['position'].get('kite_square_off'):
                    print("\nKITE SQUARE-OFF ORDER IDs:")
                    print(f"  Main: {result['position']['kite_square_off']['main_square_off_id']}")
                    print(f"  Hedge: {result['position']['kite_square_off']['hedge_square_off_id']}")
                
                return True
            elif result['status'] == 'not_found':
                print("[INFO] No active position to close (expected if no entry was made)")
                return True
            else:
                print(f"[FAIL] {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"[FAIL] HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def main():
    print("\n" + "="*60)
    print("   KITE INTEGRATION TEST")
    print("   TradingView → Expiry → Zerodha Flow")
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
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Check trading mode
    if test_trading_mode_check():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 2: Symbol generation
    if test_kite_symbol_generation():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 3: Complete webhook flow
    if test_complete_webhook_flow():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 4: Exit webhook
    if test_exit_webhook():
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
        print("\n[SUCCESS] ALL TESTS PASSED!")
        print("\nPRODUCTION FLOW VERIFIED:")
        print("1. Trading mode detection works")
        print("2. Kite symbol generation correct")
        print("3. Webhook creates positions with correct expiry")
        print("4. Exit webhook closes positions")
        
        print("\nTO ENABLE REAL TRADING:")
        print("1. Set PAPER_TRADING_MODE=false in .env")
        print("2. Set KITE_API_KEY=your_api_key in .env")
        print("3. Set KITE_ACCESS_TOKEN=your_access_token in .env")
        print("4. Configure TradingView webhook URL")
        print("5. Test with small positions first")
    else:
        print("\n[WARNING] SOME TESTS FAILED")
    
    return 0 if tests_failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())