"""
Market Hours Utility
Defines Indian stock market trading hours and provides validation functions
"""
from datetime import time, datetime
from typing import Union


# Indian Stock Market Hours (IST)
MARKET_OPEN = time(9, 15)    # 9:15 AM IST
MARKET_CLOSE = time(15, 30)   # 3:30 PM IST

# Pre-market session (optional - not included by default)
PRE_MARKET_OPEN = time(9, 0)  # 9:00 AM IST
PRE_MARKET_CLOSE = time(9, 15) # 9:15 AM IST

# Breeze API uses END TIME convention for 5-minute candles
# 9:20 timestamp = 9:15-9:20 candle
# For regular hours: we need 9:15-15:30 data
# For extended hours: we need 9:20-15:35 data
BREEZE_DATA_START_REGULAR = time(9, 15)   # Regular hours start
BREEZE_DATA_START_EXTENDED = time(9, 20)  # Extended hours start (Breeze first timestamp)
BREEZE_DATA_END_REGULAR = time(15, 30)    # Regular hours end
BREEZE_DATA_END_EXTENDED = time(15, 35)   # Extended hours end


def is_within_market_hours(timestamp: Union[datetime, str], include_pre_market: bool = False, is_breeze_data: bool = False, extended_hours: bool = False) -> bool:
    """
    Check if a timestamp falls within Indian stock market trading hours
    
    Args:
        timestamp: DateTime object or string in format 'YYYY-MM-DD HH:MM:SS'
        include_pre_market: If True, includes 9:00-9:15 AM pre-market session
        is_breeze_data: If True, uses Breeze timestamp convention (9:20-15:20)
        extended_hours: If True, extends Breeze data end time to 15:35
        
    Returns:
        True if within market hours, False otherwise
    """
    # Convert string to datetime if needed
    if isinstance(timestamp, str):
        timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    
    # Get time component
    market_time = timestamp.time()
    
    # Check if weekend (Saturday=5, Sunday=6)
    if timestamp.weekday() >= 5:
        return False
    
    # For Breeze data, use appropriate bounds based on extended_hours
    if is_breeze_data:
        if extended_hours:
            # Extended hours: 9:20-15:35 (Breeze timestamps)
            return BREEZE_DATA_START_EXTENDED <= market_time <= BREEZE_DATA_END_EXTENDED
        else:
            # Regular hours: 9:15-15:30 (actual market hours)
            return BREEZE_DATA_START_REGULAR <= market_time <= BREEZE_DATA_END_REGULAR
    
    # Check time bounds for regular market hours
    if include_pre_market:
        start_time = PRE_MARKET_OPEN
    else:
        start_time = MARKET_OPEN
    
    # Check if within market hours
    return start_time <= market_time <= MARKET_CLOSE


def filter_market_hours_data(data_records: list, include_pre_market: bool = False) -> list:
    """
    Filter a list of data records to only include those within market hours
    
    Args:
        data_records: List of dictionaries with 'datetime' field
        include_pre_market: If True, includes 9:00-9:15 AM pre-market session
        
    Returns:
        Filtered list containing only records within market hours
    """
    filtered_records = []
    removed_count = 0
    
    for record in data_records:
        timestamp = record.get('datetime', '')
        
        if is_within_market_hours(timestamp, include_pre_market):
            filtered_records.append(record)
        else:
            removed_count += 1
    
    return filtered_records


def get_market_session(timestamp: Union[datetime, str]) -> str:
    """
    Get the market session for a given timestamp
    
    Returns:
        'pre-market', 'regular', 'closed', or 'weekend'
    """
    # Convert string to datetime if needed
    if isinstance(timestamp, str):
        timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    
    # Check if weekend
    if timestamp.weekday() >= 5:
        return 'weekend'
    
    market_time = timestamp.time()
    
    # Check market session
    if market_time < PRE_MARKET_OPEN:
        return 'closed'
    elif PRE_MARKET_OPEN <= market_time < PRE_MARKET_CLOSE:
        return 'pre-market'
    elif MARKET_OPEN <= market_time <= MARKET_CLOSE:
        return 'regular'
    else:
        return 'closed'