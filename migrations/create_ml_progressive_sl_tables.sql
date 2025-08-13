-- ML Progressive P&L Stop-Loss Tables
-- Created: 2025-08-12
-- Purpose: Support ML-enhanced progressive stop-loss with decision attribution

-- Table for ML backtest runs with progressive SL
CREATE TABLE MLBacktestRunsProgressiveSL (
    Id VARCHAR(50) PRIMARY KEY,
    Name VARCHAR(200) NOT NULL,
    FromDate DATETIME NOT NULL,
    ToDate DATETIME NOT NULL,
    InitialCapital DECIMAL(18,2) NOT NULL,
    LotSize INT NOT NULL DEFAULT 75,
    LotsToTrade INT NOT NULL DEFAULT 10,
    
    -- ML Configuration
    UseMLExits BIT NOT NULL DEFAULT 1,
    UseTrailingStops BIT NOT NULL DEFAULT 1,
    UseProfitTargets BIT NOT NULL DEFAULT 1,
    UsePositionAdjustments BIT NOT NULL DEFAULT 1,
    UseRegimeFilter BIT NOT NULL DEFAULT 1,
    MLConfidenceThreshold DECIMAL(5,4) NOT NULL DEFAULT 0.7,
    
    -- Progressive SL Configuration
    UseProgressiveSL BIT NOT NULL DEFAULT 1,
    InitialSLPerLot DECIMAL(18,2) NOT NULL DEFAULT 6000,
    ProfitTriggerPercent DECIMAL(5,2) DEFAULT 40,
    Day2SLFactor DECIMAL(5,2) DEFAULT 0.5,
    Day3Breakeven BIT DEFAULT 1,
    Day4ProfitLockPercent DECIMAL(5,2) DEFAULT 5,
    
    -- ML-Enhanced Progressive SL
    MLOptimizeSLRules BIT DEFAULT 0,
    AdaptiveSLEnabled BIT DEFAULT 0,
    SignalSpecificSL BIT DEFAULT 0,
    
    -- Status and Results
    Status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    StartedAt DATETIME NULL,
    CompletedAt DATETIME NULL,
    ErrorMessage NVARCHAR(MAX) NULL,
    
    -- Performance Metrics
    TotalTrades INT NOT NULL DEFAULT 0,
    MLTriggeredExits INT DEFAULT 0,
    ProgressiveSLExits INT DEFAULT 0,
    HybridExits INT DEFAULT 0,
    
    -- Financial Results
    FinalCapital DECIMAL(18,2) NULL,
    TotalPnL DECIMAL(18,2) NULL,
    MLDecisionPnL DECIMAL(18,2) NULL,
    ProgressiveSLPnL DECIMAL(18,2) NULL,
    HybridDecisionPnL DECIMAL(18,2) NULL,
    
    -- Accuracy Metrics
    MLAccuracy DECIMAL(5,2) NULL,
    ProgressiveSLAccuracy DECIMAL(5,2) NULL,
    HybridAccuracy DECIMAL(5,2) NULL,
    
    -- Metadata
    CreatedAt DATETIME NOT NULL DEFAULT GETDATE(),
    CreatedBy VARCHAR(100) NOT NULL DEFAULT 'System'
);

-- Table for ML decision attribution
CREATE TABLE MLDecisionAttribution (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    BacktestRunId VARCHAR(50) NOT NULL,
    TradeId VARCHAR(50) NOT NULL,
    DecisionTime DATETIME NOT NULL,
    
    -- Decision Details
    DecisionType VARCHAR(50) NOT NULL, -- ML_PREDICTED, PROGRESSIVE_SL, HYBRID_CONSENSUS, etc.
    DecisionMade VARCHAR(20) NOT NULL, -- EXIT, HOLD, PARTIAL_EXIT
    Confidence DECIMAL(5,4) NOT NULL,
    
    -- ML Prediction
    MLShouldExit BIT NOT NULL,
    MLConfidence DECIMAL(5,4) NOT NULL,
    MLReason VARCHAR(200) NULL,
    MLPartialExitPercent DECIMAL(5,2) NULL,
    
    -- Progressive SL Status
    PSLHit BIT NOT NULL,
    PSLStage VARCHAR(20) NOT NULL,
    PSLCurrentLevel DECIMAL(18,2) NOT NULL,
    PSLReason VARCHAR(200) NULL,
    
    -- Market Context
    CurrentPnL DECIMAL(18,2) NOT NULL,
    MaxProfitSeen DECIMAL(18,2) NOT NULL,
    NiftyIndex DECIMAL(18,2) NOT NULL,
    DaysSinceEntry INT NOT NULL,
    
    -- Outcome
    WasCorrect BIT NULL, -- Set after trade closes
    ResultingPnL DECIMAL(18,2) NULL,
    
    CreatedAt DATETIME DEFAULT GETDATE(),
    
    FOREIGN KEY (BacktestRunId) REFERENCES MLBacktestRunsProgressiveSL(Id)
);

-- Create indexes for performance
CREATE INDEX IX_MLDecisionAttribution_BacktestRunId ON MLDecisionAttribution(BacktestRunId);
CREATE INDEX IX_MLDecisionAttribution_TradeId ON MLDecisionAttribution(TradeId);
CREATE INDEX IX_MLDecisionAttribution_DecisionType ON MLDecisionAttribution(DecisionType);

-- Table for ML-optimized progressive SL parameters
CREATE TABLE MLOptimizedSLParameters (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    SignalType VARCHAR(10) NOT NULL,
    MarketRegime VARCHAR(20) NULL, -- TRENDING, RANGING, VOLATILE
    OptimizationDate DATETIME NOT NULL,
    
    -- Optimized Parameters
    InitialSLPerLot DECIMAL(18,2) NOT NULL,
    ProfitTriggerPercent DECIMAL(5,2) NOT NULL,
    Day2SLFactor DECIMAL(5,2) NOT NULL,
    Day3Breakeven BIT NOT NULL,
    Day4ProfitLockPercent DECIMAL(5,2) NOT NULL,
    
    -- ML Model Metrics
    ModelConfidence DECIMAL(5,4) NOT NULL,
    TrainingDataSize INT NOT NULL,
    ModelMAE DECIMAL(18,2) NULL,
    
    -- Feature Importance
    TopFeature1 VARCHAR(50) NULL,
    TopFeature1Importance DECIMAL(5,4) NULL,
    TopFeature2 VARCHAR(50) NULL,
    TopFeature2Importance DECIMAL(5,4) NULL,
    TopFeature3 VARCHAR(50) NULL,
    TopFeature3Importance DECIMAL(5,4) NULL,
    
    -- Performance Metrics
    ExpectedWinRate DECIMAL(5,2) NULL,
    ExpectedAvgPnL DECIMAL(18,2) NULL,
    ExpectedMaxDrawdown DECIMAL(18,2) NULL,
    
    -- Validation
    IsActive BIT DEFAULT 1,
    ValidatedOn DATETIME NULL,
    ValidationScore DECIMAL(5,2) NULL,
    
    CreatedAt DATETIME DEFAULT GETDATE()
);

-- Create unique index for active parameters per signal and regime
CREATE UNIQUE INDEX UQ_MLOptimizedSL_Active 
ON MLOptimizedSLParameters(SignalType, MarketRegime, IsActive) 
WHERE IsActive = 1;

-- Table for ML minute-level P&L tracking
CREATE TABLE MLMinutePnL (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    TradeId VARCHAR(50) NOT NULL,
    Timestamp DATETIME NOT NULL,
    
    -- Option Prices
    MainLegPrice DECIMAL(18,2) NOT NULL,
    HedgeLegPrice DECIMAL(18,2) NOT NULL,
    
    -- P&L Calculation
    MainLegPnL DECIMAL(18,2) NOT NULL,
    HedgeLegPnL DECIMAL(18,2) NOT NULL,
    NetPnL DECIMAL(18,2) NOT NULL,
    
    -- ML Predictions at this time
    MLExitProbability DECIMAL(5,4) NULL,
    MLSuggestedAction VARCHAR(20) NULL,
    
    -- Progressive SL Status
    PSLLevel DECIMAL(18,2) NOT NULL,
    PSLStage VARCHAR(20) NOT NULL,
    
    -- Decision Made
    DecisionMade VARCHAR(50) NULL,
    DecisionConfidence DECIMAL(5,4) NULL,
    
    CreatedAt DATETIME DEFAULT GETDATE()
);

-- Create indexes for minute P&L queries
CREATE INDEX IX_MLMinutePnL_TradeId ON MLMinutePnL(TradeId);
CREATE INDEX IX_MLMinutePnL_Timestamp ON MLMinutePnL(Timestamp);

-- Table for comparing ML vs Progressive SL performance
CREATE TABLE MLProgressiveSLComparison (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    BacktestRunId VARCHAR(50) NOT NULL,
    ComparisonDate DATETIME NOT NULL,
    
    -- ML-Only Performance
    ML_TotalPnL DECIMAL(18,2),
    ML_MaxDrawdown DECIMAL(18,2),
    ML_WinRate DECIMAL(5,2),
    ML_AvgHoldTime INT, -- minutes
    ML_TradeCount INT,
    
    -- Progressive SL Only Performance
    PSL_TotalPnL DECIMAL(18,2),
    PSL_MaxDrawdown DECIMAL(18,2),
    PSL_WinRate DECIMAL(5,2),
    PSL_AvgHoldTime INT,
    PSL_TradeCount INT,
    
    -- Hybrid Performance
    Hybrid_TotalPnL DECIMAL(18,2),
    Hybrid_MaxDrawdown DECIMAL(18,2),
    Hybrid_WinRate DECIMAL(5,2),
    Hybrid_AvgHoldTime INT,
    Hybrid_TradeCount INT,
    
    -- Improvement Metrics
    HybridVsML_PnLImprovement DECIMAL(18,2),
    HybridVsPSL_PnLImprovement DECIMAL(18,2),
    HybridVsML_DrawdownReduction DECIMAL(18,2),
    HybridVsPSL_DrawdownReduction DECIMAL(18,2),
    
    -- Decision Attribution
    MLBetterCount INT,
    PSLBetterCount INT,
    HybridBetterCount INT,
    
    CreatedAt DATETIME DEFAULT GETDATE()
);

-- Table for regime-specific performance tracking
CREATE TABLE MLRegimePerformance (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    BacktestRunId VARCHAR(50) NOT NULL,
    MarketRegime VARCHAR(20) NOT NULL,
    PeriodStart DATETIME NOT NULL,
    PeriodEnd DATETIME NOT NULL,
    
    -- Performance in this regime
    TradeCount INT NOT NULL,
    WinRate DECIMAL(5,2) NOT NULL,
    AvgPnL DECIMAL(18,2) NOT NULL,
    MaxDrawdown DECIMAL(18,2) NOT NULL,
    
    -- Decision Performance
    MLDecisionAccuracy DECIMAL(5,2) NULL,
    PSLDecisionAccuracy DECIMAL(5,2) NULL,
    HybridDecisionAccuracy DECIMAL(5,2) NULL,
    
    -- Optimal Parameters for Regime
    OptimalProfitTrigger DECIMAL(5,2) NULL,
    OptimalDay2Factor DECIMAL(5,2) NULL,
    OptimalMLThreshold DECIMAL(5,4) NULL,
    
    CreatedAt DATETIME DEFAULT GETDATE()
);

-- Grant permissions if needed
-- GRANT SELECT, INSERT, UPDATE ON MLBacktestRunsProgressiveSL TO [your_user];
-- GRANT SELECT, INSERT, UPDATE ON MLDecisionAttribution TO [your_user];
-- GRANT SELECT, INSERT, UPDATE ON MLOptimizedSLParameters TO [your_user];
-- GRANT SELECT, INSERT, UPDATE ON MLMinutePnL TO [your_user];
-- GRANT SELECT, INSERT, UPDATE ON MLProgressiveSLComparison TO [your_user];
-- GRANT SELECT, INSERT, UPDATE ON MLRegimePerformance TO [your_user];