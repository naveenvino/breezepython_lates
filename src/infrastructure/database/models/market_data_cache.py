"""
Market Data Cache Model for storing real-time and historical market data
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Boolean, Index, BigInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MarketDataCache(Base):
    """Model for caching market data from WebSocket and historical sources"""
    __tablename__ = 'MarketDataCache'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Instrument identification
    symbol = Column(String(50), nullable=False)  # Full symbol like NIFTY or NIFTY25AUG24800CE
    instrument_type = Column(String(20), nullable=False)  # SPOT, CE, PE
    underlying = Column(String(20))  # NIFTY for options
    strike = Column(Integer)  # Strike price for options
    expiry_date = Column(Date)  # Expiry date for options
    
    # Price data
    spot_price = Column(Float)  # Current NIFTY spot price
    last_price = Column(Float, nullable=False)  # Last traded price
    bid_price = Column(Float)  # Best bid
    ask_price = Column(Float)  # Best ask
    open_price = Column(Float)  # Day open
    high_price = Column(Float)  # Day high
    low_price = Column(Float)  # Day low
    close_price = Column(Float)  # Previous close
    
    # Volume and OI
    volume = Column(BigInteger)  # Volume traded
    open_interest = Column(Integer)  # Open interest for options
    oi_change = Column(Integer)  # OI change from previous day
    
    # Greeks for options
    iv = Column(Float)  # Implied volatility
    delta = Column(Float)  # Delta
    gamma = Column(Float)  # Gamma
    theta = Column(Float)  # Theta
    vega = Column(Float)  # Vega
    
    # Metadata
    timestamp = Column(DateTime, nullable=False)  # When data was captured
    source = Column(String(20), nullable=False)  # 'websocket', 'historical', 'api', 'manual'
    is_stale = Column(Boolean, default=False)  # Mark if data is outdated
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Indexes for performance
    __table_args__ = (
        Index('IX_MarketDataCache_Symbol_Timestamp', 'symbol', 'timestamp'),
        Index('IX_MarketDataCache_Strike_Expiry', 'strike', 'expiry_date', 'instrument_type'),
        Index('IX_MarketDataCache_UpdatedAt', 'updated_at'),
        Index('IX_MarketDataCache_Source_Timestamp', 'source', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<MarketDataCache({self.symbol}@{self.timestamp}: {self.last_price})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'instrument_type': self.instrument_type,
            'underlying': self.underlying,
            'strike': self.strike,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'spot_price': self.spot_price,
            'last_price': self.last_price,
            'bid_price': self.bid_price,
            'ask_price': self.ask_price,
            'open_price': self.open_price,
            'high_price': self.high_price,
            'low_price': self.low_price,
            'close_price': self.close_price,
            'volume': self.volume,
            'open_interest': self.open_interest,
            'oi_change': self.oi_change,
            'iv': self.iv,
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'source': self.source,
            'is_stale': self.is_stale,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_websocket_data(cls, data: Dict[str, Any], source: str = 'websocket'):
        """Create instance from WebSocket data"""
        return cls(
            symbol=data.get('symbol'),
            instrument_type=data.get('instrument_type', 'SPOT'),
            underlying=data.get('underlying'),
            strike=data.get('strike'),
            expiry_date=data.get('expiry_date'),
            spot_price=data.get('spot_price'),
            last_price=data.get('last_price', data.get('ltp')),
            bid_price=data.get('bid_price'),
            ask_price=data.get('ask_price'),
            open_price=data.get('open'),
            high_price=data.get('high'),
            low_price=data.get('low'),
            close_price=data.get('close'),
            volume=data.get('volume'),
            open_interest=data.get('open_interest', data.get('oi')),
            oi_change=data.get('oi_change'),
            iv=data.get('iv'),
            delta=data.get('delta'),
            gamma=data.get('gamma'),
            theta=data.get('theta'),
            vega=data.get('vega'),
            timestamp=datetime.now(),
            source=source
        )
    
    @classmethod
    def from_historical_data(cls, data: Dict[str, Any]):
        """Create instance from historical API data"""
        return cls(
            symbol=data.get('symbol'),
            instrument_type=data.get('instrument_type', 'SPOT'),
            underlying=data.get('underlying'),
            strike=data.get('strike'),
            expiry_date=data.get('expiry_date'),
            spot_price=data.get('spot_price'),
            last_price=data.get('close', data.get('last_price')),
            open_price=data.get('open'),
            high_price=data.get('high'),
            low_price=data.get('low'),
            close_price=data.get('close'),
            volume=data.get('volume'),
            open_interest=data.get('open_interest'),
            timestamp=data.get('timestamp', datetime.now()),
            source='historical'
        )