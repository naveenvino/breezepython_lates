"""
NIFTY Index Data Model
SQLAlchemy model for storing NIFTY historical data
"""
from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, BigInteger, Index
from sqlalchemy.sql import func
from datetime import datetime

from ..base import Base


class NiftyIndexData(Base):
    """
    Model for NIFTY index historical data
    Matches the SQL Server table structure
    """
    __tablename__ = 'NiftyIndexData'
    
    # Primary key
    id = Column('Id', Integer, primary_key=True, autoincrement=True)
    
    # Symbol info
    symbol = Column('Symbol', String(50), nullable=False)
    
    # OHLC data
    timestamp = Column('Timestamp', DateTime, nullable=False)
    open = Column('Open', DECIMAL(18, 2), nullable=False)
    high = Column('High', DECIMAL(18, 2), nullable=False)
    low = Column('Low', DECIMAL(18, 2), nullable=False)
    close = Column('Close', DECIMAL(18, 2), nullable=False)
    last_price = Column('LastPrice', DECIMAL(18, 2), nullable=False)
    
    # Volume data
    volume = Column('Volume', BigInteger, nullable=False)
    open_interest = Column('OpenInterest', BigInteger, nullable=False, default=0)
    
    # Additional data
    change_percent = Column('ChangePercent', DECIMAL(18, 2), nullable=False, default=0)
    last_update_time = Column('LastUpdateTime', DateTime, nullable=False)
    
    # Bid/Ask data
    bid_price = Column('BidPrice', DECIMAL(18, 2), nullable=False, default=0)
    ask_price = Column('AskPrice', DECIMAL(18, 2), nullable=False, default=0)
    bid_quantity = Column('BidQuantity', BigInteger, nullable=False, default=0)
    ask_quantity = Column('AskQuantity', BigInteger, nullable=False, default=0)
    
    # Metadata
    created_at = Column('CreatedAt', DateTime, nullable=False, server_default=func.now())
    interval = Column('Interval', String(20), nullable=False, default='60minute')
    
    # Indexes
    __table_args__ = (
        Index('IX_NiftyIndexData_Symbol_Timestamp', 'Symbol', 'Timestamp'),
    )
    
    def __repr__(self):
        return f"<NiftyIndexData({self.symbol} @ {self.timestamp}: O={self.open} H={self.high} L={self.low} C={self.close})>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'open': float(self.open),
            'high': float(self.high),
            'low': float(self.low),
            'close': float(self.close),
            'last_price': float(self.last_price),
            'volume': self.volume,
            'open_interest': self.open_interest,
            'change_percent': float(self.change_percent),
            'interval': self.interval
        }
    
    @classmethod
    def from_breeze_data(cls, breeze_data: dict, symbol: str = "NIFTY", extended_hours: bool = False):
        """Create instance from Breeze API response"""
        import pytz
        from ....utils.market_hours import is_within_market_hours
        
        datetime_str = breeze_data['datetime']
        IST = pytz.timezone('Asia/Kolkata')
        
        # Check if timestamp has timezone info
        if datetime_str.endswith('Z') or ('T' in datetime_str and '+' not in datetime_str):
            # UTC format with Z suffix (used for options)
            utc_dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            # Convert UTC to IST
            ist_dt = utc_dt.astimezone(IST)
            # Store as naive IST timestamp
            timestamp = ist_dt.replace(tzinfo=None)
        else:
            # Plain datetime format - already in IST (used for NIFTY index)
            # Parse as naive datetime and use as-is
            timestamp = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        
        # Filter out data outside market hours
        # For Breeze 5-minute data, we only want 9:20 to 15:20 timestamps (or 15:35 if extended)
        if not is_within_market_hours(timestamp, is_breeze_data=True, extended_hours=extended_hours):
            return None  # This record will be skipped
        
        return cls(
            symbol=symbol,
            timestamp=timestamp,
            open=float(breeze_data['open']),
            high=float(breeze_data['high']),
            low=float(breeze_data['low']),
            close=float(breeze_data['close']),
            last_price=float(breeze_data['close']),
            volume=int(breeze_data.get('volume', 0)) if breeze_data.get('volume') else 0,
            open_interest=int(breeze_data.get('open_interest', 0)) if breeze_data.get('open_interest') else 0,
            last_update_time=timestamp,
            interval="5minute"  # Store raw 5-minute data
        )