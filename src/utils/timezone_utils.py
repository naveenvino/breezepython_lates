"""
Timezone Utilities
Handles conversion between UTC and IST for market data
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import pytz


# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')
UTC = pytz.UTC


def utc_to_ist(dt: datetime) -> datetime:
    """Convert UTC datetime to IST"""
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = UTC.localize(dt)
    return dt.astimezone(IST)


def ist_to_utc(dt: datetime) -> datetime:
    """Convert IST datetime to UTC"""
    if dt.tzinfo is None:
        # Assume naive datetime is IST
        dt = IST.localize(dt)
    return dt.astimezone(UTC)


def get_market_open_utc(date: datetime) -> datetime:
    """Get market open time (9:15 AM IST) in UTC for given date"""
    # Create IST time for 9:15 AM
    market_open_ist = IST.localize(datetime.combine(
        date.date() if hasattr(date, 'date') else date,
        datetime.strptime("09:15", "%H:%M").time()
    ))
    # Convert to UTC (will be 3:45 AM UTC)
    return market_open_ist.astimezone(UTC)


def get_market_close_utc(date: datetime) -> datetime:
    """Get market close time (3:30 PM IST) in UTC for given date"""
    # Create IST time for 3:30 PM
    market_close_ist = IST.localize(datetime.combine(
        date.date() if hasattr(date, 'date') else date,
        datetime.strptime("15:30", "%H:%M").time()
    ))
    # Convert to UTC (will be 10:00 AM UTC)
    return market_close_ist.astimezone(UTC)


def is_market_hours_utc(timestamp: datetime) -> bool:
    """Check if UTC timestamp falls within market hours"""
    # Convert to IST
    ist_time = utc_to_ist(timestamp)
    
    # Check if weekday (Monday=0, Friday=4)
    if ist_time.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Check time
    time_only = ist_time.time()
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    
    return market_open <= time_only <= market_close


def get_hourly_candles_utc(date: datetime) -> list[tuple[datetime, datetime]]:
    """
    Get hourly candle times in UTC for a trading day
    Returns list of (start, end) tuples in UTC
    """
    market_open = get_market_open_utc(date)
    market_close = get_market_close_utc(date)
    
    candles = []
    current = market_open
    
    while current < market_close:
        end = current + timedelta(hours=1)
        if end > market_close:
            end = market_close
        candles.append((current, end))
        current = end
    
    return candles


def get_candle_label_time(candle_start_utc: datetime, convention: str = "hour") -> datetime:
    """
    Get the label time for a candle based on convention
    
    Args:
        candle_start_utc: Start time of candle in UTC
        convention: "hour" (9:00 for 9:15-10:15) or "actual" (9:15 for 9:15-10:15)
    
    Returns:
        Datetime to use as candle label
    """
    if convention == "hour":
        # Round down to nearest hour for labeling
        # E.g., 3:45 AM UTC (9:15 AM IST) becomes 3:00 AM UTC (displayed as 9:00)
        return candle_start_utc.replace(minute=0, second=0, microsecond=0)
    else:
        # Use actual start time
        return candle_start_utc


def format_ist_time(dt: datetime) -> str:
    """Format datetime as IST string"""
    ist_time = utc_to_ist(dt) if dt.tzinfo == UTC else dt
    return ist_time.strftime("%Y-%m-%d %H:%M:%S IST")