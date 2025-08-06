"""Verify that we're correctly matching strikes with their expiry dates"""
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import text, and_, func
from datetime import datetime
import re

db = get_db_manager()

print("Detailed Verification: Strike-Expiry Matching")
print("=" * 70)

# Get the missing strikes from the table
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
            EntryTime,
            ExitTime
        FROM WeeklySignalInsights_ConsolidatedResults
        WHERE MissingOptionStrikes IS NOT NULL 
            AND MissingOptionStrikes != ''
            AND MissingOptionStrikes != 'NULL'
        ORDER BY WeeklyExpiryDate
    """))
    
    missing_records = result.fetchall()

print(f"Found {len(missing_records)} records with missing strikes\n")

for record in missing_records:
    result_id = record[0]
    missing_strikes_str = record[1]
    expiry_date = record[2]
    main_strike = record[3]
    hedge_strike = record[4]
    year = record[5]
    week = record[6]
    entry_time = record[7]
    exit_time = record[8]
    
    print("=" * 70)
    print(f"ResultID: {result_id}")
    print(f"Year: {year}, Week: {week}")
    print(f"Expected Expiry: {expiry_date}")
    print(f"Entry Time: {entry_time}")
    print(f"Exit Time: {exit_time}")
    print(f"Missing Strikes (from table): {missing_strikes_str}")
    print(f"Main Strike: {main_strike}, Hedge Strike: {hedge_strike}")
    print()
    
    # Parse the missing strikes
    strikes_list = [s.strip() for s in missing_strikes_str.split(',')]
    
    with db.get_session() as session:
        for strike_str in strikes_list:
            match = re.match(r'(\d+)(CE|PE)', strike_str)
            if match:
                strike_price = int(match.group(1))
                option_type = match.group(2)
                
                print(f"  Checking {strike_str}:")
                print(f"    Strike: {strike_price}, Type: {option_type}")
                
                # Check EXACT expiry date match
                exact_count = session.query(func.count(OptionsHistoricalData.id)).filter(
                    and_(
                        OptionsHistoricalData.strike == strike_price,
                        OptionsHistoricalData.option_type == option_type,
                        OptionsHistoricalData.expiry_date == expiry_date
                    )
                ).scalar()
                
                print(f"    With EXACT expiry {expiry_date}: {exact_count} records")
                
                # Check with date range (in case of time component differences)
                range_count = session.query(func.count(OptionsHistoricalData.id)).filter(
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
                
                print(f"    With expiry DATE {expiry_date.date()}: {range_count} records")
                
                # Check what expiry dates we DO have for this strike
                available_expiries = session.query(
                    func.distinct(OptionsHistoricalData.expiry_date)
                ).filter(
                    and_(
                        OptionsHistoricalData.strike == strike_price,
                        OptionsHistoricalData.option_type == option_type
                    )
                ).all()
                
                if available_expiries:
                    print(f"    Available expiries for {strike_price}{option_type}:")
                    for exp in available_expiries[:5]:  # Show first 5
                        exp_date = exp[0]
                        # Count records for this expiry
                        count = session.query(func.count(OptionsHistoricalData.id)).filter(
                            and_(
                                OptionsHistoricalData.strike == strike_price,
                                OptionsHistoricalData.option_type == option_type,
                                OptionsHistoricalData.expiry_date == exp_date
                            )
                        ).scalar()
                        print(f"      - {exp_date}: {count} records")
                
                # Check if data exists in the entry-exit time range
                if entry_time and exit_time:
                    time_range_count = session.query(func.count(OptionsHistoricalData.id)).filter(
                        and_(
                            OptionsHistoricalData.strike == strike_price,
                            OptionsHistoricalData.option_type == option_type,
                            OptionsHistoricalData.timestamp >= entry_time,
                            OptionsHistoricalData.timestamp <= exit_time
                        )
                    ).all()
                    
                    print(f"    Data in time range {entry_time} to {exit_time}: {time_range_count[0][0] if time_range_count else 0} records")
                
                # Verdict
                if exact_count > 0:
                    print(f"    >>> CORRECTLY MATCHED with expiry {expiry_date}")
                elif range_count > 0:
                    print(f"    >>> FOUND but with different time component")
                else:
                    print(f"    >>> NOT FOUND for this expiry - may have different expiry date")
                
                print()

print("=" * 70)
print("SUMMARY:")
print("-" * 70)
print("The verification shows whether we're correctly matching strikes with their")
print("specific expiry dates from the WeeklySignalInsights_ConsolidatedResults table.")