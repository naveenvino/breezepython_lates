"""
Check Breeze session status
"""
import os
from breeze_connect import BreezeConnect
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

print("=" * 60)
print("BREEZE SESSION STATUS CHECK")
print("=" * 60)

# Get credentials
api_key = os.getenv('BREEZE_API_KEY')
api_secret = os.getenv('BREEZE_API_SECRET')
session_token = os.getenv('BREEZE_API_SESSION')

print(f"\nAPI Key: {api_key[:10]}...")
print(f"API Secret: {api_secret[:10]}...")
print(f"Session Token: {session_token}")

# Try to initialize
print("\nTesting session...")
breeze = BreezeConnect(api_key=api_key)

try:
    breeze.generate_session(
        api_secret=api_secret,
        session_token=session_token
    )
    print("[OK] Session initialized successfully")
    
    # Try to fetch data
    print("\nTesting data fetch...")
    data = breeze.get_historical_data_v2(
        interval="5minute",
        from_date="2025-01-23T00:00:00.000Z",
        to_date="2025-01-23T23:59:59.000Z",
        stock_code="NIFTY",
        exchange_code="NSE",
        product_type="cash"
    )
    if data and 'Success' in data:
        print(f"[OK] Data fetch successful! Got {len(data['Success'])} records")
        print("\n[SUCCESS] SESSION IS WORKING - API ENDPOINTS SHOULD WORK")
    else:
        print("[FAIL] Data fetch returned no records")
        
except Exception as e:
    error_msg = str(e)
    if "Session key is expired" in error_msg:
        print("[FAIL] SESSION EXPIRED - You need a fresh session token")
        print("\nTo fix this:")
        print("1. Go to: https://api.icicidirect.com/apiuser/login")
        print("2. Login and get the new session token from the URL")
        print("3. Update BREEZE_API_SESSION in .env file")
        print("4. Restart the API server")
    elif "Unable to retrieve customer details" in error_msg:
        print("[WARN] Customer details error (this is normal)")
        print("Continuing with data fetch test...")
        
        # Try data fetch anyway
        try:
            data = breeze.get_historical_data_v2(
                interval="5minute",
                from_date="2025-01-23T00:00:00.000Z",
                to_date="2025-01-23T23:59:59.000Z",
                stock_code="NIFTY",
                exchange_code="NSE",
                product_type="cash"
            )
            if data and 'Success' in data:
                print(f"[OK] Data fetch successful! Got {len(data['Success'])} records")
                print("\n[SUCCESS] SESSION IS WORKING - API ENDPOINTS SHOULD WORK")
            else:
                print("[FAIL] Data fetch failed")
        except Exception as e2:
            print(f"[FAIL] Data fetch error: {e2}")
    else:
        print(f"[FAIL] Unexpected error: {error_msg}")

print("\n" + "=" * 60)