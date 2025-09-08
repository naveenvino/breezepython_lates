"""Quick test of unified settings API"""
import requests
import json

print("Testing Unified Settings API...")
print("="*50)

# Test GET /settings
try:
    response = requests.get("http://localhost:8000/settings", timeout=5)
    if response.status_code == 200:
        data = response.json()
        settings = data.get("settings", {})
        print(f"[OK] GET /settings - Retrieved {len(settings)} settings")
        # Show first 5 settings
        for i, (key, value) in enumerate(list(settings.items())[:5]):
            print(f"  {key}: {value}")
    else:
        print(f"[FAIL] GET /settings - Status: {response.status_code}")
except Exception as e:
    print(f"[ERROR] GET /settings - {e}")

print()

# Test POST /settings
try:
    test_data = {"test_unified_key": "test_value", "test_number": 42}
    response = requests.post("http://localhost:8000/settings", json=test_data, timeout=5)
    if response.status_code == 200:
        print("[OK] POST /settings - Settings saved")
    else:
        print(f"[FAIL] POST /settings - Status: {response.status_code}")
except Exception as e:
    print(f"[ERROR] POST /settings - {e}")

# Test GET /settings/all
try:
    response = requests.get("http://localhost:8000/settings/all", timeout=5)
    if response.status_code == 200:
        data = response.json()
        namespaces = data.get("settings", {})
        print(f"[OK] GET /settings/all - Found {len(namespaces)} namespaces")
        for ns in namespaces:
            print(f"  {ns}: {len(namespaces[ns])} settings")
    else:
        print(f"[FAIL] GET /settings/all - Status: {response.status_code}")
except Exception as e:
    print(f"[ERROR] GET /settings/all - {e}")

print()
print("Test complete!")