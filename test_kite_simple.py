"""
Simple Kite API Integration Test
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("KITE API INTEGRATION TEST")
print("=" * 60)
print(f"Time: {datetime.now()}")
print()

# Test 1: NIFTY Spot Price
print("1. NIFTY SPOT PRICE TEST")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/live/nifty-spot", timeout=5)
    data = response.json()
    
    if data.get("success"):
        spot_data = data["data"]
        print(f"   Status: PASS")
        print(f"   Price: {spot_data.get('price', 'N/A')}")
        print(f"   Source: {spot_data.get('source', 'UNKNOWN')}")
        
        if spot_data.get('source') == 'KITE':
            print(f"   [OK] Using Kite API")
        elif spot_data.get('source') == 'BREEZE_FALLBACK':
            print(f"   [WARNING] Using Breeze fallback")
    else:
        print(f"   Status: FAIL")
        print(f"   Error: {data.get('error', 'Unknown')}")
except Exception as e:
    print(f"   Status: FAIL - {e}")
print()

# Test 2: BANKNIFTY Spot Price
print("2. BANKNIFTY SPOT PRICE TEST")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/live/banknifty-spot", timeout=5)
    data = response.json()
    
    if data.get("success"):
        spot_data = data["data"]
        print(f"   Status: PASS")
        print(f"   Price: {spot_data.get('price', 'N/A')}")
        print(f"   Source: {spot_data.get('source', 'UNKNOWN')}")
    else:
        print(f"   Status: FAIL")
        print(f"   Error: {data.get('error', 'Unknown')}")
except Exception as e:
    print(f"   Status: FAIL - {e}")
print()

# Test 3: Option Chain
print("3. OPTION CHAIN TEST")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/option-chain?strike=25000&type=PE", timeout=10)
    data = response.json()
    
    if data:
        print(f"   Status: PASS")
        print(f"   Spot: {data.get('spot_price', 'N/A')}")
        print(f"   ATM: {data.get('atm_strike', 'N/A')}")
        print(f"   Source: {data.get('data_source', 'UNKNOWN')}")
        print(f"   Options: {len(data.get('options', []))}")
    else:
        print(f"   Status: FAIL - No data")
except Exception as e:
    print(f"   Status: FAIL - {e}")
print()

# Test 4: Orders API
print("4. ORDERS API TEST")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/orders", timeout=5)
    data = response.json()
    
    if "orders" in data:
        print(f"   Status: PASS")
        print(f"   Total Orders: {len(data['orders'])}")
        
        # Check AMO orders
        amo_orders = [o for o in data['orders'] if o.get('status') == 'AMO REQ RECEIVED']
        if amo_orders:
            print(f"   AMO Orders: {len(amo_orders)}")
    else:
        print(f"   Status: FAIL")
except Exception as e:
    print(f"   Status: FAIL - {e}")
print()

# Test 5: Positions API
print("5. POSITIONS API TEST")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/positions", timeout=5)
    data = response.json()
    
    if "positions" in data:
        print(f"   Status: PASS")
        positions = data['positions']
        print(f"   Open Positions: {len(positions)}")
        
        if positions:
            total_pnl = sum(p.get('pnl', 0) for p in positions)
            print(f"   Total P&L: Rs.{total_pnl:,.2f}")
    else:
        print(f"   Status: FAIL")
except Exception as e:
    print(f"   Status: FAIL - {e}")
print()

# Test 6: Kite Status
print("6. KITE CONNECTION STATUS")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/kite/status", timeout=5)
    data = response.json()
    
    if data.get("connected"):
        print(f"   Status: CONNECTED")
        print(f"   Has Token: {data.get('has_access_token', False)}")
    else:
        print(f"   Status: DISCONNECTED")
        if 'error' in data:
            print(f"   Error: {data['error']}")
except Exception as e:
    print(f"   Status: FAIL - {e}")

print()
print("=" * 60)
print("TEST COMPLETE")
print("=" * 60)