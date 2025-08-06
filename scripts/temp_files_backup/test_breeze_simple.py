"""Simple Breeze API Test"""
import os
from breeze_connect import BreezeConnect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("Testing Breeze API Connection")
print("-" * 40)

# Get credentials from environment
api_key = os.getenv('BREEZE_API_KEY')
api_secret = os.getenv('BREEZE_API_SECRET')
session_token = os.getenv('BREEZE_API_SESSION')

print(f"API Key: {api_key[:10]}..." if api_key else "API Key: NOT FOUND")
print(f"API Secret: {api_secret[:10]}..." if api_secret else "API Secret: NOT FOUND")
print(f"Session Token: {session_token}" if session_token else "Session Token: NOT FOUND")
print("-" * 40)

try:
    # Initialize Breeze
    breeze = BreezeConnect(api_key=api_key)
    print("Step 1: Breeze object created")
    
    # Generate session
    breeze.generate_session(api_secret=api_secret, session_token=session_token)
    print("Step 2: Session generated successfully!")
    
    # Try to get customer details
    try:
        customer = breeze.get_customer_details()
        print("Step 3: Customer details retrieved:")
        print(customer)
    except Exception as e:
        print(f"Step 3: Could not get customer details: {e}")
    
    # Try to fetch some historical data
    from datetime import datetime
    
    print("\nTrying to fetch NIFTY data...")
    data = breeze.get_historical_data(
        interval="5minute",
        from_date="2025-01-20T09:15:00.000Z",
        to_date="2025-01-20T15:30:00.000Z",
        stock_code="NIFTY",
        exchange_code="NSE",
        product_type="cash"
    )
    
    if data and 'Success' in data:
        print(f"Data fetched successfully! Got {len(data['Success'])} records")
        if data['Success']:
            print(f"First record: {data['Success'][0]}")
    else:
        print(f"Data fetch result: {data}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()