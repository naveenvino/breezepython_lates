"""
Asynchronous Hourly Aggregation Service
"""
import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Tuple
from sqlalchemy import and_, func, select
from decimal import Decimal

from ..database.models import NiftyIndexData, NiftyIndexDataHourly, NiftyIndexData5Minute
from ..database.database_manager_async import get_async_db_manager

logger = logging.getLogger(__name__)


class AsyncHourlyAggregationService:
    """
    Service to aggregate 5-minute data into hourly candles asynchronously
    """
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_async_db_manager()
        self.hourly_periods = [
            (time(9, 15), time(9, 15), time(10, 10), "First Hour (9:15-10:15)"),
            (time(10, 15), time(10, 15), time(11, 10), "Second Hour (10:15-11:15)"),
            (time(11, 15), time(11, 15), time(12, 10), "Third Hour (11:15-12:15)"),
            (time(12, 15), time(12, 15), time(13, 10), "Fourth Hour (12:15-13:15)"),
            (time(13, 15), time(13, 15), time(14, 10), "Fifth Hour (13:15-14:15)"),
            (time(14, 15), time(14, 15), time(15, 10), "Sixth Hour (14:15-15:15)"),
            (time(15, 15), time(15, 15), time(15, 30), "Last Period (15:15-15:30)"),
        ]
    
    async def get_hourly_candle(self, date: datetime, hour_start: time, symbol: str = "NIFTY") -> Optional[Dict]:
        async with self.db_manager.get_session() as session:
            # ... (implementation will be similar to the synchronous version, but with async calls)
            return None
    
    async def store_hourly_candle(self, hourly_candle: Dict) -> NiftyIndexDataHourly:
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(NiftyIndexDataHourly).filter(
                    and_(
                        NiftyIndexDataHourly.symbol == hourly_candle['symbol'],
                        NiftyIndexDataHourly.timestamp == hourly_candle['timestamp']
                    )
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"Hourly candle already exists for {hourly_candle['timestamp']}")
                return existing
            
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
            await session.commit()
            
            logger.info(f"Stored hourly candle for {hourly_candle['timestamp']}")
            return hourly_data
