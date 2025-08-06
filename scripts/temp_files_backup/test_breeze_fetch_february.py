"""Test fetching February data directly from Breeze"""
import asyncio
from datetime import datetime
from src.infrastructure.services.breeze_service import BreezeService

async def test_february_data():
    print("Testing Breeze API fetch for February 2025")
    print("-" * 50)
    
    breeze = BreezeService()
    breeze._initialize()
    
    from_date = datetime(2025, 2, 3, 9, 15)  # Monday
    to_date = datetime(2025, 2, 3, 15, 30)
    
    print(f"Fetching from {from_date} to {to_date}")
    
    data = await breeze.get_historical_data(
        interval="5minute",
        from_date=from_date,
        to_date=to_date,
        stock_code="NIFTY",
        exchange_code="NSE",
        product_type="cash"
    )
    
    if data and 'Success' in data:
        records = data['Success']
        print(f"Got {len(records)} records")
        if records:
            print(f"First: {records[0]}")
            print(f"Last: {records[-1]}")
    elif data and 'Error' in data:
        print(f"Error: {data['Error']}")
    else:
        print(f"Response: {data}")

if __name__ == "__main__":
    asyncio.run(test_february_data())