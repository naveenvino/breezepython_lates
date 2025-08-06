"""Fix the duplicate April 2025 record"""
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import text, and_, func
from datetime import datetime

db = get_db_manager()

print("Fixing Duplicate Record (ResultID 1297)")
print("=" * 70)

# Check if we have data for 21700PE April 9, 2025
with db.get_session() as session:
    count = session.query(func.count(OptionsHistoricalData.id)).filter(
        and_(
            OptionsHistoricalData.strike == 21700,
            OptionsHistoricalData.option_type == "PE",
            OptionsHistoricalData.expiry_date >= datetime(2025, 4, 9),
            OptionsHistoricalData.expiry_date < datetime(2025, 4, 10)
        )
    ).scalar()
    
    print(f"21700PE (April 9, 2025): {count} records in database")
    
    if count > 0:
        # Update the duplicate record
        update_query = text("""
            UPDATE WeeklySignalInsights_ConsolidatedResults
            SET WeeklyOutcome = 'DataAvailable',
                MissingOptionStrikes = NULL
            WHERE ResultID = 1297
        """)
        
        session.execute(update_query)
        session.commit()
        print("\nUpdated ResultID 1297 to DataAvailable")
        
        # Verify final status
        result = session.execute(text("""
            SELECT COUNT(*) 
            FROM WeeklySignalInsights_ConsolidatedResults
            WHERE WeeklyOutcome = 'DataMissing'
        """))
        
        remaining = result.scalar()
        
        result = session.execute(text("""
            SELECT COUNT(*) 
            FROM WeeklySignalInsights_ConsolidatedResults
            WHERE WeeklyOutcome = 'DataAvailable'
        """))
        
        available = result.scalar()
        
        print("\nFinal Status:")
        print(f"  DataMissing: {remaining}")
        print(f"  DataAvailable: {available}")
        
        if remaining == 0:
            print("\nSUCCESS: All DataMissing records have been resolved!")
            print("All options data is now available for backtesting.")
    else:
        print("\nNo data found for 21700PE - collection may have failed")