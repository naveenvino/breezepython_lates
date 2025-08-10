-- Add Wednesday exit comparison columns to BacktestTrades table
-- These columns store what the P&L would be if we exited on Wednesday 3:15 PM

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'BacktestTrades' 
               AND COLUMN_NAME = 'WednesdayExitTime')
BEGIN
    ALTER TABLE BacktestTrades
    ADD WednesdayExitTime DATETIME NULL
END
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'BacktestTrades' 
               AND COLUMN_NAME = 'WednesdayExitPnL')
BEGIN
    ALTER TABLE BacktestTrades
    ADD WednesdayExitPnL DECIMAL(18, 2) NULL
END
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'BacktestTrades' 
               AND COLUMN_NAME = 'WednesdayIndexPrice')
BEGIN
    ALTER TABLE BacktestTrades
    ADD WednesdayIndexPrice DECIMAL(18, 2) NULL
END
GO