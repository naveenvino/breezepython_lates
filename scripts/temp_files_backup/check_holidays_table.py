"""Check TradingHolidays table structure"""
from src.infrastructure.database.database_manager import get_db_manager
from sqlalchemy import text

db = get_db_manager()

with db.get_session() as session:
    # Check if TradingHolidays table exists
    result = session.execute(text("""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME LIKE '%Holiday%'
    """))
    
    tables = result.fetchall()
    if tables:
        print("Found holiday tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Get structure of TradingHolidays table
        result = session.execute(text("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'TradingHolidays'
            ORDER BY ORDINAL_POSITION
        """))
        
        columns = result.fetchall()
        if columns:
            print("\nTradingHolidays table structure:")
            for col in columns:
                print(f"  {col[0]}: {col[1]} (nullable: {col[2]})")
        
        # Get sample data
        result = session.execute(text("""
            SELECT TOP 10 * FROM TradingHolidays
            ORDER BY HolidayDate DESC
        """))
        
        rows = result.fetchall()
        if rows:
            print("\nSample holiday data:")
            for row in rows:
                print(f"  {row}")
    else:
        print("No holiday tables found in database")