from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class StrategyStatus(enum.Enum):
    CREATED = "created"
    DEPLOYED = "deployed"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"

class StrategyType(enum.Enum):
    INTRADAY = "intraday"
    POSITIONAL = "positional"

class TrailingType(enum.Enum):
    NONE = "none"
    POINTS = "points"
    PERCENTAGE = "percentage"
    DYNAMIC = "dynamic"

class TradingStrategy(Base):
    __tablename__ = 'trading_strategies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    instrument = Column(String(20), nullable=False)
    strategy_type = Column(SQLEnum(StrategyType), nullable=False)
    signals = Column(JSON, nullable=False)
    main_lots = Column(Integer, nullable=False)
    hedge_lots = Column(Integer, nullable=False)
    hedge_strike_distance = Column(Integer, nullable=False)
    
    stop_loss_enabled = Column(Boolean, default=False)
    stop_loss_value = Column(Float, nullable=True)
    
    target_profit_enabled = Column(Boolean, default=False)
    target_profit_value = Column(Float, nullable=True)
    
    trailing_enabled = Column(Boolean, default=False)
    trailing_type = Column(SQLEnum(TrailingType), default=TrailingType.NONE)
    trailing_value = Column(Float, nullable=True)
    
    status = Column(SQLEnum(StrategyStatus), default=StrategyStatus.CREATED)
    created_at = Column(DateTime, default=datetime.utcnow)
    deployed_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    
    current_pnl = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    
    strategy_metadata = Column(JSON, nullable=True)

class StrategyExecution(Base):
    __tablename__ = 'strategy_executions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, nullable=False)
    signal = Column(String(10), nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    
    main_strike = Column(Integer, nullable=False)
    main_entry_price = Column(Float, nullable=False)
    main_exit_price = Column(Float, nullable=True)
    main_quantity = Column(Integer, nullable=False)
    
    hedge_strike = Column(Integer, nullable=True)
    hedge_entry_price = Column(Float, nullable=True)
    hedge_exit_price = Column(Float, nullable=True)
    hedge_quantity = Column(Integer, nullable=True)
    
    pnl = Column(Float, default=0.0)
    status = Column(String(20), default="open")
    exit_reason = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)