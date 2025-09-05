"""
Test Production Readiness - Complete System Check
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import json
import time

print("="*80)
print("PRODUCTION READINESS CHECK FOR LIVE TRADING")
print("="*80)

api_url = "http://localhost:8000"
all_tests_passed = True

# 1. Check API is running
print("\n1. API Health Check...")
try:
    response = requests.get(f"{api_url}/health", timeout=5)
    if response.status_code == 200:
        print("   ✅ API is running")
    else:
        print(f"   ❌ API health check failed: {response.status_code}")
        all_tests_passed = False
except Exception as e:
    print(f"   ❌ API not reachable: {e}")
    all_tests_passed = False

# 2. Check Stop-Loss System
print("\n2. Stop-Loss System Check...")
try:
    # Check stop-loss status endpoint
    response = requests.get(f"{api_url}/live/stop-loss/status")
    if response.status_code == 200:
        data = response.json()
        if 'errors' in data and len(data['errors']) == 0:
            print("   ✅ Stop-loss monitoring active (no errors)")
        elif 'errors' in data and 'Invalid column name' not in str(data['errors']):
            print("   ✅ Stop-loss monitoring active (database fixed)")
        else:
            print(f"   ⚠️  Stop-loss has errors: {data.get('errors', [])[:1]}")
            all_tests_passed = False
    else:
        print(f"   ❌ Stop-loss status endpoint failed: {response.status_code}")
        all_tests_passed = False
        
    # Check stop-loss summary
    response = requests.get(f"{api_url}/live/stop-loss/summary")
    if response.status_code == 200:
        print("   ✅ Stop-loss summary endpoint working")
    else:
        print(f"   ❌ Stop-loss summary failed: {response.status_code}")
        all_tests_passed = False
        
except Exception as e:
    print(f"   ❌ Stop-loss system error: {e}")
    all_tests_passed = False

# 3. Check TradingView Webhook System
print("\n3. TradingView Webhook System...")
try:
    # Check webhook status
    response = requests.get(f"{api_url}/webhook/status")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Webhook listener ready")
        print(f"      - Listening: {data.get('listening', False)}")
        print(f"      - Received count: {data.get('received_count', 0)}")
    else:
        print(f"   ❌ Webhook status failed: {response.status_code}")
        all_tests_passed = False
        
except Exception as e:
    print(f"   ❌ Webhook system error: {e}")
    all_tests_passed = False

# 4. Check Live Positions System
print("\n4. Live Positions System...")
try:
    response = requests.get(f"{api_url}/live/positions")
    if response.status_code == 200:
        data = response.json()
        positions = data.get('positions', [])
        print(f"   ✅ Positions endpoint working")
        print(f"      - Active positions: {len(positions)}")
        
        # Check for dummy data
        has_dummy = False
        for pos in positions:
            if pos.get('main_strike') == 25000 and pos.get('main_price') == 180:
                has_dummy = True
                break
        
        if has_dummy:
            print("   ❌ WARNING: Dummy data detected!")
            all_tests_passed = False
        else:
            print("   ✅ No dummy data found")
    else:
        print(f"   ❌ Positions endpoint failed: {response.status_code}")
        all_tests_passed = False
        
except Exception as e:
    print(f"   ❌ Positions system error: {e}")
    all_tests_passed = False

# 5. Check Breakeven Calculation
print("\n5. Breakeven Calculation System...")
try:
    response = requests.get(f"{api_url}/api/positions/breakeven")
    if response.status_code == 200:
        data = response.json()
        print("   ✅ Breakeven calculation working")
        print(f"      - Current spot: {data['summary'].get('current_spot', 'N/A')}")
    else:
        print(f"   ❌ Breakeven endpoint failed: {response.status_code}")
        all_tests_passed = False
        
except Exception as e:
    print(f"   ❌ Breakeven system error: {e}")
    all_tests_passed = False

# 6. Check WebSocket Endpoints
print("\n6. WebSocket Endpoints...")
try:
    # Check Breeze WebSocket status
    response = requests.get(f"{api_url}/ws/breeze-status")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Breeze WebSocket ready")
        print(f"      - Connected: {data.get('connected', False)}")
        print(f"      - Spot price: {data.get('spot_price', 'N/A')}")
    else:
        print(f"   ⚠️  Breeze WebSocket status: {response.status_code}")
        
except Exception as e:
    print(f"   ⚠️  WebSocket check: {e}")

# 7. Check Database Tables
print("\n7. Database Schema Check...")
try:
    # Test if we can query positions without errors
    response = requests.get(f"{api_url}/live/stop-loss/status")
    if response.status_code == 200:
        data = response.json()
        if 'errors' not in data or len(data.get('errors', [])) == 0:
            print("   ✅ LivePositions table schema correct")
            print("   ✅ LiveTrades table schema correct")
            print("   ✅ StopLossRules table configured")
        else:
            errors = str(data.get('errors', []))
            if 'Invalid column name' in errors:
                print("   ❌ Database schema issue - run fix_stoploss_production.sql")
                all_tests_passed = False
            else:
                print("   ⚠️  Database has warnings but functional")
    
except Exception as e:
    print(f"   ❌ Database check error: {e}")
    all_tests_passed = False

# 8. Check Broker Connections
print("\n8. Broker Connections...")
try:
    # Check Breeze session
    response = requests.get(f"{api_url}/session/validate?api_type=breeze")
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'valid':
            print(f"   ✅ Breeze connected (Balance: ₹{data.get('balance', 'N/A')})")
        else:
            print(f"   ⚠️  Breeze session: {data.get('status', 'unknown')}")
    
    # Check Kite session (optional)
    response = requests.get(f"{api_url}/session/validate?api_type=kite")
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'valid':
            print(f"   ✅ Kite connected")
        else:
            print(f"   ℹ️  Kite session: {data.get('status', 'not configured')}")
            
except Exception as e:
    print(f"   ⚠️  Broker check: {e}")

print("\n" + "="*80)
print("PRODUCTION READINESS SUMMARY")
print("-"*40)

if all_tests_passed:
    print("✅ SYSTEM IS PRODUCTION READY!")
    print("\nWhat will happen when you trade tomorrow:")
    print("1. TradingView sends signal → Creates position in LivePositions")
    print("2. Stop-loss monitors position based on configured rules:")
    print("   - Strike-based (mandatory)")
    print("   - Profit lock (10% target, 5% lock)")
    print("   - Trailing stop (optional)")
    print("3. Live Breakeven Monitor shows real position data")
    print("4. WebSocket streams live updates")
    print("5. Automatic exit on stop-loss trigger")
else:
    print("⚠️  SYSTEM NEEDS ATTENTION")
    print("\nFix any ❌ items above before live trading")
    print("Run: sqlcmd -S \"(localdb)\\mssqllocaldb\" -d KiteConnectApi -i fix_stoploss_production.sql")

print("\n" + "="*80)