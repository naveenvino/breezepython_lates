-- Machine Learning and Paper Trading Tables
-- Database: KiteConnectApi

-- Signal Performance Tracking
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'SignalPerformance')
BEGIN
    CREATE TABLE SignalPerformance (
        Id INT PRIMARY KEY IDENTITY(1,1),
        SignalType VARCHAR(10) NOT NULL,
        Date DATE NOT NULL,
        WinRate DECIMAL(5,2),
        AvgProfit DECIMAL(18,2),
        AvgLoss DECIMAL(18,2),
        ProfitFactor DECIMAL(10,2),
        TotalTrades INT,
        BestTimeOfDay VARCHAR(10),
        BestDayOfWeek VARCHAR(20),
        MarketRegime VARCHAR(20),
        VIXLevel DECIMAL(10,2),
        MetricsJson NVARCHAR(MAX),
        CreatedAt DATETIME DEFAULT GETDATE(),
        INDEX IX_SignalPerformance_Signal_Date (SignalType, Date)
    );
END
GO

-- ML Model Predictions
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLPredictions')
BEGIN
    CREATE TABLE MLPredictions (
        Id INT PRIMARY KEY IDENTITY(1,1),
        SignalId VARCHAR(50),
        SignalType VARCHAR(10),
        PredictedProbability DECIMAL(5,4),
        PredictedStopLoss DECIMAL(18,2),
        ActualOutcome VARCHAR(10),
        ModelVersion VARCHAR(50),
        ModelType VARCHAR(50),
        Features NVARCHAR(MAX),
        Timestamp DATETIME,
        CreatedAt DATETIME DEFAULT GETDATE(),
        INDEX IX_MLPredictions_Signal (SignalId),
        INDEX IX_MLPredictions_Timestamp (Timestamp)
    );
END
GO

-- Paper Trading Trades
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'PaperTrades')
BEGIN
    CREATE TABLE PaperTrades (
        Id INT PRIMARY KEY IDENTITY(1,1),
        TradeId VARCHAR(50) UNIQUE,
        SignalType VARCHAR(10),
        Direction VARCHAR(20),
        EntryTime DATETIME,
        ExitTime DATETIME,
        EntryPrice DECIMAL(18,2),
        ExitPrice DECIMAL(18,2),
        StopLoss DECIMAL(18,2),
        Quantity INT,
        PnL DECIMAL(18,2),
        PnLPercent DECIMAL(10,4),
        Status VARCHAR(20),
        ExitReason VARCHAR(50),
        MLPrediction DECIMAL(5,4),
        MarketConditions NVARCHAR(MAX),
        CreatedAt DATETIME DEFAULT GETDATE(),
        INDEX IX_PaperTrades_EntryTime (EntryTime),
        INDEX IX_PaperTrades_Signal (SignalType)
    );
END
GO

-- Paper Trading Positions
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'PaperPositions')
BEGIN
    CREATE TABLE PaperPositions (
        Id INT PRIMARY KEY IDENTITY(1,1),
        PositionId VARCHAR(50) UNIQUE,
        TradeId VARCHAR(50),
        Symbol VARCHAR(50),
        PositionType VARCHAR(20),
        Direction VARCHAR(20),
        Quantity INT,
        EntryPrice DECIMAL(18,2),
        CurrentPrice DECIMAL(18,2),
        StopLoss DECIMAL(18,2),
        UnrealizedPnL DECIMAL(18,2),
        Status VARCHAR(20),
        OpenedAt DATETIME,
        UpdatedAt DATETIME,
        FOREIGN KEY (TradeId) REFERENCES PaperTrades(TradeId),
        INDEX IX_PaperPositions_Status (Status)
    );
END
GO

-- Portfolio Backtest Runs
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'PortfolioBacktests')
BEGIN
    CREATE TABLE PortfolioBacktests (
        Id INT PRIMARY KEY IDENTITY(1,1),
        RunId VARCHAR(50) UNIQUE,
        Name VARCHAR(200),
        FromDate DATE,
        ToDate DATE,
        InitialCapital DECIMAL(18,2),
        Strategies NVARCHAR(MAX), -- JSON array of strategy configurations
        AllocationMethod VARCHAR(50),
        FinalCapital DECIMAL(18,2),
        TotalReturn DECIMAL(10,4),
        SharpeRatio DECIMAL(10,4),
        MaxDrawdown DECIMAL(10,4),
        WinRate DECIMAL(5,2),
        Results NVARCHAR(MAX), -- JSON with detailed results
        Status VARCHAR(20),
        StartedAt DATETIME,
        CompletedAt DATETIME,
        CreatedAt DATETIME DEFAULT GETDATE(),
        INDEX IX_PortfolioBacktests_RunId (RunId)
    );
END
GO

-- Portfolio Positions
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'PortfolioPositions')
BEGIN
    CREATE TABLE PortfolioPositions (
        Id INT PRIMARY KEY IDENTITY(1,1),
        RunId VARCHAR(50),
        Strategy VARCHAR(50),
        SignalType VARCHAR(10),
        Weight DECIMAL(5,4),
        EntryTime DATETIME,
        ExitTime DATETIME,
        PnL DECIMAL(18,2),
        Contribution DECIMAL(10,4), -- Contribution to portfolio return
        FOREIGN KEY (RunId) REFERENCES PortfolioBacktests(RunId),
        INDEX IX_PortfolioPositions_RunId (RunId)
    );
END
GO

-- ML Training History
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLTrainingHistory')
BEGIN
    CREATE TABLE MLTrainingHistory (
        Id INT PRIMARY KEY IDENTITY(1,1),
        ModelId VARCHAR(50),
        ModelType VARCHAR(50),
        SignalType VARCHAR(10),
        TrainingDate DATETIME,
        TrainingSamples INT,
        ValidationSamples INT,
        Features NVARCHAR(MAX),
        Hyperparameters NVARCHAR(MAX),
        TrainAccuracy DECIMAL(5,4),
        ValAccuracy DECIMAL(5,4),
        TrainF1Score DECIMAL(5,4),
        ValF1Score DECIMAL(5,4),
        TrainAUC DECIMAL(5,4),
        ValAUC DECIMAL(5,4),
        ModelPath VARCHAR(500),
        Status VARCHAR(20),
        CreatedAt DATETIME DEFAULT GETDATE(),
        INDEX IX_MLTrainingHistory_ModelId (ModelId)
    );
END
GO

-- Feature Importance
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FeatureImportance')
BEGIN
    CREATE TABLE FeatureImportance (
        Id INT PRIMARY KEY IDENTITY(1,1),
        ModelId VARCHAR(50),
        FeatureName VARCHAR(100),
        Importance DECIMAL(10,6),
        Rank INT,
        CreatedAt DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (ModelId) REFERENCES MLTrainingHistory(ModelId),
        INDEX IX_FeatureImportance_ModelId (ModelId)
    );
END
GO

-- Market Regime Detection
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MarketRegimes')
BEGIN
    CREATE TABLE MarketRegimes (
        Id INT PRIMARY KEY IDENTITY(1,1),
        StartDate DATETIME,
        EndDate DATETIME,
        RegimeType VARCHAR(50), -- Trending, Sideways, Volatile, etc.
        Volatility DECIMAL(10,4),
        TrendStrength DECIMAL(10,4),
        VIXAverage DECIMAL(10,2),
        Characteristics NVARCHAR(MAX), -- JSON with detailed characteristics
        CreatedAt DATETIME DEFAULT GETDATE(),
        INDEX IX_MarketRegimes_Dates (StartDate, EndDate)
    );
END
GO

-- Signal Combinations
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'SignalCombinations')
BEGIN
    CREATE TABLE SignalCombinations (
        Id INT PRIMARY KEY IDENTITY(1,1),
        CombinationId VARCHAR(50) UNIQUE,
        Signals VARCHAR(100), -- Comma-separated signal types
        Rules NVARCHAR(MAX), -- JSON with combination rules
        BacktestResults NVARCHAR(MAX), -- JSON with performance metrics
        WinRate DECIMAL(5,2),
        ProfitFactor DECIMAL(10,2),
        SharpeRatio DECIMAL(10,4),
        DiscoveredAt DATETIME,
        Status VARCHAR(20),
        CreatedAt DATETIME DEFAULT GETDATE(),
        INDEX IX_SignalCombinations_WinRate (WinRate DESC)
    );
END
GO

-- Create stored procedure for ML prediction logging
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_LogMLPrediction')
    DROP PROCEDURE sp_LogMLPrediction
GO

CREATE PROCEDURE sp_LogMLPrediction
    @SignalId VARCHAR(50),
    @SignalType VARCHAR(10),
    @PredictedProbability DECIMAL(5,4),
    @PredictedStopLoss DECIMAL(18,2),
    @ModelVersion VARCHAR(50),
    @ModelType VARCHAR(50),
    @Features NVARCHAR(MAX)
AS
BEGIN
    INSERT INTO MLPredictions (
        SignalId, SignalType, PredictedProbability, 
        PredictedStopLoss, ModelVersion, ModelType, 
        Features, Timestamp, CreatedAt
    )
    VALUES (
        @SignalId, @SignalType, @PredictedProbability,
        @PredictedStopLoss, @ModelVersion, @ModelType,
        @Features, GETDATE(), GETDATE()
    );
    
    SELECT SCOPE_IDENTITY() AS PredictionId;
END
GO

-- Create view for signal performance summary
IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_SignalPerformanceSummary')
    DROP VIEW vw_SignalPerformanceSummary
GO

CREATE VIEW vw_SignalPerformanceSummary AS
SELECT 
    sp.SignalType,
    COUNT(*) as TotalRecords,
    AVG(sp.WinRate) as AvgWinRate,
    AVG(sp.ProfitFactor) as AvgProfitFactor,
    SUM(sp.TotalTrades) as TotalTradesAnalyzed,
    MAX(sp.Date) as LastAnalyzed,
    STRING_AGG(DISTINCT sp.MarketRegime, ', ') as MarketRegimes
FROM SignalPerformance sp
GROUP BY sp.SignalType;
GO

-- Create view for paper trading performance
IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_PaperTradingPerformance')
    DROP VIEW vw_PaperTradingPerformance
GO

CREATE VIEW vw_PaperTradingPerformance AS
SELECT 
    pt.SignalType,
    COUNT(*) as TotalTrades,
    SUM(CASE WHEN pt.PnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
    SUM(CASE WHEN pt.PnL <= 0 THEN 1 ELSE 0 END) as LosingTrades,
    CAST(SUM(CASE WHEN pt.PnL > 0 THEN 1 ELSE 0 END) AS FLOAT) / NULLIF(COUNT(*), 0) * 100 as WinRate,
    SUM(pt.PnL) as TotalPnL,
    AVG(pt.PnL) as AvgPnL,
    AVG(pt.MLPrediction) as AvgMLPrediction,
    MIN(pt.EntryTime) as FirstTrade,
    MAX(pt.EntryTime) as LastTrade
FROM PaperTrades pt
WHERE pt.Status = 'CLOSED'
GROUP BY pt.SignalType;
GO

PRINT 'ML and Paper Trading tables created successfully';