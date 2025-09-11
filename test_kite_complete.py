"""
Comprehensive Kite API Integration Test
Tests all Kite endpoints and functionality
"""
import requests
import json
from datetime import datetime
import time

BASE_URL = "http://localhost:8000"

def test_with_retry(test_func, max_retries=3):
    """Helper to retry tests"""
    for i in range(max_retries):
        try:
            return test_func()
        except Exception as e:
            if i == max_retries - 1:
                raise
            time.sleep(1)

print("=" * 60)
print("COMPREHENSIVE KITE API INTEGRATION TEST")
print("=" * 60)
print(f"Testing Time: {datetime.now()}")
print(f"Base URL: {BASE_URL}")
print()

# Test Results Summary
test_results = {}

# Test 1: Health Check
print("1. HEALTH CHECK")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/health", timeout=5)
    test_results["Health Check"] = response.status_code == 200
    print(f"   Status: {'PASS' if response.status_code == 200 else 'FAIL'}")
    print(f"   Response: {response.json()}")
except Exception as e:
    test_results["Health Check"] = False
    print(f"   Status: ❌ FAIL - {e}")
print()

# Test 2: NIFTY Spot Price (Kite)
print("2. NIFTY SPOT PRICE (Kite API)")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/live/nifty-spot", timeout=5)
    data = response.json()
    
    if data.get("success") and data.get("data"):
        spot_data = data["data"]
        test_results["NIFTY Spot"] = True
        print(f"   Status: ✅ PASS")
        print(f"   Price: {spot_data.get('price', 'N/A')}")
        print(f"   Change: {spot_data.get('change', 0):.2f} ({spot_data.get('change_percent', 0):.2f}%)")
        print(f"   Volume: {spot_data.get('volume', 0):,}")
        print(f"   Source: {spot_data.get('source', 'UNKNOWN')}")
        
        # Check if using Kite
        if spot_data.get('source') == 'KITE':
            print(f"   ✅ Using Kite API as primary source")
        elif spot_data.get('source') == 'BREEZE_FALLBACK':
            print(f"   ⚠️ Using Breeze fallback (Kite might be unavailable)")
    else:
        test_results["NIFTY Spot"] = False
        print(f"   Status: ❌ FAIL")
        print(f"   Error: {data.get('error', 'Unknown error')}")
except Exception as e:
    test_results["NIFTY Spot"] = False
    print(f"   Status: ❌ FAIL - {e}")
print()

# Test 3: BANKNIFTY Spot Price (Kite)
print("3. BANKNIFTY SPOT PRICE (Kite API)")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/live/banknifty-spot", timeout=5)
    data = response.json()
    
    if data.get("success") and data.get("data"):
        spot_data = data["data"]
        test_results["BANKNIFTY Spot"] = True
        print(f"   Status: ✅ PASS")
        print(f"   Price: {spot_data.get('price', 'N/A')}")
        print(f"   Source: {spot_data.get('source', 'UNKNOWN')}")
    else:
        test_results["BANKNIFTY Spot"] = False
        print(f"   Status: ❌ FAIL")
        print(f"   Error: {data.get('error', 'Unknown error')}")
except Exception as e:
    test_results["BANKNIFTY Spot"] = False
    print(f"   Status: ❌ FAIL - {e}")
print()

# Test 4: Option Chain (Kite)
print("4. OPTION CHAIN (Kite API)")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/option-chain?strike=25000&type=PE", timeout=10)
    data = response.json()
    
    if data:
        test_results["Option Chain"] = True
        print(f"   Status: ✅ PASS")
        print(f"   Spot Price: {data.get('spot_price', 'N/A')}")
        print(f"   ATM Strike: {data.get('atm_strike', 'N/A')}")
        print(f"   Data Source: {data.get('data_source', 'UNKNOWN')}")
        print(f"   Options Count: {len(data.get('options', []))}")
        
        # Check data source
        if data.get('data_source') == 'KITE':
            print(f"   ✅ Using Kite API for option chain")
        elif data.get('data_source') == 'BREEZE_FALLBACK':
            print(f"   ⚠️ Using Breeze fallback for option chain")
            
        # Display first few options if available
        options = data.get('options', [])
        if options:
            print(f"\n   Sample Options:")
            for opt in options[:3]:
                print(f"     - Strike: {opt['strike']} {opt['type']}, Price: {opt['price']}, OI: {opt['oi']}")
    else:
        test_results["Option Chain"] = False
        print(f"   Status: ❌ FAIL - No data returned")
except Exception as e:
    test_results["Option Chain"] = False
    print(f"   Status: ❌ FAIL - {e}")
print()

# Test 5: Kite Connection Status
print("5. KITE CONNECTION STATUS")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/kite/status", timeout=5)
    data = response.json()
    
    if data.get("connected"):
        test_results["Kite Connection"] = True
        print(f"   Status: ✅ CONNECTED")
        print(f"   Has Access Token: {data.get('has_access_token', False)}")
    else:
        test_results["Kite Connection"] = False
        print(f"   Status: ❌ DISCONNECTED")
        print(f"   Error: {data.get('error', 'Unknown')}")
except Exception as e:
    test_results["Kite Connection"] = False
    print(f"   Status: ❌ FAIL - {e}")
print()

# Test 6: Orders API
print("6. ORDERS API (Kite)")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/orders", timeout=5)
    data = response.json()
    
    if "orders" in data:
        test_results["Orders API"] = True
        print(f"   Status: ✅ PASS")
        print(f"   Total Orders Today: {len(data['orders'])}")
        
        # Check for active orders
        active_statuses = ['OPEN', 'TRIGGER PENDING', 'AMO REQ RECEIVED']
        active_orders = [o for o in data['orders'] if o.get('status') in active_statuses]
        print(f"   Active Orders: {len(active_orders)}")
        
        # Show AMO orders
        amo_orders = [o for o in data['orders'] if o.get('status') == 'AMO REQ RECEIVED']
        if amo_orders:
            print(f"   AMO Orders: {len(amo_orders)}")
            for order in amo_orders[:2]:
                print(f"     - {order.get('tradingsymbol')}: {order.get('transaction_type')} {order.get('quantity')} @ {order.get('price', 'MARKET')}")
    else:
        test_results["Orders API"] = False
        print(f"   Status: ❌ FAIL")
        print(f"   Error: {data.get('error', 'No orders data')}")
except Exception as e:
    test_results["Orders API"] = False
    print(f"   Status: ❌ FAIL - {e}")
print()

# Test 7: Positions API
print("7. POSITIONS API (Kite)")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/positions", timeout=5)
    data = response.json()
    
    if "positions" in data:
        test_results["Positions API"] = True
        print(f"   Status: ✅ PASS")
        
        positions = data['positions']
        if positions:
            print(f"   Open Positions: {len(positions)}")
            total_pnl = sum(p.get('pnl', 0) for p in positions)
            print(f"   Total P&L: ₹{total_pnl:,.2f}")
            
            # Show first few positions
            for pos in positions[:3]:
                print(f"     - {pos.get('tradingsymbol')}: Qty={pos.get('quantity')} P&L=₹{pos.get('pnl', 0):,.2f}")
        else:
            print(f"   No open positions")
    else:
        test_results["Positions API"] = False
        print(f"   Status: ❌ FAIL")
        print(f"   Error: {data.get('error', 'No positions data')}")
except Exception as e:
    test_results["Positions API"] = False
    print(f"   Status: ❌ FAIL - {e}")
print()

# Test 8: Market Status
print("8. MARKET STATUS CHECK")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/market/live", timeout=5)
    data = response.json()
    
    if data:
        test_results["Market Status"] = True
        print(f"   Status: ✅ PASS")
        
        market_data = data.get('market', {})
        print(f"   Market Open: {market_data.get('is_open', False)}")
        print(f"   Current Time: {market_data.get('current_time', 'N/A')}")
        
        if not market_data.get('is_open'):
            print(f"   Next Open: {market_data.get('next_open', 'N/A')}")
    else:
        test_results["Market Status"] = False
        print(f"   Status: ❌ FAIL - No data")
except Exception as e:
    test_results["Market Status"] = False
    print(f"   Status: ❌ FAIL - {e}")
print()

# Test 9: Fast Option Chain
print("9. FAST OPTION CHAIN")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/option-chain/fast?symbol=NIFTY&strikes=5", timeout=10)
    data = response.json()
    
    if data.get("status") == "success":
        test_results["Fast Option Chain"] = True
        print(f"   Status: ✅ PASS")
        
        chain_data = data.get("data", {})
        print(f"   Spot Price: {chain_data.get('spot_price', 'N/A')}")
        print(f"   ATM Strike: {chain_data.get('atm_strike', 'N/A')}")
        print(f"   Expiry: {chain_data.get('expiry', 'N/A')}")
        print(f"   Data Source: {chain_data.get('data_source', 'N/A')}")
        
        chain = chain_data.get('chain', [])
        if chain:
            print(f"   Strikes Available: {len(chain)}")
            
            # Find ATM option
            atm_strike = chain_data.get('atm_strike')
            for item in chain:
                if item['strike'] == atm_strike:
                    print(f"\n   ATM Option Details:")
                    print(f"     CE LTP: {item.get('call_ltp', 0)}")
                    print(f"     PE LTP: {item.get('put_ltp', 0)}")
                    print(f"     CE OI: {item.get('call_oi', 0):,}")
                    print(f"     PE OI: {item.get('put_oi', 0):,}")
                    break
    else:
        test_results["Fast Option Chain"] = False
        print(f"   Status: ❌ FAIL")
        print(f"   Error: {data.get('error', 'Unknown error')}")
except Exception as e:
    test_results["Fast Option Chain"] = False
    print(f"   Status: ❌ FAIL - {e}")
print()

# Final Summary
print("=" * 60)
print("TEST SUMMARY")
print("=" * 60)

total_tests = len(test_results)
passed_tests = sum(1 for v in test_results.values() if v)
failed_tests = total_tests - passed_tests

for test_name, result in test_results.items():
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{test_name:.<30} {status}")

print()
print(f"Total Tests: {total_tests}")
print(f"Passed: {passed_tests}")
print(f"Failed: {failed_tests}")
print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

if passed_tests == total_tests:
    print("\n🎉 ALL TESTS PASSED! Kite integration is working correctly.")
elif passed_tests >= total_tests * 0.7:
    print("\n⚠️ Most tests passed but some issues need attention.")
else:
    print("\n❌ Multiple failures detected. Please check the integration.")

print("\n" + "=" * 60)