-- PostgreSQL + TimescaleDB Schema for Trading System
-- Generated: 2025-08-29
-- This schema includes all tables needed for the trading system

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- =====================================================
-- CORE TIME-SERIES TABLES (Hypertables)
-- =====================================================

-- NIFTY 5-minute data
CREATE TABLE IF NOT EXISTS NIFTYData_5Min (
    Id SERIAL PRIMARY KEY,
    Symbol VARCHAR(50) NOT NULL,
    Timestamp TIMESTAMP NOT NULL,
    Open NUMERIC(18, 2) NOT NULL,
    High NUMERIC(18, 2) NOT NULL,
    Low NUMERIC(18, 2) NOT NULL,
    Close NUMERIC(18, 2) NOT NULL,
    LastPrice NUMERIC(18, 2) NOT NULL,
    Volume BIGINT NOT NULL,
    LastUpdateTime TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Convert to hypertable
SELECT create_hypertable('NIFTYData_5Min', 
    'Timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_nifty_5min_symbol_time ON NIFTYData_5Min (Symbol, Timestamp DESC);

-- NIFTY Hourly data
CREATE TABLE IF NOT EXISTS NIFTYData_Hourly (
    Id SERIAL PRIMARY KEY,
    Symbol VARCHAR(50) NOT NULL,
    Timestamp TIMESTAMP NOT NULL,
    Open NUMERIC(18, 2) NOT NULL,
    High NUMERIC(18, 2) NOT NULL,
    Low NUMERIC(18, 2) NOT NULL,
    Close NUMERIC(18, 2) NOT NULL,
    LastPrice NUMERIC(18, 2) NOT NULL,
    Volume BIGINT NOT NULL,
    LastUpdateTime TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

SELECT create_hypertable('NIFTYData_Hourly',
    'Timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_nifty_hourly_symbol_time ON NIFTYData_Hourly (Symbol, Timestamp DESC);

-- Options Data
CREATE TABLE IF NOT EXISTS OptionsData (
    Id SERIAL PRIMARY KEY,
    Symbol VARCHAR(100) NOT NULL,
    StrikePrice NUMERIC(18, 2) NOT NULL,
    OptionType VARCHAR(10) NOT NULL CHECK (OptionType IN ('CE', 'PE')),
    ExpiryDate DATE NOT NULL,
    Timestamp TIMESTAMP NOT NULL,
    LastPrice NUMERIC(18, 2) NOT NULL,
    Volume BIGINT,
    OpenInterest BIGINT,
    IV NUMERIC(10, 4),
    Delta NUMERIC(10, 6),
    Gamma NUMERIC(10, 6),
    Theta NUMERIC(10, 6),
    Vega NUMERIC(10, 6),
    Rho NUMERIC(10, 6),
    BidPrice NUMERIC(18, 2),
    AskPrice NUMERIC(18, 2),
    LastUpdateTime TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

SELECT create_hypertable('OptionsData',
    'Timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_options_strike_type_time ON OptionsData (StrikePrice, OptionType, Timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_options_symbol_time ON OptionsData (Symbol, Timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_options_expiry ON OptionsData (ExpiryDate, Timestamp DESC);

-- =====================================================
-- BACKTESTING TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS BacktestRuns (
    Id SERIAL PRIMARY KEY,
    RunDate TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FromDate DATE NOT NULL,
    ToDate DATE NOT NULL,
    SignalsTested VARCHAR(200),
    InitialCapital NUMERIC(18, 2) DEFAULT 500000,
    TotalTrades INTEGER DEFAULT 0,
    ProfitableTrades INTEGER DEFAULT 0,
    LossTrades INTEGER DEFAULT 0,
    TotalPnL NUMERIC(18, 2) DEFAULT 0,
    MaxDrawdown NUMERIC(18, 2),
    SharpeRatio NUMERIC(10, 4),
    WinRate NUMERIC(5, 2),
    Parameters JSONB,
    ExecutionTime NUMERIC(10, 3),
    Status VARCHAR(50) DEFAULT 'COMPLETED'
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_date ON BacktestRuns (RunDate DESC);

CREATE TABLE IF NOT EXISTS BacktestTrades (
    Id SERIAL PRIMARY KEY,
    BacktestRunId INTEGER REFERENCES BacktestRuns(Id) ON DELETE CASCADE,
    SignalType VARCHAR(10) NOT NULL,
    SignalTime TIMESTAMP NOT NULL,
    EntryTime TIMESTAMP NOT NULL,
    ExitTime TIMESTAMP,
    WeekStartDate DATE NOT NULL,
    MainStrike NUMERIC(18, 2) NOT NULL,
    HedgeStrike NUMERIC(18, 2),
    OptionType VARCHAR(10) NOT NULL,
    EntryPrice NUMERIC(18, 2) NOT NULL,
    ExitPrice NUMERIC(18, 2),
    Quantity INTEGER NOT NULL,
    PnL NUMERIC(18, 2),
    ExitReason VARCHAR(100),
    MaxProfit NUMERIC(18, 2),
    MaxLoss NUMERIC(18, 2),
    Commission NUMERIC(18, 2) DEFAULT 40,
    SlippageCost NUMERIC(18, 2) DEFAULT 0,
    NetPnL NUMERIC(18, 2)
);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_run ON BacktestTrades (BacktestRunId);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_signal ON BacktestTrades (SignalType, WeekStartDate);

CREATE TABLE IF NOT EXISTS BacktestPositions (
    Id SERIAL PRIMARY KEY,
    TradeId INTEGER REFERENCES BacktestTrades(Id) ON DELETE CASCADE,
    PositionType VARCHAR(20) NOT NULL,
    Symbol VARCHAR(100) NOT NULL,
    Quantity INTEGER NOT NULL,
    EntryPrice NUMERIC(18, 2) NOT NULL,
    ExitPrice NUMERIC(18, 2),
    PnL NUMERIC(18, 2),
    EntryTime TIMESTAMP NOT NULL,
    ExitTime TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_backtest_positions_trade ON BacktestPositions (TradeId);

-- =====================================================
-- AUTHENTICATION & SESSION TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS AuthSessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_type VARCHAR(50) NOT NULL,
    session_token VARCHAR(500),
    access_token VARCHAR(500),
    refresh_token VARCHAR(500),
    api_key VARCHAR(255),
    api_secret VARCHAR(500),
    user_id VARCHAR(100),
    user_name VARCHAR(255),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_service ON AuthSessions (service_type, is_active);

CREATE TABLE IF NOT EXISTS UserSessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL,
    session_token VARCHAR(500) NOT NULL UNIQUE,
    role VARCHAR(50) DEFAULT 'user',
    ip_address VARCHAR(50),
    user_agent VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON UserSessions (session_token) WHERE is_active = true;

-- =====================================================
-- LIVE TRADING TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS LiveTrades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_date DATE NOT NULL,
    signal_type VARCHAR(10) NOT NULL,
    signal_time TIMESTAMP NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    symbol VARCHAR(100) NOT NULL,
    strike_price NUMERIC(18, 2) NOT NULL,
    option_type VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price NUMERIC(18, 2) NOT NULL,
    exit_price NUMERIC(18, 2),
    current_price NUMERIC(18, 2),
    pnl NUMERIC(18, 2),
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    broker VARCHAR(50),
    order_id VARCHAR(100),
    exit_reason VARCHAR(200),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

SELECT create_hypertable('LiveTrades',
    'created_at',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_live_trades_status ON LiveTrades (status, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_live_trades_signal ON LiveTrades (signal_type, entry_time DESC);

-- =====================================================
-- PAPER TRADING TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS PaperTrades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100) NOT NULL,
    trade_date DATE NOT NULL,
    signal_type VARCHAR(10) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    symbol VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price NUMERIC(18, 2) NOT NULL,
    exit_price NUMERIC(18, 2),
    pnl NUMERIC(18, 2),
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_strategy ON PaperTrades (strategy_name, trade_date DESC);

CREATE TABLE IF NOT EXISTS PaperPortfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100) NOT NULL UNIQUE,
    initial_capital NUMERIC(18, 2) NOT NULL DEFAULT 500000,
    current_capital NUMERIC(18, 2) NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl NUMERIC(18, 2) DEFAULT 0,
    max_drawdown NUMERIC(18, 2),
    win_rate NUMERIC(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- ALERT & NOTIFICATION TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS AlertConfigurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    is_enabled BOOLEAN DEFAULT true,
    config JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS AlertHistory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    recipient VARCHAR(200),
    subject VARCHAR(500),
    message TEXT,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_alert_history_type ON AlertHistory (alert_type, sent_at DESC);

-- =====================================================
-- WEBHOOK & TRADINGVIEW TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS WebhookEvents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_processed ON WebhookEvents (processed, created_at DESC);

-- =====================================================
-- PERFORMANCE & ANALYTICS TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS PerformanceMetrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date DATE NOT NULL,
    metric_type VARCHAR(100) NOT NULL,
    metric_value NUMERIC(18, 4) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_date ON PerformanceMetrics (metric_date DESC, metric_type);

-- =====================================================
-- SYSTEM MONITORING TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS SystemLogs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    log_level VARCHAR(20) NOT NULL,
    component VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    error_trace TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_logs_level ON SystemLogs (log_level, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_component ON SystemLogs (component, created_at DESC);

-- =====================================================
-- CONTINUOUS AGGREGATES FOR PERFORMANCE
-- =====================================================

-- Create continuous aggregate for 1-hour OHLC
CREATE MATERIALIZED VIEW nifty_1hour_ohlc
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', Timestamp) AS bucket,
    Symbol,
    first(Open, Timestamp) AS open,
    max(High) AS high,
    min(Low) AS low,
    last(Close, Timestamp) AS close,
    sum(Volume) AS volume
FROM NIFTYData_5Min
GROUP BY bucket, Symbol
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('nifty_1hour_ohlc',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- =====================================================
-- COMPRESSION POLICIES FOR OLD DATA
-- =====================================================

-- Enable compression on hypertables
ALTER TABLE NIFTYData_5Min SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'Symbol',
    timescaledb.compress_orderby = 'Timestamp DESC'
);

-- Add compression policy (compress data older than 7 days)
SELECT add_compression_policy('NIFTYData_5Min', INTERVAL '7 days');

-- Same for OptionsData
ALTER TABLE OptionsData SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'Symbol, OptionType',
    timescaledb.compress_orderby = 'Timestamp DESC'
);

SELECT add_compression_policy('OptionsData', INTERVAL '7 days');

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Function to get latest price for a symbol
CREATE OR REPLACE FUNCTION get_latest_price(p_symbol VARCHAR)
RETURNS NUMERIC AS $$
BEGIN
    RETURN (
        SELECT Close 
        FROM NIFTYData_5Min 
        WHERE Symbol = p_symbol 
        ORDER BY Timestamp DESC 
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql;

-- Function to calculate PnL
CREATE OR REPLACE FUNCTION calculate_pnl(
    p_entry_price NUMERIC,
    p_exit_price NUMERIC,
    p_quantity INTEGER,
    p_option_type VARCHAR
) RETURNS NUMERIC AS $$
BEGIN
    IF p_option_type = 'SELL' THEN
        RETURN (p_entry_price - p_exit_price) * p_quantity;
    ELSE
        RETURN (p_exit_price - p_entry_price) * p_quantity;
    END IF;
END;
$$ LANGUAGE plpgsql;