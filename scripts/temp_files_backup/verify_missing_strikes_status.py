"""Verify status of missing strikes from WeeklySignalInsights_ConsolidatedResults"""
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import text, and_, func
from datetime import datetime
import re

db = get_db_manager()

print("Verifying Missing Strikes Status")
print("=" * 70)

# Get all missing strikes from the table
with db.get_session() as session:
    result = session.execute(text("""
        SELECT 
            ResultID,
            MissingOptionStrikes,
            WeeklyExpiryDate,
            MainStrikePrice,
            HedgeStrike,
            yr,
            wk,
            WeekStartDate
        FROM WeeklySignalInsights_ConsolidatedResults
        WHERE MissingOptionStrikes IS NOT NULL 
            AND MissingOptionStrikes != ''
            AND MissingOptionStrikes != 'NULL'
        ORDER BY WeeklyExpiryDate DESC
    """))
    
    missing_records = result.fetchall()

if not missing_records:
    print("No missing strikes found in the table")
else:
    print(f"Found {len(missing_records)} records with missing strikes\n")
    
    # Check each missing strike
    verified_results = []
    
    for record in missing_records:
        result_id = record[0]
        missing_strikes_str = record[1]
        expiry_date = record[2]
        main_strike = record[3]
        hedge_strike = record[4]
        year = record[5]
        week = record[6]
        week_start = record[7]
        
        if not missing_strikes_str:
            continue
        
        # Parse strikes
        strikes_list = [s.strip() for s in missing_strikes_str.split(',')]
        
        print(f"Year {year} Week {week} (Expiry: {expiry_date}):")
        print(f"  Missing: {missing_strikes_str}")
        
        # Check each strike in database
        with db.get_session() as session:
            for strike_str in strikes_list:
                match = re.match(r'(\d+)(CE|PE)', strike_str)
                if match:
                    strike_price = int(match.group(1))
                    option_type = match.group(2)
                    
                    # Check if data exists
                    count = session.query(func.count(OptionsHistoricalData.id)).filter(
                        and_(
                            OptionsHistoricalData.strike == strike_price,
                            OptionsHistoricalData.option_type == option_type,
                            OptionsHistoricalData.expiry_date >= expiry_date,
                            OptionsHistoricalData.expiry_date < datetime(
                                expiry_date.year, 
                                expiry_date.month, 
                                expiry_date.day + 1
                            )
                        )
                    ).scalar()
                    
                    status = "FOUND" if count > 0 else "MISSING"
                    print(f"    {strike_str}: {count} records - {status}")
                    
                    verified_results.append({
                        'year': year,
                        'week': week,
                        'expiry': expiry_date,
                        'strike': strike_str,
                        'count': count,
                        'status': status
                    })
        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("-" * 70)
    
    total_missing = len([r for r in verified_results if r['status'] == 'MISSING'])
    total_found = len([r for r in verified_results if r['status'] == 'FOUND'])
    
    print(f"Total strikes checked: {len(verified_results)}")
    print(f"Found in database: {total_found}")
    print(f"Still missing: {total_missing}")
    
    if total_missing > 0:
        print("\nStill missing strikes:")
        for r in verified_results:
            if r['status'] == 'MISSING':
                print(f"  - {r['strike']} (Week {r['week']}, Expiry: {r['expiry'].date()})")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATION:")
    print("-" * 70)
    
    if total_missing > 0:
        print("Some strikes are still missing. These may be:")
        print("1. Not available in Breeze API historical data")
        print("2. 50-point strikes that weren't traded in those weeks")
        print("3. Strikes outside the available range for those expiries")
        print("\nUse the /collect/missing-from-insights endpoint to attempt collection")
        print("of any strikes that might be available.")
    else:
        print("All strikes from the table have been successfully collected!")