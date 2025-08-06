"""Collect April 9th Wednesday expiry data"""
import asyncio
from datetime import datetime, date
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.data_collection_service import DataCollectionService

async def collect_april_9_data():
    print("Collecting April 9, 2025 (Wednesday) Expiry Options")
    print("=" * 60)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # April 7-9 date range
    from_date = date(2025, 4, 7)
    to_date = date(2025, 4, 9)
    
    # The specific strikes needed
    strikes = [21400, 21500, 21550, 21600]
    
    # April 9 is a Wednesday expiry (special case)
    from_datetime = datetime(2025, 4, 7, 9, 15)
    to_datetime = datetime(2025, 4, 9, 15, 30)
    expiry_date = datetime(2025, 4, 9, 15, 30)  # Wednesday expiry
    
    print(f"Date range: {from_date} to {to_date}")
    print(f"Strikes: {strikes}")
    print(f"Expiry: {expiry_date.date()} (Wednesday)")
    print()
    
    # Use ensure_options_data_available directly with the Wednesday expiry
    records = await data_svc.ensure_options_data_available(
        from_datetime,
        to_datetime,
        strikes,
        [expiry_date],  # Pass the Wednesday expiry
        fetch_missing=True
    )
    
    print(f"\nResult: Collected {records} records")
    
    # Verify what was stored
    from src.infrastructure.database.models import OptionsHistoricalData
    from sqlalchemy import and_
    
    print("\nVerifying stored data:")
    print("-" * 40)
    
    with db.get_session() as session:
        for strike in strikes:
            for option_type in ['CE', 'PE']:
                count = session.query(OptionsHistoricalData).filter(
                    and_(
                        OptionsHistoricalData.strike == strike,
                        OptionsHistoricalData.option_type == option_type,
                        OptionsHistoricalData.timestamp >= from_datetime,
                        OptionsHistoricalData.timestamp <= to_datetime
                    )
                ).count()
                
                if count > 0:
                    print(f"  {strike}{option_type}: {count} records ✓")
                else:
                    print(f"  {strike}{option_type}: 0 records ✗")
    
    print("\n" + "=" * 60)
    print("Collection complete!")
    print("April 9 Wednesday expiry data should now be available.")

if __name__ == "__main__":
    asyncio.run(collect_april_9_data())