"""
Test script to verify the candle display issue
"""
import requests
import json
import sys
import io

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("\n" + "="*70)
print("TESTING CANDLE DATA ENDPOINTS")
print("="*70)

# Test 1: Check if API server is running
try:
    health = requests.get("http://localhost:8000/api/health")
    print("\n✅ API Server is running")
except:
    print("\n❌ API Server is NOT running!")
    exit(1)

# Test 2: Check hourly candle endpoint
print("\n[1] Testing /api/breeze/hourly-candle endpoint:")
print("-" * 40)
try:
    response = requests.get("http://localhost:8000/api/breeze/hourly-candle")
    data = response.json()
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(data, indent=2)}")
    
    if data.get('success'):
        print(f"\n✅ Hourly candle data available:")
        print(f"   Time: {data['candle']['time']}")
        print(f"   Close: {data['candle']['close']}")
        print(f"   Source: {data['source']}")
    else:
        print(f"\n❌ No data: {data.get('error')}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Check NIFTY spot endpoint  
print("\n[2] Testing /api/live/nifty-spot endpoint:")
print("-" * 40)
try:
    response = requests.get("http://localhost:8000/api/live/nifty-spot")
    data = response.json()
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(data, indent=2)}")
    
    if data.get('success'):
        print(f"\n✅ NIFTY spot data available:")
        print(f"   Spot: {data.get('spot')}")
        print(f"   Source: {data.get('source')}")
    else:
        print(f"\n❌ No spot data available")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*70)
print("WHAT TO DO NEXT:")
print("="*70)
print("""
If both endpoints return data but UI shows 'No data':
1. The issue is in the JavaScript display logic
2. Check browser console for errors
3. Run in console: update1HCandleMonitor()

If endpoints return no data:
1. Check Breeze connection
2. Check if market hours matter for your data source
""")