"""Test improved options collection"""
import asyncio
import logging
from datetime import datetime, date
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.data_collection_service import DataCollectionService

# Enable DEBUG logging to see all messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_improved_collection():
    print("\n=== Testing Improved Options Collection ===\n")
    
    # Initialize services
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # First ensure we have NIFTY data for February
    print("Step 1: Ensuring NIFTY data is available...")
    from_date = date(2025, 2, 10)
    to_date = date(2025, 2, 14)
    
    nifty_records = await data_svc.collect_nifty_data(
        from_date,
        to_date,
        "NIFTY",
        force_refresh=True
    )
    print(f"NIFTY data: {nifty_records} records added\n")
    
    # Now try options collection
    print("Step 2: Collecting options data...")
    options_records = await data_svc.collect_options_data(
        from_date,
        to_date,
        "NIFTY",
        strike_range=200  # Just 5 strikes for testing
    )
    
    print(f"\nResult: {options_records} options records collected")

if __name__ == "__main__":
    asyncio.run(test_improved_collection())