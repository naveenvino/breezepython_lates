"""Quick API Test - Check if order endpoints are working"""

import requests
import json

print("Quick API Status Check")
print("=" * 50)

tests = [
    ("All Orders", "http://localhost:8000/orders"),
    ("Active Orders", "http://localhost:8000/api/orders/active"),
    ("Positions", "http://localhost:8000/positions")
]

results = []

for name, url in tests:
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if name == "All Orders":
                count = len(data.get('orders', []))
                results.append(f"[OK] {name}: {count} orders")
            elif name == "Active Orders":
                count = data.get('count', 0)
                results.append(f"[OK] {name}: {count} active")
            elif name == "Positions":
                count = len(data.get('positions', []))
                results.append(f"[OK] {name}: {count} positions")
        else:
            results.append(f"[FAIL] {name}: Error {response.status_code}")
    except requests.exceptions.ConnectionError:
        results.append(f"[FAIL] {name}: Server not running")
    except Exception as e:
        results.append(f"[FAIL] {name}: {str(e)[:30]}")

print("\nResults:")
for result in results:
    print(f"  {result}")

print("\n" + "=" * 50)

# Check if server is running
all_failed = all("[FAIL]" in r for r in results)
if all_failed:
    print("\nSTATUS: API server is not running or not responding")
    print("\nTo fix:")
    print("1. Open a new terminal")
    print("2. Run: python unified_api_correct.py")
    print("3. Wait for 'Application startup complete'")
    print("4. Then run this test again")
else:
    some_working = any("[OK]" in r for r in results)
    if some_working:
        print("\nSTATUS: API is partially working")
        print("Some endpoints are responding")
    else:
        print("\nSTATUS: API is running but authentication failing")
        print("The server may need to be restarted to load new credentials")