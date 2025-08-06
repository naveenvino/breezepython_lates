"""
Options Repository Implementation
Concrete implementation of options repositories
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy import create_engine, select, and_, or_, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from ...domain.repositories.ioptions_repository import (
    IOptionsRepository,
    IOptionsHistoricalDataRepository
)
from ...domain.entities.option import Option, OptionType
from ...domain.value_objects.strike_price import StrikePrice
from ...domain.value_objects.trading_symbol import TradingSymbol
from ..database.models.options_model import OptionsData, OptionsHistoricalData, OptionChainData
from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class OptionsRepository(IOptionsRepository):
    """SQL Server implementation of options repository"""
    
    def __init__(self):
        self.settings = get_settings()
        self.engine = create_engine(self.settings.database.connection_string)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    async def get_by_id(self, id: str) -> Optional[Option]:
        """Get option by ID"""
        try:
            with self.SessionLocal() as session:
                result = session.query(OptionsData).filter_by(Id=int(id)).first()
                if result:
                    return self._map_to_domain(result)
                return None
        except Exception as e:
            logger.error(f"Error getting option by ID {id}: {e}")
            return None
    
    async def get_by_symbol(self, symbol: str) -> Optional[Option]:
        """Get option by symbol"""
        try:
            with self.SessionLocal() as session:
                result = session.query(OptionsData).filter_by(Symbol=symbol).first()
                if result:
                    return self._map_to_domain(result)
                return None
        except Exception as e:
            logger.error(f"Error getting option by symbol {symbol}: {e}")
            return None
    
    async def get_option_chain(
        self,
        underlying: str,
        expiry_date: date
    ) -> List[Option]:
        """Get complete option chain for expiry"""
        try:
            with self.SessionLocal() as session:
                results = session.query(OptionsData).filter(
                    and_(
                        OptionsData.Underlying == underlying,
                        OptionsData.ExpiryDate == expiry_date
                    )
                ).order_by(OptionsData.StrikePrice).all()
                
                return [self._map_to_domain(r) for r in results]
        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            return []
    
    async def get_options_by_strike_range(
        self,
        underlying: str,
        expiry_date: date,
        min_strike: Decimal,
        max_strike: Decimal,
        option_type: Optional[OptionType] = None
    ) -> List[Option]:
        """Get options within strike range"""
        try:
            with self.SessionLocal() as session:
                query = session.query(OptionsData).filter(
                    and_(
                        OptionsData.Underlying == underlying,
                        OptionsData.ExpiryDate == expiry_date,
                        OptionsData.StrikePrice >= float(min_strike),
                        OptionsData.StrikePrice <= float(max_strike)
                    )
                )
                
                if option_type:
                    query = query.filter(OptionsData.OptionType == option_type.value)
                
                results = query.order_by(OptionsData.StrikePrice).all()
                
                return [self._map_to_domain(r) for r in results]
        except Exception as e:
            logger.error(f"Error getting options by strike range: {e}")
            return []
    
    async def get_near_expiry_options(
        self,
        underlying: str,
        days_to_expiry: int
    ) -> List[Option]:
        """Get options nearing expiry"""
        try:
            with self.SessionLocal() as session:
                expiry_cutoff = date.today() + timedelta(days=days_to_expiry)
                
                results = session.query(OptionsData).filter(
                    and_(
                        OptionsData.Underlying == underlying,
                        OptionsData.ExpiryDate <= expiry_cutoff,
                        OptionsData.ExpiryDate >= date.today()
                    )
                ).all()
                
                return [self._map_to_domain(r) for r in results]
        except Exception as e:
            logger.error(f"Error getting near expiry options: {e}")
            return []
    
    async def save(self, entity: Option) -> Option:
        """Save option"""
        try:
            with self.SessionLocal() as session:
                # Check if already exists
                existing = session.query(OptionsData).filter_by(
                    Symbol=entity.symbol
                ).first()
                
                if existing:
                    # Update existing
                    existing.LastPrice = float(entity.last_price)
                    existing.Volume = entity.volume
                    existing.OpenInterest = entity.open_interest
                    existing.BidPrice = float(entity.bid_price)
                    existing.AskPrice = float(entity.ask_price)
                    existing.ImpliedVolatility = float(entity.implied_volatility) if entity.implied_volatility else None
                    existing.Delta = float(entity.delta) if entity.delta else None
                    existing.Gamma = float(entity.gamma) if entity.gamma else None
                    existing.Theta = float(entity.theta) if entity.theta else None
                    existing.Vega = float(entity.vega) if entity.vega else None
                    existing.Rho = float(entity.rho) if entity.rho else None
                    existing.UpdatedAt = datetime.utcnow()
                    
                    session.commit()
                    return self._map_to_domain(existing)
                else:
                    # Create new
                    model = OptionsData(
                        Symbol=entity.symbol,
                        Underlying=entity.underlying,
                        StrikePrice=float(entity.strike_price.price),
                        ExpiryDate=entity.expiry_date,
                        OptionType=entity.option_type.value,
                        LastPrice=float(entity.last_price),
                        Volume=entity.volume,
                        OpenInterest=entity.open_interest,
                        BidPrice=float(entity.bid_price),
                        AskPrice=float(entity.ask_price),
                        ImpliedVolatility=float(entity.implied_volatility) if entity.implied_volatility else None,
                        Delta=float(entity.delta) if entity.delta else None,
                        Gamma=float(entity.gamma) if entity.gamma else None,
                        Theta=float(entity.theta) if entity.theta else None,
                        Vega=float(entity.vega) if entity.vega else None,
                        Rho=float(entity.rho) if entity.rho else None,
                        CreatedAt=datetime.utcnow()
                    )
                    
                    session.add(model)
                    session.commit()
                    session.refresh(model)
                    
                    entity.id = str(model.Id)
                    return entity
                    
        except Exception as e:
            logger.error(f"Error saving option: {e}")
            raise
    
    async def delete(self, id: str) -> bool:
        """Delete option by ID"""
        try:
            with self.SessionLocal() as session:
                result = session.query(OptionsData).filter_by(Id=int(id)).first()
                if result:
                    session.delete(result)
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting option {id}: {e}")
            return False
    
    async def update_greeks(
        self,
        option_id: str,
        greeks: Dict[str, Decimal]
    ) -> bool:
        """Update option Greeks"""
        try:
            with self.SessionLocal() as session:
                option = session.query(OptionsData).filter_by(Id=int(option_id)).first()
                if option:
                    option.Delta = float(greeks.get('delta', 0))
                    option.Gamma = float(greeks.get('gamma', 0))
                    option.Theta = float(greeks.get('theta', 0))
                    option.Vega = float(greeks.get('vega', 0))
                    option.Rho = float(greeks.get('rho', 0))
                    option.UpdatedAt = datetime.utcnow()
                    
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating Greeks for option {option_id}: {e}")
            return False
    
    def _map_to_domain(self, model: OptionsData) -> Option:
        """Map database model to domain entity"""
        option = Option(
            symbol=model.Symbol,
            underlying=model.Underlying,
            strike_price=StrikePrice(Decimal(str(model.StrikePrice)), model.Underlying),
            expiry_date=model.ExpiryDate,
            option_type=OptionType(model.OptionType),
            last_price=Decimal(str(model.LastPrice)),
            volume=model.Volume,
            open_interest=model.OpenInterest,
            bid_price=Decimal(str(model.BidPrice)),
            ask_price=Decimal(str(model.AskPrice)),
            implied_volatility=Decimal(str(model.ImpliedVolatility)) if model.ImpliedVolatility else None
        )
        
        # Set Greeks if available
        if model.Delta is not None:
            option.delta = Decimal(str(model.Delta))
        if model.Gamma is not None:
            option.gamma = Decimal(str(model.Gamma))
        if model.Theta is not None:
            option.theta = Decimal(str(model.Theta))
        if model.Vega is not None:
            option.vega = Decimal(str(model.Vega))
        if model.Rho is not None:
            option.rho = Decimal(str(model.Rho))
        
        # Set the ID
        option.id = str(model.Id)
        
        return option


class OptionsHistoricalDataRepository(IOptionsHistoricalDataRepository):
    """SQL Server implementation of options historical data repository"""
    
    def __init__(self):
        self.settings = get_settings()
        self.engine = create_engine(self.settings.database.connection_string)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    async def get_historical_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "1hour"
    ) -> List[Dict[str, Any]]:
        """Get historical option data"""
        try:
            with self.SessionLocal() as session:
                results = session.query(OptionsHistoricalData).filter(
                    and_(
                        OptionsHistoricalData.Symbol == symbol,
                        OptionsHistoricalData.Timestamp >= from_date,
                        OptionsHistoricalData.Timestamp <= to_date,
                        OptionsHistoricalData.Interval == interval
                    )
                ).order_by(OptionsHistoricalData.Timestamp).all()
                
                return [self._model_to_dict(r) for r in results]
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return []
    
    async def save_historical_data(
        self,
        data: List[Dict[str, Any]]
    ) -> int:
        """Save historical option data"""
        try:
            with self.SessionLocal() as session:
                saved_count = 0
                
                for record in data:
                    # Check if already exists
                    existing = session.query(OptionsHistoricalData).filter(
                        and_(
                            OptionsHistoricalData.Symbol == record['symbol'],
                            OptionsHistoricalData.Timestamp == record['timestamp'],
                            OptionsHistoricalData.Interval == record.get('interval', '1hour')
                        )
                    ).first()
                    
                    if not existing:
                        model = OptionsHistoricalData(
                            Symbol=record['symbol'],
                            Underlying=record['underlying'],
                            StrikePrice=record['strike_price'],
                            ExpiryDate=record['expiry_date'],
                            OptionType=record['option_type'],
                            Timestamp=record['timestamp'],
                            Open=record['open'],
                            High=record['high'],
                            Low=record['low'],
                            Close=record['close'],
                            Volume=record['volume'],
                            OpenInterest=record.get('open_interest'),
                            Interval=record.get('interval', '1hour'),
                            CreatedAt=datetime.utcnow()
                        )
                        session.add(model)
                        saved_count += 1
                
                session.commit()
                return saved_count
                
        except Exception as e:
            logger.error(f"Error saving historical data: {e}")
            raise
    
    async def get_data_statistics(
        self,
        underlying: str,
        from_date: date,
        to_date: date
    ) -> Dict[str, Any]:
        """Get statistics for options data"""
        try:
            with self.SessionLocal() as session:
                stats = session.query(
                    func.count(OptionsHistoricalData.Id).label('total_records'),
                    func.min(OptionsHistoricalData.Timestamp).label('min_date'),
                    func.max(OptionsHistoricalData.Timestamp).label('max_date'),
                    func.count(func.distinct(OptionsHistoricalData.Symbol)).label('unique_options')
                ).filter(
                    and_(
                        OptionsHistoricalData.Underlying == underlying,
                        OptionsHistoricalData.Timestamp >= datetime.combine(from_date, datetime.min.time()),
                        OptionsHistoricalData.Timestamp <= datetime.combine(to_date, datetime.max.time())
                    )
                ).first()
                
                if stats:
                    return {
                        "total_records": stats.total_records or 0,
                        "min_date": stats.min_date,
                        "max_date": stats.max_date,
                        "unique_options": stats.unique_options or 0
                    }
                
                return {
                    "total_records": 0,
                    "min_date": None,
                    "max_date": None,
                    "unique_options": 0
                }
                
        except Exception as e:
            logger.error(f"Error getting data statistics: {e}")
            return {}
    
    async def get_unique_dates(
        self,
        underlying: str,
        from_date: date,
        to_date: date
    ) -> List[date]:
        """Get unique dates with data"""
        try:
            with self.SessionLocal() as session:
                results = session.query(
                    func.date(OptionsHistoricalData.Timestamp).label('date')
                ).filter(
                    and_(
                        OptionsHistoricalData.Underlying == underlying,
                        OptionsHistoricalData.Timestamp >= datetime.combine(from_date, datetime.min.time()),
                        OptionsHistoricalData.Timestamp <= datetime.combine(to_date, datetime.max.time())
                    )
                ).distinct().all()
                
                return [r.date for r in results]
                
        except Exception as e:
            logger.error(f"Error getting unique dates: {e}")
            return []
    
    async def delete_historical_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime
    ) -> int:
        """Delete historical data in date range"""
        try:
            with self.SessionLocal() as session:
                result = session.query(OptionsHistoricalData).filter(
                    and_(
                        OptionsHistoricalData.Symbol == symbol,
                        OptionsHistoricalData.Timestamp >= from_date,
                        OptionsHistoricalData.Timestamp <= to_date
                    )
                ).delete()
                
                session.commit()
                return result
                
        except Exception as e:
            logger.error(f"Error deleting historical data: {e}")
            return 0
    
    def _model_to_dict(self, model: OptionsHistoricalData) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            "id": model.Id,
            "symbol": model.Symbol,
            "underlying": model.Underlying,
            "strike_price": model.StrikePrice,
            "expiry_date": model.ExpiryDate,
            "option_type": model.OptionType,
            "timestamp": model.Timestamp,
            "open": model.Open,
            "high": model.High,
            "low": model.Low,
            "close": model.Close,
            "volume": model.Volume,
            "open_interest": model.OpenInterest,
            "interval": model.Interval
        }
    
    async def get_option_prices_batch(
        self,
        timestamp: datetime,
        options: List[Dict[str, Any]],
        expiry_date: date
    ) -> Dict[str, float]:
        """
        Batch fetch option prices for multiple strikes/types
        Eliminates N+1 query problem
        
        Args:
            timestamp: Time to get prices for
            options: List of dicts with 'strike' and 'option_type' keys
            expiry_date: Expiry date of options
            
        Returns:
            Dict mapping "strike_type" to price (e.g., "25000_CE": 150.5)
        """
        try:
            with self.SessionLocal() as session:
                # Build OR conditions for all requested options
                conditions = []
                for opt in options:
                    conditions.append(
                        and_(
                            OptionsHistoricalData.StrikePrice == opt["strike"],
                            OptionsHistoricalData.OptionType == opt["option_type"]
                        )
                    )
                
                # Single query for all options
                results = session.query(
                    OptionsHistoricalData.StrikePrice,
                    OptionsHistoricalData.OptionType,
                    OptionsHistoricalData.Close,
                    OptionsHistoricalData.BidPrice,
                    OptionsHistoricalData.AskPrice
                ).filter(
                    and_(
                        OptionsHistoricalData.Timestamp == timestamp,
                        OptionsHistoricalData.ExpiryDate == expiry_date,
                        or_(*conditions)
                    )
                ).all()
                
                # Build result dictionary
                price_map = {}
                for result in results:
                    key = f"{int(result.StrikePrice)}_{result.OptionType}"
                    
                    # Use mid price if bid/ask available, otherwise use close
                    if result.BidPrice and result.AskPrice:
                        price = (result.BidPrice + result.AskPrice) / 2
                    else:
                        price = result.Close
                        
                    price_map[key] = float(price)
                
                # Log any missing prices
                for opt in options:
                    key = f"{opt['strike']}_{opt['option_type']}"
                    if key not in price_map:
                        logger.warning(f"No price found for {key} at {timestamp}")
                
                return price_map
                
        except Exception as e:
            logger.error(f"Error in batch option price fetch: {e}")
            return {}
    
    async def get_option_chain_batch(
        self,
        timestamp: datetime,
        strikes: List[int],
        expiry_date: date
    ) -> Dict[int, Dict[str, float]]:
        """
        Get entire option chain for multiple strikes in one query
        
        Returns:
            Dict mapping strike to {'CE': price, 'PE': price}
        """
        try:
            with self.SessionLocal() as session:
                # Get all CE and PE options for given strikes
                results = session.query(
                    OptionsHistoricalData.StrikePrice,
                    OptionsHistoricalData.OptionType,
                    OptionsHistoricalData.Close,
                    OptionsHistoricalData.Volume,
                    OptionsHistoricalData.OpenInterest
                ).filter(
                    and_(
                        OptionsHistoricalData.Timestamp == timestamp,
                        OptionsHistoricalData.ExpiryDate == expiry_date,
                        OptionsHistoricalData.StrikePrice.in_(strikes)
                    )
                ).all()
                
                # Build result structure
                chain = {strike: {} for strike in strikes}
                
                for result in results:
                    strike = int(result.StrikePrice)
                    option_type = result.OptionType
                    
                    if strike in chain:
                        chain[strike][option_type] = {
                            'price': float(result.Close),
                            'volume': result.Volume,
                            'oi': result.OpenInterest
                        }
                
                return chain
                
        except Exception as e:
            logger.error(f"Error in batch option chain fetch: {e}")
            return {}
    
    async def get_historical_data_batch(
        self,
        symbols: List[str],
        from_date: datetime,
        to_date: datetime,
        interval: str = "5minute"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get historical data for multiple symbols in one query
        
        Returns:
            Dict mapping symbol to list of price records
        """
        try:
            with self.SessionLocal() as session:
                results = session.query(OptionsHistoricalData).filter(
                    and_(
                        OptionsHistoricalData.Symbol.in_(symbols),
                        OptionsHistoricalData.Timestamp >= from_date,
                        OptionsHistoricalData.Timestamp <= to_date,
                        OptionsHistoricalData.Interval == interval
                    )
                ).order_by(
                    OptionsHistoricalData.Symbol,
                    OptionsHistoricalData.Timestamp
                ).all()
                
                # Group results by symbol
                data_by_symbol = {symbol: [] for symbol in symbols}
                
                for result in results:
                    data_by_symbol[result.Symbol].append(self._model_to_dict(result))
                
                return data_by_symbol
                
        except Exception as e:
            logger.error(f"Error in batch historical data fetch: {e}")
            return {}