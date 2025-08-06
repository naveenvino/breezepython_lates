-- Add zone and context columns to BacktestTrades table
-- This migration adds detailed market context information to trades

-- Add resistance zone columns
ALTER TABLE BacktestTrades
ADD ResistanceZoneTop DECIMAL(18, 2) NULL;

ALTER TABLE BacktestTrades
ADD ResistanceZoneBottom DECIMAL(18, 2) NULL;

-- Add support zone columns
ALTER TABLE BacktestTrades
ADD SupportZoneTop DECIMAL(18, 2) NULL;

ALTER TABLE BacktestTrades
ADD SupportZoneBottom DECIMAL(18, 2) NULL;

-- Add market bias columns
ALTER TABLE BacktestTrades
ADD BiasDirection VARCHAR(20) NULL;

ALTER TABLE BacktestTrades
ADD BiasStrength DECIMAL(5, 2) NULL;

-- Add weekly extremes
ALTER TABLE BacktestTrades
ADD WeeklyMaxHigh DECIMAL(18, 2) NULL;

ALTER TABLE BacktestTrades
ADD WeeklyMinLow DECIMAL(18, 2) NULL;

-- Add additional context columns
ALTER TABLE BacktestTrades
ADD FirstBarOpen DECIMAL(18, 2) NULL;

ALTER TABLE BacktestTrades
ADD FirstBarClose DECIMAL(18, 2) NULL;

ALTER TABLE BacktestTrades
ADD FirstBarHigh DECIMAL(18, 2) NULL;

ALTER TABLE BacktestTrades
ADD FirstBarLow DECIMAL(18, 2) NULL;

-- Add distance metrics
ALTER TABLE BacktestTrades
ADD DistanceToResistance DECIMAL(10, 6) NULL;

ALTER TABLE BacktestTrades
ADD DistanceToSupport DECIMAL(10, 6) NULL;

-- Add index for date-based queries
CREATE INDEX IX_BacktestTrades_EntryTime ON BacktestTrades(EntryTime);
CREATE INDEX IX_BacktestTrades_WeekStartDate ON BacktestTrades(WeekStartDate);