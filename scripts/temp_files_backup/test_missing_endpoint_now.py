"""Test the /collect/missing-from-insights endpoint"""
import asyncio
from datetime import datetime, timedelta
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.services.data_collection_service import DataCollectionService
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import text, and_, func
import re

async def test_missing_endpoint():
    """Test the /collect/missing-from-insights endpoint logic directly"""
    
    print("Testing /collect/missing-from-insights Endpoint Logic")
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
        print("Result: No missing strikes found in the table")
        return {
            "status": "success",
            "message": "No missing strikes found in the table",
            "records_collected": 0
        }
    
    print(f"Found {len(missing_records)} records with missing strikes\n")
    
    # Group missing strikes by expiry date
    expiry_strikes = {}
    
    for record in missing_records:
        result_id = record[0]
        missing_strikes_str = record[1]
        entry_time = record[2]
        exit_time = record[3]
        expiry_date = record[4]
        
        print(f"Processing ResultID {result_id}:")
        print(f"  Missing strikes: {missing_strikes_str}")
        print(f"  Expiry: {expiry_date}")
        
        # Parse missing strikes string
        if missing_strikes_str:
            strikes_list = [s.strip() for s in missing_strikes_str.split(',')]
            
            for strike_str in strikes_list:
                # Extract strike price and option type
                match = re.match(r'(\d+)(CE|PE)', strike_str)
                if match:
                    strike_price = int(match.group(1))
                    
                    if expiry_date not in expiry_strikes:
                        expiry_strikes[expiry_date] = {
                            'strikes': set(),
                            'date_range': (entry_time, exit_time)
                        }
                    
                    expiry_strikes[expiry_date]['strikes'].add(strike_price)
                    print(f"    Parsed: {strike_price} from {strike_str}")
    
    print("\n" + "-" * 70)
    print("Grouped by Expiry:")
    for expiry, data in expiry_strikes.items():
        print(f"  {expiry}: strikes {sorted(data['strikes'])}")
    
    # Collect missing strikes for each expiry
    print("\n" + "-" * 70)
    print("Attempting Collection:")
    total_collected = 0
    details = []
    
    for expiry_date, data in expiry_strikes.items():
        strikes = list(data['strikes'])
        date_range = data['date_range']
        
        # Determine date range
        if date_range[0] and date_range[1]:
            from_date = date_range[0]
            to_date = date_range[1]
        else:
            from_date = expiry_date - timedelta(days=3)
            to_date = expiry_date
        
        print(f"\nExpiry {expiry_date}:")
        print(f"  Strikes to collect: {sorted(strikes)}")
        print(f"  Date range: {from_date} to {to_date}")
        
        try:
            # Check what's already available
            with db.get_session() as session:
                for strike in strikes:
                    for opt_type in ['CE', 'PE']:
                        count = session.query(func.count(OptionsHistoricalData.id)).filter(
                            and_(
                                OptionsHistoricalData.strike == strike,
                                OptionsHistoricalData.option_type == opt_type,
                                OptionsHistoricalData.expiry_date >= expiry_date,
                                OptionsHistoricalData.expiry_date < expiry_date + timedelta(days=1)
                            )
                        ).scalar()
                        if count > 0:
                            print(f"    {strike}{opt_type}: Already have {count} records")
            
            # Attempt to collect any missing data
            records = await data_svc.ensure_options_data_available(
                from_date,
                to_date,
                strikes,
                [expiry_date],
                fetch_missing=True
            )
            
            total_collected += records
            print(f"  Result: Collected {records} new records")
            
            details.append({
                "expiry": str(expiry_date),
                "strikes": sorted(strikes),
                "records": records
            })
            
        except Exception as e:
            print(f"  ERROR: {e}")
            details.append({
                "expiry": str(expiry_date),
                "strikes": sorted(strikes),
                "error": str(e)
            })
    
    result = {
        "status": "success",
        "message": f"Processed missing strikes from {len(expiry_strikes)} expiries",
        "records_collected": total_collected,
        "details": details
    }
    
    print("\n" + "=" * 70)
    print("ENDPOINT RESULT:")
    print("-" * 70)
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    print(f"Total Records Collected: {result['records_collected']}")
    print("\nDetails:")
    for detail in result['details']:
        print(f"  Expiry {detail['expiry']}: {detail.get('records', 0)} records")
        if 'error' in detail:
            print(f"    Error: {detail['error']}")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(test_missing_endpoint())
    print("\n" + "=" * 70)
    print("Test Complete!")