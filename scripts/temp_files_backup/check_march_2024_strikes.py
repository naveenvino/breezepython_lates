"""Check missing strikes for March 2024"""
from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.database.models import OptionsHistoricalData
from sqlalchemy import and_, func, Date
from datetime import datetime

db = get_db_manager()

# Missing strikes from the report
missing_strikes = [
    {"strike": 22250, "type": "PE", "expiry": datetime(2024, 3, 7)},
    {"strike": 22700, "type": "CE", "expiry": datetime(2024, 3, 14)},
    {"strike": 22750, "type": "CE", "expiry": datetime(2024, 3, 14)},
    {"strike": 22800, "type": "CE", "expiry": datetime(2024, 3, 14)},
    {"strike": 22900, "type": "CE", "expiry": datetime(2024, 3, 14)},
    {"strike": 21750, "type": "PE", "expiry": datetime(2024, 3, 21)},
    {"strike": 21750, "type": "PE", "expiry": datetime(2024, 3, 28)},
]

print("Checking March 2024 Missing Strikes")
print("=" * 60)

with db.get_session() as session:
    for item in missing_strikes:
        strike = item["strike"]
        option_type = item["type"]
        expiry = item["expiry"]
        
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
                print(f"{strike}{option_type} exp {expiry.date()}: {count} records (expiry time: {exp_var.time()})")
                found = True
                break
        
        if not found:
            print(f"{strike}{option_type} exp {expiry.date()}: NOT FOUND")
    
    # Check what strikes ARE available for March 14 expiry
    print("\n" + "-" * 60)
    print("Available strikes for March 14, 2024 expiry:")
    
    march_14_strikes = session.query(
        OptionsHistoricalData.strike,
        OptionsHistoricalData.option_type,
        func.count(OptionsHistoricalData.id)
    ).filter(
        and_(
            OptionsHistoricalData.expiry_date >= datetime(2024, 3, 14, 0, 0, 0),
            OptionsHistoricalData.expiry_date < datetime(2024, 3, 15, 0, 0, 0)
        )
    ).group_by(
        OptionsHistoricalData.strike,
        OptionsHistoricalData.option_type
    ).order_by(
        OptionsHistoricalData.strike
    ).all()
    
    if march_14_strikes:
        ce_strikes = [s[0] for s in march_14_strikes if s[1] == "CE"]
        pe_strikes = [s[0] for s in march_14_strikes if s[1] == "PE"]
        
        print(f"CE strikes: {ce_strikes[:5]}...{ce_strikes[-5:] if len(ce_strikes) > 10 else ce_strikes[5:]}")
        print(f"PE strikes: {pe_strikes[:5]}...{pe_strikes[-5:] if len(pe_strikes) > 10 else pe_strikes[5:]}")
        print(f"Total: {len(ce_strikes)} CE, {len(pe_strikes)} PE")
        
        # Check if 50-point strikes are present
        if any(s % 100 == 50 for s in ce_strikes):
            print("50-point strikes ARE present")
        else:
            print("50-point strikes NOT present - only 100-point intervals")
    else:
        print("No data found for March 14, 2024 expiry")
    
    # Get all March 2024 expiries
    print("\n" + "-" * 60)
    print("All March 2024 expiries in database:")
    
    march_expiries = session.query(
        func.cast(OptionsHistoricalData.expiry_date, Date),
        func.count(func.distinct(OptionsHistoricalData.strike))
    ).filter(
        and_(
            OptionsHistoricalData.expiry_date >= datetime(2024, 3, 1),
            OptionsHistoricalData.expiry_date < datetime(2024, 4, 1)
        )
    ).group_by(
        func.cast(OptionsHistoricalData.expiry_date, Date)
    ).order_by(
        func.cast(OptionsHistoricalData.expiry_date, Date)
    ).all()
    
    for expiry_date, strike_count in march_expiries:
        weekday = datetime.strptime(str(expiry_date), "%Y-%m-%d").strftime("%A")
        print(f"  {expiry_date} ({weekday}): {strike_count} unique strikes")