"""
Market Data Repository Implementation
Concrete implementation of IMarketDataRepository
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from decimal import Decimal
import pyodbc
from sqlalchemy import create_engine, select, and_, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from ...domain.repositories.imarket_data_repository import IMarketDataRepository
from ...domain.entities.market_data import MarketData, TimeInterval
from ..database.models.market_data_model import NiftyIndexData
from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class MarketDataRepository(IMarketDataRepository):
    """SQL Server implementation of market data repository"""
    
    def __init__(self):
        self.settings = get_settings()
        self.engine = create_engine(self.settings.database.connection_string)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    async def get_by_id(self, id: str) -> Optional[MarketData]:
        """Get market data by ID"""
        try:
            with self.SessionLocal() as session:
                result = session.query(NiftyIndexData).filter_by(Id=int(id)).first()
                if result:
                    return self._map_to_domain(result)
                return None
        except Exception as e:
            logger.error(f"Error getting market data by ID {id}: {e}")
            return None
    
    async def get_by_symbol_and_date_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: TimeInterval
    ) -> List[MarketData]:
        """Get market data for symbol within date range"""
        try:
            with self.SessionLocal() as session:
                query = session.query(NiftyIndexData).filter(
                    and_(
                        NiftyIndexData.Symbol == symbol,
                        NiftyIndexData.Timestamp >= start_date,
                        NiftyIndexData.Timestamp <= end_date,
                        NiftyIndexData.Interval == interval.value
                    )
                ).order_by(NiftyIndexData.Timestamp)
                
                results = query.all()
                return [self._map_to_domain(r) for r in results]
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return []
    
    async def get_latest_by_symbol(
        self,
        symbol: str,
        interval: TimeInterval
    ) -> Optional[MarketData]:
        """Get latest market data for symbol"""
        try:
            with self.SessionLocal() as session:
                result = session.query(NiftyIndexData).filter(
                    and_(
                        NiftyIndexData.Symbol == symbol,
                        NiftyIndexData.Interval == interval.value
                    )
                ).order_by(NiftyIndexData.Timestamp.desc()).first()
                
                if result:
                    return self._map_to_domain(result)
                return None
        except Exception as e:
            logger.error(f"Error getting latest market data for {symbol}: {e}")
            return None
    
    async def save(self, entity: MarketData) -> MarketData:
        """Save market data"""
        try:
            with self.SessionLocal() as session:
                # Check if already exists
                existing = session.query(NiftyIndexData).filter(
                    and_(
                        NiftyIndexData.Symbol == entity.symbol,
                        NiftyIndexData.Timestamp == entity.timestamp,
                        NiftyIndexData.Interval == entity.interval.value
                    )
                ).first()
                
                if existing:
                    # Update existing
                    existing.Open = float(entity.open)
                    existing.High = float(entity.high)
                    existing.Low = float(entity.low)
                    existing.Close = float(entity.close)
                    existing.Volume = entity.volume
                    existing.OpenInterest = entity.open_interest
                    existing.UpdatedAt = datetime.utcnow()
                    
                    session.commit()
                    return self._map_to_domain(existing)
                else:
                    # Create new
                    model = NiftyIndexData(
                        Symbol=entity.symbol,
                        Timestamp=entity.timestamp,
                        Open=float(entity.open),
                        High=float(entity.high),
                        Low=float(entity.low),
                        Close=float(entity.close),
                        Volume=entity.volume,
                        OpenInterest=entity.open_interest,
                        Interval=entity.interval.value,
                        CreatedAt=datetime.utcnow()
                    )
                    
                    session.add(model)
                    session.commit()
                    session.refresh(model)
                    
                    # Set the ID on the entity
                    entity.id = str(model.Id)
                    return entity
                    
        except Exception as e:
            logger.error(f"Error saving market data: {e}")
            raise
    
    async def save_batch(self, entities: List[MarketData]) -> int:
        """Save multiple market data records"""
        try:
            with self.SessionLocal() as session:
                saved_count = 0
                
                for entity in entities:
                    # Check if already exists
                    existing = session.query(NiftyIndexData).filter(
                        and_(
                            NiftyIndexData.Symbol == entity.symbol,
                            NiftyIndexData.Timestamp == entity.timestamp,
                            NiftyIndexData.Interval == entity.interval.value
                        )
                    ).first()
                    
                    if not existing:
                        model = NiftyIndexData(
                            Symbol=entity.symbol,
                            Timestamp=entity.timestamp,
                            Open=float(entity.open),
                            High=float(entity.high),
                            Low=float(entity.low),
                            Close=float(entity.close),
                            Volume=entity.volume,
                            OpenInterest=entity.open_interest,
                            Interval=entity.interval.value,
                            CreatedAt=datetime.utcnow()
                        )
                        session.add(model)
                        saved_count += 1
                
                session.commit()
                return saved_count
                
        except Exception as e:
            logger.error(f"Error saving batch market data: {e}")
            raise
    
    async def delete(self, id: str) -> bool:
        """Delete market data by ID"""
        try:
            with self.SessionLocal() as session:
                result = session.query(NiftyIndexData).filter_by(Id=int(id)).first()
                if result:
                    session.delete(result)
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting market data {id}: {e}")
            return False
    
    async def get_aggregated_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        aggregation_interval: TimeInterval,
        source_interval: TimeInterval
    ) -> List[MarketData]:
        """Get aggregated market data"""
        # This is a simplified implementation
        # In production, you would use proper time-based aggregation
        return await self.get_by_symbol_and_date_range(
            symbol, start_date, end_date, aggregation_interval
        )
    
    async def get_data_gaps(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: TimeInterval
    ) -> List[Dict[str, datetime]]:
        """Find gaps in market data"""
        try:
            with self.SessionLocal() as session:
                # Get all timestamps
                results = session.query(NiftyIndexData.Timestamp).filter(
                    and_(
                        NiftyIndexData.Symbol == symbol,
                        NiftyIndexData.Timestamp >= start_date,
                        NiftyIndexData.Timestamp <= end_date,
                        NiftyIndexData.Interval == interval.value
                    )
                ).order_by(NiftyIndexData.Timestamp).all()
                
                if not results:
                    return [{"start": start_date, "end": end_date}]
                
                gaps = []
                timestamps = [r[0] for r in results]
                
                # Check for gaps
                expected_delta = self._get_expected_timedelta(interval)
                
                for i in range(1, len(timestamps)):
                    time_diff = timestamps[i] - timestamps[i-1]
                    if time_diff > expected_delta * 1.5:  # Allow some tolerance
                        gaps.append({
                            "start": timestamps[i-1],
                            "end": timestamps[i]
                        })
                
                return gaps
                
        except Exception as e:
            logger.error(f"Error finding data gaps: {e}")
            return []
    
    async def get_statistics(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get statistics for market data"""
        try:
            with self.SessionLocal() as session:
                stats = session.query(
                    func.count(NiftyIndexData.Id).label('count'),
                    func.min(NiftyIndexData.Timestamp).label('min_date'),
                    func.max(NiftyIndexData.Timestamp).label('max_date'),
                    func.avg(NiftyIndexData.Close).label('avg_close'),
                    func.min(NiftyIndexData.Low).label('min_low'),
                    func.max(NiftyIndexData.High).label('max_high')
                ).filter(
                    and_(
                        NiftyIndexData.Symbol == symbol,
                        NiftyIndexData.Timestamp >= start_date,
                        NiftyIndexData.Timestamp <= end_date
                    )
                ).first()
                
                if stats:
                    return {
                        "total_records": stats.count or 0,
                        "date_range": {
                            "start": stats.min_date,
                            "end": stats.max_date
                        },
                        "price_stats": {
                            "average": float(stats.avg_close) if stats.avg_close else 0,
                            "min": float(stats.min_low) if stats.min_low else 0,
                            "max": float(stats.max_high) if stats.max_high else 0
                        }
                    }
                
                return {
                    "total_records": 0,
                    "date_range": {"start": None, "end": None},
                    "price_stats": {"average": 0, "min": 0, "max": 0}
                }
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def _map_to_domain(self, model: NiftyIndexData) -> MarketData:
        """Map database model to domain entity"""
        # Map interval string to enum
        interval_map = {
            "1minute": TimeInterval.ONE_MINUTE,
            "5minute": TimeInterval.FIVE_MINUTE,
            "30minute": TimeInterval.THIRTY_MINUTE,
            "1hour": TimeInterval.ONE_HOUR,
            "1day": TimeInterval.ONE_DAY
        }
        
        market_data = MarketData(
            symbol=model.Symbol,
            timestamp=model.Timestamp,
            open=Decimal(str(model.Open)),
            high=Decimal(str(model.High)),
            low=Decimal(str(model.Low)),
            close=Decimal(str(model.Close)),
            volume=model.Volume,
            interval=interval_map.get(model.Interval, TimeInterval.ONE_HOUR),
            open_interest=model.OpenInterest
        )
        
        # Set the ID
        market_data.id = str(model.Id)
        
        return market_data
    
    def _get_expected_timedelta(self, interval: TimeInterval):
        """Get expected time delta for interval"""
        from datetime import timedelta
        
        interval_deltas = {
            TimeInterval.ONE_MINUTE: timedelta(minutes=1),
            TimeInterval.FIVE_MINUTE: timedelta(minutes=5),
            TimeInterval.THIRTY_MINUTE: timedelta(minutes=30),
            TimeInterval.ONE_HOUR: timedelta(hours=1),
            TimeInterval.ONE_DAY: timedelta(days=1)
        }
        
        return interval_deltas.get(interval, timedelta(hours=1))
    
    async def exists(self, id: str) -> bool:
        """Check if market data exists by ID"""
        try:
            with self.SessionLocal() as session:
                result = session.query(NiftyIndexData).filter_by(Id=int(id)).first()
                return result is not None
        except Exception:
            return False
    
    async def get_by_symbols_and_date(
        self,
        symbols: List[str],
        date: datetime,
        interval: TimeInterval
    ) -> List[MarketData]:
        """Get market data for multiple symbols on a specific date"""
        try:
            with self.SessionLocal() as session:
                results = session.query(NiftyIndexData).filter(
                    and_(
                        NiftyIndexData.Symbol.in_(symbols),
                        func.date(NiftyIndexData.Timestamp) == date.date(),
                        NiftyIndexData.Interval == interval.value
                    )
                ).all()
                return [self._map_to_domain(r) for r in results]
        except Exception as e:
            logger.error(f"Error getting market data for symbols: {e}")
            return []
    
    async def get_data_statistics(
        self,
        symbol: str,
        interval: TimeInterval
    ) -> Dict[str, Any]:
        """Get data statistics for a symbol"""
        try:
            with self.SessionLocal() as session:
                stats = session.query(
                    func.count(NiftyIndexData.Id).label('count'),
                    func.min(NiftyIndexData.Timestamp).label('min_date'),
                    func.max(NiftyIndexData.Timestamp).label('max_date')
                ).filter(
                    and_(
                        NiftyIndexData.Symbol == symbol,
                        NiftyIndexData.Interval == interval.value
                    )
                ).first()
                
                return {
                    "total_records": stats.count or 0,
                    "date_range": {
                        "start": stats.min_date,
                        "end": stats.max_date
                    }
                }
        except Exception as e:
            logger.error(f"Error getting data statistics: {e}")
            return {"total_records": 0}
    
    async def get_date_range_for_symbol(
        self,
        symbol: str,
        interval: TimeInterval
    ) -> Optional[Dict[str, datetime]]:
        """Get date range for symbol"""
        try:
            with self.SessionLocal() as session:
                result = session.query(
                    func.min(NiftyIndexData.Timestamp).label('start'),
                    func.max(NiftyIndexData.Timestamp).label('end')
                ).filter(
                    and_(
                        NiftyIndexData.Symbol == symbol,
                        NiftyIndexData.Interval == interval.value
                    )
                ).first()
                
                if result and result.start:
                    return {"start": result.start, "end": result.end}
                return None
        except Exception:
            return None
    
    async def get_latest(self, symbols: List[str], interval: TimeInterval) -> List[MarketData]:
        """Get latest market data for multiple symbols"""
        try:
            with self.SessionLocal() as session:
                latest_data = []
                for symbol in symbols:
                    result = session.query(NiftyIndexData).filter(
                        and_(
                            NiftyIndexData.Symbol == symbol,
                            NiftyIndexData.Interval == interval.value
                        )
                    ).order_by(NiftyIndexData.Timestamp.desc()).first()
                    
                    if result:
                        latest_data.append(self._map_to_domain(result))
                
                return latest_data
        except Exception as e:
            logger.error(f"Error getting latest data: {e}")
            return []
    
    async def get_missing_dates(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: TimeInterval
    ) -> List[datetime]:
        """Get missing dates in the range"""
        try:
            with self.SessionLocal() as session:
                existing = session.query(NiftyIndexData.Timestamp).filter(
                    and_(
                        NiftyIndexData.Symbol == symbol,
                        NiftyIndexData.Timestamp >= start_date,
                        NiftyIndexData.Timestamp <= end_date,
                        NiftyIndexData.Interval == interval.value
                    )
                ).all()
                
                existing_dates = {r[0].date() for r in existing}
                
                # Generate expected dates (excluding weekends)
                missing = []
                current = start_date
                while current <= end_date:
                    if current.weekday() < 5 and current.date() not in existing_dates:
                        missing.append(current)
                    current += timedelta(days=1)
                
                return missing
        except Exception:
            return []
    
    async def get_unique_symbols(self) -> List[str]:
        """Get unique symbols in database"""
        try:
            with self.SessionLocal() as session:
                results = session.query(NiftyIndexData.Symbol).distinct().all()
                return [r[0] for r in results]
        except Exception:
            return []
    
    async def save_market_data(self, data: Dict[str, Any]) -> bool:
        """Save market data from dict"""
        try:
            entity = MarketData(
                symbol=data['symbol'],
                timestamp=data['timestamp'],
                open=Decimal(str(data['open'])),
                high=Decimal(str(data['high'])),
                low=Decimal(str(data['low'])),
                close=Decimal(str(data['close'])),
                volume=data.get('volume', 0),
                interval=TimeInterval(data.get('interval', '1hour'))
            )
            await self.save(entity)
            return True
        except Exception:
            return False
    
    async def save_market_data_bulk(self, data_list: List[Dict[str, Any]]) -> int:
        """Save multiple market data records from dicts"""
        entities = []
        for data in data_list:
            try:
                entity = MarketData(
                    symbol=data['symbol'],
                    timestamp=data['timestamp'],
                    open=Decimal(str(data['open'])),
                    high=Decimal(str(data['high'])),
                    low=Decimal(str(data['low'])),
                    close=Decimal(str(data['close'])),
                    volume=data.get('volume', 0),
                    interval=TimeInterval(data.get('interval', '1hour'))
                )
                entities.append(entity)
            except Exception:
                continue
        
        return await self.save_batch(entities)
    
    async def delete_by_symbol_and_date_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """Delete market data by symbol and date range"""
        try:
            with self.SessionLocal() as session:
                result = session.query(NiftyIndexData).filter(
                    and_(
                        NiftyIndexData.Symbol == symbol,
                        NiftyIndexData.Timestamp >= start_date,
                        NiftyIndexData.Timestamp <= end_date
                    )
                ).delete()
                session.commit()
                return result
        except Exception:
            return 0