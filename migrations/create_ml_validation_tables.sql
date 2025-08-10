-- ML Validation Tables for Comprehensive Backtesting
-- Database: KiteConnectApi
-- Purpose: Store validation runs, minute-by-minute P&L, hedge analysis, and market classification

-- 1. Main Validation Runs Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLValidationRuns')
BEGIN
    CREATE TABLE MLValidationRuns (
        Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        RunDate DATETIME NOT NULL,
        FromDate DATE NOT NULL,
        ToDate DATE NOT NULL,
        Parameters NVARCHAR(MAX), -- JSON with request parameters
        Status VARCHAR(50) NOT NULL, -- PROCESSING, COMPLETED, FAILED
        SlippageModel VARCHAR(50),
        CommissionModel VARCHAR(50),
        Results NVARCHAR(MAX), -- JSON with summary results
        CreatedAt DATETIME DEFAULT GETDATE(),
        CompletedAt DATETIME,
        INDEX IX_MLValidationRuns_Status (Status),
        INDEX IX_MLValidationRuns_Dates (FromDate, ToDate)
    );
END
GO

-- 2. Minute-by-Minute P&L Tracking Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLMinutePnL')
BEGIN
    CREATE TABLE MLMinutePnL (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ValidationRunId UNIQUEIDENTIFIER NOT NULL,
        TradeId VARCHAR(50) NOT NULL,
        SignalType VARCHAR(10),
        Timestamp DATETIME NOT NULL,
        MainLegPrice DECIMAL(18,2),
        HedgeLegPrice DECIMAL(18,2),
        CombinedPnL DECIMAL(18,2),
        Slippage DECIMAL(18,2),
        Commission DECIMAL(18,2),
        NetPnL DECIMAL(18,2),
        MaxProfitSoFar DECIMAL(18,2),
        MaxDrawdownSoFar DECIMAL(18,2),
        FOREIGN KEY (ValidationRunId) REFERENCES MLValidationRuns(Id),
        INDEX IX_MLMinutePnL_ValidationRun (ValidationRunId),
        INDEX IX_MLMinutePnL_TradeId (TradeId),
        INDEX IX_MLMinutePnL_Timestamp (Timestamp)
    );
END
GO

-- 3. Hedge Analysis Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLHedgeAnalysis')
BEGIN
    CREATE TABLE MLHedgeAnalysis (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ValidationRunId UNIQUEIDENTIFIER NOT NULL,
        TradeId VARCHAR(50) NOT NULL,
        SignalType VARCHAR(10) NOT NULL,
        TradeDate DATE,
        HedgeDistance INT NOT NULL,
        HedgeRatio DECIMAL(5,2) DEFAULT 1.0,
        MainStrike INT,
        HedgeStrike INT,
        MainEntryPrice DECIMAL(18,2),
        HedgeEntryPrice DECIMAL(18,2),
        MainExitPrice DECIMAL(18,2),
        HedgeExitPrice DECIMAL(18,2),
        MainPnL DECIMAL(18,2),
        HedgePnL DECIMAL(18,2),
        HedgeDecay DECIMAL(18,2), -- Theta decay of hedge
        ImpliedVolatility DECIMAL(18,2), -- IV at entry
        NetPnL DECIMAL(18,2),
        OTMProbability DECIMAL(5,2), -- Probability of OTM becoming ITM
        OTMPenalty DECIMAL(18,2), -- Additional loss if OTM becomes ITM
        ExpectedCost DECIMAL(18,2), -- Expected cost of hedge
        SharpeRatio DECIMAL(10,4),
        SortinoRatio DECIMAL(10,4),
        FOREIGN KEY (ValidationRunId) REFERENCES MLValidationRuns(Id),
        INDEX IX_MLHedgeAnalysis_ValidationRun (ValidationRunId),
        INDEX IX_MLHedgeAnalysis_Signal (SignalType),
        INDEX IX_MLHedgeAnalysis_HedgeDistance (HedgeDistance)
    );
END
GO

-- 4. Market Regime Classification Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLMarketRegime')
BEGIN
    CREATE TABLE MLMarketRegime (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ValidationRunId UNIQUEIDENTIFIER NOT NULL,
        TradeId VARCHAR(50) NOT NULL,
        SignalType VARCHAR(10),
        EntryTime DATETIME NOT NULL,
        ExitTime DATETIME NOT NULL,
        EntryNiftyPrice DECIMAL(18,2),
        ExitNiftyPrice DECIMAL(18,2),
        HighPrice DECIMAL(18,2),
        HighTime DATETIME,
        LowPrice DECIMAL(18,2),
        LowTime DATETIME,
        TotalMovement DECIMAL(18,2),
        DirectionalMove DECIMAL(18,2),
        TrendClassification VARCHAR(50), -- STRONG_UP, WEAK_UP, SIDEWAYS, WEAK_DOWN, STRONG_DOWN
        VolatilityRegime VARCHAR(20), -- HIGH, MEDIUM, LOW
        ATR DECIMAL(18,2), -- Average True Range
        ADX DECIMAL(18,2), -- Average Directional Index
        MarketBreadth DECIMAL(18,2),
        HourlyPath NVARCHAR(MAX), -- JSON with hourly OHLC data
        FOREIGN KEY (ValidationRunId) REFERENCES MLValidationRuns(Id),
        INDEX IX_MLMarketRegime_ValidationRun (ValidationRunId),
        INDEX IX_MLMarketRegime_Classification (TrendClassification)
    );
END
GO

-- 5. Breakeven Analysis Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLBreakevenAnalysis')
BEGIN
    CREATE TABLE MLBreakevenAnalysis (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ValidationRunId UNIQUEIDENTIFIER NOT NULL,
        TradeId VARCHAR(50) NOT NULL,
        SignalType VARCHAR(10),
        EntryTime DATETIME,
        FirstBreakevenTime DATETIME, -- When P&L first becomes positive
        MinutesToBreakeven INT,
        MaxProfit DECIMAL(18,2),
        MaxProfitTime DATETIME,
        MaxDrawdown DECIMAL(18,2),
        MaxDrawdownTime DATETIME,
        Strategy VARCHAR(100), -- e.g., "20% profit + 4 hours"
        ProfitThreshold DECIMAL(5,2), -- Percentage
        TimeThreshold INT, -- Minutes
        WouldHitStopLoss BIT,
        FinalPnL DECIMAL(18,2),
        IsOptimal BIT DEFAULT 0,
        FOREIGN KEY (ValidationRunId) REFERENCES MLValidationRuns(Id),
        INDEX IX_MLBreakevenAnalysis_ValidationRun (ValidationRunId),
        INDEX IX_MLBreakevenAnalysis_Signal (SignalType)
    );
END
GO

-- 6. Early Exit Analysis Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLEarlyExitAnalysis')
BEGIN
    CREATE TABLE MLEarlyExitAnalysis (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ValidationRunId UNIQUEIDENTIFIER NOT NULL,
        TradeId VARCHAR(50) NOT NULL,
        SignalType VARCHAR(10),
        EntryDate DATE,
        ActualExitDate DATE,
        ActualExitTime DATETIME,
        ActualPnL DECIMAL(18,2),
        MondayExitTime DATETIME,
        MondayPnL DECIMAL(18,2),
        MondayMainPrice DECIMAL(18,2),
        MondayHedgePrice DECIMAL(18,2),
        TuesdayExitTime DATETIME,
        TuesdayPnL DECIMAL(18,2),
        TuesdayMainPrice DECIMAL(18,2),
        TuesdayHedgePrice DECIMAL(18,2),
        WednesdayExitTime DATETIME,
        WednesdayPnL DECIMAL(18,2),
        WednesdayMainPrice DECIMAL(18,2),
        WednesdayHedgePrice DECIMAL(18,2),
        ThursdayExitTime DATETIME,
        ThursdayPnL DECIMAL(18,2),
        ThursdayMainPrice DECIMAL(18,2),
        ThursdayHedgePrice DECIMAL(18,2),
        OptimalExitDay VARCHAR(20),
        ThetaDecayPattern NVARCHAR(MAX), -- JSON with daily theta decay
        FOREIGN KEY (ValidationRunId) REFERENCES MLValidationRuns(Id),
        INDEX IX_MLEarlyExitAnalysis_ValidationRun (ValidationRunId),
        INDEX IX_MLEarlyExitAnalysis_Signal (SignalType)
    );
END
GO

-- 7. Signal Overlap Tracking Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLSignalOverlap')
BEGIN
    CREATE TABLE MLSignalOverlap (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ValidationRunId UNIQUEIDENTIFIER NOT NULL,
        Timestamp DATETIME NOT NULL,
        TriggeredSignals VARCHAR(100), -- Comma-separated list of signals
        HandlingMethod VARCHAR(50), -- SKIP, TAKE_ALL, TAKE_FIRST
        Outcome VARCHAR(200),
        Notes NVARCHAR(MAX),
        FOREIGN KEY (ValidationRunId) REFERENCES MLValidationRuns(Id),
        INDEX IX_MLSignalOverlap_ValidationRun (ValidationRunId),
        INDEX IX_MLSignalOverlap_Timestamp (Timestamp)
    );
END
GO

-- 8. Stress Test Results Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLStressTestResults')
BEGIN
    CREATE TABLE MLStressTestResults (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ValidationRunId UNIQUEIDENTIFIER NOT NULL,
        ScenarioName VARCHAR(100), -- Flash Crash, Gap Down, Circuit Breaker
        SignalType VARCHAR(10),
        SimulatedLoss DECIMAL(18,2),
        SurvivalRate DECIMAL(5,2),
        RecoveryTime INT, -- Minutes to recover
        ImpactDescription NVARCHAR(MAX),
        FOREIGN KEY (ValidationRunId) REFERENCES MLValidationRuns(Id),
        INDEX IX_MLStressTestResults_ValidationRun (ValidationRunId),
        INDEX IX_MLStressTestResults_Scenario (ScenarioName)
    );
END
GO

-- 9. Gemini Analysis Results Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLGeminiAnalysis')
BEGIN
    CREATE TABLE MLGeminiAnalysis (
        Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        ValidationRunId UNIQUEIDENTIFIER NOT NULL,
        RequestData NVARCHAR(MAX), -- What we sent to Gemini
        ResponseData NVARCHAR(MAX), -- Full response from Gemini
        Recommendations NVARCHAR(MAX), -- Extracted recommendations
        HedgeRecommendation NVARCHAR(500),
        ExitStrategyRecommendation NVARCHAR(500),
        BreakevenRecommendation NVARCHAR(500),
        SignalPriority NVARCHAR(200),
        ActionableInsights NVARCHAR(MAX),
        CreatedAt DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (ValidationRunId) REFERENCES MLValidationRuns(Id),
        INDEX IX_MLGeminiAnalysis_ValidationRun (ValidationRunId)
    );
END
GO

-- 10. Performance Metrics Summary Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MLPerformanceMetrics')
BEGIN
    CREATE TABLE MLPerformanceMetrics (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ValidationRunId UNIQUEIDENTIFIER NOT NULL,
        SignalType VARCHAR(10),
        TotalTrades INT,
        WinningTrades INT,
        LosingTrades INT,
        WinRate DECIMAL(5,2),
        AvgPnL DECIMAL(18,2),
        MaxPnL DECIMAL(18,2),
        MinPnL DECIMAL(18,2),
        StdPnL DECIMAL(18,2),
        SharpeRatio DECIMAL(10,4),
        SortinoRatio DECIMAL(10,4),
        MaxDrawdown DECIMAL(18,2),
        CalmarRatio DECIMAL(10,4),
        Expectancy DECIMAL(18,2),
        ProfitFactor DECIMAL(10,4),
        RecoveryFactor DECIMAL(10,4),
        TotalSlippage DECIMAL(18,2),
        TotalCommission DECIMAL(18,2),
        FOREIGN KEY (ValidationRunId) REFERENCES MLValidationRuns(Id),
        INDEX IX_MLPerformanceMetrics_ValidationRun (ValidationRunId),
        INDEX IX_MLPerformanceMetrics_Signal (SignalType)
    );
END
GO

-- Create Views for Easy Analysis

-- View for Signal Performance Summary
IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_MLSignalPerformance')
    DROP VIEW vw_MLSignalPerformance
GO

CREATE VIEW vw_MLSignalPerformance AS
SELECT 
    pm.SignalType,
    COUNT(DISTINCT pm.ValidationRunId) as TotalRuns,
    AVG(pm.WinRate) as AvgWinRate,
    AVG(pm.AvgPnL) as AvgPnL,
    AVG(pm.SharpeRatio) as AvgSharpeRatio,
    AVG(pm.MaxDrawdown) as AvgMaxDrawdown,
    MIN(pm.MinPnL) as WorstLoss,
    MAX(pm.MaxPnL) as BestGain
FROM MLPerformanceMetrics pm
GROUP BY pm.SignalType;
GO

-- View for Hedge Distance Performance
IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_MLHedgePerformance')
    DROP VIEW vw_MLHedgePerformance
GO

CREATE VIEW vw_MLHedgePerformance AS
SELECT 
    ha.HedgeDistance,
    ha.SignalType,
    COUNT(*) as TradeCount,
    AVG(ha.NetPnL) as AvgNetPnL,
    AVG(ha.OTMPenalty) as AvgOTMPenalty,
    AVG(ha.SharpeRatio) as AvgSharpeRatio,
    SUM(CASE WHEN ha.NetPnL > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as WinRate
FROM MLHedgeAnalysis ha
GROUP BY ha.HedgeDistance, ha.SignalType;
GO

-- View for Market Regime Performance
IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_MLMarketRegimePerformance')
    DROP VIEW vw_MLMarketRegimePerformance
GO

CREATE VIEW vw_MLMarketRegimePerformance AS
SELECT 
    mr.TrendClassification,
    mr.VolatilityRegime,
    COUNT(*) as TradeCount,
    AVG(ha.NetPnL) as AvgPnL,
    MIN(ha.NetPnL) as MinPnL,
    MAX(ha.NetPnL) as MaxPnL
FROM MLMarketRegime mr
JOIN MLHedgeAnalysis ha ON mr.TradeId = ha.TradeId AND mr.ValidationRunId = ha.ValidationRunId
GROUP BY mr.TrendClassification, mr.VolatilityRegime;
GO

-- Stored Procedure to Get Validation Summary
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_GetMLValidationSummary')
    DROP PROCEDURE sp_GetMLValidationSummary
GO

CREATE PROCEDURE sp_GetMLValidationSummary
    @ValidationRunId UNIQUEIDENTIFIER
AS
BEGIN
    -- Get run details
    SELECT * FROM MLValidationRuns WHERE Id = @ValidationRunId;
    
    -- Get performance metrics
    SELECT * FROM MLPerformanceMetrics WHERE ValidationRunId = @ValidationRunId;
    
    -- Get hedge analysis summary
    SELECT 
        HedgeDistance,
        COUNT(*) as TradeCount,
        AVG(NetPnL) as AvgPnL,
        AVG(OTMPenalty) as AvgPenalty
    FROM MLHedgeAnalysis 
    WHERE ValidationRunId = @ValidationRunId
    GROUP BY HedgeDistance;
    
    -- Get market regime summary
    SELECT 
        TrendClassification,
        COUNT(*) as Count
    FROM MLMarketRegime
    WHERE ValidationRunId = @ValidationRunId
    GROUP BY TrendClassification;
    
    -- Get signal overlap events
    SELECT * FROM MLSignalOverlap WHERE ValidationRunId = @ValidationRunId;
END
GO

PRINT 'ML Validation tables created successfully';
PRINT 'Views created for analysis';
PRINT 'Stored procedures created for reporting';