"""Update WeeklyOutcome from DataMissing to DataAvailable for records that have data"""
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import text, and_, func
from datetime import datetime
import re

db = get_db_manager()

print("Updating WeeklyOutcome Status")
print("=" * 70)

# Get all DataMissing records
with db.get_session() as session:
    result = session.execute(text("""
        SELECT 
            ResultID,
            MissingOptionStrikes,
            WeeklyExpiryDate,
            yr,
            wk
        FROM WeeklySignalInsights_ConsolidatedResults
        WHERE WeeklyOutcome = 'DataMissing'
        ORDER BY WeeklyExpiryDate
    """))
    
    missing_records = result.fetchall()

print(f"Found {len(missing_records)} records marked as DataMissing\n")

records_to_update = []

for record in missing_records:
    result_id = record[0]
    missing_strikes_str = record[1]
    expiry_date = record[2]
    year = record[3]
    week = record[4]
    
    if not missing_strikes_str:
        continue
    
    # Parse strikes
    strikes_list = [s.strip() for s in missing_strikes_str.split(',')]
    
    all_found = True
    min_records = float('inf')
    
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
                
                if count == 0:
                    all_found = False
                    break
                else:
                    min_records = min(min_records, count)
    
    if all_found:
        records_to_update.append({
            'result_id': result_id,
            'week': week,
            'year': year,
            'expiry': expiry_date.date(),
            'strikes': missing_strikes_str,
            'min_records': min_records
        })
        print(f"ResultID {result_id}: Week {week}/{year} - HAS DATA ({min_records} records minimum)")

# Update the records
if records_to_update:
    print("\n" + "-" * 70)
    print(f"Updating {len(records_to_update)} records...")
    
    with db.get_session() as session:
        for record in records_to_update:
            # Update WeeklyOutcome to 'DataAvailable' and clear MissingOptionStrikes
            update_query = text("""
                UPDATE WeeklySignalInsights_ConsolidatedResults
                SET WeeklyOutcome = 'DataAvailable',
                    MissingOptionStrikes = NULL
                WHERE ResultID = :result_id
            """)
            
            session.execute(update_query, {'result_id': record['result_id']})
            print(f"  Updated ResultID {record['result_id']} - Week {record['week']}/{record['year']}")
        
        # Commit the changes
        session.commit()
        print("\nChanges committed successfully!")

# Final verification
print("\n" + "=" * 70)
print("VERIFICATION")
print("-" * 70)

with db.get_session() as session:
    # Count remaining DataMissing records
    result = session.execute(text("""
        SELECT COUNT(*) 
        FROM WeeklySignalInsights_ConsolidatedResults
        WHERE WeeklyOutcome = 'DataMissing'
    """))
    
    remaining = result.scalar()
    
    # Count DataAvailable records
    result = session.execute(text("""
        SELECT COUNT(*) 
        FROM WeeklySignalInsights_ConsolidatedResults
        WHERE WeeklyOutcome = 'DataAvailable'
    """))
    
    available = result.scalar()
    
    print(f"Records with WeeklyOutcome = 'DataMissing': {remaining}")
    print(f"Records with WeeklyOutcome = 'DataAvailable': {available}")
    
    if remaining > 0:
        print("\nRemaining DataMissing records:")
        result = session.execute(text("""
            SELECT ResultID, yr, wk, WeeklyExpiryDate, MissingOptionStrikes
            FROM WeeklySignalInsights_ConsolidatedResults
            WHERE WeeklyOutcome = 'DataMissing'
        """))
        
        for row in result:
            print(f"  ResultID {row[0]}: Week {row[2]}/{row[1]} ({row[3].date()}) - Missing: {row[4]}")
            print("    Note: This likely needs Breeze session update to collect April 2025 data")

print("\n" + "=" * 70)
print("Update complete!")