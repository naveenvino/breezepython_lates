"""Collect the missing April 2025 data with updated session token"""
import asyncio
from datetime import datetime
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.services.data_collection_service import DataCollectionService
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import and_, func

async def collect_april_2025():
    print("Collecting April 2025 Missing Data (21700PE)")
    print("=" * 70)
    
    db = get_db_manager()
    breeze = BreezeService()  # Will use new session token from .env
    data_svc = DataCollectionService(breeze, db)
    
    # April 9, 2025 data (Wednesday expiry - likely due to holiday on Thursday)
    expiry_date = datetime(2025, 4, 9, 15, 30)
    strikes = [21700]
    
    # From the table: Entry 2025-04-07 16:15:00, Exit 2025-04-09 15:15:00
    from_date = datetime(2025, 4, 7, 9, 15)  # Start from market open
    to_date = datetime(2025, 4, 9, 15, 30)   # Till expiry
    
    print(f"Expiry: {expiry_date} ({expiry_date.strftime('%A')})")
    print(f"Strike: 21700PE")
    print(f"Date range: {from_date} to {to_date}")
    print(f"Using updated session token from .env")
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
        
        with db.get_session() as session:
            for option_type in ['CE', 'PE']:
                count = session.query(func.count(OptionsHistoricalData.id)).filter(
                    and_(
                        OptionsHistoricalData.strike == 21700,
                        OptionsHistoricalData.option_type == option_type,
                        OptionsHistoricalData.expiry_date >= datetime(2025, 4, 9),
                        OptionsHistoricalData.expiry_date < datetime(2025, 4, 10)
                    )
                ).scalar()
                
                status = "SUCCESS" if count > 0 else "FAILED"
                print(f"  21700{option_type} (Apr 9): {count} records - {status}")
        
        # Update WeeklyOutcome if successful
        if records > 0:
            print("\nUpdating WeeklySignalInsights_ConsolidatedResults...")
            from sqlalchemy import text
            
            with db.get_session() as session:
                update_query = text("""
                    UPDATE WeeklySignalInsights_ConsolidatedResults
                    SET WeeklyOutcome = 'DataAvailable',
                        MissingOptionStrikes = NULL
                    WHERE ResultID = 1247
                """)
                
                session.execute(update_query)
                session.commit()
                print("Updated ResultID 1247 to DataAvailable")
        
    except Exception as e:
        print(f"Error: {e}")
        if "Session key is expired" in str(e):
            print("\nSession token is still expired or invalid.")
            print("Please check if the token is correct.")
    
    print("\n" + "=" * 70)
    print("April 2025 data collection complete!")

if __name__ == "__main__":
    asyncio.run(collect_april_2025())