-- Fixed TradingView Signal Detection Implementation
-- Corrected date arithmetic issues

-- Drop and recreate table
IF OBJECT_ID('SignalAnalysis', 'U') IS NOT NULL
    DROP TABLE SignalAnalysis;

CREATE TABLE SignalAnalysis (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    WeekStartDate DATE NOT NULL,
    WeekEndDate DATE NOT NULL,
    
    -- Previous Week Data
    PrevWeekHigh DECIMAL(18,2),
    PrevWeekLow DECIMAL(18,2),
    PrevWeekClose DECIMAL(18,2),
    PrevWeek4HMaxBody DECIMAL(18,2),
    PrevWeek4HMinBody DECIMAL(18,2),
    
    -- Zone Calculations
    ResistanceZoneTop DECIMAL(18,2),
    ResistanceZoneBottom DECIMAL(18,2),
    SupportZoneTop DECIMAL(18,2),
    SupportZoneBottom DECIMAL(18,2),
    MarginHigh DECIMAL(18,2),
    MarginLow DECIMAL(18,2),
    
    -- Weekly Bias
    WeeklyBias VARCHAR(10),
    
    -- First Hour Candle
    FirstHourTime DATETIME,
    FirstHourOpen DECIMAL(18,2),
    FirstHourHigh DECIMAL(18,2),
    FirstHourLow DECIMAL(18,2),
    FirstHourClose DECIMAL(18,2),
    
    -- Signal Information
    SignalType VARCHAR(10),
    SignalTriggeredTime DATETIME,
    EntryTime DATETIME,
    EntryPrice DECIMAL(18,2),
    
    -- Candle Details
    FirstCandleOpen DECIMAL(18,2),
    FirstCandleHigh DECIMAL(18,2),
    FirstCandleLow DECIMAL(18,2),
    FirstCandleClose DECIMAL(18,2),
    
    SecondCandleOpen DECIMAL(18,2),
    SecondCandleHigh DECIMAL(18,2),
    SecondCandleLow DECIMAL(18,2),
    SecondCandleClose DECIMAL(18,2),
    
    EntryCandleOpen DECIMAL(18,2),
    EntryCandleHigh DECIMAL(18,2),
    EntryCandleLow DECIMAL(18,2),
    EntryCandleClose DECIMAL(18,2),
    
    -- Stop Loss and Strike Information
    StopLossPrice DECIMAL(18,2),
    MainStrikePrice INT,
    OptionType VARCHAR(2),
    
    -- Hedge Strike Options
    HedgeStrike100Away INT,
    HedgeStrike150Away INT,
    HedgeStrike200Away INT,
    HedgeStrike300Away INT,
    
    -- Stop Loss Hit Information
    StopLossHit BIT DEFAULT 0,
    StopLossHitTime DATETIME,
    StopLossHitCandleOpen DECIMAL(18,2),
    StopLossHitCandleHigh DECIMAL(18,2),
    StopLossHitCandleLow DECIMAL(18,2),
    StopLossHitCandleClose DECIMAL(18,2),
    
    -- Final Outcome
    WeeklyOutcome VARCHAR(10),
    
    INDEX IX_WeekStart (WeekStartDate),
    INDEX IX_SignalType (SignalType),
    INDEX IX_EntryTime (EntryTime)
);

GO

-- Test with just 2025 data first
DECLARE @StartDate DATE = '2025-01-01';
DECLARE @EndDate DATE = '2025-12-31';

-- Get week boundaries and previous week data
WITH WeekData AS (
    SELECT 
        DATEADD(day, 2 - DATEPART(dw, CAST(Timestamp as DATE)), CAST(Timestamp as DATE)) as WeekStart,
        MAX(High) as WeekHigh,
        MIN(Low) as WeekLow,
        MAX([Open]) as WeekOpen,
        MAX([Close]) as WeekClose
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= DATEADD(day, -14, @StartDate) AND Timestamp <= @EndDate
    GROUP BY DATEADD(day, 2 - DATEPART(dw, CAST(Timestamp as DATE)), CAST(Timestamp as DATE))
),
-- Get candles for analysis
TestWeek AS (
    SELECT TOP 7 * FROM NiftyIndexDataHourly
    WHERE Timestamp >= '2025-01-13' AND Timestamp < '2025-01-18'
    ORDER BY Timestamp
)
SELECT 
    ROW_NUMBER() OVER (ORDER BY Timestamp) as CandleNum,
    Timestamp,
    [Open],
    High,
    Low,
    [Close],
    'First week should have S7' as Note
FROM TestWeek;

-- Let me run a simpler detection first
WITH SimpleDetection AS (
    SELECT 
        h.*,
        DATEADD(day, 2 - DATEPART(dw, CAST(h.Timestamp as DATE)), CAST(h.Timestamp as DATE)) as WeekStart,
        ROW_NUMBER() OVER (PARTITION BY DATEADD(day, 2 - DATEPART(dw, CAST(h.Timestamp as DATE)), CAST(h.Timestamp as DATE)) ORDER BY h.Timestamp) as CandleNum
    FROM NiftyIndexDataHourly h
    WHERE h.Timestamp >= '2025-01-01' AND h.Timestamp <= '2025-01-31'
),
FirstCandles AS (
    SELECT 
        WeekStart,
        MAX(CASE WHEN CandleNum = 1 THEN [Open] END) as FirstOpen,
        MAX(CASE WHEN CandleNum = 1 THEN High END) as FirstHigh,
        MAX(CASE WHEN CandleNum = 1 THEN Low END) as FirstLow,
        MAX(CASE WHEN CandleNum = 1 THEN [Close] END) as FirstClose,
        MAX(CASE WHEN CandleNum = 2 THEN [Open] END) as SecondOpen,
        MAX(CASE WHEN CandleNum = 2 THEN High END) as SecondHigh,
        MAX(CASE WHEN CandleNum = 2 THEN Low END) as SecondLow,
        MAX(CASE WHEN CandleNum = 2 THEN [Close] END) as SecondClose
    FROM SimpleDetection
    GROUP BY WeekStart
)
SELECT 
    WeekStart,
    'First: ' + CAST(FirstOpen as VARCHAR) + '/' + CAST(FirstClose as VARCHAR) as FirstCandle,
    'Second: ' + CAST(SecondOpen as VARCHAR) + '/' + CAST(SecondClose as VARCHAR) as SecondCandle
FROM FirstCandles
ORDER BY WeekStart;