"""
Token Expiry Helper Functions
Manages token expiry times and refresh logic for Breeze and Kite
"""
from datetime import datetime, date, time, timedelta
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

def get_breeze_expiry() -> datetime:
    """
    Get Breeze token expiry time
    Breeze tokens expire at midnight OR 24 hours, whichever is earlier
    
    Returns:
        datetime: Midnight tonight
    """
    # Get today's midnight (next day at 00:00)
    tomorrow = date.today() + timedelta(days=1)
    midnight = datetime.combine(tomorrow, time(0, 0))
    
    # Also check 24 hours from now
    twenty_four_hours = datetime.now() + timedelta(hours=24)
    
    # Return whichever is earlier
    return min(midnight, twenty_four_hours)

def get_kite_expiry() -> datetime:
    """
    Get Kite token expiry time
    Kite tokens expire at 7:30 AM next day
    
    Returns:
        datetime: 7:30 AM tomorrow
    """
    # If current time is before 7:30 AM, token expires today at 7:30 AM
    # Otherwise, it expires tomorrow at 7:30 AM
    now = datetime.now()
    today_730am = datetime.combine(date.today(), time(7, 30))
    
    if now < today_730am:
        # Token from yesterday, expires today at 7:30 AM
        return today_730am
    else:
        # Token from today, expires tomorrow at 7:30 AM
        tomorrow = date.today() + timedelta(days=1)
        return datetime.combine(tomorrow, time(7, 30))

def should_refresh_token(expires_at: datetime, buffer_hours: int = 2) -> bool:
    """
    Check if token should be refreshed (within buffer hours of expiry)
    
    Args:
        expires_at: Token expiry time
        buffer_hours: Hours before expiry to trigger refresh (default 2)
        
    Returns:
        bool: True if token should be refreshed
    """
    if not expires_at:
        return True  # No expiry set, should refresh
    
    refresh_time = expires_at - timedelta(hours=buffer_hours)
    should_refresh = datetime.now() >= refresh_time
    
    if should_refresh:
        logger.info(f"Token should be refreshed. Expires at {expires_at}, current time {datetime.now()}")
    
    return should_refresh

def get_time_until_expiry(expires_at: datetime) -> Tuple[int, int, int]:
    """
    Get time remaining until token expiry
    
    Args:
        expires_at: Token expiry time
        
    Returns:
        Tuple of (hours, minutes, seconds) until expiry
    """
    if not expires_at:
        return (0, 0, 0)
    
    time_remaining = expires_at - datetime.now()
    
    if time_remaining.total_seconds() <= 0:
        return (0, 0, 0)
    
    hours = int(time_remaining.total_seconds() // 3600)
    minutes = int((time_remaining.total_seconds() % 3600) // 60)
    seconds = int(time_remaining.total_seconds() % 60)
    
    return (hours, minutes, seconds)

def format_time_remaining(expires_at: datetime) -> str:
    """
    Format time remaining until expiry as human-readable string
    
    Args:
        expires_at: Token expiry time
        
    Returns:
        str: Formatted time string (e.g., "5h 23m 45s")
    """
    hours, minutes, seconds = get_time_until_expiry(expires_at)
    
    if hours == 0 and minutes == 0 and seconds == 0:
        return "Expired"
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or len(parts) == 0:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)

def get_expiry_status(expires_at: datetime, buffer_hours: int = 2) -> str:
    """
    Get status of token based on expiry time
    
    Args:
        expires_at: Token expiry time
        buffer_hours: Hours before expiry to show warning
        
    Returns:
        str: Status - 'valid', 'warning', or 'expired'
    """
    if not expires_at:
        return 'expired'
    
    now = datetime.now()
    
    if now >= expires_at:
        return 'expired'
    elif now >= expires_at - timedelta(hours=buffer_hours):
        return 'warning'
    else:
        return 'valid'

def get_expiry_percentage(expires_at: datetime, total_hours: int = 24) -> float:
    """
    Get percentage of token lifetime remaining
    
    Args:
        expires_at: Token expiry time
        total_hours: Total token lifetime in hours
        
    Returns:
        float: Percentage remaining (0-100)
    """
    if not expires_at:
        return 0.0
    
    # Calculate when token was created (expires_at - total_hours)
    created_at = expires_at - timedelta(hours=total_hours)
    now = datetime.now()
    
    if now >= expires_at:
        return 0.0
    elif now <= created_at:
        return 100.0
    
    total_seconds = (expires_at - created_at).total_seconds()
    remaining_seconds = (expires_at - now).total_seconds()
    
    return (remaining_seconds / total_seconds) * 100