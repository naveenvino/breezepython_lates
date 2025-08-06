"""Debug data fetching"""
import asyncio
import logging
from datetime import datetime, date
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.data_collection_service import DataCollectionService

# Enable DEBUG logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_collection():
    print("\n=== Testing Data Collection with Debug ===\n")
    
    # Initialize services
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # Test dates
    from_date = date(2025, 1, 20)
    to_date = date(2025, 1, 21)
    
    print(f"Collecting NIFTY data from {from_date} to {to_date}")
    print("-" * 50)
    
    try:
        # Call the collection method
        records = await data_svc.collect_nifty_data(
            from_date,
            to_date,
            "NIFTY",
            force_refresh=True
        )
        
        print(f"\nResult: {records} records collected")
        
        # Now check what's in the database
        print("\nChecking database...")
        from_datetime = datetime.combine(from_date, datetime.strptime("09:15", "%H:%M").time())
        to_datetime = datetime.combine(to_date, datetime.strptime("15:30", "%H:%M").time())
        
        db_records = await data_svc.get_nifty_data(
            from_datetime,
            to_datetime,
            "NIFTY",
            timeframe="5minute"
        )
        
        print(f"Database has {len(db_records)} records for this period")
        if db_records:
            print(f"First record: {db_records[0].timestamp}")
            print(f"Last record: {db_records[-1].timestamp}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_collection())