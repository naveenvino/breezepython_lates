"""
PostgreSQL Database Models with TimescaleDB support
Compatible with both SQL Server (legacy) and PostgreSQL (new)
"""

from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, BigInteger, Boolean, JSON, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from database_migration.postgresql_config import Base

# =====================================================
# TIME-SERIES MODELS (Hypertables)
# =====================================================

class NIFTYData5Min(Base):
    """5-minute NIFTY data - Hypertable"""
    __tablename__ = 'niftydata_5min'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(DECIMAL(18, 2), nullable=False)
    high = Column(DECIMAL(18, 2), nullable=False)
    low = Column(DECIMAL(18, 2), nullable=False)
    close = Column(DECIMAL(18, 2), nullable=False)
    lastprice = Column(DECIMAL(18, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    lastupdatetime = Column(DateTime, nullable=False, default=func.now())
    
    __table_args__ = (
        Index('idx_nifty_5min_symbol_time', 'symbol', 'timestamp'),
    )

class NIFTYDataHourly(Base):
    """Hourly NIFTY data - Hypertable"""
    __tablename__ = 'niftydata_hourly'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(DECIMAL(18, 2), nullable=False)
    high = Column(DECIMAL(18, 2), nullable=False)
    low = Column(DECIMAL(18, 2), nullable=False)
    close = Column(DECIMAL(18, 2), nullable=False)
    lastprice = Column(DECIMAL(18, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    lastupdatetime = Column(DateTime, nullable=False, default=func.now())
    
    __table_args__ = (
        Index('idx_nifty_hourly_symbol_time', 'symbol', 'timestamp'),
    )

class OptionsData(Base):
    """Options data with Greeks - Hypertable"""
    __tablename__ = 'optionsdata'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(100), nullable=False)
    strikeprice = Column(DECIMAL(18, 2), nullable=False)
    optiontype = Column(String(10), nullable=False)
    expirydate = Column(DateTime, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    lastprice = Column(DECIMAL(18, 2), nullable=False)
    volume = Column(BigInteger)
    openinterest = Column(BigInteger)
    iv = Column(DECIMAL(10, 4))
    delta = Column(DECIMAL(10, 6))
    gamma = Column(DECIMAL(10, 6))
    theta = Column(DECIMAL(10, 6))
    vega = Column(DECIMAL(10, 6))
    rho = Column(DECIMAL(10, 6))
    bidprice = Column(DECIMAL(18, 2))
    askprice = Column(DECIMAL(18, 2))
    lastupdatetime = Column(DateTime, nullable=False, default=func.now())
    
    __table_args__ = (
        Index('idx_options_strike_type_time', 'strikeprice', 'optiontype', 'timestamp'),
        Index('idx_options_symbol_time', 'symbol', 'timestamp'),
        Index('idx_options_expiry', 'expirydate', 'timestamp'),
    )

# =====================================================
# BACKTESTING MODELS
# =====================================================

class BacktestRun(Base):
    """Backtest run metadata"""
    __tablename__ = 'backtestruns'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rundate = Column(DateTime, nullable=False, default=func.now())
    fromdate = Column(DateTime, nullable=False)
    todate = Column(DateTime, nullable=False)
    signalstested = Column(String(200))
    initialcapital = Column(DECIMAL(18, 2), default=500000)
    totaltrades = Column(Integer, default=0)
    profitabletrades = Column(Integer, default=0)
    losstrades = Column(Integer, default=0)
    totalpnl = Column(DECIMAL(18, 2), default=0)
    maxdrawdown = Column(DECIMAL(18, 2))
    sharperatio = Column(DECIMAL(10, 4))
    winrate = Column(DECIMAL(5, 2))
    parameters = Column(JSON)
    executiontime = Column(DECIMAL(10, 3))
    status = Column(String(50), default='COMPLETED')
    
    # Relationships
    trades = relationship("BacktestTrade", back_populates="run", cascade="all, delete-orphan")

class BacktestTrade(Base):
    """Individual backtest trades"""
    __tablename__ = 'backtesttrades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    backtestrunid = Column(Integer, ForeignKey('backtestruns.id', ondelete='CASCADE'))
    signaltype = Column(String(10), nullable=False)
    signaltime = Column(DateTime, nullable=False)
    entrytime = Column(DateTime, nullable=False)
    exittime = Column(DateTime)
    weekstartdate = Column(DateTime, nullable=False)
    mainstrike = Column(DECIMAL(18, 2), nullable=False)
    hedgestrike = Column(DECIMAL(18, 2))
    optiontype = Column(String(10), nullable=False)
    entryprice = Column(DECIMAL(18, 2), nullable=False)
    exitprice = Column(DECIMAL(18, 2))
    quantity = Column(Integer, nullable=False)
    pnl = Column(DECIMAL(18, 2))
    exitreason = Column(String(100))
    maxprofit = Column(DECIMAL(18, 2))
    maxloss = Column(DECIMAL(18, 2))
    commission = Column(DECIMAL(18, 2), default=40)
    slippagecost = Column(DECIMAL(18, 2), default=0)
    netpnl = Column(DECIMAL(18, 2))
    
    # Relationships
    run = relationship("BacktestRun", back_populates="trades")
    positions = relationship("BacktestPosition", back_populates="trade", cascade="all, delete-orphan")

class BacktestPosition(Base):
    """Position details for backtest trades"""
    __tablename__ = 'backtestpositions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tradeid = Column(Integer, ForeignKey('backtesttrades.id', ondelete='CASCADE'))
    positiontype = Column(String(20), nullable=False)
    symbol = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    entryprice = Column(DECIMAL(18, 2), nullable=False)
    exitprice = Column(DECIMAL(18, 2))
    pnl = Column(DECIMAL(18, 2))
    entrytime = Column(DateTime, nullable=False)
    exittime = Column(DateTime)
    
    # Relationships
    trade = relationship("BacktestTrade", back_populates="positions")

# =====================================================
# AUTHENTICATION MODELS
# =====================================================

class AuthSession(Base):
    """Authentication sessions for brokers"""
    __tablename__ = 'authsessions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_type = Column(String(50), nullable=False)
    session_token = Column(String(500))
    access_token = Column(String(500))
    refresh_token = Column(String(500))
    api_key = Column(String(255))
    api_secret = Column(String(500))
    user_id = Column(String(100))
    user_name = Column(String(255))
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    metadata = Column(JSON)

class UserSession(Base):
    """User sessions for web UI"""
    __tablename__ = 'usersessions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), nullable=False)
    session_token = Column(String(500), nullable=False, unique=True)
    role = Column(String(50), default='user')
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=func.now())
    last_activity = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

# =====================================================
# LIVE TRADING MODELS
# =====================================================

class LiveTrade(Base):
    """Live trading records - Hypertable"""
    __tablename__ = 'livetrades'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_date = Column(DateTime, nullable=False)
    signal_type = Column(String(10), nullable=False)
    signal_time = Column(DateTime, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    symbol = Column(String(100), nullable=False)
    strike_price = Column(DECIMAL(18, 2), nullable=False)
    option_type = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(DECIMAL(18, 2), nullable=False)
    exit_price = Column(DECIMAL(18, 2))
    current_price = Column(DECIMAL(18, 2))
    pnl = Column(DECIMAL(18, 2))
    status = Column(String(50), nullable=False, default='OPEN')
    broker = Column(String(50))
    order_id = Column(String(100))
    exit_reason = Column(String(200))
    metadata = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# =====================================================
# PAPER TRADING MODELS
# =====================================================

class PaperTrade(Base):
    """Paper trading records"""
    __tablename__ = 'papertrades'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_name = Column(String(100), nullable=False)
    trade_date = Column(DateTime, nullable=False)
    signal_type = Column(String(10), nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    symbol = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(DECIMAL(18, 2), nullable=False)
    exit_price = Column(DECIMAL(18, 2))
    pnl = Column(DECIMAL(18, 2))
    status = Column(String(50), nullable=False, default='OPEN')
    metadata = Column(JSON)
    created_at = Column(DateTime, default=func.now())

class PaperPortfolio(Base):
    """Paper trading portfolios"""
    __tablename__ = 'paperportfolios'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_name = Column(String(100), nullable=False, unique=True)
    initial_capital = Column(DECIMAL(18, 2), nullable=False, default=500000)
    current_capital = Column(DECIMAL(18, 2), nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(DECIMAL(18, 2), default=0)
    max_drawdown = Column(DECIMAL(18, 2))
    win_rate = Column(DECIMAL(5, 2))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# =====================================================
# ALERT & NOTIFICATION MODELS
# =====================================================

class AlertConfiguration(Base):
    """Alert configuration settings"""
    __tablename__ = 'alertconfigurations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String(50), nullable=False)
    channel = Column(String(50), nullable=False)
    is_enabled = Column(Boolean, default=True)
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class AlertHistory(Base):
    """Alert history log"""
    __tablename__ = 'alerthistory'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String(50), nullable=False)
    channel = Column(String(50), nullable=False)
    recipient = Column(String(200))
    subject = Column(String(500))
    message = Column(String)
    status = Column(String(50), nullable=False)
    error_message = Column(String)
    sent_at = Column(DateTime, default=func.now())
    metadata = Column(JSON)

# =====================================================
# WEBHOOK MODELS
# =====================================================

class WebhookEvent(Base):
    """Webhook events from TradingView"""
    __tablename__ = 'webhookevents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime)
    error_message = Column(String)
    created_at = Column(DateTime, default=func.now())

# =====================================================
# PERFORMANCE MODELS
# =====================================================

class PerformanceMetric(Base):
    """Performance metrics tracking"""
    __tablename__ = 'performancemetrics'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_date = Column(DateTime, nullable=False)
    metric_type = Column(String(100), nullable=False)
    metric_value = Column(DECIMAL(18, 4), nullable=False)
    metadata = Column(JSON)
    created_at = Column(DateTime, default=func.now())

# =====================================================
# SYSTEM MONITORING MODELS
# =====================================================

class SystemLog(Base):
    """System logs for monitoring"""
    __tablename__ = 'systemlogs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    log_level = Column(String(20), nullable=False)
    component = Column(String(100), nullable=False)
    message = Column(String, nullable=False)
    error_trace = Column(String)
    metadata = Column(JSON)
    created_at = Column(DateTime, default=func.now())