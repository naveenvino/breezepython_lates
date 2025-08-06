"""Test the missing strikes collection endpoint"""
import requests
import json

# Test the new endpoint
print("Testing /collect/missing-from-insights endpoint")
print("=" * 60)

try:
    response = requests.post("http://localhost:8000/collect/missing-from-insights")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
        print(f"Total Records Collected: {result['records_collected']}")
        
        if 'details' in result:
            print("\nDetails by expiry:")
            for detail in result['details']:
                print(f"  Expiry: {detail['expiry']}")
                print(f"    Strikes: {detail.get('strikes', [])}")
                if 'records' in detail:
                    print(f"    Records: {detail['records']}")
                if 'error' in detail:
                    print(f"    Error: {detail['error']}")
    else:
        print(f"Error: Status code {response.status_code}")
        print(f"Response: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("ERROR: Could not connect to API. Make sure the API is running at http://localhost:8000")
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 60)
print("Comparison with existing endpoints:")
print("-" * 60)

# Compare with existing endpoints
endpoints = [
    "/api/v1/collect/options-by-signals",
    "/api/v1/collect/options-by-signals-fast", 
    "/api/v1/collect/options-by-signals-optimized"
]

test_data = {
    "from_date": "2024-07-01",
    "to_date": "2024-07-30",
    "symbol": "NIFTY",
    "strike_range": 1000  # Wider range to catch missing strikes
}

print(f"Test parameters: {test_data}")
print()

for endpoint in endpoints:
    print(f"Testing {endpoint}:")
    try:
        response = requests.post(
            f"http://localhost:8000{endpoint}",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  Status: {result['status']}")
            print(f"  Records: {result.get('records_collected', 'N/A')}")
        else:
            print(f"  Error: Status code {response.status_code}")
    except Exception as e:
        print(f"  Error: {e}")
    print()