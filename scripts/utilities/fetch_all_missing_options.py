"""
Fetch all missing options data for the backtest period
"""
import requests
import json
from datetime import datetime, timedelta, date
import time

def get_all_thursdays(from_date, to_date):
    """Get all Thursday expiry dates in the period"""
    thursdays = []
    current = from_date
    
    while current <= to_date:
        # Find next Thursday (weekday 3)
        days_ahead = (3 - current.weekday()) % 7
        if days_ahead == 0 and current > from_date:
            days_ahead = 7
        thursday = current + timedelta(days=days_ahead)
        
        if thursday <= to_date:
            thursdays.append(thursday)
        
        current = thursday + timedelta(days=1)
    
    return thursdays

def fetch_options_for_period(from_date, to_date, strikes=None):
    """Fetch options data for a specific period"""
    
    url = "http://localhost:8000/collect/options-specific"
    
    # If no strikes specified, use a wide range based on typical NIFTY levels
    if not strikes:
        # For Jan-July 2025, NIFTY ranges from ~22500 to ~25500
        strikes = list(range(22000, 26500, 50))
    
    request_data = {
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
        "strikes": strikes,
        "option_types": ["CE", "PE"],
        "symbol": "NIFTY"
    }
    
    print(f"\nFetching options for {from_date} to {to_date}")
    print(f"Strikes: {min(strikes)} to {max(strikes)} ({len(strikes)} strikes)")
    
    try:
        response = requests.post(url, json=request_data, timeout=300)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Success: {result.get('records_added', 0)} records added")
            return True
        else:
            print(f"✗ Error {response.status_code}: {response.text[:200]}")
            return False
    except requests.Timeout:
        print("✗ Request timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("="*80)
    print("FETCHING ALL MISSING OPTIONS DATA")
    print("="*80)
    
    # Define the full period
    from_date = date(2025, 1, 1)
    to_date = date(2025, 7, 31)
    
    print(f"\nPeriod: {from_date} to {to_date}")
    
    # Get all Thursday expiries
    thursdays = get_all_thursdays(from_date, to_date)
    print(f"Found {len(thursdays)} Thursday expiries")
    
    # Define strike ranges for different periods
    # Based on the NIFTY levels shown in the logs
    strike_ranges = [
        # January 2025 - NIFTY around 23000-24000
        (date(2025, 1, 1), date(2025, 1, 31), list(range(22500, 24500, 50))),
        
        # February 2025 - NIFTY around 22500-23500
        (date(2025, 2, 1), date(2025, 2, 28), list(range(22000, 24000, 50))),
        
        # March 2025 - NIFTY around 23000-24000
        (date(2025, 3, 1), date(2025, 3, 31), list(range(22500, 24500, 50))),
        
        # April 2025 - NIFTY around 23500-24500
        (date(2025, 4, 1), date(2025, 4, 30), list(range(23000, 25000, 50))),
        
        # May 2025 - NIFTY around 24000-25000
        (date(2025, 5, 1), date(2025, 5, 31), list(range(23500, 25500, 50))),
        
        # June 2025 - NIFTY around 24500-25500
        (date(2025, 6, 1), date(2025, 6, 30), list(range(24000, 26000, 50))),
        
        # July 2025 - NIFTY around 24500-25500
        (date(2025, 7, 1), date(2025, 7, 31), list(range(24000, 26000, 50))),
    ]
    
    # Option 1: Fetch month by month with appropriate strikes
    print("\n" + "="*80)
    print("FETCHING OPTIONS DATA MONTH BY MONTH")
    print("="*80)
    
    for period_start, period_end, strikes in strike_ranges:
        success = fetch_options_for_period(period_start, period_end, strikes)
        
        if not success:
            print(f"Failed to fetch data for {period_start} to {period_end}")
            print("Continuing with next period...")
        
        # Small delay between requests
        time.sleep(2)
    
    print("\n" + "="*80)
    print("FETCH COMPLETE")
    print("="*80)
    print("\nOptions data fetching completed.")
    print("You can now run the backtest without missing data warnings.")

if __name__ == "__main__":
    print("This will fetch options data for Jan-July 2025")
    print("It may take several minutes to complete")
    print("\nMake sure the API is running on port 8000")
    input("\nPress Enter to start fetching...")
    
    main()