"""Test fetching options data"""
import asyncio
from datetime import datetime
from src.infrastructure.services.breeze_service import BreezeService

async def test_options():
    print("Testing Options Data Fetch")
    print("=" * 50)
    
    breeze = BreezeService()
    breeze._initialize()
    
    # Test parameters
    from_date = datetime(2025, 2, 3, 9, 15)
    to_date = datetime(2025, 2, 3, 15, 30)
    expiry = datetime(2025, 2, 6)  # Thursday
    strike = 23300
    
    print(f"Fetching {strike} PE for expiry {expiry.date()}")
    
    data = await breeze.get_historical_data(
        interval="5minute",
        from_date=from_date,
        to_date=to_date,
        stock_code="NIFTY",
        exchange_code="NFO",
        product_type="options",
        strike_price=str(strike),
        right="Put",
        expiry_date=expiry
    )
    
    if data and 'Success' in data:
        records = data['Success']
        print(f"Got {len(records)} records")
        if records:
            print(f"First: {records[0]}")
    elif data and 'Error' in data:
        print(f"Error: {data['Error']}")
    else:
        print(f"Response: {data}")

if __name__ == "__main__":
    asyncio.run(test_options())