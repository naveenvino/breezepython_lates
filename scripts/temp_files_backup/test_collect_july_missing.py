"""Test collecting missing strikes for July 2024 from the table"""
import asyncio
from datetime import datetime, timedelta
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.services.data_collection_service import DataCollectionService
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import text, and_, func
import re

async def test_july_missing():
    """Test collecting July 2024 missing strikes from WeeklySignalInsights_ConsolidatedResults"""
    
    print("Testing July 2024 Missing Strikes Collection")
    print("=" * 70)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # First, check what's in the table for July 2024
    with db.get_session() as session:
        result = session.execute(text("""
            SELECT 
                ResultID,
                MissingOptionStrikes,
                EntryTime,
                ExitTime,
                WeeklyExpiryDate,
                MainStrikePrice,
                HedgeStrike,
                yr,
                wk
            FROM WeeklySignalInsights_ConsolidatedResults
            WHERE MissingOptionStrikes IS NOT NULL 
                AND MissingOptionStrikes != ''
                AND MissingOptionStrikes != 'NULL'
                AND yr = 2024
                AND WeeklyExpiryDate >= '2024-07-01'
                AND WeeklyExpiryDate <= '2024-07-31'
            ORDER BY WeeklyExpiryDate
        """))
        
        july_missing = result.fetchall()
    
    if not july_missing:
        print("No July 2024 missing strikes found in the table")
        return
    
    print(f"Found {len(july_missing)} July 2024 records with missing strikes:\n")
    
    # Display what's missing
    for record in july_missing:
        result_id = record[0]
        missing_strikes = record[1]
        entry_time = record[2]
        exit_time = record[3]
        expiry_date = record[4]
        main_strike = record[5]
        hedge_strike = record[6]
        year = record[7]
        week = record[8]
        
        print(f"Week {week} (Expiry: {expiry_date}):")
        print(f"  Missing: {missing_strikes}")
        print(f"  Main Strike: {main_strike}, Hedge Strike: {hedge_strike}")
        print(f"  Entry: {entry_time}, Exit: {exit_time}")
        print()
    
    # Parse and collect the missing strikes
    print("-" * 70)
    print("Collecting missing strikes...")
    print("-" * 70)
    
    for record in july_missing:
        missing_strikes_str = record[1]
        entry_time = record[2]
        exit_time = record[3]
        expiry_date = record[4]
        week = record[8]
        
        if not missing_strikes_str:
            continue
            
        # Parse strikes
        strikes_to_collect = []
        strikes_list = [s.strip() for s in missing_strikes_str.split(',')]
        
        for strike_str in strikes_list:
            match = re.match(r'(\d+)(CE|PE)', strike_str)
            if match:
                strike_price = int(match.group(1))
                option_type = match.group(2)
                strikes_to_collect.append((strike_price, option_type))
        
        if not strikes_to_collect:
            continue
            
        print(f"\nWeek {week} - Expiry {expiry_date}:")
        print(f"  Strikes to collect: {strikes_to_collect}")
        
        # Collect unique strike prices
        unique_strikes = list(set([s[0] for s in strikes_to_collect]))
        
        # Date range
        from_date = entry_time if entry_time else expiry_date - timedelta(days=3)
        to_date = exit_time if exit_time else expiry_date
        
        print(f"  Date range: {from_date} to {to_date}")
        
        try:
            # Collect the missing strikes
            records = await data_svc.ensure_options_data_available(
                from_date,
                to_date,
                unique_strikes,
                [expiry_date],
                fetch_missing=True
            )
            
            print(f"  Collected {records} records")
            
            # Verify collection
            with db.get_session() as session:
                for strike_price, option_type in strikes_to_collect:
                    count = session.query(func.count(OptionsHistoricalData.id)).filter(
                        and_(
                            OptionsHistoricalData.strike == strike_price,
                            OptionsHistoricalData.option_type == option_type,
                            OptionsHistoricalData.expiry_date >= expiry_date,
                            OptionsHistoricalData.expiry_date < expiry_date + timedelta(days=1)
                        )
                    ).scalar()
                    
                    status = "FOUND" if count > 0 else "STILL MISSING"
                    print(f"    {strike_price}{option_type}: {count} records - {status}")
                    
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print("\n" + "=" * 70)
    print("July 2024 missing strikes collection complete!")

if __name__ == "__main__":
    asyncio.run(test_july_missing())