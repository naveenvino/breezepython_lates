"""Trading Holiday Service"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
import aiohttp
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from ..database.models.trading_holidays import TradingHoliday
from ..database.database_manager import get_db_manager
from .breeze_service import BreezeService

logger = logging.getLogger(__name__)

class HolidayService:
    """Service for managing trading holidays"""
    
    def __init__(self, breeze_service: BreezeService = None):
        self.breeze_service = breeze_service or BreezeService()
        self.db_manager = get_db_manager()
        
    async def fetch_holidays_from_nse(self, year: int) -> List[Dict]:
        """
        Fetch holidays from NSE website
        NSE provides holiday list in their website
        """
        try:
            # NSE holiday list URL (this is a common pattern for NSE)
            url = f"https://www.nseindia.com/api/holiday-master?type=trading"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_nse_holidays(data, year)
                    else:
                        logger.error(f"Failed to fetch NSE holidays: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching NSE holidays: {e}")
            return []
    
    def _parse_nse_holidays(self, data: Dict, year: int) -> List[Dict]:
        """Parse NSE holiday response"""
        holidays = []
        
        try:
            # NSE response structure may vary, this is a common pattern
            if 'FO' in data:  # Futures & Options segment
                for holiday in data['FO']:
                    holiday_date = datetime.strptime(holiday['tradingDate'], '%d-%b-%Y').date()
                    if holiday_date.year == year:
                        holidays.append({
                            'date': holiday_date,
                            'name': holiday['weekDay'],
                            'description': holiday.get('description', ''),
                            'exchange': 'NSE'
                        })
                        
            if 'CM' in data:  # Cash Market segment
                for holiday in data['CM']:
                    holiday_date = datetime.strptime(holiday['tradingDate'], '%d-%b-%Y').date()
                    if holiday_date.year == year:
                        holidays.append({
                            'date': holiday_date,
                            'name': holiday['weekDay'],
                            'description': holiday.get('description', ''),
                            'exchange': 'NSE'
                        })
                        
        except Exception as e:
            logger.error(f"Error parsing NSE holidays: {e}")
            
        return holidays
    
    async def fetch_holidays_from_breeze(self, year: int, exchange: str = "NSE") -> List[Dict]:
        """
        Fetch holidays using Breeze API if available
        Note: This endpoint might not be available in all Breeze API versions
        """
        try:
            # Initialize Breeze service
            await self.breeze_service.initialize()
            
            # Try to get exchange holidays
            # Note: The exact method name may vary based on Breeze API version
            result = await self.breeze_service.breeze.get_exchange_holidays(
                exchange=exchange,
                from_date=f"{year}-01-01",
                to_date=f"{year}-12-31"
            )
            
            if result and 'Success' in result:
                return self._parse_breeze_holidays(result['Success'])
            else:
                logger.warning(f"No holiday data from Breeze: {result}")
                return []
                
        except AttributeError:
            logger.info("Breeze API does not have get_exchange_holidays method")
            return []
        except Exception as e:
            logger.error(f"Error fetching holidays from Breeze: {e}")
            return []
    
    def _parse_breeze_holidays(self, holidays_data: List) -> List[Dict]:
        """Parse Breeze holiday response"""
        holidays = []
        
        for holiday in holidays_data:
            try:
                holidays.append({
                    'date': datetime.strptime(holiday['holiday_date'], '%Y-%m-%d').date(),
                    'name': holiday['holiday_name'],
                    'description': holiday.get('holiday_description', ''),
                    'exchange': holiday.get('exchange', 'NSE')
                })
            except Exception as e:
                logger.error(f"Error parsing holiday: {e}")
                
        return holidays
    
    async def save_holidays_to_db(self, holidays: List[Dict]) -> int:
        """Save holidays to database"""
        saved_count = 0
        
        with self.db_manager.get_session() as session:
            for holiday in holidays:
                try:
                    # Check if holiday already exists
                    existing = session.query(TradingHoliday).filter(
                        and_(
                            TradingHoliday.Exchange == holiday['exchange'],
                            TradingHoliday.HolidayDate == holiday['date']
                        )
                    ).first()
                    
                    if not existing:
                        new_holiday = TradingHoliday(
                            Exchange=holiday['exchange'],
                            HolidayDate=holiday['date'],
                            HolidayName=holiday['name'],
                            HolidayType='Trading Holiday',
                            IsTradingHoliday=True,
                            IsSettlementHoliday=False
                        )
                        session.add(new_holiday)
                        saved_count += 1
                        
                except Exception as e:
                    logger.error(f"Error saving holiday {holiday}: {e}")
                    
            session.commit()
            
        logger.info(f"Saved {saved_count} new holidays to database")
        return saved_count
    
    def get_holidays_for_year(self, year: int, exchange: str = "NSE") -> List[TradingHoliday]:
        """Get holidays for a specific year from database"""
        with self.db_manager.get_session() as session:
            holidays = session.query(TradingHoliday).filter(
                and_(
                    TradingHoliday.Exchange == exchange,
                    TradingHoliday.HolidayDate >= date(year, 1, 1),
                    TradingHoliday.HolidayDate <= date(year, 12, 31)
                )
            ).order_by(TradingHoliday.HolidayDate).all()
            
            return holidays
    
    def is_trading_holiday(self, check_date: date, exchange: str = "NSE") -> bool:
        """Check if a specific date is a trading holiday"""
        with self.db_manager.get_session() as session:
            holiday = session.query(TradingHoliday).filter(
                and_(
                    TradingHoliday.Exchange == exchange,
                    TradingHoliday.HolidayDate == check_date,
                    TradingHoliday.IsTradingHoliday == True
                )
            ).first()
            
            return holiday is not None
    
    def get_next_trading_day(self, from_date: date, exchange: str = "NSE") -> date:
        """Get the next trading day after a given date"""
        current_date = from_date
        
        while True:
            # Skip weekends
            if current_date.weekday() in [5, 6]:  # Saturday or Sunday
                current_date = current_date + timedelta(days=1)
                continue
                
            # Check if it's a holiday
            if not self.is_trading_holiday(current_date, exchange):
                return current_date
                
            current_date = current_date + timedelta(days=1)
    
    def get_trading_days_in_range(self, start_date: date, end_date: date, exchange: str = "NSE") -> List[date]:
        """Get all trading days in a date range"""
        trading_days = []
        current_date = start_date
        
        # Get all holidays in the range
        with self.db_manager.get_session() as session:
            holidays = session.query(TradingHoliday.HolidayDate).filter(
                and_(
                    TradingHoliday.Exchange == exchange,
                    TradingHoliday.HolidayDate >= start_date,
                    TradingHoliday.HolidayDate <= end_date,
                    TradingHoliday.IsTradingHoliday == True
                )
            ).all()
            
            holiday_dates = {h.HolidayDate for h in holidays}
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() not in [5, 6]:  # Not Saturday or Sunday
                # Check if it's not a holiday
                if current_date not in holiday_dates:
                    trading_days.append(current_date)
                    
            current_date = current_date + timedelta(days=1)
            
        return trading_days

# Predefined NSE holidays for multiple years
NSE_HOLIDAYS_2024 = [
    {'date': date(2024, 1, 26), 'name': 'Republic Day', 'exchange': 'NSE'},
    {'date': date(2024, 3, 8), 'name': 'Mahashivratri', 'exchange': 'NSE'},
    {'date': date(2024, 3, 25), 'name': 'Holi', 'exchange': 'NSE'},
    {'date': date(2024, 3, 29), 'name': 'Good Friday', 'exchange': 'NSE'},
    {'date': date(2024, 4, 11), 'name': 'Id-Ul-Fitr', 'exchange': 'NSE'},
    {'date': date(2024, 4, 17), 'name': 'Ram Navami', 'exchange': 'NSE'},
    {'date': date(2024, 5, 1), 'name': 'Maharashtra Day', 'exchange': 'NSE'},
    {'date': date(2024, 6, 17), 'name': 'Bakri Id', 'exchange': 'NSE'},
    {'date': date(2024, 7, 17), 'name': 'Muharram', 'exchange': 'NSE'},
    {'date': date(2024, 8, 15), 'name': 'Independence Day', 'exchange': 'NSE'},
    {'date': date(2024, 10, 2), 'name': 'Gandhi Jayanti', 'exchange': 'NSE'},
    {'date': date(2024, 11, 1), 'name': 'Diwali - Laxmi Pujan', 'exchange': 'NSE'},
    {'date': date(2024, 11, 15), 'name': 'Guru Nanak Jayanti', 'exchange': 'NSE'},
    {'date': date(2024, 12, 25), 'name': 'Christmas', 'exchange': 'NSE'},
]

NSE_HOLIDAYS_2025 = [
    {'date': date(2025, 1, 26), 'name': 'Republic Day', 'exchange': 'NSE'},
    {'date': date(2025, 3, 14), 'name': 'Holi', 'exchange': 'NSE'},
    {'date': date(2025, 3, 31), 'name': 'Ram Navami', 'exchange': 'NSE'},  # This is why March 31 has no data!
    {'date': date(2025, 4, 10), 'name': 'Mahavir Jayanti', 'exchange': 'NSE'},
    {'date': date(2025, 4, 14), 'name': 'Ambedkar Jayanti', 'exchange': 'NSE'},
    {'date': date(2025, 4, 18), 'name': 'Good Friday', 'exchange': 'NSE'},
    {'date': date(2025, 5, 1), 'name': 'Maharashtra Day', 'exchange': 'NSE'},
    {'date': date(2025, 8, 15), 'name': 'Independence Day', 'exchange': 'NSE'},
    {'date': date(2025, 8, 27), 'name': 'Ganesh Chaturthi', 'exchange': 'NSE'},
    {'date': date(2025, 10, 2), 'name': 'Gandhi Jayanti', 'exchange': 'NSE'},
    {'date': date(2025, 10, 21), 'name': 'Dussehra', 'exchange': 'NSE'},
    {'date': date(2025, 11, 10), 'name': 'Diwali - Laxmi Pujan', 'exchange': 'NSE'},
    {'date': date(2025, 11, 11), 'name': 'Diwali - Balipratipada', 'exchange': 'NSE'},
    {'date': date(2025, 11, 14), 'name': 'Guru Nanak Jayanti', 'exchange': 'NSE'},
    {'date': date(2025, 12, 25), 'name': 'Christmas', 'exchange': 'NSE'},
]

NSE_HOLIDAYS_2023 = [
    {'date': date(2023, 1, 26), 'name': 'Republic Day', 'exchange': 'NSE'},
    {'date': date(2023, 3, 7), 'name': 'Holi', 'exchange': 'NSE'},
    {'date': date(2023, 3, 30), 'name': 'Ram Navami', 'exchange': 'NSE'},
    {'date': date(2023, 4, 4), 'name': 'Mahavir Jayanti', 'exchange': 'NSE'},
    {'date': date(2023, 4, 7), 'name': 'Good Friday', 'exchange': 'NSE'},
    {'date': date(2023, 4, 14), 'name': 'Ambedkar Jayanti', 'exchange': 'NSE'},
    {'date': date(2023, 5, 1), 'name': 'Maharashtra Day', 'exchange': 'NSE'},
    {'date': date(2023, 6, 29), 'name': 'Bakri Id', 'exchange': 'NSE'},
    {'date': date(2023, 8, 15), 'name': 'Independence Day', 'exchange': 'NSE'},
    {'date': date(2023, 9, 19), 'name': 'Ganesh Chaturthi', 'exchange': 'NSE'},
    {'date': date(2023, 10, 2), 'name': 'Gandhi Jayanti', 'exchange': 'NSE'},
    {'date': date(2023, 10, 24), 'name': 'Dussehra', 'exchange': 'NSE'},
    {'date': date(2023, 11, 13), 'name': 'Diwali - Laxmi Pujan', 'exchange': 'NSE'},
    {'date': date(2023, 11, 14), 'name': 'Diwali - Balipratipada', 'exchange': 'NSE'},
    {'date': date(2023, 11, 27), 'name': 'Guru Nanak Jayanti', 'exchange': 'NSE'},
    {'date': date(2023, 12, 25), 'name': 'Christmas', 'exchange': 'NSE'},
]

NSE_HOLIDAYS_2022 = [
    {'date': date(2022, 1, 26), 'name': 'Republic Day', 'exchange': 'NSE'},
    {'date': date(2022, 3, 1), 'name': 'Mahashivratri', 'exchange': 'NSE'},
    {'date': date(2022, 3, 18), 'name': 'Holi', 'exchange': 'NSE'},
    {'date': date(2022, 4, 14), 'name': 'Ambedkar Jayanti', 'exchange': 'NSE'},
    {'date': date(2022, 4, 15), 'name': 'Good Friday', 'exchange': 'NSE'},
    {'date': date(2022, 5, 3), 'name': 'Id-Ul-Fitr', 'exchange': 'NSE'},
    {'date': date(2022, 8, 9), 'name': 'Muharram', 'exchange': 'NSE'},
    {'date': date(2022, 8, 15), 'name': 'Independence Day', 'exchange': 'NSE'},
    {'date': date(2022, 8, 31), 'name': 'Ganesh Chaturthi', 'exchange': 'NSE'},
    {'date': date(2022, 10, 5), 'name': 'Dussehra', 'exchange': 'NSE'},
    {'date': date(2022, 10, 24), 'name': 'Diwali - Laxmi Pujan', 'exchange': 'NSE'},
    {'date': date(2022, 10, 26), 'name': 'Diwali - Balipratipada', 'exchange': 'NSE'},
    {'date': date(2022, 11, 8), 'name': 'Guru Nanak Jayanti', 'exchange': 'NSE'},
]

# Combine all holidays
ALL_NSE_HOLIDAYS = {
    2022: NSE_HOLIDAYS_2022,
    2023: NSE_HOLIDAYS_2023,
    2024: NSE_HOLIDAYS_2024,
    2025: NSE_HOLIDAYS_2025
}