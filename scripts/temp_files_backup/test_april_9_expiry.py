"""Test April 9th (Wednesday) expiry data availability"""
import asyncio
from datetime import datetime
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.data_collection_service import DataCollectionService

async def test_april_9_expiry():
    print("Testing April 9, 2025 (Wednesday) Expiry Data")
    print("=" * 60)
    
    breeze = BreezeService()
    breeze._initialize()
    
    # Test dates for April 7-9
    from_date = datetime(2025, 4, 7, 9, 15)
    to_date = datetime(2025, 4, 9, 15, 30)
    
    # April 9 is Wednesday (unusual for weekly expiry)
    expiry_wed = datetime(2025, 4, 9)  # Wednesday
    expiry_thu = datetime(2025, 4, 10)  # Thursday (normal weekly expiry)
    
    print(f"Date range: {from_date.date()} to {to_date.date()}")
    print(f"Wednesday expiry: {expiry_wed.date()} (weekday: {expiry_wed.weekday()})")
    print(f"Thursday expiry: {expiry_thu.date()} (weekday: {expiry_thu.weekday()})")
    print()
    
    # Test the specific strikes that are missing
    strikes = [21400, 21500, 21550, 21600]
    
    for expiry, expiry_name in [(expiry_wed, "April 9 (Wed)"), (expiry_thu, "April 10 (Thu)")]:
        print(f"\nTesting {expiry_name} expiry:")
        print("-" * 40)
        
        for strike in strikes:
            print(f"\n  Testing {strike}PE:")
            
            data = await breeze.get_historical_data(
                interval="5minute",
                from_date=from_date,
                to_date=to_date,
                stock_code="NIFTY",
                exchange_code="NFO",
                product_type="options",
                strike_price=str(strike),
                right="Put",
                expiry_date=expiry
            )
            
            if data and 'Success' in data:
                records = data['Success']
                print(f"    Got {len(records)} records")
                if records and len(records) > 0:
                    print(f"    First: {records[0].get('datetime')}")
                    print(f"    Expiry in data: {records[0].get('expiry_date')}")
            elif data and 'Error' in data:
                print(f"    Error: {data['Error']}")
            else:
                print(f"    Response: {data}")
    
    # Now check what's in the database
    print("\n" + "=" * 60)
    print("Checking Database for April 7-9 data:")
    print("-" * 40)
    
    db = get_db_manager()
    data_svc = DataCollectionService(breeze, db)
    
    # Check if we have NIFTY data for those dates
    nifty_data = await data_svc.get_nifty_data(
        from_date,
        to_date,
        "NIFTY",
        timeframe="5minute"
    )
    
    print(f"NIFTY data records: {len(nifty_data)}")
    if nifty_data:
        print(f"  First: {nifty_data[0].timestamp}")
        print(f"  Last: {nifty_data[-1].timestamp}")
        print(f"  Spot price on April 7: {nifty_data[0].close}")
    
    # Check options data in database
    from src.infrastructure.database.models import OptionsHistoricalData
    from sqlalchemy import and_
    
    with db.get_session() as session:
        for strike in strikes:
            count = session.query(OptionsHistoricalData).filter(
                and_(
                    OptionsHistoricalData.strike == strike,
                    OptionsHistoricalData.option_type == "PE",
                    OptionsHistoricalData.timestamp >= from_date,
                    OptionsHistoricalData.timestamp <= to_date
                )
            ).count()
            
            if count > 0:
                sample = session.query(OptionsHistoricalData).filter(
                    and_(
                        OptionsHistoricalData.strike == strike,
                        OptionsHistoricalData.option_type == "PE",
                        OptionsHistoricalData.timestamp >= from_date,
                        OptionsHistoricalData.timestamp <= to_date
                    )
                ).first()
                print(f"\n  {strike}PE in DB: {count} records")
                print(f"    Expiry: {sample.expiry_date}")
                print(f"    Trading Symbol: {sample.trading_symbol}")
            else:
                print(f"\n  {strike}PE in DB: 0 records")
    
    print("\n" + "=" * 60)
    print("Conclusion:")
    print("April 9 is Wednesday - unusual for NIFTY weekly expiry.")
    print("This might be a special/holiday week expiry.")
    print("Check if April 9 or 10 data is available in Breeze.")

if __name__ == "__main__":
    asyncio.run(test_april_9_expiry())