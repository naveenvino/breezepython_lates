"""
Fix missing Thursday July 17, 2025 options data
"""
import requests
from datetime import date

BASE_URL = "http://localhost:8002"

print("Fixing Missing Thursday July 17, 2025 Options Data")
print("=" * 60)

# The issue: Thursday collection was partial, missing strikes 24800-25350

print("\n1. Re-collecting Thursday data with force_refresh...")

response = requests.post(
    f"{BASE_URL}/api/v1/collect/options-direct",
    json={
        "from_date": "2025-07-17",
        "to_date": "2025-07-17",
        "symbol": "NIFTY",
        "force_refresh": True  # Force to recollect even if some data exists
    },
    timeout=300
)

if response.status_code == 200:
    data = response.json()
    print("\nCollection completed!")
    
    if "summary" in data:
        summary = data["summary"]
        print(f"\nSummary:")
        print(f"- Days processed: {summary['days_processed']}")
        print(f"- Records added: {summary['total_records_added']}")
    
    if "daily_results" in data:
        for daily in data["daily_results"]:
            if daily["status"] == "processed":
                print(f"\n{daily['date']}:")
                print(f"- Strike range: {daily['strike_range']}")
                print(f"- Strikes processed: {daily['strikes_processed']}")
                print(f"- Records added: {daily['records_added']}")
                
                if daily.get("errors"):
                    print(f"- Errors: {len(daily['errors'])}")
                    # Show first few errors
                    for err in daily['errors'][:5]:
                        print(f"  * {err}")
else:
    print(f"\nError: {response.status_code}")
    print(response.text)

print("\n" + "=" * 60)
print("\nTo prevent this issue in the future:")
print("1. Always use force_refresh=True for expiry day collection")
print("2. Add retry logic for failed strikes")
print("3. Monitor collection logs for partial failures")
print("4. Consider adding a validation step after collection")