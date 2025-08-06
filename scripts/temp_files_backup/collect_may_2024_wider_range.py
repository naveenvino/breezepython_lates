"""Collect wider strike range for May 2024"""
import asyncio
from datetime import datetime, date
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.data_collection_service import DataCollectionService

async def collect_may_2024_wider_range():
    print("Collecting Wider Strike Range for May 2024")
    print("=" * 60)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # Specific strikes that are missing
    missing_data = [
        {
            "strikes": [21500, 21600, 21700],  # Missing lower strikes for May 16
            "from_date": datetime(2024, 5, 13, 9, 15),
            "to_date": datetime(2024, 5, 16, 15, 30),
            "expiry": datetime(2024, 5, 16, 15, 30),
            "description": "May 16 lower strikes"
        },
        {
            "strikes": [23200, 23300, 23400],  # Missing upper strikes for May 30
            "from_date": datetime(2024, 5, 27, 9, 15),
            "to_date": datetime(2024, 5, 30, 15, 30),
            "expiry": datetime(2024, 5, 30, 15, 30),
            "description": "May 30 upper strikes"
        }
    ]
    
    total_collected = 0
    
    for item in missing_data:
        strikes = item["strikes"]
        from_date = item["from_date"]
        to_date = item["to_date"]
        expiry = item["expiry"]
        description = item["description"]
        
        print(f"\n{description}:")
        print("-" * 40)
        print(f"Strikes: {strikes}")
        print(f"Expiry: {expiry.date()}")
        print(f"Date range: {from_date.date()} to {to_date.date()}")
        
        # Collect the missing strikes
        records = await data_svc.ensure_options_data_available(
            from_date,
            to_date,
            strikes,
            [expiry],
            fetch_missing=True
        )
        
        total_collected += records
        print(f"Collected {records} records")
    
    print("\n" + "=" * 60)
    print(f"Total collected: {total_collected} records")
    
    # Verify the specific missing strikes are now present
    print("\nVerifying specific missing strikes:")
    from src.infrastructure.database.models import OptionsHistoricalData
    from sqlalchemy import and_, func
    
    with db.get_session() as session:
        # Check May 16 strikes
        for strike in [21500, 21700]:
            for option_type in ["CE", "PE"]:
                count = session.query(func.count(OptionsHistoricalData.id)).filter(
                    and_(
                        OptionsHistoricalData.strike == strike,
                        OptionsHistoricalData.option_type == option_type,
                        OptionsHistoricalData.expiry_date >= datetime(2024, 5, 16, 0, 0),
                        OptionsHistoricalData.expiry_date < datetime(2024, 5, 17, 0, 0)
                    )
                ).scalar()
                status = "FOUND" if count > 0 else "MISSING"
                print(f"  {strike}{option_type} (May 16): {count} records - {status}")
        
        # Check May 30 strikes
        count = session.query(func.count(OptionsHistoricalData.id)).filter(
            and_(
                OptionsHistoricalData.strike == 23300,
                OptionsHistoricalData.option_type == "CE",
                OptionsHistoricalData.expiry_date >= datetime(2024, 5, 30, 0, 0),
                OptionsHistoricalData.expiry_date < datetime(2024, 5, 31, 0, 0)
            )
        ).scalar()
        status = "FOUND" if count > 0 else "MISSING"
        print(f"  23300CE (May 30): {count} records - {status}")

if __name__ == "__main__":
    asyncio.run(collect_may_2024_wider_range())