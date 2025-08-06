"""
Options Database Models
SQLAlchemy models for options tables
"""
from sqlalchemy import Column, Integer, String, Float, BigInteger, DateTime, Date, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class OptionsData(Base):
    """Options data model"""
    __tablename__ = 'OptionsData'
    
    Id = Column(Integer, primary_key=True, autoincrement=True)
    Symbol = Column(String(50), nullable=False, unique=True)
    Underlying = Column(String(50), nullable=False)
    StrikePrice = Column(Float, nullable=False)
    ExpiryDate = Column(Date, nullable=False)
    OptionType = Column(String(2), nullable=False)  # CE or PE
    LastPrice = Column(Float, nullable=False)
    Volume = Column(BigInteger, nullable=False)
    OpenInterest = Column(Integer, nullable=False)
    BidPrice = Column(Float, nullable=False)
    AskPrice = Column(Float, nullable=False)
    ImpliedVolatility = Column(Float, nullable=True)
    Delta = Column(Float, nullable=True)
    Gamma = Column(Float, nullable=True)
    Theta = Column(Float, nullable=True)
    Vega = Column(Float, nullable=True)
    Rho = Column(Float, nullable=True)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    UpdatedAt = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('IX_OptionsData_Underlying_ExpiryDate', 'Underlying', 'ExpiryDate'),
        Index('IX_OptionsData_Symbol', 'Symbol'),
    )


class OptionsHistoricalData(Base):
    """Options historical data model"""
    __tablename__ = 'OptionsHistoricalData'
    
    Id = Column(Integer, primary_key=True, autoincrement=True)
    Symbol = Column(String(50), nullable=False)
    Underlying = Column(String(50), nullable=False)
    StrikePrice = Column(Float, nullable=False)
    ExpiryDate = Column(Date, nullable=False)
    OptionType = Column(String(2), nullable=False)
    Timestamp = Column(DateTime, nullable=False)
    Open = Column(Float, nullable=False)
    High = Column(Float, nullable=False)
    Low = Column(Float, nullable=False)
    Close = Column(Float, nullable=False)
    Volume = Column(BigInteger, nullable=False)
    OpenInterest = Column(Integer, nullable=True)
    Interval = Column(String(10), nullable=False)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('IX_OptionsHistoricalData_Symbol_Timestamp', 'Symbol', 'Timestamp'),
        Index('IX_OptionsHistoricalData_Underlying_ExpiryDate', 'Underlying', 'ExpiryDate'),
        Index('IX_OptionsHistoricalData_Timestamp', 'Timestamp'),
    )


class OptionChainData(Base):
    """Option chain snapshot data"""
    __tablename__ = 'OptionChainData'
    
    Id = Column(Integer, primary_key=True, autoincrement=True)
    Underlying = Column(String(50), nullable=False)
    ExpiryDate = Column(Date, nullable=False)
    Timestamp = Column(DateTime, nullable=False)
    SpotPrice = Column(Float, nullable=False)
    ChainData = Column(String, nullable=False)  # JSON data
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('IX_OptionChainData_Underlying_ExpiryDate_Timestamp', 
              'Underlying', 'ExpiryDate', 'Timestamp'),
    )