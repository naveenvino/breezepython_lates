"""Check if April 10, 2025 is a holiday"""
from src.infrastructure.database.database_manager import get_db_manager
from sqlalchemy import text
from datetime import date

db = get_db_manager()

with db.get_session() as session:
    # Check April holidays
    result = session.execute(text("""
        SELECT HolidayDate, HolidayName, HolidayType
        FROM TradingHolidays
        WHERE HolidayDate BETWEEN '2025-04-01' AND '2025-04-30'
        AND IsTradingHoliday = 1
        ORDER BY HolidayDate
    """))
    
    holidays = result.fetchall()
    
    print("April 2025 Trading Holidays:")
    print("=" * 50)
    
    if holidays:
        for holiday in holidays:
            holiday_date = holiday[0]
            weekday = holiday_date.strftime("%A")
            print(f"  {holiday_date} ({weekday}): {holiday[1]}")
            
            # Check if it's a Thursday
            if weekday == "Thursday":
                print(f"    => THURSDAY HOLIDAY - Expiry moves to Wednesday!")
    else:
        print("  No holidays found")
    
    # Also check April 9 and 10 specifically
    print("\nChecking April 9-10 specifically:")
    april_9 = date(2025, 4, 9)
    april_10 = date(2025, 4, 10)
    
    print(f"  April 9, 2025: {april_9.strftime('%A')} - Wednesday")
    print(f"  April 10, 2025: {april_10.strftime('%A')} - Thursday")
    
    # Check if April 10 is a holiday
    result = session.execute(text("""
        SELECT COUNT(*) FROM TradingHolidays
        WHERE HolidayDate = '2025-04-10'
        AND IsTradingHoliday = 1
    """))
    
    is_holiday = result.scalar() > 0
    
    if is_holiday:
        print("\n  => April 10 (Thursday) is a HOLIDAY")
        print("  => That's why expiry is on April 9 (Wednesday)!")
    else:
        print("\n  => April 10 is NOT a holiday")
        print("  => April 9 Wednesday expiry might be for other reasons")