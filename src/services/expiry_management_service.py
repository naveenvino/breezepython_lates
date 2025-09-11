"""
NIFTY Weekly Expiry Management Service
Handles calculation of available expiry dates based on current day
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ExpiryManagementService:
    """Manages NIFTY weekly expiry calculations and selections"""
    
    # NSE Holidays for 2025 (to be updated annually)
    NSE_HOLIDAYS_2025 = [
        datetime(2025, 1, 26),  # Republic Day
        datetime(2025, 3, 14),  # Holi
        datetime(2025, 3, 31),  # Ram Navami
        datetime(2025, 4, 10),  # Mahavir Jayanti
        datetime(2025, 4, 18),  # Good Friday
        datetime(2025, 5, 1),   # Maharashtra Day
        datetime(2025, 8, 15),  # Independence Day
        datetime(2025, 8, 27),  # Ganesh Chaturthi
        datetime(2025, 10, 2),  # Gandhi Jayanti
        datetime(2025, 10, 21), # Dussehra
        datetime(2025, 11, 1),  # Diwali
        datetime(2025, 11, 5),  # Bhai Dooj
        datetime(2025, 11, 19), # Guru Nanak Jayanti
        datetime(2025, 12, 25), # Christmas
    ]
    
    def __init__(self):
        self.holidays = set(self.NSE_HOLIDAYS_2025)
    
    def get_next_tuesday(self, from_date: datetime) -> datetime:
        """Get the next Tuesday from given date"""
        days_ahead = 1 - from_date.weekday()  # Tuesday is 1
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        return from_date + timedelta(days=days_ahead)
    
    def get_current_week_tuesday(self, from_date: datetime) -> datetime:
        """Get Tuesday of the current week"""
        # Monday is 0, Tuesday is 1
        days_since_monday = from_date.weekday()
        monday = from_date - timedelta(days=days_since_monday)
        tuesday = monday + timedelta(days=1)
        return tuesday
    
    def get_month_end_tuesday(self, from_date: datetime) -> datetime:
        """Get the last Tuesday of the current month"""
        # Start from the last day of the month
        if from_date.month == 12:
            last_day = datetime(from_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(from_date.year, from_date.month + 1, 1) - timedelta(days=1)
        
        # Find the last Tuesday
        while last_day.weekday() != 1:  # Tuesday is 1
            last_day -= timedelta(days=1)
        
        return last_day
    
    def is_trading_day(self, date: datetime) -> bool:
        """Check if given date is a trading day"""
        # Check if weekend
        if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if holiday
        # Handle both datetime and date objects in holidays set
        date_to_check = date.date() if hasattr(date, 'date') else date
        for h in self.holidays:
            holiday_date = h.date() if hasattr(h, 'date') else h
            if date_to_check == holiday_date:
                return False
        
        return True
    
    def adjust_for_holiday(self, expiry_date: datetime) -> datetime:
        """Adjust expiry date if it falls on a holiday"""
        original = expiry_date
        
        # If Tuesday is a holiday, move to previous trading day
        while not self.is_trading_day(expiry_date):
            expiry_date -= timedelta(days=1)
        
        if expiry_date != original:
            logger.info(f"Expiry adjusted from {original.date()} to {expiry_date.date()} due to holiday")
        
        return expiry_date
    
    def get_available_expiries(self, current_date: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        """
        Get available expiry dates based on current day of week
        
        Returns:
            Dict with:
            - available_expiries: List of expiry options
            - default_expiry: Recommended default selection
            - current_week_available: Boolean indicating if current week is tradeable
        """
        if current_date is None:
            current_date = datetime.now()
        
        weekday = current_date.weekday()  # Monday=0, Sunday=6
        available_expiries = []
        
        # Get key dates
        current_tuesday = self.get_current_week_tuesday(current_date)
        next_tuesday = current_tuesday + timedelta(days=7)
        month_end_tuesday = self.get_month_end_tuesday(current_date)
        
        # Adjust for holidays
        current_tuesday = self.adjust_for_holiday(current_tuesday)
        next_tuesday = self.adjust_for_holiday(next_tuesday)
        month_end_tuesday = self.adjust_for_holiday(month_end_tuesday)
        
        # Determine available expiries based on current day
        current_week_available = False
        
        if weekday in [0, 1]:  # Monday or Tuesday
            # Current week expiry is available
            if current_tuesday >= current_date:
                current_week_available = True
                available_expiries.append({
                    "date": current_tuesday.strftime("%Y-%m-%d"),
                    "display": f"Current Week - {current_tuesday.strftime('%b %d')}",
                    "type": "current_week",
                    "days_to_expiry": (current_tuesday - current_date).days
                })
        
        # Next week is always available
        available_expiries.append({
            "date": next_tuesday.strftime("%Y-%m-%d"),
            "display": f"Next Week - {next_tuesday.strftime('%b %d')}",
            "type": "next_week",
            "days_to_expiry": (next_tuesday - current_date).days
        })
        
        # Month-end expiry (if different from next week)
        if month_end_tuesday != next_tuesday and month_end_tuesday > current_date:
            available_expiries.append({
                "date": month_end_tuesday.strftime("%Y-%m-%d"),
                "display": f"Month End - {month_end_tuesday.strftime('%b %d')}",
                "type": "month_end",
                "days_to_expiry": (month_end_tuesday - current_date).days
            })
        
        # Determine default selection
        default_expiry = available_expiries[0]["date"] if available_expiries else None
        
        return {
            "available_expiries": available_expiries,
            "default_expiry": default_expiry,
            "current_week_available": current_week_available,
            "current_date": current_date.strftime("%Y-%m-%d"),
            "current_day": current_date.strftime("%A")
        }
    
    def calculate_exit_date(self, entry_date: datetime, t_plus_days: int) -> Tuple[datetime, str]:
        """
        Calculate exit date based on T+N days (excluding weekends)
        
        Args:
            entry_date: The trade entry date
            t_plus_days: Number of trading days after entry (0 for expiry day, 1-7 for T+N)
        
        Returns:
            Tuple of (exit_date, display_string)
        """
        # Handle expiry day (T+0)
        if t_plus_days == 0:
            # Get the expiry date for the position
            # Determine which week's expiry based on entry date
            current_weekday = entry_date.strftime("%A").lower()
            
            # Load weekday config to determine expiry selection
            import json
            config_file = "expiry_weekday_config.json"
            try:
                with open(config_file, 'r') as f:
                    weekday_config = json.load(f)
                    expiry_type = weekday_config.get(current_weekday, "next")
            except:
                expiry_type = "next"  # Default to next week
            
            # Get the appropriate expiry date
            if expiry_type == "current" and current_weekday in ["monday", "tuesday"]:
                expiry_date = self.get_current_week_expiry(entry_date)
            elif expiry_type == "month_end":
                expiry_date = self.get_month_end_expiry(entry_date)
            else:
                expiry_date = self.get_next_week_expiry(entry_date)
            
            display = f"Expiry Day ({expiry_date.strftime('%A, %b %d')})"
            return expiry_date, display
        
        if t_plus_days < 1 or t_plus_days > 7:
            raise ValueError("T+N days must be between 1 and 7")
        
        exit_date = entry_date
        days_added = 0
        
        while days_added < t_plus_days:
            exit_date += timedelta(days=1)
            # Only count trading days
            if self.is_trading_day(exit_date):
                days_added += 1
        
        display = f"T+{t_plus_days} ({exit_date.strftime('%A, %b %d')})"
        
        return exit_date, display
    
    def get_exit_timing_options(self) -> Dict:
        """Get available exit timing options"""
        return {
            "exit_days": [
                {"value": 0, "label": "Expiry Day"},
                {"value": 1, "label": "T+1 (Next trading day)"},
                {"value": 2, "label": "T+2 (2 trading days)"},
                {"value": 3, "label": "T+3 (3 trading days)"},
                {"value": 4, "label": "T+4 (4 trading days)"},
                {"value": 5, "label": "T+5 (5 trading days)"},
                {"value": 6, "label": "T+6 (6 trading days)"},
                {"value": 7, "label": "T+7 (7 trading days)"}
            ],
            "exit_times": [
                {"value": "09:30", "label": "9:30 AM"},
                {"value": "10:15", "label": "10:15 AM"},
                {"value": "12:15", "label": "12:15 PM"},
                {"value": "14:15", "label": "2:15 PM"},
                {"value": "15:15", "label": "3:15 PM"}
            ],
            "default_exit_day": 2,
            "default_exit_time": "15:15"
        }
    
    def get_current_week_expiry(self, reference_date: datetime = None) -> datetime:
        """Get current week's actual expiry date (checking Mon-Fri for NSE expiry)"""
        if reference_date is None:
            reference_date = datetime.now()
        
        # Get Monday of current week
        days_since_monday = reference_date.weekday()
        monday_this_week = reference_date - timedelta(days=days_since_monday)
        
        # Check each day of the week for expiry (Mon-Fri)
        # Default is Tuesday, but adjust if holiday
        for day_offset in range(5):  # Monday to Friday
            potential_expiry = monday_this_week + timedelta(days=day_offset)
            
            # For current week, skip if date has already passed
            if potential_expiry.date() < reference_date.date():
                continue
                
            # Tuesday (day_offset=1) is the standard expiry day
            if day_offset == 1:  # Tuesday
                if self.is_trading_day(potential_expiry):
                    return potential_expiry
                # If Tuesday is holiday, continue checking other days
            
            # Check if this could be an alternate expiry day (Mon/Wed/Thu/Fri)
            # This happens when Tuesday is a holiday
            if day_offset in [0, 2, 3, 4]:  # Mon, Wed, Thu, Fri
                # Check if Tuesday was a holiday
                tuesday = monday_this_week + timedelta(days=1)
                if not self.is_trading_day(tuesday) and self.is_trading_day(potential_expiry):
                    # This is likely the adjusted expiry day
                    return potential_expiry
        
        # Fallback to next week if no valid expiry found in current week
        return self.get_next_week_expiry(reference_date)
    
    def get_next_week_expiry(self, reference_date: datetime = None) -> datetime:
        """Get next week's actual expiry date (checking Mon-Fri for NSE expiry)"""
        if reference_date is None:
            reference_date = datetime.now()
        
        # Get Monday of next week
        days_since_monday = reference_date.weekday()
        monday_this_week = reference_date - timedelta(days=days_since_monday)
        monday_next_week = monday_this_week + timedelta(days=7)
        
        # Check each day of next week for expiry (Mon-Fri)
        for day_offset in range(5):  # Monday to Friday
            potential_expiry = monday_next_week + timedelta(days=day_offset)
            
            # Tuesday (day_offset=1) is the standard expiry day
            if day_offset == 1:  # Tuesday
                if self.is_trading_day(potential_expiry):
                    return potential_expiry
                # If Tuesday is holiday, continue checking other days
            
            # Check if this could be an alternate expiry day (Mon/Wed/Thu/Fri)
            # This happens when Tuesday is a holiday
            if day_offset in [0, 2, 3, 4]:  # Mon, Wed, Thu, Fri
                # Check if Tuesday was a holiday
                tuesday = monday_next_week + timedelta(days=1)
                if not self.is_trading_day(tuesday) and self.is_trading_day(potential_expiry):
                    # This is likely the adjusted expiry day
                    return potential_expiry
        
        # If no valid expiry found (unlikely), return Tuesday anyway
        return monday_next_week + timedelta(days=1)
    
    def get_month_end_expiry(self, reference_date: datetime = None) -> datetime:
        """Get month-end expiry date (last Tuesday of the month)"""
        if reference_date is None:
            reference_date = datetime.now()
        
        # Get last day of current month
        if reference_date.month == 12:
            last_day = datetime(reference_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(reference_date.year, reference_date.month + 1, 1) - timedelta(days=1)
        
        # Find last Tuesday
        while last_day.weekday() != 1:  # Tuesday is 1
            last_day -= timedelta(days=1)
        
        # Check if it's a holiday
        if last_day.date() in self.holidays:
            # Move to Wednesday
            last_day += timedelta(days=1)
        
        return last_day
    
    def format_expiry_for_symbol(self, expiry_date: str, symbol_base: str = "NIFTY") -> str:
        """
        Format expiry date for option symbol creation
        
        Args:
            expiry_date: Date string in YYYY-MM-DD format
            symbol_base: Base symbol (default NIFTY)
        
        Returns:
            Formatted symbol like NIFTY07JAN25
        """
        date_obj = datetime.strptime(expiry_date, "%Y-%m-%d")
        
        # Format: NIFTY DDMMMYY (e.g., NIFTY07JAN25)
        day = date_obj.strftime("%d")
        month = date_obj.strftime("%b").upper()
        year = date_obj.strftime("%y")
        
        return f"{symbol_base}{day}{month}{year}"
    
    def validate_expiry_selection(self, selected_expiry: str) -> Tuple[bool, str]:
        """
        Validate if selected expiry is valid for trading
        
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            expiry_date = datetime.strptime(selected_expiry, "%Y-%m-%d")
            current_date = datetime.now()
            
            # Check if expiry is in the past
            if expiry_date.date() < current_date.date():
                return False, "Selected expiry is in the past"
            
            # Check if it's a valid trading day
            if not self.is_trading_day(expiry_date):
                return False, "Selected date is not a trading day"
            
            # Check if it's too far in the future (max 30 days)
            if (expiry_date - current_date).days > 30:
                return False, "Selected expiry is too far in the future (max 30 days)"
            
            return True, "Valid expiry selection"
            
        except ValueError as e:
            return False, f"Invalid date format: {str(e)}"


# Singleton instance
_expiry_service = None

def get_expiry_service() -> ExpiryManagementService:
    """Get singleton instance of expiry service"""
    global _expiry_service
    if _expiry_service is None:
        _expiry_service = ExpiryManagementService()
    return _expiry_service