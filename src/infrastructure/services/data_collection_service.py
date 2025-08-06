"""
Data Collection Service
Service for fetching and storing historical NIFTY and options data
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from ..database.models import (
    NiftyIndexData, OptionsHistoricalData, NiftyIndexDataHourly, 
    NiftyIndexData5Minute, get_nifty_model_for_timeframe, TradingHoliday
)
from ..database.database_manager import get_db_manager
from .breeze_service import BreezeService
from .hourly_aggregation_service import HourlyAggregationService


logger = logging.getLogger(__name__)


class DataCollectionService:
    """
    Service for collecting and managing historical market data
    """
    
    def __init__(self, breeze_service: BreezeService, db_manager=None):
        self.breeze_service = breeze_service
        self.db_manager = db_manager or get_db_manager()
        self.hourly_aggregation_service = HourlyAggregationService(self.db_manager)
    
    async def ensure_nifty_data_available(
        self, 
        from_date: datetime, 
        to_date: datetime,
        symbol: str = "NIFTY",
        fetch_missing: bool = True
    ) -> int:
        """
        Ensure NIFTY index data is available for the given date range
        Fetches missing data if necessary
        
        Args:
            from_date: Start date
            to_date: End date
            symbol: Symbol to fetch (default: NIFTY)
            fetch_missing: If False, don't fetch from API (for backtesting)
        
        Returns: Number of records added
        """
        logger.info(f"Ensuring NIFTY data available from {from_date} to {to_date}")
        
        # Find missing date ranges
        missing_ranges = await self._find_missing_nifty_ranges(from_date, to_date, symbol)
        
        if not missing_ranges:
            logger.info("All NIFTY data already available")
            return 0
        
        if not fetch_missing:
            # Don't fetch from Breeze API during backtesting - use only existing data
            logger.warning(f"NIFTY data missing for {len(missing_ranges)} ranges, but skipping API fetch (backtesting mode)")
            return 0
        
        total_added = 0
        
        # Fetch and store missing data
        for start, end in missing_ranges:
            logger.info(f"Fetching NIFTY data from {start} to {end}")
            
            try:
                # Fetch from Breeze API
                data = await self.breeze_service.get_historical_data(
                    interval="5minute",  # Changed to 5-minute for hourly aggregation
                    from_date=start,
                    to_date=end,
                    stock_code=symbol,
                    exchange_code="NSE",
                    product_type="cash"
                )
                
                if data and 'Success' in data:
                    records = data['Success']
                    
                    # Log sample timestamp format
                    if records and len(records) > 0:
                        sample_dt = records[0].get('datetime', '')
                        logger.info(f"Breeze API timestamp format for NIFTY: '{sample_dt}'")
                    
                    added = await self._store_nifty_data(records, symbol)
                    total_added += added
                    logger.info(f"Added {added} NIFTY records")
                else:
                    logger.warning(f"No data returned for period {start} to {end}")
                    
            except Exception as e:
                logger.error(f"Error fetching NIFTY data: {e}")
                # Continue with next range
        
        # After fetching all 5-minute data, create hourly candles
        if total_added > 0:
            logger.info("Creating hourly candles from 5-minute data")
            hourly_created = await self.create_hourly_data_from_5min(from_date, to_date, symbol)
            logger.info(f"Created {hourly_created} hourly candles")
        
        return total_added
    
    async def ensure_options_data_available(
        self,
        from_date: datetime,
        to_date: datetime,
        strikes: List[int],
        expiry_dates: List[datetime],
        fetch_missing: bool = True
    ) -> int:
        """
        Ensure options data is available for given strikes and expiries
        
        Args:
            from_date: Start date
            to_date: End date
            strikes: List of strike prices
            expiry_dates: List of expiry dates
            fetch_missing: If False, don't fetch from API (for backtesting)
        
        Returns: Number of records added
        """
        logger.info(f"Ensuring options data for {len(strikes)} strikes and {len(expiry_dates)} expiries")
        logger.info(f"Strikes: {strikes}")
        logger.info(f"Expiries: {[e.date() for e in expiry_dates]}")
        
        total_added = 0
        total_combinations = len(expiry_dates) * len(strikes) * 2  # CE and PE
        current_combination = 0
        
        for expiry in expiry_dates:
            for strike in strikes:
                for option_type in ['CE', 'PE']:
                    current_combination += 1
                    
                    # Find missing ranges for this specific option
                    missing_ranges = await self._find_missing_option_ranges(
                        strike, option_type, expiry, from_date, to_date
                    )
                    
                    if not missing_ranges:
                        logger.debug(f"[{current_combination}/{total_combinations}] {strike}{option_type} exp {expiry.date()}: Complete data available")
                        continue
                    
                    if not fetch_missing:
                        logger.warning(f"[{current_combination}/{total_combinations}] {strike}{option_type} exp {expiry.date()}: Missing {len(missing_ranges)} ranges (backtesting mode)")
                        continue
                    
                    # Fetch missing data for each range
                    logger.info(f"[{current_combination}/{total_combinations}] {strike}{option_type} exp {expiry.date()}: Fetching {len(missing_ranges)} missing ranges")
                    
                    for range_start, range_end in missing_ranges:
                        added = await self._fetch_and_store_option_data(
                            strike, option_type, expiry, range_start, range_end
                        )
                        total_added += added
                        if added > 0:
                            logger.info(f"  Added {added} records for range {range_start} to {range_end}")
        
        logger.info(f"Options data collection complete: {total_added} total records added")
        return total_added
    
    async def _find_missing_nifty_ranges(
        self, 
        from_date: datetime, 
        to_date: datetime,
        symbol: str
    ) -> List[Tuple[datetime, datetime]]:
        """Find date ranges where NIFTY data is missing"""
        missing_ranges = []
        
        with self.db_manager.get_session() as session:
            # Get existing data timestamps from 5-minute table
            existing = session.query(NiftyIndexData5Minute.timestamp).filter(
                and_(
                    NiftyIndexData5Minute.symbol == symbol,
                    NiftyIndexData5Minute.timestamp >= from_date,
                    NiftyIndexData5Minute.timestamp <= to_date
                )
            ).order_by(NiftyIndexData5Minute.timestamp).all()
            
            existing_timestamps = {row[0] for row in existing}
            
            # Generate expected hourly timestamps (market hours only) in IST
            current = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
            expected_timestamps = []
            
            # Get all holidays in the date range
            holidays_result = session.query(TradingHoliday.HolidayDate).filter(
                and_(
                    TradingHoliday.HolidayDate >= from_date.date(),
                    TradingHoliday.HolidayDate <= to_date.date(),
                    TradingHoliday.Exchange == "NSE",
                    TradingHoliday.IsTradingHoliday == True
                )
            ).all()
            holidays = {h[0] for h in holidays_result}
            
            while current <= to_date:
                # Skip weekends and holidays
                if current.weekday() < 5 and current.date() not in holidays:  # Monday=0, Friday=4
                    # Market hours: 9:15 AM to 3:30 PM IST
                    market_open = current.replace(hour=9, minute=15)
                    market_close = current.replace(hour=15, minute=30)
                    
                    # Generate hourly timestamps
                    hour_time = market_open
                    while hour_time <= market_close:
                        if hour_time not in existing_timestamps:
                            expected_timestamps.append(hour_time)
                        
                        # Next hour
                        hour_time += timedelta(hours=1)
                        if hour_time.hour == 15 and hour_time.minute > 30:
                            break
                
                current += timedelta(days=1)
            
            # Group missing timestamps into ranges
            if expected_timestamps:
                expected_timestamps.sort()
                start = expected_timestamps[0]
                prev = start
                
                for ts in expected_timestamps[1:]:
                    if ts - prev > timedelta(hours=24):  # Gap found
                        missing_ranges.append((start, prev))
                        start = ts
                    prev = ts
                
                # Add last range
                missing_ranges.append((start, prev))
        
        return missing_ranges
    
    async def _find_missing_option_ranges(
        self,
        strike: int,
        option_type: str,
        expiry: datetime,
        from_date: datetime,
        to_date: datetime
    ) -> List[Tuple[datetime, datetime]]:
        """Find date/time ranges where option data is missing"""
        missing_ranges = []
        
        with self.db_manager.get_session() as session:
            # Get existing timestamps for this specific option
            expiry_start = expiry.replace(hour=0, minute=0, second=0, microsecond=0)
            expiry_end = expiry.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            existing = session.query(OptionsHistoricalData.timestamp).filter(
                and_(
                    OptionsHistoricalData.strike == strike,
                    OptionsHistoricalData.option_type == option_type,
                    OptionsHistoricalData.expiry_date.between(expiry_start, expiry_end),
                    OptionsHistoricalData.timestamp >= from_date,
                    OptionsHistoricalData.timestamp <= to_date
                )
            ).order_by(OptionsHistoricalData.timestamp).all()
            
            existing_timestamps = {row[0] for row in existing}
            
            # Generate expected timestamps (5-minute intervals during market hours)
            expected_timestamps = []
            current = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Get all holidays in the date range
            holidays_result = session.query(TradingHoliday.HolidayDate).filter(
                and_(
                    TradingHoliday.HolidayDate >= from_date.date(),
                    TradingHoliday.HolidayDate <= to_date.date(),
                    TradingHoliday.Exchange == "NSE",
                    TradingHoliday.IsTradingHoliday == True
                )
            ).all()
            holidays = {h[0] for h in holidays_result}
            
            while current <= to_date:
                # Skip weekends and holidays
                if current.weekday() < 5 and current.date() not in holidays:  # Monday=0, Friday=4
                    # Market hours: 9:15 AM to 3:30 PM
                    market_time = current.replace(hour=9, minute=15)
                    market_close = current.replace(hour=15, minute=30)
                    
                    # Generate 5-minute timestamps
                    while market_time <= market_close:
                        if market_time >= from_date and market_time <= to_date:
                            if market_time not in existing_timestamps:
                                expected_timestamps.append(market_time)
                        
                        market_time += timedelta(minutes=5)
                
                current += timedelta(days=1)
            
            # Group missing timestamps into ranges
            if expected_timestamps:
                expected_timestamps.sort()
                start = expected_timestamps[0]
                prev = start
                
                for ts in expected_timestamps[1:]:
                    # If gap is more than 5 minutes, create a new range
                    if ts - prev > timedelta(minutes=5):
                        missing_ranges.append((start, prev))
                        start = ts
                    prev = ts
                
                # Add last range
                missing_ranges.append((start, prev))
        
        return missing_ranges
    
    async def _store_nifty_data(self, records: List[Dict], symbol: str) -> int:
        """Store NIFTY data records in database"""
        added = 0
        
        with self.db_manager.get_session() as session:
            for record in records:
                try:
                    # Create NiftyIndexData object using from_breeze_data which handles timezone correctly
                    nifty_data = NiftyIndexData.from_breeze_data(record, symbol)
                    
                    # Skip if None (outside market hours)
                    if nifty_data is None:
                        continue
                    
                    # Check if already exists
                    exists = session.query(NiftyIndexData).filter(
                        and_(
                            NiftyIndexData.symbol == symbol,
                            NiftyIndexData.timestamp == nifty_data.timestamp,
                            NiftyIndexData.interval == nifty_data.interval
                        )
                    ).first()
                    
                    if not exists:
                        session.add(nifty_data)
                        added += 1
                        
                except Exception as e:
                    logger.error(f"Error storing NIFTY record: {e}")
                    continue
            
            session.commit()
        
        return added
    
    async def _check_option_data_exists(
        self,
        strike: int,
        option_type: str,
        expiry: datetime,
        from_date: datetime,
        to_date: datetime
    ) -> bool:
        """Check if COMPLETE option data exists for given parameters"""
        with self.db_manager.get_session() as session:
            # Check both date and datetime to handle timezone differences
            # Use date range comparison for SQL Server compatibility
            expiry_start = expiry.replace(hour=0, minute=0, second=0, microsecond=0)
            expiry_end = expiry.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            count = session.query(func.count(OptionsHistoricalData.id)).filter(
                and_(
                    OptionsHistoricalData.strike == strike,
                    OptionsHistoricalData.option_type == option_type,
                    OptionsHistoricalData.expiry_date.between(expiry_start, expiry_end),
                    OptionsHistoricalData.timestamp >= from_date,
                    OptionsHistoricalData.timestamp <= to_date
                )
            ).scalar()
            
            # Calculate expected data points (75 per trading day for 5-minute data)
            # Get holidays in the range
            holidays_result = session.query(TradingHoliday.HolidayDate).filter(
                and_(
                    TradingHoliday.HolidayDate >= from_date.date(),
                    TradingHoliday.HolidayDate <= to_date.date(),
                    TradingHoliday.Exchange == "NSE",
                    TradingHoliday.IsTradingHoliday == True
                )
            ).all()
            holidays = {h[0] for h in holidays_result}
            
            trading_days = 0
            current = from_date.date() if hasattr(from_date, 'date') else from_date
            end = to_date.date() if hasattr(to_date, 'date') else to_date
            
            while current <= end:
                if current.weekday() < 5 and current not in holidays:  # Not weekend or holiday
                    trading_days += 1
                current += timedelta(days=1)
            
            expected_points = trading_days * 75  # 75 five-minute candles per day
            
            # Consider data complete if we have at least 90% of expected points
            completeness_threshold = 0.9
            is_complete = count >= (expected_points * completeness_threshold)
            
            if count > 0 and not is_complete:
                logger.info(f"Partial data for {strike}{option_type}: {count}/{expected_points} points ({count/expected_points*100:.1f}%)")
            
            return is_complete
    
    async def _fetch_and_store_option_data(
        self,
        strike: int,
        option_type: str,
        expiry: datetime,
        from_date: datetime,
        to_date: datetime,
        interval: str = "5minute"
    ) -> int:
        """Fetch and store option data"""
        try:
            # First check if data already exists
            if await self._check_option_data_exists(strike, option_type, expiry, from_date, to_date):
                logger.info(f"Option data already exists for {strike}{option_type} expiry {expiry.date()}")
                return 0  # No new records added
            
            # Generate stock code for option
            expiry_str = expiry.strftime("%y%b").upper()  # e.g., "24JAN"
            stock_code = f"NIFTY{expiry_str}{strike}{option_type}"
            
            logger.info(f"Fetching option data for {stock_code} with {interval} interval")
            
            # Fetch from Breeze with proper option parameters
            data = await self.breeze_service.get_historical_data(
                interval=interval,
                from_date=from_date,
                to_date=to_date,
                stock_code="NIFTY",  # Just the underlying symbol
                exchange_code="NFO",
                product_type="options",
                strike_price=str(strike),
                right="Put" if option_type == "PE" else "Call",
                expiry_date=expiry
            )
            
            if data and 'Success' in data:
                records = data['Success']
                logger.info(f"Got {len(records)} records for {stock_code}")
                if records:
                    return await self._store_option_data(records)
                else:
                    logger.warning(f"Empty Success array for {stock_code}")
                    return 0
            else:
                logger.warning(f"No option data returned for {stock_code}. Response: {data}")
                return 0
                
        except Exception as e:
            logger.error(f"Error fetching option data: {e}")
            return 0
    
    async def _store_option_data(self, records: List[Dict]) -> int:
        """Store option data records in database"""
        added = 0
        
        with self.db_manager.get_session() as session:
            for record in records:
                try:
                    option_data = OptionsHistoricalData.from_breeze_data(record)
                    
                    # Skip if None (outside market hours)
                    if option_data is None:
                        continue
                    
                    # Check if exists
                    exists = session.query(OptionsHistoricalData).filter(
                        and_(
                            OptionsHistoricalData.trading_symbol == option_data.trading_symbol,
                            OptionsHistoricalData.timestamp == option_data.timestamp
                        )
                    ).first()
                    
                    if not exists:
                        session.add(option_data)
                        added += 1
                        
                except Exception as e:
                    logger.error(f"Error storing option record: {e}")
                    continue
            
            session.commit()
        
        return added
    
    async def get_nifty_data(
        self,
        from_date: datetime,
        to_date: datetime,
        symbol: str = "NIFTY",
        timeframe: str = "hourly"
    ) -> List:
        """Get NIFTY data from database for specified timeframe"""
        # Get the appropriate model class
        model_class = get_nifty_model_for_timeframe(timeframe)
        
        with self.db_manager.get_session() as session:
            return session.query(model_class).filter(
                and_(
                    model_class.symbol == symbol,
                    model_class.timestamp >= from_date,
                    model_class.timestamp <= to_date
                )
            ).order_by(model_class.timestamp).all()
    
    async def get_option_data(
        self,
        timestamp: datetime,
        strike: int,
        option_type: str,
        expiry: datetime
    ) -> Optional[OptionsHistoricalData]:
        """Get option data at specific timestamp"""
        with self.db_manager.get_session() as session:
            # Get closest data point within 1 hour
            # Handle expiry time mismatch - DB has 05:30:00 but we might look for 15:30:00
            # First try exact match
            result = session.query(OptionsHistoricalData).filter(
                and_(
                    OptionsHistoricalData.strike == strike,
                    OptionsHistoricalData.option_type == option_type,
                    OptionsHistoricalData.expiry_date == expiry,
                    OptionsHistoricalData.timestamp >= timestamp - timedelta(hours=1),
                    OptionsHistoricalData.timestamp <= timestamp + timedelta(hours=1)
                )
            ).order_by(OptionsHistoricalData.timestamp).first()
            
            # If not found and expiry time is 15:30, try with 05:30 and 00:00
            if not result and expiry.hour == 15 and expiry.minute == 30:
                # Try 05:30
                expiry_with_db_time = expiry.replace(hour=5, minute=30)
                result = session.query(OptionsHistoricalData).filter(
                    and_(
                        OptionsHistoricalData.strike == strike,
                        OptionsHistoricalData.option_type == option_type,
                        OptionsHistoricalData.expiry_date == expiry_with_db_time,
                        OptionsHistoricalData.timestamp >= timestamp - timedelta(hours=1),
                        OptionsHistoricalData.timestamp <= timestamp + timedelta(hours=1)
                    )
                ).order_by(OptionsHistoricalData.timestamp).first()
                
                # If still not found, try 00:00 (midnight)
                if not result:
                    expiry_midnight = expiry.replace(hour=0, minute=0)
                    result = session.query(OptionsHistoricalData).filter(
                        and_(
                            OptionsHistoricalData.strike == strike,
                            OptionsHistoricalData.option_type == option_type,
                            OptionsHistoricalData.expiry_date == expiry_midnight,
                            OptionsHistoricalData.timestamp >= timestamp - timedelta(hours=1),
                            OptionsHistoricalData.timestamp <= timestamp + timedelta(hours=1)
                        )
                    ).order_by(OptionsHistoricalData.timestamp).first()
            
            return result
    
    async def get_available_strikes(
        self,
        expiry: datetime,
        underlying: str = "NIFTY"
    ) -> List[int]:
        """Get available strikes for an expiry"""
        with self.db_manager.get_session() as session:
            strikes = session.query(OptionsHistoricalData.strike).filter(
                and_(
                    OptionsHistoricalData.underlying == underlying,
                    OptionsHistoricalData.expiry_date == expiry
                )
            ).distinct().all()
            
            return sorted([s[0] for s in strikes])
    
    def is_trading_day(self, date_to_check: datetime) -> bool:
        """Check if a given date is a trading day (not weekend or holiday)"""
        # Check if weekend
        if date_to_check.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Check if holiday
        with self.db_manager.get_session() as session:
            is_holiday = session.query(TradingHoliday).filter(
                and_(
                    TradingHoliday.HolidayDate == date_to_check.date(),
                    TradingHoliday.Exchange == "NSE",
                    TradingHoliday.IsTradingHoliday == True
                )
            ).first() is not None
            
            return not is_holiday
    
    async def get_nearest_expiry(self, date: datetime) -> Optional[datetime]:
        """Get nearest weekly expiry from given date
        
        Handles holidays - if Thursday is a holiday, expiry moves to Wednesday
        """
        # NIFTY weekly expiry is normally on Thursday
        days_ahead = 3 - date.weekday()  # Thursday is 3
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        thursday_expiry = date + timedelta(days=days_ahead)
        thursday_expiry = thursday_expiry.replace(hour=15, minute=30, second=0, microsecond=0)
        
        # Check if Thursday is a holiday
        with self.db_manager.get_session() as session:
            is_holiday = session.query(TradingHoliday).filter(
                and_(
                    TradingHoliday.HolidayDate == thursday_expiry.date(),
                    TradingHoliday.Exchange == "NSE",
                    TradingHoliday.IsTradingHoliday == True
                )
            ).first() is not None
            
            if is_holiday:
                # Move to Wednesday
                wednesday_expiry = thursday_expiry - timedelta(days=1)
                logger.info(f"Thursday {thursday_expiry.date()} is a holiday, expiry moves to Wednesday {wednesday_expiry.date()}")
                return wednesday_expiry
            else:
                return thursday_expiry
    
    async def create_hourly_data_from_5min(
        self,
        from_date: datetime,
        to_date: datetime,
        symbol: str = "NIFTY"
    ) -> int:
        """
        Create hourly candles from 5-minute data
        
        Args:
            from_date: Start date
            to_date: End date
            symbol: Symbol to process
            
        Returns:
            Number of hourly candles created
        """
        logger.info(f"Creating hourly candles from {from_date} to {to_date}")
        
        # Get all 5-minute data for the date range
        five_min_data = await self.get_nifty_data(from_date, to_date, symbol, timeframe="5minute")
        
        if not five_min_data:
            logger.warning("No 5-minute data found to aggregate")
            return 0
        
        # Group by date and create hourly candles
        current_date = from_date.date()
        hourly_count = 0
        
        while current_date <= to_date.date():
            # Get 5-minute data for this day
            day_data = [d for d in five_min_data if d.timestamp.date() == current_date]
            
            if day_data:
                # Create hourly candles
                hourly_candles = self.hourly_aggregation_service.create_hourly_bars_from_5min(day_data)
                
                # Store each hourly candle
                for candle in hourly_candles:
                    stored = self.hourly_aggregation_service.store_hourly_candle(candle)
                    if stored:
                        hourly_count += 1
            
            current_date += timedelta(days=1)
        
        logger.info(f"Created {hourly_count} hourly candles")
        return hourly_count
    
    async def collect_nifty_data(
        self,
        from_date,
        to_date,
        symbol="NIFTY",
        force_refresh=False
    ):
        """Collect NIFTY data for the specified date range"""
        from_datetime = datetime.combine(from_date, datetime.strptime("09:15", "%H:%M").time())
        to_datetime = datetime.combine(to_date, datetime.strptime("15:30", "%H:%M").time())
        
        records = await self.ensure_nifty_data_available(
            from_datetime,
            to_datetime,
            symbol,
            fetch_missing=True
        )
        return records
    
    async def collect_options_data(
        self,
        from_date,
        to_date,
        symbol="NIFTY",
        strike_range=500,
        specific_strikes=None,
        strike_interval=100
    ):
        """Collect options data for the specified date range
        
        Args:
            from_date: Start date
            to_date: End date
            symbol: Symbol (default NIFTY)
            strike_range: Range around ATM to fetch (ignored if specific_strikes provided)
            specific_strikes: List of specific strikes to fetch (e.g., [21400, 21550, 21600])
            strike_interval: Interval between strikes (50 or 100, default 100)
        """
        from datetime import date
        # Handle both date and datetime objects
        if isinstance(from_date, datetime):
            from_datetime = from_date
        else:
            from_datetime = datetime.combine(from_date, datetime.strptime("09:15", "%H:%M").time())
        
        if isinstance(to_date, datetime):
            to_datetime = to_date
        else:
            to_datetime = datetime.combine(to_date, datetime.strptime("15:30", "%H:%M").time())
        
        # Get NIFTY data to determine ATM strike
        nifty_data = await self.get_nifty_data(
            from_datetime,
            to_datetime,
            symbol,
            timeframe="5minute"
        )
        
        if not nifty_data:
            logger.warning("No NIFTY data available to determine strikes")
            return 0
        
        # Use specific strikes if provided, otherwise generate based on ATM
        if specific_strikes:
            strikes = specific_strikes
            logger.info(f"Using specific strikes: {strikes}")
        else:
            # Get the first available price to determine ATM
            spot_price = float(nifty_data[0].close)
            # Round to nearest strike interval
            atm_strike = round(spot_price / strike_interval) * strike_interval
            
            # Generate strikes around ATM with specified interval
            strikes = []
            for offset in range(-strike_range, strike_range + strike_interval, strike_interval):
                strike = atm_strike + offset
                if strike > 0:
                    strikes.append(strike)
            logger.info(f"Generated strikes with {strike_interval} interval: ATM={atm_strike}, range={strikes[0]}-{strikes[-1]}")
        
        # Get weekly expiries in the date range
        expiry_dates = []
        # Work with date objects for comparison
        if isinstance(from_date, datetime):
            start_date = from_date.date()
            end_date = to_date.date() if isinstance(to_date, datetime) else to_date
        else:
            start_date = from_date
            end_date = to_date
        
        current = start_date
        while current <= end_date:
            # Thursday is weekday 3
            days_ahead = 3 - current.weekday()
            if days_ahead < 0:
                days_ahead += 7
            thursday = current + timedelta(days=days_ahead)
            
            if start_date <= thursday <= end_date:
                # Check if Thursday is a holiday
                with self.db_manager.get_session() as session:
                    is_holiday = session.query(TradingHoliday).filter(
                        and_(
                            TradingHoliday.HolidayDate == thursday,
                            TradingHoliday.Exchange == "NSE",
                            TradingHoliday.IsTradingHoliday == True
                        )
                    ).first() is not None
                    
                    if is_holiday:
                        # Expiry moves to Wednesday
                        wednesday = thursday - timedelta(days=1)
                        expiry_dates.append(datetime.combine(wednesday, datetime.strptime("15:30", "%H:%M").time()))
                        logger.info(f"Expiry moved from Thursday {thursday} to Wednesday {wednesday} due to holiday")
                    else:
                        expiry_dates.append(datetime.combine(thursday, datetime.strptime("15:30", "%H:%M").time()))
            
            current += timedelta(days=7)
        
        if not expiry_dates:
            # Get nearest expiry
            expiry = await self.get_nearest_expiry(from_datetime)
            if expiry:
                expiry_dates = [expiry]
        
        # Show all strikes if less than 20, otherwise show summary
        if len(strikes) <= 20:
            logger.info(f"Collecting options for strikes {strikes} and expiries {[e.date() for e in expiry_dates]}")
        else:
            logger.info(f"Collecting options for strikes {strikes[:3]}...{strikes[-3:]} ({len(strikes)} total) and expiries {[e.date() for e in expiry_dates]}")
        
        # Track failed strikes for reporting
        failed_strikes = []
        
        records = await self.ensure_options_data_available(
            from_datetime,
            to_datetime,
            strikes,
            expiry_dates,
            fetch_missing=True
        )
        
        # Log summary
        if records == 0:
            logger.warning(f"No records collected. Check if data is available for {expiry_dates}")
        else:
            logger.info(f"Successfully collected {records} records")
        
        return records