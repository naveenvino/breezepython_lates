"""
Trade Database Models
SQLAlchemy models for trade tables
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from ..base import Base


class TradeModel(Base):
    """Trade data model"""
    __tablename__ = 'Trades'
    
    Id = Column(Integer, primary_key=True, autoincrement=True)
    Symbol = Column(String(50), nullable=False)
    TradeType = Column(String(10), nullable=False)  # BUY or SELL
    EntryPrice = Column(Float, nullable=False)
    ExitPrice = Column(Float, nullable=True)
    Quantity = Column(Integer, nullable=False)
    Status = Column(String(20), nullable=False)  # OPEN, CLOSED, CANCELLED
    SignalId = Column(String(10), nullable=True)
    EntryTime = Column(DateTime, nullable=False)
    ExitTime = Column(DateTime, nullable=True)
    StopLoss = Column(Float, nullable=True)
    Target = Column(Float, nullable=True)
    PnL = Column(Float, nullable=True)
    ExitReason = Column(String(100), nullable=True)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    UpdatedAt = Column(DateTime, nullable=True)
    
    # Relationship
    logs = relationship("TradeLogModel", back_populates="trade", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('IX_Trades_Symbol_Status', 'Symbol', 'Status'),
        Index('IX_Trades_EntryTime', 'EntryTime'),
        Index('IX_Trades_Status', 'Status'),
    )


class TradeLogModel(Base):
    """Trade log/audit model"""
    __tablename__ = 'TradeLogs'
    
    Id = Column(Integer, primary_key=True, autoincrement=True)
    TradeId = Column(Integer, ForeignKey('Trades.Id'), nullable=False)
    Action = Column(String(50), nullable=False)
    Message = Column(String(500), nullable=True)
    Details = Column(Text, nullable=True)
    Timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationship
    trade = relationship("TradeModel", back_populates="logs")
    
    __table_args__ = (
        Index('IX_TradeLogs_TradeId', 'TradeId'),
        Index('IX_TradeLogs_Timestamp', 'Timestamp'),
    )