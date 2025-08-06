"""Test why April 2025 data is not being fetched"""
import asyncio
from datetime import datetime
from src.infrastructure.services.breeze_service import BreezeService

async def test_april_data():
    print("Testing April 2025 Data Fetch")
    print("=" * 50)
    
    breeze = BreezeService()
    breeze._initialize()
    
    # Test NIFTY data for April first
    print("\n1. Testing NIFTY data for April 7-10, 2025:")
    from_date = datetime(2025, 4, 7, 9, 15)
    to_date = datetime(2025, 4, 10, 15, 30)
    
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
        print(f"   NIFTY: Got {len(records)} records")
        if records:
            print(f"   First: {records[0].get('datetime')} - Close: {records[0].get('close')}")
    elif data and 'Error' in data:
        print(f"   NIFTY Error: {data['Error']}")
    else:
        print(f"   NIFTY Response: {data}")
    
    # Test specific option strike
    print("\n2. Testing Option 21700PE for April 10, 2025 expiry:")
    expiry = datetime(2025, 4, 10)  # Thursday
    
    data = await breeze.get_historical_data(
        interval="5minute",
        from_date=from_date,
        to_date=to_date,
        stock_code="NIFTY",
        exchange_code="NFO",
        product_type="options",
        strike_price="21700",
        right="Put",
        expiry_date=expiry
    )
    
    if data and 'Success' in data:
        records = data['Success']
        print(f"   21700PE: Got {len(records)} records")
        if records:
            print(f"   First: {records[0]}")
    elif data and 'Error' in data:
        print(f"   21700PE Error: {data['Error']}")
    else:
        print(f"   21700PE Response: {data}")
    
    # Try different expiry format
    print("\n3. Testing with different date - April 3, 2025 (Thursday):")
    expiry2 = datetime(2025, 4, 3)
    from_date2 = datetime(2025, 4, 1, 9, 15)
    to_date2 = datetime(2025, 4, 3, 15, 30)
    
    data = await breeze.get_historical_data(
        interval="5minute",
        from_date=from_date2,
        to_date=to_date2,
        stock_code="NIFTY",
        exchange_code="NFO",
        product_type="options",
        strike_price="22000",
        right="Call",
        expiry_date=expiry2
    )
    
    if data and 'Success' in data:
        records = data['Success']
        print(f"   22000CE (Apr 3 expiry): Got {len(records)} records")
    elif data and 'Error' in data:
        print(f"   22000CE Error: {data['Error']}")
    else:
        print(f"   22000CE Response: {data}")
    
    # Check what data IS available
    print("\n4. Testing March data (which we know works):")
    march_from = datetime(2025, 3, 3, 9, 15)
    march_to = datetime(2025, 3, 3, 15, 30)
    march_expiry = datetime(2025, 3, 6)  # Thursday
    
    data = await breeze.get_historical_data(
        interval="5minute",
        from_date=march_from,
        to_date=march_to,
        stock_code="NIFTY",
        exchange_code="NFO",
        product_type="options",
        strike_price="22300",
        right="Put",
        expiry_date=march_expiry
    )
    
    if data and 'Success' in data:
        records = data['Success']
        print(f"   22300PE (Mar 6 expiry): Got {len(records)} records")
    
    print("\n" + "=" * 50)
    print("Conclusion:")
    print("If April data returns 0 records but March data works,")
    print("it likely means April 2025 data is not yet available in Breeze API.")

if __name__ == "__main__":
    asyncio.run(test_april_data())