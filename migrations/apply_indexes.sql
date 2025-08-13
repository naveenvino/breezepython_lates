-- Set required options for index creation
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET NUMERIC_ROUNDABORT OFF;
GO

-- Critical Performance Indexes for BreezeConnect Trading System
PRINT 'Starting index creation...';
GO

-- 1. BacktestTrades Performance Index
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='IX_BacktestTrades_Perf' AND object_id = OBJECT_ID('BacktestTrades'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_BacktestTrades_Perf
    ON BacktestTrades (BacktestRunId, EntryTime)
    INCLUDE (SignalType, ExitTime, TotalPnL);
    PRINT 'Created IX_BacktestTrades_Perf';
END
ELSE
    PRINT 'IX_BacktestTrades_Perf already exists';
GO

-- 2. BacktestPositions Lookup Index
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='IX_BacktestPositions_Trade' AND object_id = OBJECT_ID('BacktestPositions'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_BacktestPositions_Trade
    ON BacktestPositions (TradeId);
    PRINT 'Created IX_BacktestPositions_Trade';
END
ELSE
    PRINT 'IX_BacktestPositions_Trade already exists';
GO

-- 3. Update Statistics
UPDATE STATISTICS BacktestTrades;
UPDATE STATISTICS BacktestPositions;
PRINT 'Statistics updated';
GO

-- 4. Verify indexes were created
SELECT 
    'Index Created' AS Status,
    i.name AS IndexName,
    t.name AS TableName,
    i.type_desc AS IndexType
FROM sys.indexes i
INNER JOIN sys.tables t ON i.object_id = t.object_id
WHERE t.name IN ('BacktestTrades', 'BacktestPositions')
    AND i.name LIKE 'IX_%'
ORDER BY t.name, i.name;