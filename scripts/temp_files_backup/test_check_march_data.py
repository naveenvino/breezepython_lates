"""Check March data in database"""
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.database.models import OptionsHistoricalData
from datetime import datetime

db = get_db_manager()
with db.get_session() as session:
    # Check March 3rd data
    from_date = datetime(2025, 3, 3, 0, 0)
    to_date = datetime(2025, 3, 3, 23, 59)
    
    count = session.query(OptionsHistoricalData).filter(
        OptionsHistoricalData.timestamp.between(from_date, to_date)
    ).count()
    
    print(f"Total options records for March 3: {count}")
    
    if count > 0:
        # Get sample records
        samples = session.query(OptionsHistoricalData).filter(
            OptionsHistoricalData.timestamp.between(from_date, to_date)
        ).limit(5).all()
        
        print("\nSample records:")
        for s in samples:
            print(f"  {s.trading_symbol} @ {s.timestamp}: {s.last_price}")