"""Collect the missing October 10, 2024 data"""
import asyncio
from datetime import datetime
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.services.data_collection_service import DataCollectionService

async def collect_october_10():
    print("Collecting October 10, 2024 Missing Data")
    print("=" * 70)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # October 10, 2024 data
    expiry_date = datetime(2024, 10, 10, 15, 30)  # Thursday expiry
    strikes = [25000, 24800]
    
    # Note from the table: Entry and Exit times are Oct 9
    # This suggests it's an intraday trade on Oct 9 for Oct 10 expiry
    from_date = datetime(2024, 10, 7, 9, 15)  # Start of week
    to_date = datetime(2024, 10, 10, 15, 30)   # Expiry
    
    print(f"Expiry: {expiry_date} ({expiry_date.strftime('%A')})")
    print(f"Strikes: {strikes}")
    print(f"Date range: {from_date.date()} to {to_date.date()}")
    print()
    
    try:
        # Collect the missing data
        print("Fetching from Breeze API...")
        records = await data_svc.ensure_options_data_available(
            from_date,
            to_date,
            strikes,
            [expiry_date],
            fetch_missing=True
        )
        
        print(f"\nCollected {records} records")
        
        # Verify what was stored
        print("\nVerifying stored data:")
        print("-" * 50)
        
        from src.infrastructure.database.models import OptionsHistoricalData
        from sqlalchemy import and_, func
        
        with db.get_session() as session:
            for strike in strikes:
                for option_type in ['CE', 'PE']:
                    count = session.query(func.count(OptionsHistoricalData.id)).filter(
                        and_(
                            OptionsHistoricalData.strike == strike,
                            OptionsHistoricalData.option_type == option_type,
                            OptionsHistoricalData.expiry_date >= datetime(2024, 10, 10),
                            OptionsHistoricalData.expiry_date < datetime(2024, 10, 11)
                        )
                    ).scalar()
                    
                    status = "SUCCESS" if count > 0 else "FAILED"
                    print(f"  {strike}{option_type} (Oct 10): {count} records - {status}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 70)
    print("October 10, 2024 data collection complete!")

if __name__ == "__main__":
    asyncio.run(collect_october_10())