"""Debug why /collect/missing-from-insights returns 0 records"""
import asyncio
from datetime import datetime, timedelta
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.services.data_collection_service import DataCollectionService
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import text, and_, func
import re

async def debug_missing_collection():
    print("Debugging Missing Collection Issue")
    print("=" * 70)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # Test with specific cases from the table
    test_cases = [
        {
            "expiry": datetime(2024, 10, 10),
            "strikes": [25000, 24800],
            "desc": "October 10 (Previously fixed)"
        },
        {
            "expiry": datetime(2024, 8, 1),
            "strikes": [25000, 25200],
            "desc": "August 1"
        },
        {
            "expiry": datetime(2024, 11, 14),
            "strikes": [24000, 23800],
            "desc": "November 14"
        }
    ]
    
    for test in test_cases:
        expiry = test["expiry"]
        strikes = test["strikes"]
        desc = test["desc"]
        
        print(f"\n{desc} - Expiry: {expiry.date()}")
        print("-" * 50)
        
        # 1. Check if data already exists
        print("1. Checking existing data:")
        with db.get_session() as session:
            for strike in strikes:
                for opt_type in ['CE', 'PE']:
                    count = session.query(func.count(OptionsHistoricalData.id)).filter(
                        and_(
                            OptionsHistoricalData.strike == strike,
                            OptionsHistoricalData.option_type == opt_type,
                            OptionsHistoricalData.expiry_date >= expiry,
                            OptionsHistoricalData.expiry_date < expiry + timedelta(days=1)
                        )
                    ).scalar()
                    
                    print(f"   {strike}{opt_type}: {count} records")
        
        # 2. If no data, try to understand why collection might fail
        if any(strike for strike in strikes):
            print("\n2. Testing collection logic:")
            
            # Check what ensure_options_data_available does
            from_date = expiry - timedelta(days=3)
            to_date = expiry
            
            print(f"   Date range: {from_date} to {to_date}")
            
            # The ensure_options_data_available should check existing data
            print(f"   Will check for existing data and fetch if missing")
            
            # Try to fetch directly
            print("\n3. Attempting direct fetch:")
            try:
                records = await data_svc.ensure_options_data_available(
                    from_date,
                    to_date,
                    strikes[:1],  # Just one strike
                    [expiry],
                    fetch_missing=True  # Force fetch
                )
                print(f"   Records collected: {records}")
            except Exception as e:
                print(f"   Error: {e}")
    
    # Check the actual endpoint logic
    print("\n" + "=" * 70)
    print("Testing endpoint logic simulation:")
    print("-" * 50)
    
    with db.get_session() as session:
        # Get one record from the table
        result = session.execute(text("""
            SELECT TOP 1
                MissingOptionStrikes,
                EntryTime,
                ExitTime,
                WeeklyExpiryDate
            FROM WeeklySignalInsights_ConsolidatedResults
            WHERE MissingOptionStrikes IS NOT NULL 
                AND MissingOptionStrikes != ''
                AND MissingOptionStrikes != 'NULL'
                AND WeeklyOutcome = 'DataMissing'
            ORDER BY WeeklyExpiryDate DESC
        """))
        
        record = result.fetchone()
        
        if record:
            missing_strikes_str = record[0]
            entry_time = record[1]
            exit_time = record[2]
            expiry_date = record[3]
            
            print(f"Sample record:")
            print(f"  Missing: {missing_strikes_str}")
            print(f"  Expiry: {expiry_date}")
            print(f"  Entry: {entry_time}, Exit: {exit_time}")
            
            # Parse strikes
            strikes_to_collect = []
            if missing_strikes_str:
                strikes_list = [s.strip() for s in missing_strikes_str.split(',')]
                for strike_str in strikes_list:
                    match = re.match(r'(\d+)(CE|PE)', strike_str)
                    if match:
                        strike_price = int(match.group(1))
                        strikes_to_collect.append(strike_price)
            
            unique_strikes = list(set(strikes_to_collect))
            print(f"  Parsed strikes: {unique_strikes}")
            
            # Determine date range
            if entry_time and exit_time:
                from_date = entry_time
                to_date = exit_time
            else:
                from_date = expiry_date - timedelta(days=3)
                to_date = expiry_date
            
            print(f"  Date range for collection: {from_date} to {to_date}")
            
            # Try collection
            print("\n  Attempting collection...")
            try:
                records = await data_svc.ensure_options_data_available(
                    from_date,
                    to_date,
                    unique_strikes,
                    [expiry_date],
                    fetch_missing=True
                )
                print(f"  Result: {records} records")
            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_missing_collection())