"""Test Breeze API Connection"""
import asyncio
import logging
from datetime import datetime, timedelta
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.data_collection_service import DataCollectionService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_breeze_connection():
    """Test if Breeze API is working"""
    print("\n=== Testing Breeze API Connection ===\n")
    
    # Initialize Breeze Service
    breeze = BreezeService()
    breeze._initialize()
    
    if breeze._breeze is None:
        print("❌ Breeze API not initialized - check credentials")
        return False
    
    print("✅ Breeze API initialized")
    
    # Test fetching some data
    from_date = datetime(2025, 1, 20, 9, 15)
    to_date = datetime(2025, 1, 20, 15, 30)
    
    print(f"\nTesting data fetch from {from_date} to {to_date}")
    
    try:
        # Test NIFTY data fetch
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
            print(f"✅ Got {len(records)} NIFTY records")
            if records and len(records) > 0:
                print(f"Sample record: {records[0]}")
        elif data and 'Error' in data:
            print(f"❌ Breeze API Error: {data['Error']}")
        else:
            print(f"❌ Unexpected response: {data}")
            
    except Exception as e:
        print(f"❌ Exception during API call: {e}")
        import traceback
        traceback.print_exc()
    
    return True

async def test_data_collection_service():
    """Test the data collection service"""
    print("\n=== Testing Data Collection Service ===\n")
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # Test with a date that should fetch data
    from_date = datetime(2025, 1, 20)
    to_date = datetime(2025, 1, 24)
    
    print(f"Testing NIFTY collection from {from_date.date()} to {to_date.date()}")
    
    try:
        # This should trigger actual API calls
        records = await data_svc.collect_nifty_data(
            from_date.date(),
            to_date.date(),
            "NIFTY",
            force_refresh=True  # Force fetching even if data exists
        )
        
        print(f"✅ Collection returned {records} records")
        
    except Exception as e:
        print(f"❌ Error in data collection: {e}")
        import traceback
        traceback.print_exc()

async def test_options_collection():
    """Test options data collection"""
    print("\n=== Testing Options Collection ===\n")
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    from_date = datetime(2025, 1, 20).date()
    to_date = datetime(2025, 1, 24).date()
    
    print(f"Testing options collection from {from_date} to {to_date}")
    
    try:
        records = await data_svc.collect_options_data(
            from_date,
            to_date,
            "NIFTY",
            strike_range=300
        )
        
        print(f"✅ Options collection returned {records} records")
        
    except Exception as e:
        print(f"❌ Error in options collection: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all tests"""
    await test_breeze_connection()
    await test_data_collection_service()
    await test_options_collection()

if __name__ == "__main__":
    asyncio.run(main())