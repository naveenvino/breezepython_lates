"""Check why October 10, 2024 data is not being fetched"""
import asyncio
from datetime import datetime, timedelta
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.services.data_collection_service import DataCollectionService
from src.infrastructure.database.models import TradingHoliday, OptionsHistoricalData
from sqlalchemy import text, and_, func

async def check_october_10():
    print("Investigating October 10, 2024 Data Issue")
    print("=" * 70)
    
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    
    # October 10, 2024 details
    expiry_date = datetime(2024, 10, 10)
    strikes = [25000, 24800]
    
    print(f"Expiry Date: {expiry_date} ({expiry_date.strftime('%A')})")
    print(f"Strikes to check: {strikes}")
    print()
    
    # 1. Check if October 10 is a holiday
    print("1. Checking if October 10, 2024 is a holiday:")
    print("-" * 50)
    
    with db.get_session() as session:
        # Check for holidays around October 10
        holidays = session.query(TradingHoliday).filter(
            and_(
                TradingHoliday.HolidayDate >= datetime(2024, 10, 7).date(),
                TradingHoliday.HolidayDate <= datetime(2024, 10, 11).date(),
                TradingHoliday.Exchange == "NSE",
                TradingHoliday.IsTradingHoliday == True
            )
        ).all()
        
        if holidays:
            for holiday in holidays:
                print(f"  {holiday.HolidayDate} ({holiday.HolidayDate.strftime('%A')}): {holiday.HolidayName}")
        else:
            print("  No holidays found in this week")
    
    # 2. Check what expiry dates are available for October 2024
    print("\n2. Available October 2024 expiries in database:")
    print("-" * 50)
    
    with db.get_session() as session:
        from sqlalchemy import Date
        october_expiries = session.query(
            func.distinct(func.cast(OptionsHistoricalData.expiry_date, Date))
        ).filter(
            and_(
                OptionsHistoricalData.expiry_date >= datetime(2024, 10, 1),
                OptionsHistoricalData.expiry_date < datetime(2024, 11, 1)
            )
        ).order_by(func.cast(OptionsHistoricalData.expiry_date, Date)).all()
        
        for exp in october_expiries:
            exp_date = exp[0]
            if exp_date:
                # Convert string to datetime if needed
                if isinstance(exp_date, str):
                    exp_dt = datetime.strptime(exp_date, "%Y-%m-%d")
                else:
                    exp_dt = datetime.combine(exp_date, datetime.min.time())
                print(f"  {exp_date} ({exp_dt.strftime('%A')})")
    
    # 3. Check if data exists for the specific strikes
    print("\n3. Checking if data exists for strikes 25000 and 24800:")
    print("-" * 50)
    
    with db.get_session() as session:
        for strike in strikes:
            for option_type in ['CE', 'PE']:
                # Check for October 10 expiry
                count_oct10 = session.query(func.count(OptionsHistoricalData.id)).filter(
                    and_(
                        OptionsHistoricalData.strike == strike,
                        OptionsHistoricalData.option_type == option_type,
                        OptionsHistoricalData.expiry_date >= datetime(2024, 10, 10),
                        OptionsHistoricalData.expiry_date < datetime(2024, 10, 11)
                    )
                ).scalar()
                
                print(f"  {strike}{option_type} with Oct 10 expiry: {count_oct10} records")
                
                # Check what expiries ARE available for this strike
                available_expiries = session.query(
                    OptionsHistoricalData.expiry_date,
                    func.count(OptionsHistoricalData.id)
                ).filter(
                    and_(
                        OptionsHistoricalData.strike == strike,
                        OptionsHistoricalData.option_type == option_type,
                        OptionsHistoricalData.expiry_date >= datetime(2024, 10, 1),
                        OptionsHistoricalData.expiry_date < datetime(2024, 11, 1)
                    )
                ).group_by(OptionsHistoricalData.expiry_date).all()
                
                if available_expiries:
                    print(f"    Available October expiries for {strike}{option_type}:")
                    for exp, count in available_expiries:
                        print(f"      - {exp}: {count} records")
    
    # 4. Try to fetch from Breeze API
    print("\n4. Attempting to fetch from Breeze API:")
    print("-" * 50)
    
    # October 10 is Thursday, so check if it's the normal weekly expiry
    # or if expiry moved due to holiday
    
    # First check October 10 (Thursday)
    print("Trying October 10 (Thursday) expiry:")
    for strike in strikes[:1]:  # Test with just one strike
        for option_type in ['CE']:  # Test with just CE
            try:
                expiry_str = expiry_date.strftime("%y%b").upper()  # "24OCT"
                stock_code = f"NIFTY{expiry_str}{strike}{option_type}"
                print(f"  Fetching {stock_code}...")
                
                data = await breeze.get_historical_data(
                    interval="5minute",
                    from_date=datetime(2024, 10, 7, 9, 15),
                    to_date=datetime(2024, 10, 10, 15, 30),
                    stock_code="NIFTY",
                    exchange_code="NFO",
                    product_type="options",
                    strike_price=str(strike),
                    right="Call" if option_type == "CE" else "Put",
                    expiry_date=expiry_date
                )
                
                if data and 'Success' in data:
                    records = data['Success']
                    print(f"    Got {len(records)} records")
                    if records and len(records) > 0:
                        print(f"    Sample: {records[0]}")
                elif data and 'Error' in data:
                    print(f"    Error: {data['Error']}")
                else:
                    print(f"    Response: {data}")
                    
            except Exception as e:
                print(f"    Exception: {e}")
    
    # Check if October 9 (Wednesday) has expiry instead
    print("\nChecking if expiry moved to October 9 (Wednesday):")
    wednesday_expiry = datetime(2024, 10, 9, 15, 30)
    
    with db.get_session() as session:
        wed_count = session.query(func.count(OptionsHistoricalData.id)).filter(
            and_(
                OptionsHistoricalData.expiry_date >= datetime(2024, 10, 9),
                OptionsHistoricalData.expiry_date < datetime(2024, 10, 10),
                OptionsHistoricalData.strike.in_(strikes)
            )
        ).scalar()
        
        print(f"  Records with Oct 9 expiry: {wed_count}")
    
    # 5. Check the WeeklySignalInsights table for October 10
    print("\n5. Checking WeeklySignalInsights_ConsolidatedResults for Oct 10:")
    print("-" * 50)
    
    with db.get_session() as session:
        result = session.execute(text("""
            SELECT 
                ResultID,
                MissingOptionStrikes,
                WeeklyExpiryDate,
                EntryTime,
                ExitTime,
                MainStrikePrice,
                HedgeStrike
            FROM WeeklySignalInsights_ConsolidatedResults
            WHERE WeeklyExpiryDate = '2024-10-10'
        """))
        
        oct10_records = result.fetchall()
        
        if oct10_records:
            for record in oct10_records:
                print(f"  ResultID: {record[0]}")
                print(f"  Missing: {record[1]}")
                print(f"  Entry: {record[3]}, Exit: {record[4]}")
                print(f"  Main Strike: {record[5]}, Hedge: {record[6]}")
        else:
            print("  No records found for October 10 expiry")
    
    print("\n" + "=" * 70)
    print("CONCLUSION:")
    print("-" * 50)
    print("Possible reasons for 0 records on October 10:")
    print("1. October 10 might be a holiday (check holidays table)")
    print("2. Expiry might have moved to October 9 (Wednesday)")
    print("3. Data might not be available in Breeze API")
    print("4. Strike prices might be outside tradeable range")

if __name__ == "__main__":
    asyncio.run(check_october_10())