"""Test storing February data"""
import asyncio
from datetime import datetime
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.data_collection_service import DataCollectionService
from src.infrastructure.database.models.nifty_index_model import NiftyIndexData

async def test_store_february():
    print("Testing data storage for February")
    print("=" * 50)
    
    # Get February data from Breeze
    breeze = BreezeService()
    breeze._initialize()
    
    from_date = datetime(2025, 2, 3, 9, 15)
    to_date = datetime(2025, 2, 3, 15, 30)
    
    print(f"Fetching data from {from_date} to {to_date}")
    
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
        print(f"Got {len(records)} records from Breeze")
        
        # Try to convert each record
        converted = []
        skipped = []
        
        for i, record in enumerate(records):
            nifty_data = NiftyIndexData.from_breeze_data(record, "NIFTY")
            if nifty_data:
                converted.append(nifty_data)
            else:
                skipped.append(record)
        
        print(f"Converted: {len(converted)} records")
        print(f"Skipped: {len(skipped)} records")
        
        if skipped:
            print(f"First skipped: {skipped[0]}")
        
        if converted:
            print(f"First converted: {converted[0].timestamp}")
            
            # Try to store
            db = get_db_manager()
            with db.get_session() as session:
                for data_point in converted[:5]:  # Store first 5 as test
                    # Check if exists
                    from sqlalchemy import and_
                    exists = session.query(NiftyIndexData).filter(
                        and_(
                            NiftyIndexData.symbol == data_point.symbol,
                            NiftyIndexData.timestamp == data_point.timestamp
                        )
                    ).first()
                    
                    if not exists:
                        session.add(data_point)
                        print(f"Added: {data_point.timestamp}")
                    else:
                        print(f"Already exists: {data_point.timestamp}")
                
                session.commit()
                print("Data committed to database")

if __name__ == "__main__":
    asyncio.run(test_store_february())