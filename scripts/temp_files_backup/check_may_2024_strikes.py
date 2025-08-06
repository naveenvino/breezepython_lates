"""Check missing strikes for May 2024"""
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import and_, func, Date
from datetime import datetime

db = get_db_manager()

# Missing strikes from the report
missing_strikes = [
    {"strike": 21700, "type": "PE", "expiry": datetime(2024, 5, 16), "dates": "May 13-16"},
    {"strike": 21500, "type": "CE", "expiry": datetime(2024, 5, 16), "dates": "May 13-16 (hedge)"},
    {"strike": 21500, "type": "PE", "expiry": datetime(2024, 5, 16), "dates": "May 13-16 (hedge)"},
    {"strike": 23300, "type": "CE", "expiry": datetime(2024, 5, 30), "dates": "May 27 (hedge)"},
    {"strike": 23100, "type": "CE", "expiry": datetime(2024, 5, 30), "dates": "May 27 (main)"},
]

print("Checking May 2024 Missing Strikes")
print("=" * 60)

with db.get_session() as session:
    for item in missing_strikes:
        strike = item["strike"]
        option_type = item["type"]
        expiry = item["expiry"]
        dates = item["dates"]
        
        # Check with different time components for expiry
        expiry_variants = [
            expiry.replace(hour=0, minute=0, second=0),      # 00:00
            expiry.replace(hour=5, minute=30, second=0),     # 05:30
            expiry.replace(hour=15, minute=30, second=0),    # 15:30
        ]
        
        found = False
        for exp_var in expiry_variants:
            # Check if data exists with this expiry variant
            count = session.query(func.count(OptionsHistoricalData.id)).filter(
                and_(
                    OptionsHistoricalData.strike == strike,
                    OptionsHistoricalData.option_type == option_type,
                    OptionsHistoricalData.expiry_date == exp_var
                )
            ).scalar()
            
            if count > 0:
                print(f"{strike}{option_type} exp {expiry.date()} ({dates}): {count} records")
                found = True
                break
        
        if not found:
            print(f"{strike}{option_type} exp {expiry.date()} ({dates}): NOT FOUND")
    
    # Check what strikes ARE available for May expiries
    print("\n" + "-" * 60)
    print("May 2024 expiries and available strikes:")
    
    may_expiries = session.query(
        func.cast(OptionsHistoricalData.expiry_date, Date),
        func.count(func.distinct(OptionsHistoricalData.strike))
    ).filter(
        and_(
            OptionsHistoricalData.expiry_date >= datetime(2024, 5, 1),
            OptionsHistoricalData.expiry_date < datetime(2024, 6, 1)
        )
    ).group_by(
        func.cast(OptionsHistoricalData.expiry_date, Date)
    ).order_by(
        func.cast(OptionsHistoricalData.expiry_date, Date)
    ).all()
    
    for expiry_date, strike_count in may_expiries:
        weekday = datetime.strptime(str(expiry_date), "%Y-%m-%d").strftime("%A")
        print(f"  {expiry_date} ({weekday}): {strike_count} unique strikes")
    
    # Check specific expiry dates in detail
    print("\n" + "-" * 60)
    print("Detailed check for May 16, 2024 expiry:")
    
    may16_strikes = session.query(
        OptionsHistoricalData.strike,
        OptionsHistoricalData.option_type,
        func.count(OptionsHistoricalData.id)
    ).filter(
        and_(
            OptionsHistoricalData.expiry_date >= datetime(2024, 5, 16, 0, 0, 0),
            OptionsHistoricalData.expiry_date < datetime(2024, 5, 17, 0, 0, 0)
        )
    ).group_by(
        OptionsHistoricalData.strike,
        OptionsHistoricalData.option_type
    ).order_by(
        OptionsHistoricalData.strike
    ).all()
    
    if may16_strikes:
        strikes_list = sorted(set([s[0] for s in may16_strikes]))
        print(f"Available strikes: {strikes_list[:5]}...{strikes_list[-5:]}")
        print(f"Total unique strikes: {len(strikes_list)}")
        
        # Check if 21700 is in the list
        if 21700 in strikes_list:
            print(f"  21700 IS available")
            # Check if PE exists
            pe_exists = any(s[0] == 21700 and s[1] == "PE" for s in may16_strikes)
            print(f"  21700PE: {'EXISTS' if pe_exists else 'MISSING'}")
        else:
            print(f"  21700 NOT in available strikes")
    else:
        print("No data found for May 16, 2024")
    
    print("\n" + "-" * 60)
    print("Detailed check for May 30, 2024 expiry:")
    
    may30_strikes = session.query(
        OptionsHistoricalData.strike,
        OptionsHistoricalData.option_type,
        func.count(OptionsHistoricalData.id)
    ).filter(
        and_(
            OptionsHistoricalData.expiry_date >= datetime(2024, 5, 30, 0, 0, 0),
            OptionsHistoricalData.expiry_date < datetime(2024, 5, 31, 0, 0, 0)
        )
    ).group_by(
        OptionsHistoricalData.strike,
        OptionsHistoricalData.option_type
    ).order_by(
        OptionsHistoricalData.strike
    ).all()
    
    if may30_strikes:
        strikes_list = sorted(set([s[0] for s in may30_strikes]))
        print(f"Available strikes: {strikes_list[:5]}...{strikes_list[-5:]}")
        print(f"Total unique strikes: {len(strikes_list)}")
        
        # Check if 23300 is in the list
        if 23300 in strikes_list:
            print(f"  23300 IS available")
            ce_exists = any(s[0] == 23300 and s[1] == "CE" for s in may30_strikes)
            print(f"  23300CE: {'EXISTS' if ce_exists else 'MISSING'}")
        else:
            print(f"  23300 NOT in available strikes")
            
        # Check if 23100 is in the list
        if 23100 in strikes_list:
            print(f"  23100 IS available")
            ce_exists = any(s[0] == 23100 and s[1] == "CE" for s in may30_strikes)
            print(f"  23100CE: {'EXISTS' if ce_exists else 'MISSING'}")
        else:
            print(f"  23100 NOT in available strikes")