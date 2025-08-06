"""Compare the different collection endpoints"""
import asyncio
from datetime import datetime, date
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.services.data_collection_service import DataCollectionService
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import and_, func

async def test_endpoints_comparison():
    """Compare different collection methods for March 2024"""
    
    print("Comparing Collection Endpoints for March 2024")
    print("=" * 70)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # Test date range - March 2024 (we know this data exists)
    from_date = date(2024, 3, 11)
    to_date = date(2024, 3, 14)
    
    print(f"Test Date Range: {from_date} to {to_date}")
    print(f"Known missing strikes: 22700CE, 22750CE, 22800CE, 22900CE for March 14 expiry")
    print()
    
    # Method 1: Standard collection with default strike_range (1000)
    print("Method 1: Standard Collection (strike_range=1000)")
    print("-" * 50)
    try:
        result1 = await data_svc.collect_options_data(
            from_date,
            to_date,
            symbol="NIFTY",
            strike_range=1000,
            strike_interval=100
        )
        print(f"  Records collected: {result1}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Method 2: Collection with 50-point intervals
    print("\nMethod 2: Collection with 50-point intervals")
    print("-" * 50)
    try:
        result2 = await data_svc.collect_options_data(
            from_date,
            to_date,
            symbol="NIFTY",
            strike_range=500,
            strike_interval=50  # 50-point intervals
        )
        print(f"  Records collected: {result2}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Method 3: Specific strikes collection
    print("\nMethod 3: Specific Strikes Collection")
    print("-" * 50)
    specific_strikes = [22700, 22750, 22800, 22900]
    print(f"  Collecting specific strikes: {specific_strikes}")
    try:
        from_datetime = datetime(2024, 3, 11, 9, 15)
        to_datetime = datetime(2024, 3, 14, 15, 30)
        expiry = datetime(2024, 3, 14, 15, 30)
        
        result3 = await data_svc.ensure_options_data_available(
            from_datetime,
            to_datetime,
            specific_strikes,
            [expiry],
            fetch_missing=True
        )
        print(f"  Records collected: {result3}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Check what's actually in the database now
    print("\n" + "=" * 70)
    print("Verification: Checking March 14, 2024 strikes in database")
    print("-" * 50)
    
    with db.get_session() as session:
        # Check specific strikes
        for strike in [22700, 22750, 22800, 22900]:
            for option_type in ["CE", "PE"]:
                count = session.query(func.count(OptionsHistoricalData.id)).filter(
                    and_(
                        OptionsHistoricalData.strike == strike,
                        OptionsHistoricalData.option_type == option_type,
                        OptionsHistoricalData.expiry_date >= datetime(2024, 3, 14, 0, 0),
                        OptionsHistoricalData.expiry_date < datetime(2024, 3, 15, 0, 0)
                    )
                ).scalar()
                
                status = "AVAILABLE" if count > 0 else "NOT FOUND"
                print(f"  {strike}{option_type}: {count} records - {status}")
        
        # Get all unique strikes for March 14
        print("\nAll strikes available for March 14, 2024:")
        strikes = session.query(
            func.distinct(OptionsHistoricalData.strike)
        ).filter(
            and_(
                OptionsHistoricalData.expiry_date >= datetime(2024, 3, 14, 0, 0),
                OptionsHistoricalData.expiry_date < datetime(2024, 3, 15, 0, 0)
            )
        ).order_by(OptionsHistoricalData.strike).all()
        
        strikes_list = [s[0] for s in strikes]
        if strikes_list:
            print(f"  {strikes_list}")
            print(f"  Total: {len(strikes_list)} unique strikes")
            
            # Check for 50-point intervals
            has_50_point = any(s % 100 == 50 for s in strikes_list)
            print(f"  Has 50-point intervals: {has_50_point}")
    
    print("\n" + "=" * 70)
    print("Summary:")
    print("-" * 50)
    print("1. Standard collection: Collects strikes around ATM with specified interval")
    print("2. 50-point collection: Can collect 50-point strikes if they exist")
    print("3. Specific strikes: Directly targets missing strikes")
    print("\nNote: Strikes 22700, 22750, 22800, 22900 may not exist in Breeze API for March 14")

if __name__ == "__main__":
    asyncio.run(test_endpoints_comparison())