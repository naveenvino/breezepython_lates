-- Performance Optimization Indexes for BreezeConnect Trading System
-- Created: 2025-08-12
-- Purpose: Critical indexes to improve query performance by 50-70%

-- ============================================
-- 1. Options Historical Data Indexes
-- ============================================

-- Composite index for option price lookups (most critical)
CREATE NONCLUSTERED INDEX IX_OptionsHistoricalData_Lookup
ON OptionsHistoricalData (timestamp, strike_price, option_type, expiry_date)
INCLUDE ([close], volume, open_interest, iv, delta, gamma, theta, vega);

-- Index for expiry date filtering
CREATE NONCLUSTERED INDEX IX_OptionsHistoricalData_Expiry
ON OptionsHistoricalData (expiry_date, option_type, strike_price);

-- Index for timestamp range queries
CREATE NONCLUSTERED INDEX IX_OptionsHistoricalData_TimeRange
ON OptionsHistoricalData (timestamp)
WHERE timestamp >= '2024-01-01';

-- ============================================
-- 2. Backtest Trade Indexes
-- ============================================

-- Composite index for backtest trade lookups
CREATE NONCLUSTERED INDEX IX_BacktestTrade_Lookup
ON BacktestTrades (BacktestRunId, EntryTime, SignalType)
INCLUDE (ExitTime, IndexPriceAtEntry, IndexPriceAtExit, TotalPnL, Outcome);

-- Partial index for active trades
CREATE NONCLUSTERED INDEX IX_BacktestTrade_Active
ON BacktestTrades (BacktestRunId, EntryTime)
WHERE ExitTime IS NULL;

-- Index for PnL analysis
CREATE NONCLUSTERED INDEX IX_BacktestTrade_PnL
ON BacktestTrades (BacktestRunId, TotalPnL, SignalType)
WHERE TotalPnL IS NOT NULL;

-- ============================================
-- 3. Backtest Position Indexes
-- ============================================

-- Index for position lookups by trade
CREATE NONCLUSTERED INDEX IX_BacktestPosition_Trade
ON BacktestPositions (TradeId, PositionType)
INCLUDE (Strike, OptionType, EntryPrice, ExitPrice, Quantity);

-- Index for open positions
CREATE NONCLUSTERED INDEX IX_BacktestPosition_Open
ON BacktestPositions (TradeId)
WHERE ExitTime IS NULL;

-- ============================================
-- 4. NIFTY Data Indexes
-- ============================================

-- Composite index for NIFTY 5-minute data
CREATE NONCLUSTERED INDEX IX_NIFTYData5Min_Lookup
ON NIFTYData_5Min (timestamp, [open], high, low, [close])
INCLUDE (volume);

-- Index for date range queries
CREATE NONCLUSTERED INDEX IX_NIFTYData5Min_DateRange
ON NIFTYData_5Min (timestamp DESC)
WHERE timestamp >= '2024-01-01';

-- Composite index for NIFTY hourly data
CREATE NONCLUSTERED INDEX IX_NIFTYDataHourly_Lookup
ON NIFTYData_Hourly (timestamp, [open], high, low, [close]);

-- ============================================
-- 5. ML Model Indexes
-- ============================================

-- Index for ML backtest results
CREATE NONCLUSTERED INDEX IX_MLBacktestResult_Lookup
ON MLBacktestResults (backtest_run_id, signal_detected_at)
INCLUDE (ml_confidence, ml_decision, actual_signal, signal_strength);

-- Index for ML model performance tracking
CREATE NONCLUSTERED INDEX IX_MLBacktestResult_Performance
ON MLBacktestResults (backtest_run_id, ml_decision, actual_outcome)
WHERE ml_confidence > 0.5;

-- ============================================
-- 6. Signal Detection Indexes
-- ============================================

-- Index for signal detection queries
CREATE NONCLUSTERED INDEX IX_SignalDetection_Lookup
ON BacktestTrades (SignalType, EntryTime, BacktestRunId)
INCLUDE (IndexPriceAtEntry, StopLossPrice);

-- ============================================
-- 7. Statistics Update
-- ============================================

-- Update statistics for all tables with new indexes
UPDATE STATISTICS OptionsHistoricalData WITH FULLSCAN;
UPDATE STATISTICS BacktestTrades WITH FULLSCAN;
UPDATE STATISTICS BacktestPositions WITH FULLSCAN;
UPDATE STATISTICS NIFTYData_5Min WITH FULLSCAN;
UPDATE STATISTICS NIFTYData_Hourly WITH FULLSCAN;
UPDATE STATISTICS MLBacktestResults WITH FULLSCAN;

-- ============================================
-- 8. Query Hints for Optimizer
-- ============================================

-- Enable query store for performance monitoring
ALTER DATABASE KiteConnectApi SET QUERY_STORE = ON;
ALTER DATABASE KiteConnectApi SET QUERY_STORE (OPERATION_MODE = READ_WRITE);

-- ============================================
-- Performance Check Queries
-- ============================================

-- Check index usage stats
SELECT 
    OBJECT_NAME(s.object_id) AS TableName,
    i.name AS IndexName,
    s.user_seeks,
    s.user_scans,
    s.user_lookups,
    s.user_updates
FROM sys.dm_db_index_usage_stats s
JOIN sys.indexes i ON s.object_id = i.object_id AND s.index_id = i.index_id
WHERE database_id = DB_ID('KiteConnectApi')
ORDER BY s.user_seeks + s.user_scans + s.user_lookups DESC;

-- Check missing index recommendations
SELECT 
    migs.avg_total_user_cost * (migs.avg_user_impact / 100.0) * (migs.user_seeks + migs.user_scans) AS improvement_measure,
    'CREATE INDEX [IX_' + OBJECT_NAME(mid.object_id) + '_'
    + REPLACE(REPLACE(REPLACE(ISNULL(mid.equality_columns, ''), ', ', '_'), '[', ''), ']', '') 
    + CASE
        WHEN mid.equality_columns IS NOT NULL AND mid.inequality_columns IS NOT NULL THEN '_'
        ELSE ''
      END
    + REPLACE(REPLACE(REPLACE(ISNULL(mid.inequality_columns, ''), ', ', '_'), '[', ''), ']', '')
    + '] ON ' + mid.statement
    + ' (' + ISNULL(mid.equality_columns, '')
    + CASE WHEN mid.equality_columns IS NOT NULL AND mid.inequality_columns IS NOT NULL THEN ',' ELSE '' END
    + ISNULL(mid.inequality_columns, '')
    + ')'
    + ISNULL(' INCLUDE (' + mid.included_columns + ')', '') AS create_index_statement,
    migs.*
FROM sys.dm_db_missing_index_groups mig
INNER JOIN sys.dm_db_missing_index_group_stats migs ON migs.group_handle = mig.index_group_handle
INNER JOIN sys.dm_db_missing_index_details mid ON mig.index_handle = mid.index_handle
WHERE mid.database_id = DB_ID('KiteConnectApi')
ORDER BY improvement_measure DESC;