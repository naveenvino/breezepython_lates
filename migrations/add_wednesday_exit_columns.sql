-- Add Wednesday exit comparison columns to BacktestTrades table
-- These columns store what the P&L would be if we exited on Wednesday 3:15 PM

ALTER TABLE BacktestTrades
ADD WednesdayExitTime DATETIME NULL;

ALTER TABLE BacktestTrades
ADD WednesdayExitPnL DECIMAL(18, 2) NULL;

ALTER TABLE BacktestTrades
ADD WednesdayIndexPrice DECIMAL(18, 2) NULL;

-- Add index for faster queries on Wednesday exit data
CREATE INDEX IX_BacktestTrades_WednesdayExit 
ON BacktestTrades(WednesdayExitTime) 
WHERE WednesdayExitTime IS NOT NULL;