"""
NIFTY Timeframe-specific Data Models
SQLAlchemy models for storing NIFTY data in separate tables by timeframe
"""
from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, BigInteger, Index
from sqlalchemy.sql import func
from datetime import datetime

from ..base import Base


class NiftyBaseModel:
    """Base model with common NIFTY fields - not a table itself"""
    
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
    
    # Update time
    last_update_time = Column('LastUpdateTime', DateTime, nullable=False)
    
    def __repr__(self):
        return f"<{self.__class__.__name__}({self.symbol} @ {self.timestamp}: O={self.open} H={self.high} L={self.low} C={self.close})>"
    
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
            'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None
        }


class NiftyIndexData5Minute(NiftyBaseModel, Base):
    """Model for NIFTY 5-minute data"""
    __tablename__ = 'NiftyIndexData5Minute'
    
    __table_args__ = (
        Index('IX_NiftyIndexData5Minute_Symbol_Timestamp', 'Symbol', 'Timestamp'),
    )


class NiftyIndexData15Minute(NiftyBaseModel, Base):
    """Model for NIFTY 15-minute data"""
    __tablename__ = 'NiftyIndexData15Minute'
    
    __table_args__ = (
        Index('IX_NiftyIndexData15Minute_Symbol_Timestamp', 'Symbol', 'Timestamp'),
    )


class NiftyIndexDataHourly(NiftyBaseModel, Base):
    """Model for NIFTY hourly data"""
    __tablename__ = 'NiftyIndexDataHourly'
    
    __table_args__ = (
        Index('IX_NiftyIndexDataHourly_Symbol_Timestamp', 'Symbol', 'Timestamp'),
    )


class NiftyIndexData4Hour(NiftyBaseModel, Base):
    """Model for NIFTY 4-hour data"""
    __tablename__ = 'NiftyIndexData4Hour'
    
    __table_args__ = (
        Index('IX_NiftyIndexData4Hour_Symbol_Timestamp', 'Symbol', 'Timestamp'),
    )


class NiftyIndexDataDaily(NiftyBaseModel, Base):
    """Model for NIFTY daily data"""
    __tablename__ = 'NiftyIndexDataDaily'
    
    __table_args__ = (
        Index('IX_NiftyIndexDataDaily_Symbol_Timestamp', 'Symbol', 'Timestamp'),
    )


class NiftyIndexDataWeekly(NiftyBaseModel, Base):
    """Model for NIFTY weekly data"""
    __tablename__ = 'NiftyIndexDataWeekly'
    
    __table_args__ = (
        Index('IX_NiftyIndexDataWeekly_Symbol_Timestamp', 'Symbol', 'Timestamp'),
    )


class NiftyIndexDataMonthly(NiftyBaseModel, Base):
    """Model for NIFTY monthly data"""
    __tablename__ = 'NiftyIndexDataMonthly'
    
    __table_args__ = (
        Index('IX_NiftyIndexDataMonthly_Symbol_Timestamp', 'Symbol', 'Timestamp'),
    )


# Helper function to get the appropriate model class based on timeframe
def get_nifty_model_for_timeframe(timeframe: str):
    """
    Get the appropriate NIFTY model class for a given timeframe
    
    Args:
        timeframe: One of '5minute', '15minute', 'hourly', '4hour', 'daily', 'weekly', 'monthly'
    
    Returns:
        The corresponding model class
    """
    timeframe_model_map = {
        '5minute': NiftyIndexData5Minute,
        '15minute': NiftyIndexData15Minute,
        'hourly': NiftyIndexDataHourly,
        '4hour': NiftyIndexData4Hour,
        'daily': NiftyIndexDataDaily,
        'weekly': NiftyIndexDataWeekly,
        'monthly': NiftyIndexDataMonthly,
        # Also support the input format from TradingView
        '5min': NiftyIndexData5Minute,
        '15min': NiftyIndexData15Minute,
        '1hour': NiftyIndexDataHourly,
        '4hour': NiftyIndexData4Hour,
        '1day': NiftyIndexDataDaily,
        '1week': NiftyIndexDataWeekly,
        '1month': NiftyIndexDataMonthly
    }
    
    model_class = timeframe_model_map.get(timeframe)
    if not model_class:
        raise ValueError(f"Unknown timeframe: {timeframe}")
    
    return model_class