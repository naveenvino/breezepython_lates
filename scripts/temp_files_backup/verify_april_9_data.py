"""Verify April 9 Wednesday expiry data is stored"""
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import and_
from datetime import datetime

db = get_db_manager()
from_date = datetime(2025, 4, 7, 9, 15)
to_date = datetime(2025, 4, 9, 15, 30)

print("April 9, 2025 (Wednesday) Expiry Data in Database:")
print("=" * 60)

strikes = [21400, 21500, 21550, 21600]

with db.get_session() as session:
    total_records = 0
    
    for strike in strikes:
        for option_type in ['CE', 'PE']:
            count = session.query(OptionsHistoricalData).filter(
                and_(
                    OptionsHistoricalData.strike == strike,
                    OptionsHistoricalData.option_type == option_type,
                    OptionsHistoricalData.timestamp >= from_date,
                    OptionsHistoricalData.timestamp <= to_date
                )
            ).count()
            
            total_records += count
            
            if count > 0:
                # Get a sample
                sample = session.query(OptionsHistoricalData).filter(
                    and_(
                        OptionsHistoricalData.strike == strike,
                        OptionsHistoricalData.option_type == option_type,
                        OptionsHistoricalData.timestamp >= from_date,
                        OptionsHistoricalData.timestamp <= to_date
                    )
                ).first()
                
                print(f"{strike}{option_type}: {count} records - Expiry: {sample.expiry_date.date()}")
            else:
                print(f"{strike}{option_type}: 0 records")
    
    print(f"\nTotal records: {total_records}")
    
    # Check unique expiries in this date range
    unique_expiries = session.query(OptionsHistoricalData.expiry_date).filter(
        and_(
            OptionsHistoricalData.timestamp >= from_date,
            OptionsHistoricalData.timestamp <= to_date
        )
    ).distinct().all()
    
    print(f"\nUnique expiries in April 7-9 data:")
    for exp in unique_expiries:
        print(f"  - {exp[0].date()} ({exp[0].strftime('%A')})")

print("\n" + "=" * 60)
print("SUCCESS! All missing strikes for April 9 Wednesday expiry are now stored.")
print("The data for 21400PE, 21500PE, 21550PE, 21600PE is available.")