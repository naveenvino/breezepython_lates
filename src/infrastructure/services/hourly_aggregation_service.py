"""
Hourly Aggregation Service
Aggregates 5-minute data into hourly candles for trading
"""
import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Tuple
from sqlalchemy import and_, func
from decimal import Decimal

from ..database.models import NiftyIndexData, NiftyIndexDataHourly, NiftyIndexData5Minute
from ..database.database_manager import get_db_manager

logger = logging.getLogger(__name__)


class HourlyAggregationService:
    """
    Service to aggregate 5-minute data into hourly candles
    Market hours: 9:15 AM to 3:30 PM IST
    """
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_db_manager()
        
        # Define hourly periods for Indian market based on Breeze data pattern
        # First hour: 9:15-10:10 (11 candles)
        # Other hours: XX:15-XX:10 (12 candles each)
        # hour_start: The actual hour timestamp (9:15, 10:15, etc.)
        # data_start: First 5-min candle to include
        # data_end: Last 5-min candle to include
        
        self.hourly_periods = [
            # (hour_start, data_start, data_end, period_name)
            (time(9, 15), time(9, 15), time(10, 10), "First Hour (9:15-10:15)"),    # 9:15-10:10 (11 candles)
            (time(10, 15), time(10, 15), time(11, 10), "Second Hour (10:15-11:15)"), # 10:15-11:10 (12 candles)
            (time(11, 15), time(11, 15), time(12, 10), "Third Hour (11:15-12:15)"),  # 11:15-12:10 (12 candles)
            (time(12, 15), time(12, 15), time(13, 10), "Fourth Hour (12:15-13:15)"), # 12:15-13:10 (12 candles)
            (time(13, 15), time(13, 15), time(14, 10), "Fifth Hour (13:15-14:15)"),  # 13:15-14:10 (12 candles)
            (time(14, 15), time(14, 15), time(15, 10), "Sixth Hour (14:15-15:15)"),  # 14:15-15:10 (12 candles)
            (time(15, 15), time(15, 15), time(15, 30), "Last Period (15:15-15:30)"), # 15:15-15:30 (4 candles)
        ]
    
    def get_hourly_candle(
        self, 
        date: datetime, 
        hour_start: time,
        symbol: str = "NIFTY"
    ) -> Optional[Dict]:
        """
        Get hourly candle for a specific hour
        
        Args:
            date: The date for which to get the candle
            hour_start: Start time of the hour (e.g., time(9, 15) for first hour)
            symbol: Symbol to fetch data for
            
        Returns:
            Dictionary with OHLC data or None if no data
        """
        with self.db_manager.get_session() as session:
            # Find the hour period
            hour_info = None
            for hour_time, data_start, data_end, name in self.hourly_periods:
                if hour_time == hour_start:
                    hour_info = (hour_time, data_start, data_end, name)
                    break
            
            if not hour_info:
                logger.warning(f"Invalid hour start time: {hour_start}")
                return None
            
            hour_time, data_start_time, data_end_time, period_name = hour_info
            
            # Create datetime ranges for data query
            start_datetime = datetime.combine(date.date(), data_start_time)
            end_datetime = datetime.combine(date.date(), data_end_time)
            
            # Query 5-minute data for this hour
            five_min_data = session.query(NiftyIndexData5Minute).filter(
                and_(
                    NiftyIndexData5Minute.symbol == symbol,
                    NiftyIndexData5Minute.timestamp >= start_datetime,
                    NiftyIndexData5Minute.timestamp <= end_datetime
                )
            ).order_by(NiftyIndexData5Minute.timestamp).all()
            
            if not five_min_data:
                logger.info(f"No 5-minute data found for {date.date()} {hour_time}")
                return None
            
            # Aggregate to hourly
            # Use the actual hour timestamp (9:15, 10:15, etc.)
            hour_timestamp = datetime.combine(date.date(), hour_time)
            
            hourly_candle = {
                'date': date.date(),
                'hour_start': hour_time,
                'hour_end': time((hour_time.hour + 1) % 24, hour_time.minute),
                'period_name': period_name,
                'timestamp': hour_timestamp,
                'open': float(five_min_data[0].open),
                'high': max(float(bar.high) for bar in five_min_data),
                'low': min(float(bar.low) for bar in five_min_data),
                'close': float(five_min_data[-1].close),
                'volume': sum(bar.volume for bar in five_min_data),
                'bar_count': len(five_min_data)
            }
            
            return hourly_candle
    
    def get_hourly_candles_for_day(
        self, 
        date: datetime,
        symbol: str = "NIFTY"
    ) -> List[Dict]:
        """
        Get all hourly candles for a specific day
        
        Args:
            date: The date for which to get candles
            symbol: Symbol to fetch data for
            
        Returns:
            List of hourly candles
        """
        hourly_candles = []
        
        for hour_time, data_start, data_end, period_name in self.hourly_periods:
            candle = self.get_hourly_candle(date, hour_time, symbol)
            if candle:
                hourly_candles.append(candle)
        
        return hourly_candles
    
    def get_first_two_hourly_candles(
        self, 
        date: datetime,
        symbol: str = "NIFTY"
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Get first two hourly candles for signal evaluation
        
        Returns:
            Tuple of (first_hour_candle, second_hour_candle)
        """
        first_hour = self.get_hourly_candle(date, time(9, 15), symbol)
        second_hour = self.get_hourly_candle(date, time(10, 15), symbol)
        
        return first_hour, second_hour
    
    def create_hourly_bars_from_5min(
        self,
        five_min_bars: List[NiftyIndexData5Minute]
    ) -> List[Dict]:
        """
        Create hourly bars from a list of 5-minute bars
        
        Args:
            five_min_bars: List of 5-minute NiftyIndexData objects
            
        Returns:
            List of hourly candles
        """
        if not five_min_bars:
            return []
        
        hourly_bars = []
        
        # Group by hour
        current_hour_bars = []
        current_hour_start = None
        
        for bar in five_min_bars:
            bar_time = bar.timestamp.time()
            
            # Find which hour this bar belongs to
            for hour_time, data_start, data_end, period_name in self.hourly_periods:
                # Use the data_start and data_end directly from hourly_periods
                # They are already configured correctly based on extended_hours
                if data_start <= bar_time <= data_end:
                    if current_hour_start != hour_time:
                        # New hour started, aggregate previous hour
                        if current_hour_bars:
                            hourly_bar = self._aggregate_bars(
                                current_hour_bars, 
                                current_hour_start
                            )
                            hourly_bars.append(hourly_bar)
                        
                        # Start new hour
                        current_hour_bars = [bar]
                        current_hour_start = hour_time
                    else:
                        # Same hour, add to list
                        current_hour_bars.append(bar)
                    break
        
        # Don't forget the last hour
        if current_hour_bars:
            hourly_bar = self._aggregate_bars(current_hour_bars, current_hour_start)
            hourly_bars.append(hourly_bar)
        
        return hourly_bars
    
    def _aggregate_bars(
        self, 
        bars: List[NiftyIndexData5Minute], 
        hour_start: time
    ) -> Dict:
        """
        Aggregate a list of 5-minute bars into one hourly bar
        """
        # Find period name
        period_name = "Unknown"
        for hour_time, data_start, data_end, name in self.hourly_periods:
            if hour_time == hour_start:
                period_name = name
                break
        
        # Create timestamp with hour start time (9:15, 10:15, etc.)
        timestamp = bars[0].timestamp.replace(hour=hour_start.hour, minute=hour_start.minute)
        
        return {
            'timestamp': timestamp,
            'date': bars[0].timestamp.date(),
            'hour_start': hour_start,
            'period_name': period_name,
            'open': float(bars[0].open),
            'high': max(float(bar.high) for bar in bars),
            'low': min(float(bar.low) for bar in bars),
            'close': float(bars[-1].close),
            'volume': sum(bar.volume for bar in bars),
            'bar_count': len(bars),
            'symbol': bars[0].symbol
        }
    
    def store_hourly_candle(self, hourly_candle: Dict) -> NiftyIndexDataHourly:
        """
        Store an hourly candle in the database
        
        Args:
            hourly_candle: Dictionary with hourly OHLC data
            
        Returns:
            Created NiftyIndexDataHourly object
        """
        with self.db_manager.get_session() as session:
            # Check if already exists in hourly table
            existing = session.query(NiftyIndexDataHourly).filter(
                and_(
                    NiftyIndexDataHourly.symbol == hourly_candle['symbol'],
                    NiftyIndexDataHourly.timestamp == hourly_candle['timestamp']
                )
            ).first()
            
            if existing:
                logger.info(f"Hourly candle already exists for {hourly_candle['timestamp']}")
                return existing
            
            # Create new hourly candle
            hourly_data = NiftyIndexDataHourly(
                symbol=hourly_candle['symbol'],
                timestamp=hourly_candle['timestamp'],
                open=Decimal(str(hourly_candle['open'])),
                high=Decimal(str(hourly_candle['high'])),
                low=Decimal(str(hourly_candle['low'])),
                close=Decimal(str(hourly_candle['close'])),
                last_price=Decimal(str(hourly_candle['close'])),
                volume=hourly_candle['volume'],
                last_update_time=datetime.now()
            )
            
            session.add(hourly_data)
            session.commit()
            
            logger.info(f"Stored hourly candle for {hourly_candle['timestamp']}")
            return hourly_data