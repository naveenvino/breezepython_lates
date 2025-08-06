"""
Market Calendar Service
NSE market calendar with holidays and trading hours
"""
from datetime import datetime, date, time, timedelta
from typing import List, Set, Optional, Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MarketSession(Enum):
    """Market session types"""
    PRE_OPEN = "pre_open"
    NORMAL = "normal"
    CLOSING = "closing"
    CLOSED = "closed"
    HOLIDAY = "holiday"


class MarketCalendar:
    """
    NSE market calendar with holidays and trading hours
    Handles trading days, market hours, and expiry calculations
    """
    
    def __init__(self):
        # Market timings (IST)
        self.pre_open_start = time(9, 0)
        self.pre_open_end = time(9, 15)
        self.market_open = time(9, 15)
        self.market_close = time(15, 30)
        self.closing_session_start = time(15, 30)
        self.closing_session_end = time(16, 0)
        
        # NSE Holidays for 2025
        self.holidays_2025 = {
            date(2025, 1, 26),  # Republic Day
            date(2025, 3, 14),  # Holi
            date(2025, 3, 31),  # Ram Navami
            date(2025, 4, 10),  # Mahavir Jayanti
            date(2025, 4, 18),  # Good Friday
            date(2025, 5, 1),   # Maharashtra Day
            date(2025, 8, 15),  # Independence Day
            date(2025, 8, 27),  # Ganesh Chaturthi
            date(2025, 10, 2),  # Gandhi Jayanti
            date(2025, 10, 21), # Dussehra
            date(2025, 11, 1),  # Diwali (Laxmi Pujan)
            date(2025, 11, 2),  # Diwali (Balipratipada)
            date(2025, 11, 17), # Guru Nanak Jayanti
        }
        
        # NSE Holidays for 2024 (for backtesting)
        self.holidays_2024 = {
            date(2024, 1, 26),  # Republic Day
            date(2024, 3, 8),   # Mahashivratri
            date(2024, 3, 25),  # Holi
            date(2024, 3, 29),  # Good Friday
            date(2024, 4, 11),  # Id-Ul-Fitr
            date(2024, 4, 17),  # Ram Navami
            date(2024, 4, 21),  # Mahavir Jayanti
            date(2024, 5, 1),   # Maharashtra Day
            date(2024, 5, 20),  # Buddha Purnima
            date(2024, 6, 17),  # Bakri Id
            date(2024, 7, 17),  # Muharram
            date(2024, 8, 15),  # Independence Day
            date(2024, 8, 19),  # Parsi New Year
            date(2024, 10, 2),  # Gandhi Jayanti
            date(2024, 10, 12), # Dussehra
            date(2024, 11, 1),  # Diwali
            date(2024, 11, 15), # Guru Nanak Jayanti
        }
        
        # Combine all holidays
        self.all_holidays = self.holidays_2024.union(self.holidays_2025)
        
        # Add more years as needed
        logger.info(f"Market calendar initialized with {len(self.all_holidays)} holidays")
        
    def is_holiday(self, check_date: date) -> bool:
        """Check if given date is a market holiday"""
        return check_date in self.all_holidays
        
    def is_weekend(self, check_date: date) -> bool:
        """Check if given date is weekend"""
        return check_date.weekday() in [5, 6]  # Saturday = 5, Sunday = 6
        
    def is_trading_day(self, check_date: date) -> bool:
        """Check if given date is a trading day"""
        return not (self.is_weekend(check_date) or self.is_holiday(check_date))
        
    def get_market_session(self, check_time: datetime) -> MarketSession:
        """Get current market session"""
        if not self.is_trading_day(check_time.date()):
            return MarketSession.HOLIDAY
            
        current_time = check_time.time()
        
        if self.pre_open_start <= current_time < self.pre_open_end:
            return MarketSession.PRE_OPEN
        elif self.market_open <= current_time < self.market_close:
            return MarketSession.NORMAL
        elif self.closing_session_start <= current_time < self.closing_session_end:
            return MarketSession.CLOSING
        else:
            return MarketSession.CLOSED
            
    def is_market_open(self, check_time: datetime) -> bool:
        """Check if market is open for normal trading"""
        session = self.get_market_session(check_time)
        return session == MarketSession.NORMAL
        
    def can_place_order(self, check_time: datetime) -> bool:
        """Check if orders can be placed"""
        session = self.get_market_session(check_time)
        return session in [MarketSession.PRE_OPEN, MarketSession.NORMAL]
        
    def get_next_trading_day(self, from_date: date) -> date:
        """Get next trading day from given date"""
        next_day = from_date + timedelta(days=1)
        
        while not self.is_trading_day(next_day):
            next_day = next_day + timedelta(days=1)
            
        return next_day
        
    def get_previous_trading_day(self, from_date: date) -> date:
        """Get previous trading day from given date"""
        prev_day = from_date - timedelta(days=1)
        
        while not self.is_trading_day(prev_day):
            prev_day = prev_day - timedelta(days=1)
            
        return prev_day
        
    def get_trading_days_between(
        self, 
        start_date: date, 
        end_date: date,
        include_start: bool = True,
        include_end: bool = True
    ) -> List[date]:
        """Get list of trading days between dates"""
        trading_days = []
        
        current = start_date if include_start else start_date + timedelta(days=1)
        end = end_date if include_end else end_date - timedelta(days=1)
        
        while current <= end:
            if self.is_trading_day(current):
                trading_days.append(current)
            current = current + timedelta(days=1)
            
        return trading_days
        
    def get_weekly_expiry(self, for_date: date) -> date:
        """
        Get weekly expiry date (Thursday) for given date
        If Thursday is holiday, expiry is on previous trading day
        """
        # Find Thursday of the week (weekday 3)
        days_until_thursday = (3 - for_date.weekday()) % 7
        if days_until_thursday == 0 and for_date.weekday() == 3:
            # If it's already Thursday, get this Thursday
            thursday = for_date
        else:
            # Get next Thursday
            if for_date.weekday() > 3:  # Friday, Saturday, Sunday
                days_until_thursday = 3 + (7 - for_date.weekday())
            thursday = for_date + timedelta(days=days_until_thursday)
            
        # Check if Thursday is a trading day
        if self.is_trading_day(thursday):
            return thursday
            
        # If Thursday is holiday, find previous trading day
        expiry_date = thursday - timedelta(days=1)
        while not self.is_trading_day(expiry_date):
            expiry_date = expiry_date - timedelta(days=1)
            
        return expiry_date
        
    def get_monthly_expiry(self, year: int, month: int) -> date:
        """
        Get monthly expiry date (last Thursday of month)
        If last Thursday is holiday, expiry is on previous trading day
        """
        # Find last Thursday of the month
        # Start from last day of month and work backwards
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
            
        last_day = next_month - timedelta(days=1)
        
        # Find last Thursday
        while last_day.weekday() != 3:  # Thursday is 3
            last_day = last_day - timedelta(days=1)
            
        # Check if it's a trading day
        if self.is_trading_day(last_day):
            return last_day
            
        # Find previous trading day
        expiry_date = last_day - timedelta(days=1)
        while not self.is_trading_day(expiry_date):
            expiry_date = expiry_date - timedelta(days=1)
            
        return expiry_date
        
    def get_market_open_time(self, trading_date: date) -> Optional[datetime]:
        """Get market open time for a trading day"""
        if not self.is_trading_day(trading_date):
            return None
            
        return datetime.combine(trading_date, self.market_open)
        
    def get_market_close_time(self, trading_date: date) -> Optional[datetime]:
        """Get market close time for a trading day"""
        if not self.is_trading_day(trading_date):
            return None
            
        return datetime.combine(trading_date, self.market_close)
        
    def is_expiry_day(self, check_date: date) -> bool:
        """Check if given date is an expiry day (weekly or monthly)"""
        # Check if it's a weekly expiry
        weekly_expiry = self.get_weekly_expiry(check_date)
        if check_date == weekly_expiry:
            return True
            
        # Check if it's a monthly expiry
        monthly_expiry = self.get_monthly_expiry(check_date.year, check_date.month)
        if check_date == monthly_expiry:
            return True
            
        return False
        
    def get_time_to_expiry(self, current_time: datetime, expiry_date: date) -> timedelta:
        """Get time remaining to expiry"""
        # Expiry happens at 15:30 on expiry day
        expiry_time = datetime.combine(expiry_date, self.market_close)
        
        if current_time >= expiry_time:
            return timedelta(0)
            
        return expiry_time - current_time
        
    def get_trading_sessions_between(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, datetime]]:
        """Get list of trading sessions between two times"""
        sessions = []
        
        current_date = start_time.date()
        end_date = end_time.date()
        
        while current_date <= end_date:
            if self.is_trading_day(current_date):
                session_start = self.get_market_open_time(current_date)
                session_end = self.get_market_close_time(current_date)
                
                # Adjust for start and end times
                if current_date == start_time.date():
                    session_start = max(session_start, start_time)
                if current_date == end_time.date():
                    session_end = min(session_end, end_time)
                    
                if session_start < session_end:
                    sessions.append({
                        "date": current_date,
                        "start": session_start,
                        "end": session_end
                    })
                    
            current_date = current_date + timedelta(days=1)
            
        return sessions
        
    def is_near_expiry(self, current_time: datetime, expiry_date: date, hours: int = 24) -> bool:
        """Check if within specified hours of expiry"""
        time_to_expiry = self.get_time_to_expiry(current_time, expiry_date)
        return time_to_expiry <= timedelta(hours=hours)
        
    def add_trading_days(self, from_date: date, num_days: int) -> date:
        """Add specified number of trading days to date"""
        current = from_date
        days_added = 0
        
        while days_added < num_days:
            current = current + timedelta(days=1)
            if self.is_trading_day(current):
                days_added += 1
                
        return current
        
    def get_holiday_name(self, check_date: date) -> Optional[str]:
        """Get holiday name if date is a holiday"""
        # This would need a more detailed holiday mapping
        # For now, just return generic holiday
        if self.is_holiday(check_date):
            return "Market Holiday"
        elif self.is_weekend(check_date):
            return "Weekend"
        return None