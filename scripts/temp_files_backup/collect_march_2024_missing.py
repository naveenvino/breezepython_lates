"""Collect missing strikes for March 2024 with 50-point intervals"""
import asyncio
from datetime import datetime, date, timedelta
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.data_collection_service import DataCollectionService

async def collect_march_2024_missing():
    print("Collecting Missing March 2024 Strikes (50-point intervals)")
    print("=" * 60)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # Missing strikes that need to be collected
    missing_data = [
        {
            "expiry": datetime(2024, 3, 14, 15, 30),
            "strikes": [22700, 22750, 22800, 22900],  # Missing CE strikes
            "week": "March 14"
        },
        {
            "expiry": datetime(2024, 3, 21, 15, 30),
            "strikes": [21750],  # Missing PE strike
            "week": "March 21"
        },
        {
            "expiry": datetime(2024, 3, 28, 15, 30),
            "strikes": [21750],  # Missing PE strike  
            "week": "March 28"
        }
    ]
    
    total_collected = 0
    
    for item in missing_data:
        expiry = item["expiry"]
        strikes = item["strikes"]
        week = item["week"]
        
        print(f"\n{week} Expiry ({expiry.date()}):")
        print("-" * 40)
        
        # Date range for the week
        from_date = expiry - timedelta(days=3)
        to_date = expiry
        
        print(f"Collecting strikes: {strikes}")
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
        print(f"Collected {records} records for {week}")
    
    # Also collect more comprehensive strikes for these weeks with 50-point intervals
    print("\n" + "=" * 60)
    print("Collecting comprehensive 50-point strikes for March 2024:")
    
    # For each week, collect with 50-point intervals
    weeks = [
        {"from": date(2024, 3, 11), "to": date(2024, 3, 14)},
        {"from": date(2024, 3, 18), "to": date(2024, 3, 21)},
        {"from": date(2024, 3, 25), "to": date(2024, 3, 28)},
    ]
    
    for week in weeks:
        print(f"\nWeek {week['from']} to {week['to']}:")
        
        # Use strike_interval=50 for 50-point intervals
        records = await data_svc.collect_options_data(
            week['from'],
            week['to'],
            symbol="NIFTY",
            strike_range=500,
            strike_interval=50  # 50-point intervals
        )
        
        total_collected += records
        print(f"  Collected {records} records")
    
    print("\n" + "=" * 60)
    print(f"Total collected: {total_collected} records")
    print("Missing strikes collection complete!")
    
    # Verify the specific missing strikes are now present
    print("\nVerifying specific missing strikes:")
    from src.infrastructure.database.models import OptionsHistoricalData
    from sqlalchemy import and_, func
    
    with db.get_session() as session:
        # Check March 14 strikes
        for strike in [22700, 22750, 22800, 22900]:
            count = session.query(func.count(OptionsHistoricalData.id)).filter(
                and_(
                    OptionsHistoricalData.strike == strike,
                    OptionsHistoricalData.option_type == "CE",
                    OptionsHistoricalData.expiry_date >= datetime(2024, 3, 14, 0, 0),
                    OptionsHistoricalData.expiry_date < datetime(2024, 3, 15, 0, 0)
                )
            ).scalar()
            status = "✓" if count > 0 else "✗"
            print(f"  {strike}CE (Mar 14): {count} records {status}")
        
        # Check March 21 and 28 strikes
        for expiry_date in [datetime(2024, 3, 21), datetime(2024, 3, 28)]:
            count = session.query(func.count(OptionsHistoricalData.id)).filter(
                and_(
                    OptionsHistoricalData.strike == 21750,
                    OptionsHistoricalData.option_type == "PE",
                    OptionsHistoricalData.expiry_date >= expiry_date,
                    OptionsHistoricalData.expiry_date < expiry_date + timedelta(days=1)
                )
            ).scalar()
            status = "✓" if count > 0 else "✗"
            print(f"  21750PE ({expiry_date.date()}): {count} records {status}")

if __name__ == "__main__":
    asyncio.run(collect_march_2024_missing())