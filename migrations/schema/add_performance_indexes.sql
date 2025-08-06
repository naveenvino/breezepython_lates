-- Performance critical indexes for BreezeConnect Trading System
-- Run this migration to improve query performance

-- ===========================
-- Backtest Performance Indexes
-- ===========================

-- Composite index for backtest trade queries
CREATE INDEX IF NOT EXISTS idx_backtest_trades_composite 
ON BacktestTrade(backtest_run_id, entry_time, signal_type);

-- Index for filtering by outcome and calculating P&L
CREATE INDEX IF NOT EXISTS idx_backtest_trades_outcome
ON BacktestTrade(backtest_run_id, outcome, total_pnl);

-- Index for position lookups
CREATE INDEX IF NOT EXISTS idx_backtest_positions_trade
ON BacktestPosition(trade_id, position_type);

-- Index for backtest runs by date
CREATE INDEX IF NOT EXISTS idx_backtest_runs_date
ON BacktestRun(created_at, status);

-- ===========================
-- Options Data Indexes
-- ===========================

-- Composite index for option price lookups (most critical for performance)
CREATE INDEX IF NOT EXISTS idx_options_price_lookup 
ON OptionsHistoricalData(timestamp, strike, option_type, expiry_date);

-- Index for symbol and time queries
CREATE INDEX IF NOT EXISTS idx_options_symbol_time
ON OptionsHistoricalData(symbol, timestamp, interval);

-- Index for finding options by expiry
CREATE INDEX IF NOT EXISTS idx_options_expiry
ON OptionsHistoricalData(expiry_date, symbol, strike);

-- Index for bid-ask spread analysis
CREATE INDEX IF NOT EXISTS idx_options_spread
ON OptionsHistoricalData(timestamp, bid_price, ask_price)
WHERE bid_price IS NOT NULL AND ask_price IS NOT NULL;

-- ===========================
-- NIFTY Index Data Indexes
-- ===========================

-- Primary index for time-based queries
CREATE INDEX IF NOT EXISTS idx_nifty_time_interval 
ON NiftyIndexData(timestamp, interval);

-- Index for date-based aggregations
CREATE INDEX IF NOT EXISTS idx_nifty_symbol_date
ON NiftyIndexData(symbol, timestamp, interval);

-- Index for finding gaps in data
CREATE INDEX IF NOT EXISTS idx_nifty_sequential
ON NiftyIndexData(symbol, interval, timestamp DESC);

-- ===========================
-- Additional Performance Indexes
-- ===========================

-- Index for weekly context calculations
CREATE INDEX IF NOT EXISTS idx_nifty_weekly_context
ON NiftyIndexData(symbol, timestamp)
WHERE interval = '5minute';

-- Index for hourly data queries
CREATE INDEX IF NOT EXISTS idx_nifty_hourly
ON NiftyIndexData(symbol, timestamp)
WHERE interval = 'hourly';

-- ===========================
-- Partial Indexes for Common Queries
-- ===========================

-- Index for active backtest trades (not exited)
CREATE INDEX IF NOT EXISTS idx_backtest_trades_active
ON BacktestTrade(backtest_run_id, entry_time)
WHERE exit_time IS NULL;

-- Index for profitable trades
CREATE INDEX IF NOT EXISTS idx_backtest_trades_profitable
ON BacktestTrade(backtest_run_id, total_pnl)
WHERE total_pnl > 0;

-- Index for stop loss analysis
CREATE INDEX IF NOT EXISTS idx_backtest_trades_stoploss
ON BacktestTrade(backtest_run_id, exit_reason)
WHERE exit_reason = 'stop_loss';

-- ===========================
-- Statistics Update
-- ===========================

-- Update statistics for query optimizer
-- (SQL Server specific, comment out for other databases)
-- UPDATE STATISTICS BacktestTrade WITH FULLSCAN;
-- UPDATE STATISTICS OptionsHistoricalData WITH FULLSCAN;
-- UPDATE STATISTICS NiftyIndexData WITH FULLSCAN;
-- UPDATE STATISTICS BacktestPosition WITH FULLSCAN;
-- UPDATE STATISTICS BacktestRun WITH FULLSCAN;

-- ===========================
-- Verification Query
-- ===========================

-- Query to verify indexes were created
SELECT 
    'Indexes created successfully. Run this query to verify:' as message
UNION ALL
SELECT 
    'SELECT name FROM sqlite_master WHERE type="index" AND name LIKE "idx_%";' as message;

-- For SQL Server:
-- SELECT i.name AS index_name, t.name AS table_name
-- FROM sys.indexes i
-- JOIN sys.tables t ON i.object_id = t.object_id
-- WHERE i.name LIKE 'idx_%'
-- ORDER BY t.name, i.name;