-- Add missing columns to BacktestRuns table if they don't exist

-- Check and add SharpeRatio
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[BacktestRuns]') AND name = 'SharpeRatio')
BEGIN
    ALTER TABLE BacktestRuns ADD SharpeRatio DECIMAL(10, 4) NULL;
END

-- Check and add SortinoRatio  
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[BacktestRuns]') AND name = 'SortinoRatio')
BEGIN
    ALTER TABLE BacktestRuns ADD SortinoRatio DECIMAL(10, 4) NULL;
END

PRINT 'Missing columns added successfully';