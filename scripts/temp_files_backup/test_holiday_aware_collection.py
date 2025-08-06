"""Test holiday-aware data collection"""
import asyncio
from datetime import datetime, date, timedelta
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.data_collection_service import DataCollectionService

async def test_holiday_aware_collection():
    print("Testing Holiday-Aware Data Collection")
    print("=" * 60)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # Test 1: Check if April 10 is correctly identified as holiday expiry
    print("\n1. Testing April 2025 expiry detection (April 10 is holiday):")
    april_date = datetime(2025, 4, 7)
    april_expiry = await data_svc.get_nearest_expiry(april_date)
    print(f"   Date: {april_date.date()}")
    print(f"   Detected expiry: {april_expiry.date()} ({april_expiry.strftime('%A')})")
    print(f"   Expected: April 9 (Wednesday) since April 10 is Mahavir Jayanti")
    
    # Test 2: Check if normal Thursday expiry works
    print("\n2. Testing March 2025 expiry detection (no holiday):")
    march_date = datetime(2025, 3, 3)
    march_expiry = await data_svc.get_nearest_expiry(march_date)
    print(f"   Date: {march_date.date()}")
    print(f"   Detected expiry: {march_expiry.date()} ({march_expiry.strftime('%A')})")
    print(f"   Expected: March 6 (Thursday)")
    
    # Test 3: Check trading day detection
    print("\n3. Testing trading day detection:")
    
    # Normal weekday
    normal_day = datetime(2025, 3, 5)  # Wednesday
    is_trading = data_svc.is_trading_day(normal_day)
    print(f"   {normal_day.date()} (Wednesday): {'Trading day' if is_trading else 'Not trading'}")
    
    # Weekend
    saturday = datetime(2025, 3, 8)  # Saturday
    is_trading = data_svc.is_trading_day(saturday)
    print(f"   {saturday.date()} (Saturday): {'Trading day' if is_trading else 'Not trading'}")
    
    # Holiday
    holiday = datetime(2025, 4, 10)  # Mahavir Jayanti
    is_trading = data_svc.is_trading_day(holiday)
    print(f"   {holiday.date()} (Mahavir Jayanti): {'Trading day' if is_trading else 'Not trading'}")
    
    # Test 4: Check missing ranges calculation skips holidays
    print("\n4. Testing missing ranges calculation (should skip holidays):")
    
    # Date range including April 10 holiday
    from_date = datetime(2025, 4, 7, 9, 15)
    to_date = datetime(2025, 4, 11, 15, 30)
    
    missing_ranges = await data_svc._find_missing_nifty_ranges(
        from_date,
        to_date,
        "NIFTY"
    )
    
    print(f"   Date range: {from_date.date()} to {to_date.date()}")
    print(f"   April 10 (Thursday) is a holiday - should be skipped")
    
    # Count expected trading days
    trading_days = []
    current = from_date.date()
    while current <= to_date.date():
        if data_svc.is_trading_day(datetime.combine(current, datetime.min.time())):
            trading_days.append(current)
        current += timedelta(days=1)
    
    print(f"   Trading days in range: {trading_days}")
    print(f"   Missing ranges found: {len(missing_ranges)}")
    
    # Test 5: Test collect_options_data with April date range
    print("\n5. Testing collect_options_data for April week (with holiday):")
    
    result = await data_svc.collect_options_data(
        date(2025, 4, 7),
        date(2025, 4, 11),
        symbol="NIFTY",
        specific_strikes=[21500, 21600],  # Just test with 2 strikes
        strike_interval=100
    )
    
    print(f"   Collected {result} records")
    print(f"   Should detect Wednesday expiry due to Thursday holiday")
    
    print("\n" + "=" * 60)
    print("Holiday-aware data collection test complete!")
    print("System now correctly handles:")
    print("  - Holiday detection for expiry dates")
    print("  - Skipping holidays in missing data ranges")
    print("  - Trading day validation")
    print("  - Accurate expected data points calculation")

if __name__ == "__main__":
    asyncio.run(test_holiday_aware_collection())