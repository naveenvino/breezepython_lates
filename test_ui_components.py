"""
Test TradingView Pro UI Components
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("TRADINGVIEW PRO UI COMPONENT TEST")
print("=" * 60)
print(f"Time: {datetime.now()}")
print()

# Test Results
results = {}

# 1. Test NIFTY Spot Price API
print("1. NIFTY SPOT PRICE API")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/live/nifty-spot", timeout=5)
    data = response.json()
    
    if data.get("success") and data.get("data"):
        price = data["data"].get("price") or data["data"].get("ltp")
        source = data["data"].get("source", "UNKNOWN")
        results["NIFTY Spot"] = f"PASS - {price} from {source}"
        print(f"   Status: PASS")
        print(f"   Price: {price}")
        print(f"   Source: {source}")
    else:
        results["NIFTY Spot"] = "FAIL - No data"
        print(f"   Status: FAIL")
        print(f"   Error: {data.get('error', 'No data')}")
except Exception as e:
    results["NIFTY Spot"] = f"FAIL - {e}"
    print(f"   Status: FAIL - {e}")
print()

# 2. Test Option Chain
print("2. OPTION CHAIN API")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/option-chain/fast?symbol=NIFTY&strikes=5", timeout=10)
    data = response.json()
    
    if data.get("status") == "success" and data.get("data"):
        spot_price = data["data"].get("spot_price")
        chain_length = len(data["data"].get("chain", []))
        source = data["data"].get("data_source", "UNKNOWN")
        results["Option Chain"] = f"PASS - {chain_length} strikes"
        print(f"   Status: PASS")
        print(f"   Spot Price: {spot_price}")
        print(f"   Strikes: {chain_length}")
        print(f"   Source: {source}")
    else:
        results["Option Chain"] = "FAIL - No data"
        print(f"   Status: FAIL")
        print(f"   Error: {data.get('error', 'No data')}")
except Exception as e:
    results["Option Chain"] = f"FAIL - {e}"
    print(f"   Status: FAIL - {e}")
print()

# 3. Test Active Orders
print("3. ACTIVE ORDERS API")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/orders/active", timeout=5)
    data = response.json()
    
    if "orders" in data:
        order_count = data.get("count", 0)
        results["Active Orders"] = f"PASS - {order_count} orders"
        print(f"   Status: PASS")
        print(f"   Active Orders: {order_count}")
    else:
        results["Active Orders"] = "FAIL - No data"
        print(f"   Status: FAIL")
except Exception as e:
    results["Active Orders"] = f"FAIL - {e}"
    print(f"   Status: FAIL - {e}")
print()

# 4. Test Positions
print("4. POSITIONS API")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/live/positions", timeout=5)
    data = response.json()
    
    if "positions" in data:
        position_count = len(data["positions"])
        total_pnl = data.get("total_pnl", 0)
        results["Positions"] = f"PASS - {position_count} positions"
        print(f"   Status: PASS")
        print(f"   Open Positions: {position_count}")
        print(f"   Total P&L: Rs.{total_pnl:,.2f}")
    else:
        results["Positions"] = "FAIL - No data"
        print(f"   Status: FAIL")
except Exception as e:
    results["Positions"] = f"FAIL - {e}"
    print(f"   Status: FAIL - {e}")
print()

# 5. Test Hourly Candle
print("5. HOURLY CANDLE API")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/breeze/hourly-candle", timeout=5)
    data = response.json()
    
    if data.get("success") and data.get("candle"):
        candle = data["candle"]
        close_price = candle.get("close")
        results["Hourly Candle"] = f"PASS - Close: {close_price}"
        print(f"   Status: PASS")
        print(f"   Close: {close_price}")
        print(f"   Time: {candle.get('datetime')}")
    else:
        results["Hourly Candle"] = "FAIL - No data"
        print(f"   Status: FAIL")
        print(f"   Error: {data.get('error', 'No data')}")
except Exception as e:
    results["Hourly Candle"] = f"FAIL - {e}"
    print(f"   Status: FAIL - {e}")
print()

# 6. Test Webhook Status
print("6. WEBHOOK STATUS API")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/api/webhook/status", timeout=5)
    data = response.json()
    
    if "webhook_active" in data:
        webhook_active = data["webhook_active"]
        results["Webhook Status"] = f"PASS - {'Active' if webhook_active else 'Inactive'}"
        print(f"   Status: PASS")
        print(f"   Webhook: {'Active' if webhook_active else 'Inactive'}")
        print(f"   Last Alert: {data.get('last_alert_time', 'Never')}")
    else:
        results["Webhook Status"] = "FAIL - No data"
        print(f"   Status: FAIL")
except Exception as e:
    results["Webhook Status"] = f"FAIL - {e}"
    print(f"   Status: FAIL - {e}")
print()

# 7. Test Kite WebSocket Status
print("7. KITE WEBSOCKET STATUS")
print("-" * 40)
try:
    response = requests.get(f"{BASE_URL}/kite/status", timeout=5)
    data = response.json()
    
    if data.get("connected"):
        results["Kite WebSocket"] = "PASS - Connected"
        print(f"   Status: PASS")
        print(f"   Connected: Yes")
        print(f"   Has Token: {data.get('has_access_token', False)}")
    else:
        results["Kite WebSocket"] = "FAIL - Disconnected"
        print(f"   Status: FAIL")
        print(f"   Connected: No")
except Exception as e:
    results["Kite WebSocket"] = f"FAIL - {e}"
    print(f"   Status: FAIL - {e}")
print()

# Summary
print("=" * 60)
print("TEST SUMMARY")
print("=" * 60)

passed = 0
failed = 0

for component, result in results.items():
    status = "PASS" if "PASS" in result else "FAIL"
    if status == "PASS":
        passed += 1
    else:
        failed += 1
    print(f"{component:.<30} {result}")

print()
print(f"Total Tests: {len(results)}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print(f"Success Rate: {(passed/len(results))*100:.1f}%")

if passed == len(results):
    print("\nALL UI COMPONENTS WORKING! TradingView Pro is ready.")
elif passed >= len(results) * 0.7:
    print("\nMost components working. Check failed items.")
else:
    print("\nMultiple failures detected. UI may not function properly.")

print("\n" + "=" * 60)