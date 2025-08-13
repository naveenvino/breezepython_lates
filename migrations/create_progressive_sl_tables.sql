-- Progressive P&L Stop-Loss Tables
-- Created: 2025-08-12
-- Purpose: Support P&L-based progressive stop-loss in backtesting

-- Table for P&L-based backtest runs
CREATE TABLE BacktestRunsProgressiveSL (
    Id VARCHAR(50) PRIMARY KEY,
    Name VARCHAR(200) NOT NULL,
    FromDate DATETIME NOT NULL,
    ToDate DATETIME NOT NULL,
    InitialCapital DECIMAL(18,2) NOT NULL,
    LotSize INT NOT NULL DEFAULT 75,
    LotsToTrade INT NOT NULL DEFAULT 10,
    
    -- Configuration
    SignalsToTest VARCHAR(100) NOT NULL,
    UseHedging BIT NOT NULL DEFAULT 1,
    HedgeOffset INT NOT NULL DEFAULT 200,
    CommissionPerLot DECIMAL(10,2) NOT NULL DEFAULT 40,
    SlippagePercent DECIMAL(5,4) NOT NULL DEFAULT 0.001,
    
    -- P&L Stop-Loss specific parameters
    InitialSLPerLot DECIMAL(18,2) NOT NULL DEFAULT 6000,
    UsePnLStopLoss BIT DEFAULT 1,
    ProfitTriggerPercent DECIMAL(5,2) DEFAULT 40,
    Day2SLFactor DECIMAL(5,2) DEFAULT 0.5,
    Day3Breakeven BIT DEFAULT 1,
    Day4ProfitLockPercent DECIMAL(5,2) DEFAULT 5,
    
    -- Status tracking
    Status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    StartedAt DATETIME NULL,
    CompletedAt DATETIME NULL,
    ErrorMessage NVARCHAR(MAX) NULL,
    
    -- Results summary
    TotalTrades INT NOT NULL DEFAULT 0,
    WinningTrades INT NOT NULL DEFAULT 0,
    LosingTrades INT NOT NULL DEFAULT 0,
    WinRate DECIMAL(5,2) NULL,
    
    -- Financial results
    FinalCapital DECIMAL(18,2) NULL,
    TotalPnL DECIMAL(18,2) NULL,
    TotalReturnPercent DECIMAL(10,2) NULL,
    MaxDrawdown DECIMAL(18,2) NULL,
    MaxDrawdownPercent DECIMAL(10,2) NULL,
    
    -- P&L SL specific results
    TradesStoppedByPnLSL INT DEFAULT 0,
    TradesStoppedByIndexSL INT DEFAULT 0,
    AvgPnLAtSLHit DECIMAL(18,2) NULL,
    
    -- Metadata
    CreatedAt DATETIME NOT NULL DEFAULT GETDATE(),
    CreatedBy VARCHAR(100) NOT NULL DEFAULT 'System'
);

-- Track P&L at each 5-min interval for each trade
CREATE TABLE BacktestPnLTracking (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    TradeId VARCHAR(50) NOT NULL,
    BacktestRunId VARCHAR(50) NOT NULL,
    Timestamp DATETIME NOT NULL,
    
    -- Option prices at this time
    MainLegStrike INT NOT NULL,
    MainLegPrice DECIMAL(18,2) NOT NULL,
    HedgeLegStrike INT NOT NULL,
    HedgeLegPrice DECIMAL(18,2) NOT NULL,
    
    -- P&L calculation
    MainLegPnL DECIMAL(18,2) NOT NULL,
    HedgeLegPnL DECIMAL(18,2) NOT NULL,
    NetPnL DECIMAL(18,2) NOT NULL,
    
    -- Stop-loss levels at this time
    IndexSLLevel DECIMAL(18,2) NOT NULL,
    PnLSLLevel DECIMAL(18,2) NOT NULL,
    SLStage VARCHAR(20) NOT NULL, -- INITIAL/HALF/BREAKEVEN/PROFIT_LOCK
    
    -- Market data
    NiftyIndex DECIMAL(18,2) NOT NULL,
    DaysSinceEntry INT NOT NULL,
    
    CreatedAt DATETIME DEFAULT GETDATE()
);

-- Create index for faster queries
CREATE INDEX IX_BacktestPnLTracking_TradeId ON BacktestPnLTracking(TradeId);
CREATE INDEX IX_BacktestPnLTracking_Timestamp ON BacktestPnLTracking(Timestamp);

-- Log stop-loss updates
CREATE TABLE BacktestSLUpdates (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    TradeId VARCHAR(50) NOT NULL,
    BacktestRunId VARCHAR(50) NOT NULL,
    UpdateTime DATETIME NOT NULL,
    
    -- Stop-loss change details
    OldPnLSL DECIMAL(18,2) NOT NULL,
    NewPnLSL DECIMAL(18,2) NOT NULL,
    OldStage VARCHAR(20) NOT NULL,
    NewStage VARCHAR(20) NOT NULL,
    
    -- Context at update
    CurrentPnL DECIMAL(18,2) NOT NULL,
    MaxProfitReceivable DECIMAL(18,2) NOT NULL,
    DayNumber INT NOT NULL,
    UpdateReason VARCHAR(100) NOT NULL,
    
    -- Market context
    NiftyIndex DECIMAL(18,2) NULL,
    MainLegPrice DECIMAL(18,2) NULL,
    HedgeLegPrice DECIMAL(18,2) NULL,
    
    CreatedAt DATETIME DEFAULT GETDATE()
);

-- Create index for faster queries
CREATE INDEX IX_BacktestSLUpdates_TradeId ON BacktestSLUpdates(TradeId);
CREATE INDEX IX_BacktestSLUpdates_BacktestRunId ON BacktestSLUpdates(BacktestRunId);

-- Summary table for comparing strategies
CREATE TABLE BacktestProgressiveSLComparison (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    BacktestRunId VARCHAR(50) NOT NULL,
    ComparisonDate DATETIME NOT NULL,
    
    -- With Progressive SL
    WithSL_TotalPnL DECIMAL(18,2),
    WithSL_MaxDrawdown DECIMAL(18,2),
    WithSL_WinRate DECIMAL(5,2),
    WithSL_TradesStopped INT,
    WithSL_AvgLossAtStop DECIMAL(18,2),
    
    -- Without Progressive SL (index only)
    WithoutSL_TotalPnL DECIMAL(18,2),
    WithoutSL_MaxDrawdown DECIMAL(18,2),
    WithoutSL_WinRate DECIMAL(5,2),
    WithoutSL_TradesStopped INT,
    WithoutSL_AvgLossAtStop DECIMAL(18,2),
    
    -- Improvement metrics
    PnLImprovement DECIMAL(18,2),
    DrawdownReduction DECIMAL(18,2),
    WinRateImprovement DECIMAL(5,2),
    
    CreatedAt DATETIME DEFAULT GETDATE()
);

-- Grant permissions if needed
-- GRANT SELECT, INSERT, UPDATE ON BacktestRunsProgressiveSL TO [your_user];
-- GRANT SELECT, INSERT, UPDATE ON BacktestPnLTracking TO [your_user];
-- GRANT SELECT, INSERT, UPDATE ON BacktestSLUpdates TO [your_user];
-- GRANT SELECT, INSERT, UPDATE ON BacktestProgressiveSLComparison TO [your_user];