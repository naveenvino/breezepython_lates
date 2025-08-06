"""
Backtest Models
SQLAlchemy models for backtesting data
"""
from sqlalchemy import Column, String, DateTime, DECIMAL, Integer, ForeignKey, Boolean, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from ..base import Base


class BacktestStatus(enum.Enum):
    """Backtest run status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TradeOutcome(enum.Enum):
    """Trade outcome"""
    OPEN = "OPEN"
    WIN = "WIN"
    LOSS = "LOSS"
    EXPIRED = "EXPIRED"
    STOPPED = "STOPPED"


class BacktestRun(Base):
    """
    Model for tracking backtest executions
    """
    __tablename__ = 'BacktestRuns'
    
    # Primary key
    id = Column('Id', String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Backtest parameters
    name = Column('Name', String(200), nullable=False)
    from_date = Column('FromDate', DateTime, nullable=False)
    to_date = Column('ToDate', DateTime, nullable=False)
    initial_capital = Column('InitialCapital', DECIMAL(18, 2), nullable=False)
    lot_size = Column('LotSize', Integer, nullable=False, default=75)
    lots_to_trade = Column('LotsToTrade', Integer, nullable=False, default=10)
    
    # Configuration
    signals_to_test = Column('SignalsToTest', String(100), nullable=False)  # JSON array
    use_hedging = Column('UseHedging', Boolean, nullable=False, default=True)
    hedge_offset = Column('HedgeOffset', Integer, nullable=False, default=200)
    commission_per_lot = Column('CommissionPerLot', DECIMAL(10, 2), nullable=False, default=40)
    slippage_percent = Column('SlippagePercent', DECIMAL(5, 4), nullable=False, default=0.001)
    
    # Status tracking
    status = Column('Status', SQLEnum(BacktestStatus), nullable=False, default=BacktestStatus.PENDING)
    started_at = Column('StartedAt', DateTime, nullable=True)
    completed_at = Column('CompletedAt', DateTime, nullable=True)
    error_message = Column('ErrorMessage', Text, nullable=True)
    
    # Results summary
    total_trades = Column('TotalTrades', Integer, nullable=False, default=0)
    winning_trades = Column('WinningTrades', Integer, nullable=False, default=0)
    losing_trades = Column('LosingTrades', Integer, nullable=False, default=0)
    win_rate = Column('WinRate', DECIMAL(5, 2), nullable=True)
    
    # Financial results
    final_capital = Column('FinalCapital', DECIMAL(18, 2), nullable=True)
    total_pnl = Column('TotalPnL', DECIMAL(18, 2), nullable=True)
    total_return_percent = Column('TotalReturnPercent', DECIMAL(10, 2), nullable=True)
    max_drawdown = Column('MaxDrawdown', DECIMAL(18, 2), nullable=True)
    max_drawdown_percent = Column('MaxDrawdownPercent', DECIMAL(10, 2), nullable=True)
    
    # Metadata
    created_at = Column('CreatedAt', DateTime, nullable=False, server_default=func.now())
    created_by = Column('CreatedBy', String(100), nullable=False, default='System')
    
    # Relationships
    trades = relationship("BacktestTrade", back_populates="backtest_run", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<BacktestRun({self.name} [{self.from_date} to {self.to_date}] - {self.status.value})>"


class BacktestTrade(Base):
    """
    Model for individual trades in a backtest
    """
    __tablename__ = 'BacktestTrades'
    
    # Primary key
    id = Column('Id', String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign key
    backtest_run_id = Column('BacktestRunId', String(50), ForeignKey('BacktestRuns.Id'), nullable=False)
    
    # Trade identification
    week_start_date = Column('WeekStartDate', DateTime, nullable=False)
    signal_type = Column('SignalType', String(10), nullable=False)  # S1-S8
    direction = Column('Direction', String(10), nullable=False)  # BULLISH/BEARISH
    
    # Entry details
    entry_time = Column('EntryTime', DateTime, nullable=False)
    index_price_at_entry = Column('IndexPriceAtEntry', DECIMAL(18, 2), nullable=False)
    signal_trigger_price = Column('SignalTriggerPrice', DECIMAL(18, 2), nullable=False)
    stop_loss_price = Column('StopLossPrice', DECIMAL(18, 2), nullable=False)
    
    # Exit details
    exit_time = Column('ExitTime', DateTime, nullable=True)
    index_price_at_exit = Column('IndexPriceAtExit', DECIMAL(18, 2), nullable=True)
    outcome = Column('Outcome', SQLEnum(TradeOutcome), nullable=False, default=TradeOutcome.OPEN)
    exit_reason = Column('ExitReason', String(100), nullable=True)
    
    # P&L
    total_pnl = Column('TotalPnL', DECIMAL(18, 2), nullable=True)
    
    # Zone information at trade entry
    resistance_zone_top = Column('ResistanceZoneTop', DECIMAL(18, 2), nullable=True)
    resistance_zone_bottom = Column('ResistanceZoneBottom', DECIMAL(18, 2), nullable=True)
    support_zone_top = Column('SupportZoneTop', DECIMAL(18, 2), nullable=True)
    support_zone_bottom = Column('SupportZoneBottom', DECIMAL(18, 2), nullable=True)
    
    # Market bias at trade entry
    bias_direction = Column('BiasDirection', String(20), nullable=True)
    bias_strength = Column('BiasStrength', DECIMAL(5, 2), nullable=True)
    
    # Weekly extremes before signal
    weekly_max_high = Column('WeeklyMaxHigh', DECIMAL(18, 2), nullable=True)
    weekly_min_low = Column('WeeklyMinLow', DECIMAL(18, 2), nullable=True)
    
    # First bar details (for signal context)
    first_bar_open = Column('FirstBarOpen', DECIMAL(18, 2), nullable=True)
    first_bar_close = Column('FirstBarClose', DECIMAL(18, 2), nullable=True)
    first_bar_high = Column('FirstBarHigh', DECIMAL(18, 2), nullable=True)
    first_bar_low = Column('FirstBarLow', DECIMAL(18, 2), nullable=True)
    
    # Distance metrics
    distance_to_resistance = Column('DistanceToResistance', DECIMAL(10, 6), nullable=True)
    distance_to_support = Column('DistanceToSupport', DECIMAL(10, 6), nullable=True)
    
    # Metadata
    created_at = Column('CreatedAt', DateTime, nullable=False, server_default=func.now())
    
    # Relationships
    backtest_run = relationship("BacktestRun", back_populates="trades")
    positions = relationship("BacktestPosition", back_populates="trade", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<BacktestTrade({self.signal_type} @ {self.entry_time} - {self.outcome.value})>"


class BacktestPosition(Base):
    """
    Model for option positions (main + hedge) in a trade
    """
    __tablename__ = 'BacktestPositions'
    
    # Primary key
    id = Column('Id', String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign key
    trade_id = Column('TradeId', String(50), ForeignKey('BacktestTrades.Id'), nullable=False)
    
    # Position details
    position_type = Column('PositionType', String(20), nullable=False)  # MAIN/HEDGE
    option_type = Column('OptionType', String(2), nullable=False)  # CE/PE
    strike_price = Column('StrikePrice', Integer, nullable=False)
    expiry_date = Column('ExpiryDate', DateTime, nullable=False)
    
    # Entry
    entry_time = Column('EntryTime', DateTime, nullable=False)
    entry_price = Column('EntryPrice', DECIMAL(18, 2), nullable=False)
    quantity = Column('Quantity', Integer, nullable=False)  # Negative for sell
    
    # Exit
    exit_time = Column('ExitTime', DateTime, nullable=True)
    exit_price = Column('ExitPrice', DECIMAL(18, 2), nullable=True)
    
    # P&L
    gross_pnl = Column('GrossPnL', DECIMAL(18, 2), nullable=True)
    commission = Column('Commission', DECIMAL(10, 2), nullable=True)
    net_pnl = Column('NetPnL', DECIMAL(18, 2), nullable=True)
    
    # Greeks at entry (optional)
    delta_at_entry = Column('DeltaAtEntry', DECIMAL(8, 4), nullable=True)
    iv_at_entry = Column('IVAtEntry', DECIMAL(8, 4), nullable=True)
    
    # Metadata
    created_at = Column('CreatedAt', DateTime, nullable=False, server_default=func.now())
    
    # Relationships
    trade = relationship("BacktestTrade", back_populates="positions")
    
    def __repr__(self):
        return f"<BacktestPosition({self.position_type} {self.option_type} @ {self.strike_price})>"


class BacktestDailyResult(Base):
    """
    Model for daily P&L tracking
    """
    __tablename__ = 'BacktestDailyResults'
    
    # Primary key
    id = Column('Id', Integer, primary_key=True, autoincrement=True)
    
    # Foreign key
    backtest_run_id = Column('BacktestRunId', String(50), ForeignKey('BacktestRuns.Id'), nullable=False)
    
    # Daily data
    date = Column('Date', DateTime, nullable=False)
    starting_capital = Column('StartingCapital', DECIMAL(18, 2), nullable=False)
    ending_capital = Column('EndingCapital', DECIMAL(18, 2), nullable=False)
    daily_pnl = Column('DailyPnL', DECIMAL(18, 2), nullable=False)
    daily_return_percent = Column('DailyReturnPercent', DECIMAL(10, 4), nullable=False)
    
    # Trade stats
    trades_opened = Column('TradesOpened', Integer, nullable=False, default=0)
    trades_closed = Column('TradesClosed', Integer, nullable=False, default=0)
    open_positions = Column('OpenPositions', Integer, nullable=False, default=0)
    
    # Metadata
    created_at = Column('CreatedAt', DateTime, nullable=False, server_default=func.now())
    
    def __repr__(self):
        return f"<BacktestDailyResult({self.date}: PnL={self.daily_pnl})>"