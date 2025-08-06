-- Fixed Signal Analysis Script
-- This combines all scripts with corrections for SQL Server compatibility

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

-- Process the data
DECLARE @StartDate DATE = '2022-01-01';
DECLARE @EndDate DATE = GETDATE();

-- Get all weeks with proper Monday start
WITH AllDates AS (
    SELECT DISTINCT CAST(Timestamp AS DATE) as TradingDate
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= @StartDate AND Timestamp <= @EndDate
),
WeekStarts AS (
    SELECT DISTINCT
        CASE 
            WHEN DATEPART(dw, TradingDate) = 2 THEN TradingDate  -- Monday
            WHEN DATEPART(dw, TradingDate) = 3 THEN DATEADD(day, -1, TradingDate)  -- Tuesday -> Monday
            WHEN DATEPART(dw, TradingDate) = 4 THEN DATEADD(day, -2, TradingDate)  -- Wednesday -> Monday
            WHEN DATEPART(dw, TradingDate) = 5 THEN DATEADD(day, -3, TradingDate)  -- Thursday -> Monday
            WHEN DATEPART(dw, TradingDate) = 6 THEN DATEADD(day, -4, TradingDate)  -- Friday -> Monday
        END as WeekStart
    FROM AllDates
    WHERE DATEPART(dw, TradingDate) BETWEEN 2 AND 6
),
WeekBoundaries AS (
    SELECT DISTINCT
        WeekStart,
        DATEADD(day, 4, WeekStart) as WeekEnd
    FROM WeekStarts
    WHERE WeekStart IS NOT NULL
),
-- Calculate previous week data
PreviousWeekData AS (
    SELECT 
        wb.WeekStart,
        wb.WeekEnd,
        MAX(h.High) as PrevWeekHigh,
        MIN(h.Low) as PrevWeekLow,
        -- Get Friday 3:30 PM close
        (SELECT TOP 1 [Close] 
         FROM NiftyIndexDataHourly 
         WHERE CAST(Timestamp as DATE) = DATEADD(day, -3, wb.WeekStart)  -- Previous Friday
           AND DATEPART(hour, Timestamp) = 15
         ORDER BY Timestamp DESC) as PrevWeekClose
    FROM WeekBoundaries wb
    INNER JOIN NiftyIndexDataHourly h 
        ON CAST(h.Timestamp as DATE) >= DATEADD(day, -7, wb.WeekStart)
        AND CAST(h.Timestamp as DATE) < wb.WeekStart
    GROUP BY wb.WeekStart, wb.WeekEnd
),
-- Calculate 4H bodies
FourHourBodies AS (
    SELECT 
        pw.WeekStart,
        pw.WeekEnd,
        pw.PrevWeekHigh,
        pw.PrevWeekLow,
        pw.PrevWeekClose,
        MAX(CASE WHEN h.[Open] > h.[Close] THEN h.[Open] ELSE h.[Close] END) as PrevWeek4HMaxBody,
        MIN(CASE WHEN h.[Open] < h.[Close] THEN h.[Open] ELSE h.[Close] END) as PrevWeek4HMinBody
    FROM PreviousWeekData pw
    INNER JOIN NiftyIndexDataHourly h 
        ON CAST(h.Timestamp as DATE) >= DATEADD(day, -7, pw.WeekStart)
        AND CAST(h.Timestamp as DATE) < pw.WeekStart
    WHERE pw.PrevWeekHigh IS NOT NULL
    GROUP BY pw.WeekStart, pw.WeekEnd, pw.PrevWeekHigh, pw.PrevWeekLow, pw.PrevWeekClose
),
-- Calculate zones and bias
WeeklyZones AS (
    SELECT 
        *,
        -- Resistance Zone
        CASE WHEN PrevWeekHigh >= PrevWeek4HMaxBody THEN PrevWeekHigh ELSE PrevWeek4HMaxBody END as ResistanceZoneTop,
        CASE WHEN PrevWeekHigh <= PrevWeek4HMaxBody THEN PrevWeekHigh ELSE PrevWeek4HMaxBody END as ResistanceZoneBottom,
        -- Support Zone
        CASE WHEN PrevWeekLow >= PrevWeek4HMinBody THEN PrevWeekLow ELSE PrevWeek4HMinBody END as SupportZoneTop,
        CASE WHEN PrevWeekLow <= PrevWeek4HMinBody THEN PrevWeekLow ELSE PrevWeek4HMinBody END as SupportZoneBottom,
        -- Weekly Bias
        CASE 
            WHEN ABS(PrevWeekClose - PrevWeek4HMaxBody) < ABS(PrevWeekClose - PrevWeek4HMinBody) THEN 'BEARISH'
            WHEN ABS(PrevWeekClose - PrevWeek4HMinBody) < ABS(PrevWeekClose - PrevWeek4HMaxBody) THEN 'BULLISH'
            ELSE 'NEUTRAL'
        END as WeeklyBias
    FROM FourHourBodies
    WHERE PrevWeek4HMaxBody IS NOT NULL AND PrevWeek4HMinBody IS NOT NULL
),
-- Get all candles for current week with numbering
CurrentWeekCandles AS (
    SELECT 
        wz.*,
        h.Timestamp,
        h.[Open],
        h.High,
        h.Low,
        h.[Close],
        ROW_NUMBER() OVER (PARTITION BY wz.WeekStart ORDER BY h.Timestamp) as CandleNum
    FROM WeeklyZones wz
    INNER JOIN NiftyIndexDataHourly h 
        ON h.Timestamp >= wz.WeekStart 
        AND h.Timestamp < DATEADD(day, 5, wz.WeekStart)
),
-- Get first and second candle data
CandleData AS (
    SELECT 
        c1.WeekStart,
        c1.WeekEnd,
        c1.PrevWeekHigh,
        c1.PrevWeekLow,
        c1.PrevWeekClose,
        c1.PrevWeek4HMaxBody,
        c1.PrevWeek4HMinBody,
        c1.ResistanceZoneTop,
        c1.ResistanceZoneBottom,
        c1.SupportZoneTop,
        c1.SupportZoneBottom,
        c1.WeeklyBias,
        -- First candle
        c1.Timestamp as FirstHourTime,
        c1.[Open] as FirstCandleOpen,
        c1.High as FirstCandleHigh,
        c1.Low as FirstCandleLow,
        c1.[Close] as FirstCandleClose,
        -- Second candle
        c2.[Open] as SecondCandleOpen,
        c2.High as SecondCandleHigh,
        c2.Low as SecondCandleLow,
        c2.[Close] as SecondCandleClose,
        c2.Timestamp as SecondCandleTime
    FROM CurrentWeekCandles c1
    LEFT JOIN CurrentWeekCandles c2 ON c2.WeekStart = c1.WeekStart AND c2.CandleNum = 2
    WHERE c1.CandleNum = 1
),
-- Detect S1 and S2 signals (2nd candle only)
SimpleSignals AS (
    SELECT 
        cd.*,
        SecondCandleTime as EntryTime,
        SecondCandleClose as EntryPrice,
        SecondCandleOpen as EntryCandleOpen,
        SecondCandleHigh as EntryCandleHigh,
        SecondCandleLow as EntryCandleLow,
        SecondCandleClose as EntryCandleClose,
        CASE
            -- S1: Bear Trap
            WHEN FirstCandleOpen >= SupportZoneBottom
                AND FirstCandleClose < SupportZoneBottom
                AND SecondCandleClose > FirstCandleLow
            THEN 'S1'
            
            -- S2: Support Hold  
            WHEN WeeklyBias = 'BULLISH'
                AND FirstCandleOpen > PrevWeekLow
                AND FirstCandleClose >= SupportZoneBottom
                AND FirstCandleClose >= PrevWeekClose
                AND SecondCandleClose >= FirstCandleLow
                AND SecondCandleClose > PrevWeekClose
                AND SecondCandleClose > SupportZoneBottom
            THEN 'S2'
            
            ELSE NULL
        END as SignalType,
        
        CASE
            -- S1 stop loss
            WHEN FirstCandleOpen >= SupportZoneBottom
                AND FirstCandleClose < SupportZoneBottom
                AND SecondCandleClose > FirstCandleLow
            THEN FirstCandleLow - 5
            
            -- S2 stop loss
            WHEN WeeklyBias = 'BULLISH'
                AND SecondCandleClose > SupportZoneBottom
            THEN SupportZoneBottom
            
            ELSE NULL
        END as StopLossPrice
    FROM CandleData cd
    WHERE SecondCandleTime IS NOT NULL
),
-- Process signals with strikes
SignalsWithStrikes AS (
    SELECT 
        *,
        'PE' as OptionType,  -- S1 and S2 are bullish
        FLOOR(StopLossPrice/50) * 50 as MainStrikePrice
    FROM SimpleSignals
    WHERE SignalType IS NOT NULL
),
-- Add hedge strikes
SignalsWithHedges AS (
    SELECT 
        *,
        MainStrikePrice - 100 as HedgeStrike100Away,
        MainStrikePrice - 150 as HedgeStrike150Away,
        MainStrikePrice - 200 as HedgeStrike200Away,
        MainStrikePrice - 300 as HedgeStrike300Away
    FROM SignalsWithStrikes
),
-- Check for stop loss hits
FinalSignals AS (
    SELECT 
        s.*,
        sl.Timestamp as StopLossHitTime,
        sl.[Open] as StopLossHitCandleOpen,
        sl.High as StopLossHitCandleHigh,
        sl.Low as StopLossHitCandleLow,
        sl.[Close] as StopLossHitCandleClose,
        CASE WHEN sl.Timestamp IS NOT NULL THEN 1 ELSE 0 END as StopLossHit,
        CASE WHEN sl.Timestamp IS NOT NULL THEN 'LOSS' ELSE 'WIN' END as WeeklyOutcome
    FROM SignalsWithHedges s
    OUTER APPLY (
        SELECT TOP 1 *
        FROM NiftyIndexDataHourly h
        WHERE h.Timestamp > s.EntryTime
            AND h.Timestamp < DATEADD(day, 5, s.WeekStart)
            AND h.[Close] < s.StopLossPrice  -- Bullish stop loss
        ORDER BY h.Timestamp
    ) sl
)
-- Insert into table
INSERT INTO SignalAnalysis (
    WeekStartDate, WeekEndDate,
    PrevWeekHigh, PrevWeekLow, PrevWeekClose,
    PrevWeek4HMaxBody, PrevWeek4HMinBody,
    ResistanceZoneTop, ResistanceZoneBottom,
    SupportZoneTop, SupportZoneBottom,
    WeeklyBias,
    FirstHourTime, FirstHourOpen, FirstHourHigh, FirstHourLow, FirstHourClose,
    SignalType, SignalTriggeredTime, EntryTime, EntryPrice,
    FirstCandleOpen, FirstCandleHigh, FirstCandleLow, FirstCandleClose,
    SecondCandleOpen, SecondCandleHigh, SecondCandleLow, SecondCandleClose,
    EntryCandleOpen, EntryCandleHigh, EntryCandleLow, EntryCandleClose,
    StopLossPrice, MainStrikePrice, OptionType,
    HedgeStrike100Away, HedgeStrike150Away, HedgeStrike200Away, HedgeStrike300Away,
    StopLossHit, StopLossHitTime,
    StopLossHitCandleOpen, StopLossHitCandleHigh, StopLossHitCandleLow, StopLossHitCandleClose,
    WeeklyOutcome
)
SELECT 
    WeekStart, WeekEnd,
    PrevWeekHigh, PrevWeekLow, PrevWeekClose,
    PrevWeek4HMaxBody, PrevWeek4HMinBody,
    ResistanceZoneTop, ResistanceZoneBottom,
    SupportZoneTop, SupportZoneBottom,
    WeeklyBias,
    FirstHourTime, FirstCandleOpen, FirstCandleHigh, FirstCandleLow, FirstCandleClose,
    SignalType, EntryTime, EntryTime, EntryPrice,
    FirstCandleOpen, FirstCandleHigh, FirstCandleLow, FirstCandleClose,
    SecondCandleOpen, SecondCandleHigh, SecondCandleLow, SecondCandleClose,
    EntryCandleOpen, EntryCandleHigh, EntryCandleLow, EntryCandleClose,
    StopLossPrice, MainStrikePrice, OptionType,
    HedgeStrike100Away, HedgeStrike150Away, HedgeStrike200Away, HedgeStrike300Away,
    StopLossHit, StopLossHitTime,
    StopLossHitCandleOpen, StopLossHitCandleHigh, StopLossHitCandleLow, StopLossHitCandleClose,
    WeeklyOutcome
FROM FinalSignals;

-- Show summary
PRINT 'Signal Analysis Complete!';
PRINT '';

SELECT 
    'Total Signals Found: ' + CAST(COUNT(*) as VARCHAR) as Summary,
    COUNT(CASE WHEN SignalType = 'S1' THEN 1 END) as S1_Count,
    COUNT(CASE WHEN SignalType = 'S2' THEN 1 END) as S2_Count
FROM SignalAnalysis;

-- Show recent examples
SELECT TOP 5
    WeekStartDate,
    SignalType,
    EntryTime,
    EntryPrice,
    StopLossPrice,
    MainStrikePrice,
    WeeklyOutcome
FROM SignalAnalysis
ORDER BY EntryTime DESC;