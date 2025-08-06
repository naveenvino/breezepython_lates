"""Collect missing strikes from WeeklySignalInsights_ConsolidatedResults table"""
import asyncio
from datetime import datetime, timedelta
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.services.data_collection_service import DataCollectionService
from sqlalchemy import text, and_
import re

async def collect_missing_from_table():
    """Fetch and store missing strikes based on WeeklySignalInsights_ConsolidatedResults table"""
    
    print("Collecting Missing Strikes from WeeklySignalInsights_ConsolidatedResults")
    print("=" * 70)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    with db.get_session() as session:
        # Query for records with missing strikes
        result = session.execute(text("""
            SELECT 
                ResultID,
                MissingOptionStrikes,
                EntryTime,
                ExitTime,
                WeeklyExpiryDate,
                MainStrikePrice,
                MainOptionType,
                HedgeStrike,
                yr,
                wk
            FROM WeeklySignalInsights_ConsolidatedResults
            WHERE MissingOptionStrikes IS NOT NULL 
                AND MissingOptionStrikes != ''
                AND MissingOptionStrikes != 'NULL'
            ORDER BY WeeklyExpiryDate DESC
        """))
        
        missing_records = result.fetchall()
        
    if not missing_records:
        print("No missing strikes found in the table")
        return
    
    print(f"Found {len(missing_records)} records with missing strikes\n")
    
    # Group missing strikes by expiry date
    expiry_strikes = {}
    
    for record in missing_records:
        result_id = record[0]
        missing_strikes_str = record[1]
        entry_time = record[2]
        exit_time = record[3]
        expiry_date = record[4]
        main_strike = record[5]
        year = record[8]
        week = record[9]
        
        # Parse missing strikes string (e.g., "25000CE, 25200CE" or "24500PE, 24300PE")
        if missing_strikes_str:
            strikes_list = [s.strip() for s in missing_strikes_str.split(',')]
            
            for strike_str in strikes_list:
                # Extract strike price and option type using regex
                match = re.match(r'(\d+)(CE|PE)', strike_str)
                if match:
                    strike_price = int(match.group(1))
                    option_type = match.group(2)
                    
                    # Create key for grouping
                    if expiry_date not in expiry_strikes:
                        expiry_strikes[expiry_date] = {
                            'strikes': set(),
                            'date_range': (entry_time, exit_time),
                            'records': []
                        }
                    
                    expiry_strikes[expiry_date]['strikes'].add(strike_price)
                    expiry_strikes[expiry_date]['records'].append({
                        'result_id': result_id,
                        'strike': strike_price,
                        'option_type': option_type,
                        'year': year,
                        'week': week
                    })
    
    # Collect missing strikes for each expiry
    total_collected = 0
    
    for expiry_date, data in expiry_strikes.items():
        strikes = list(data['strikes'])
        date_range = data['date_range']
        
        print(f"\nExpiry: {expiry_date}")
        print("-" * 50)
        print(f"Strikes to collect: {sorted(strikes)}")
        
        # Determine date range (use entry to exit time, or week range)
        if date_range[0] and date_range[1]:
            from_date = date_range[0]
            to_date = date_range[1]
        else:
            # Use week range around expiry
            from_date = expiry_date - timedelta(days=3)
            to_date = expiry_date
        
        print(f"Date range: {from_date} to {to_date}")
        
        try:
            # Collect the missing strikes
            records = await data_svc.ensure_options_data_available(
                from_date,
                to_date,
                strikes,
                [expiry_date],
                fetch_missing=True
            )
            
            total_collected += records
            print(f"Collected {records} records")
            
            # Update the database to mark these as collected (optional)
            # You might want to add a column to track collection status
            
        except Exception as e:
            print(f"Error collecting strikes for {expiry_date}: {e}")
    
    print("\n" + "=" * 70)
    print(f"Total records collected: {total_collected}")
    
    # Verify collection
    print("\nVerifying collected strikes:")
    print("-" * 50)
    
    from src.infrastructure.database.models import OptionsHistoricalData
    from sqlalchemy import func
    
    with db.get_session() as session:
        for expiry_date, data in expiry_strikes.items():
            for record_info in data['records'][:5]:  # Check first 5 for each expiry
                count = session.query(func.count(OptionsHistoricalData.id)).filter(
                    and_(
                        OptionsHistoricalData.strike == record_info['strike'],
                        OptionsHistoricalData.option_type == record_info['option_type'],
                        OptionsHistoricalData.expiry_date >= expiry_date,
                        OptionsHistoricalData.expiry_date < expiry_date + timedelta(days=1)
                    )
                ).scalar()
                
                status = "✓" if count > 0 else "✗"
                print(f"  {record_info['strike']}{record_info['option_type']} (Week {record_info['week']}): {count} records {status}")

if __name__ == "__main__":
    asyncio.run(collect_missing_from_table())