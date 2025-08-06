"""
Market Data Database Models
SQLAlchemy models for market data tables
"""
from sqlalchemy import Column, Integer, String, Float, BigInteger, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class NiftyIndexData(Base):
    """NIFTY index data model"""
    __tablename__ = 'NiftyIndexData'
    
    Id = Column(Integer, primary_key=True, autoincrement=True)
    Symbol = Column(String(50), nullable=False)
    Timestamp = Column(DateTime, nullable=False)
    Open = Column(Float, nullable=False)
    High = Column(Float, nullable=False)
    Low = Column(Float, nullable=False)
    Close = Column(Float, nullable=False)
    Volume = Column(BigInteger, nullable=False)
    OpenInterest = Column(Integer, nullable=True)
    Interval = Column(String(10), nullable=False)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    UpdatedAt = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('IX_NiftyIndexData_Symbol_Timestamp_Interval', 'Symbol', 'Timestamp', 'Interval'),
        Index('IX_NiftyIndexData_Timestamp', 'Timestamp'),
    )