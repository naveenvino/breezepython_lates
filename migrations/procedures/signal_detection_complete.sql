-- Complete Signal Detection and Analysis Script
-- This script detects all 8 signals and tracks their outcomes

-- First, ensure the table exists
IF OBJECT_ID('SignalAnalysis', 'U') IS NULL
BEGIN
    PRINT 'Please run create_signal_analysis.sql first to create the table structure';
    RETURN;
END;

-- Clear existing data for fresh analysis
TRUNCATE TABLE SignalAnalysis;

-- Main signal detection and analysis
DECLARE @StartDate DATE = '2022-01-01';
DECLARE @EndDate DATE = GETDATE();

WITH WeekBoundaries AS (
    SELECT DISTINCT
        dbo.GetWeekStart(Timestamp) as WeekStart,
        DATEADD(day, 4, dbo.GetWeekStart(Timestamp)) as WeekEnd
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= @StartDate
        AND Timestamp <= @EndDate
        AND DATEPART(dw, Timestamp) BETWEEN 2 AND 6
),
PreviousWeekData AS (
    SELECT 
        wb.WeekStart,
        wb.WeekEnd,
        MAX(CASE WHEN h.Timestamp >= DATEADD(week, -1, wb.WeekStart) 
                  AND h.Timestamp < wb.WeekStart 
                 THEN h.High END) as PrevWeekHigh,
        MIN(CASE WHEN h.Timestamp >= DATEADD(week, -1, wb.WeekStart) 
                  AND h.Timestamp < wb.WeekStart 
                 THEN h.Low END) as PrevWeekLow,
        MAX(CASE WHEN h.Timestamp >= DATEADD(week, -1, wb.WeekStart) 
                  AND h.Timestamp < wb.WeekStart 
                  AND DATEPART(hour, h.Timestamp) = 15
                 THEN h.[Close] END) as PrevWeekClose
    FROM WeekBoundaries wb
    LEFT JOIN NiftyIndexDataHourly h ON h.Timestamp >= DATEADD(week, -1, wb.WeekStart) 
                                     AND h.Timestamp < wb.WeekStart
    GROUP BY wb.WeekStart, wb.WeekEnd
),
FourHourBodies AS (
    SELECT 
        pw.WeekStart,
        pw.WeekEnd,
        pw.PrevWeekHigh,
        pw.PrevWeekLow,
        pw.PrevWeekClose,
        MAX(CASE 
            WHEN h.Timestamp >= DATEADD(week, -1, pw.WeekStart) 
             AND h.Timestamp < pw.WeekStart
            THEN CASE WHEN h.[Open] > h.[Close] THEN h.[Open] ELSE h.[Close] END
        END) as PrevWeek4HMaxBody,
        MIN(CASE 
            WHEN h.Timestamp >= DATEADD(week, -1, pw.WeekStart) 
             AND h.Timestamp < pw.WeekStart
            THEN CASE WHEN h.[Open] < h.[Close] THEN h.[Open] ELSE h.[Close] END
        END) as PrevWeek4HMinBody
    FROM PreviousWeekData pw
    LEFT JOIN NiftyIndexDataHourly h ON h.Timestamp >= DATEADD(week, -1, pw.WeekStart) 
                                     AND h.Timestamp < pw.WeekStart
    GROUP BY pw.WeekStart, pw.WeekEnd, pw.PrevWeekHigh, pw.PrevWeekLow, pw.PrevWeekClose
),
WeeklyZones AS (
    SELECT 
        *,
        -- Resistance Zone
        CASE WHEN PrevWeekHigh >= PrevWeek4HMaxBody 
             THEN PrevWeekHigh 
             ELSE PrevWeek4HMaxBody END as ResistanceZoneTop,
        CASE WHEN PrevWeekHigh <= PrevWeek4HMaxBody 
             THEN PrevWeekHigh 
             ELSE PrevWeek4HMaxBody END as ResistanceZoneBottom,
        -- Support Zone
        CASE WHEN PrevWeekLow >= PrevWeek4HMinBody 
             THEN PrevWeekLow 
             ELSE PrevWeek4HMinBody END as SupportZoneTop,
        CASE WHEN PrevWeekLow <= PrevWeek4HMinBody 
             THEN PrevWeekLow 
             ELSE PrevWeek4HMinBody END as SupportZoneBottom,
        -- Weekly Bias
        CASE 
            WHEN ABS(PrevWeekClose - PrevWeek4HMaxBody) < ABS(PrevWeekClose - PrevWeek4HMinBody) 
            THEN 'BEARISH'
            WHEN ABS(PrevWeekClose - PrevWeek4HMinBody) < ABS(PrevWeekClose - PrevWeek4HMaxBody)
            THEN 'BULLISH'
            ELSE 'NEUTRAL'
        END as WeeklyBias
    FROM FourHourBodies
    WHERE PrevWeekHigh IS NOT NULL
),
CurrentWeekCandles AS (
    SELECT 
        wz.*,
        h.Timestamp,
        h.[Open],
        h.High,
        h.Low,
        h.[Close],
        ROW_NUMBER() OVER (PARTITION BY wz.WeekStart ORDER BY h.Timestamp) as CandleNum,
        -- Running weekly stats
        MAX(h.High) OVER (PARTITION BY wz.WeekStart ORDER BY h.Timestamp) as WeeklyMaxHigh,
        MIN(h.Low) OVER (PARTITION BY wz.WeekStart ORDER BY h.Timestamp) as WeeklyMinLow,
        MAX(h.[Close]) OVER (PARTITION BY wz.WeekStart ORDER BY h.Timestamp) as WeeklyMaxClose,
        MIN(h.[Close]) OVER (PARTITION BY wz.WeekStart ORDER BY h.Timestamp) as WeeklyMinClose
    FROM WeeklyZones wz
    INNER JOIN NiftyIndexDataHourly h ON h.Timestamp >= wz.WeekStart 
                                      AND h.Timestamp <= DATEADD(hour, 23, wz.WeekEnd)
),
CandlePairs AS (
    SELECT 
        c1.*,
        -- First candle data
        c1.[Open] as FirstCandleOpen,
        c1.High as FirstCandleHigh,
        c1.Low as FirstCandleLow,
        c1.[Close] as FirstCandleClose,
        c1.Timestamp as FirstCandleTime,
        -- Second candle data  
        c2.[Open] as SecondCandleOpen,
        c2.High as SecondCandleHigh,
        c2.Low as SecondCandleLow,
        c2.[Close] as SecondCandleClose,
        c2.Timestamp as SecondCandleTime,
        -- Current candle data
        cn.[Open] as CurrentCandleOpen,
        cn.High as CurrentCandleHigh,
        cn.Low as CurrentCandleLow,
        cn.[Close] as CurrentCandleClose,
        cn.Timestamp as CurrentCandleTime,
        cn.CandleNum as CurrentCandleNum,
        -- Previous candle stats
        LAG(cn.Low, 1) OVER (PARTITION BY c1.WeekStart ORDER BY cn.Timestamp) as PrevCandleLow,
        LAG(cn.High, 1) OVER (PARTITION BY c1.WeekStart ORDER BY cn.Timestamp) as PrevCandleHigh,
        -- Weekly stats before current candle
        LAG(cn.WeeklyMinLow, 1) OVER (PARTITION BY c1.WeekStart ORDER BY cn.Timestamp) as PrevWeeklyMinLow,
        LAG(cn.WeeklyMinClose, 1) OVER (PARTITION BY c1.WeekStart ORDER BY cn.Timestamp) as PrevWeeklyMinClose,
        LAG(cn.WeeklyMaxHigh, 1) OVER (PARTITION BY c1.WeekStart ORDER BY cn.Timestamp) as PrevWeeklyMaxHigh,
        LAG(cn.WeeklyMaxClose, 1) OVER (PARTITION BY c1.WeekStart ORDER BY cn.Timestamp) as PrevWeeklyMaxClose
    FROM CurrentWeekCandles c1
    LEFT JOIN CurrentWeekCandles c2 ON c2.WeekStart = c1.WeekStart AND c2.CandleNum = 2
    INNER JOIN CurrentWeekCandles cn ON cn.WeekStart = c1.WeekStart AND cn.CandleNum >= 2
    WHERE c1.CandleNum = 1
),
SignalDetection AS (
    SELECT 
        WeekStart,
        WeekEnd,
        PrevWeekHigh,
        PrevWeekLow,
        PrevWeekClose,
        PrevWeek4HMaxBody,
        PrevWeek4HMinBody,
        ResistanceZoneTop,
        ResistanceZoneBottom,
        SupportZoneTop,
        SupportZoneBottom,
        WeeklyBias,
        FirstCandleTime,
        FirstCandleOpen,
        FirstCandleHigh,
        FirstCandleLow,
        FirstCandleClose,
        SecondCandleOpen,
        SecondCandleHigh,
        SecondCandleLow,
        SecondCandleClose,
        CurrentCandleTime as EntryTime,
        CurrentCandleOpen as EntryCandleOpen,
        CurrentCandleHigh as EntryCandleHigh,
        CurrentCandleLow as EntryCandleLow,
        CurrentCandleClose as EntryCandleClose,
        CurrentCandleClose as EntryPrice,
        CurrentCandleNum,
        
        -- Signal Detection Logic
        CASE
            -- S1: Bear Trap (Bullish) - 2nd candle only
            WHEN CurrentCandleNum = 2 
                AND FirstCandleOpen >= SupportZoneBottom
                AND FirstCandleClose < SupportZoneBottom
                AND CurrentCandleClose > FirstCandleLow
            THEN 'S1'
            
            -- S2: Support Hold (Bullish) - 2nd candle only
            WHEN CurrentCandleNum = 2
                AND WeeklyBias = 'BULLISH'
                AND FirstCandleOpen > PrevWeekLow
                AND ABS(PrevWeekClose - SupportZoneBottom) / PrevWeekClose < 0.01 -- Near support
                AND ABS(FirstCandleOpen - SupportZoneBottom) / FirstCandleOpen < 0.01 -- Near support
                AND FirstCandleClose >= SupportZoneBottom
                AND FirstCandleClose >= PrevWeekClose
                AND CurrentCandleClose >= FirstCandleLow
                AND CurrentCandleClose > PrevWeekClose
                AND CurrentCandleClose > SupportZoneBottom
            THEN 'S2'
            
            -- S3: Resistance Hold (Bearish) - Scenario A (2nd candle)
            WHEN CurrentCandleNum = 2
                AND WeeklyBias = 'BEARISH'
                AND ABS(PrevWeekClose - ResistanceZoneBottom) / PrevWeekClose < 0.01
                AND ABS(FirstCandleOpen - ResistanceZoneBottom) / FirstCandleOpen < 0.01
                AND FirstCandleClose <= PrevWeekHigh
                AND CurrentCandleClose < FirstCandleHigh
                AND CurrentCandleClose < ResistanceZoneBottom
                AND (FirstCandleHigh >= ResistanceZoneBottom OR CurrentCandleHigh >= ResistanceZoneBottom)
            THEN 'S3'
            
            -- S3: Resistance Hold (Bearish) - Scenario B (any candle)
            WHEN WeeklyBias = 'BEARISH'
                AND ABS(PrevWeekClose - ResistanceZoneBottom) / PrevWeekClose < 0.01
                AND ABS(FirstCandleOpen - ResistanceZoneBottom) / FirstCandleOpen < 0.01
                AND FirstCandleClose <= PrevWeekHigh
                AND CurrentCandleClose < FirstCandleLow
                AND CurrentCandleClose < ResistanceZoneBottom
                AND CurrentCandleClose < ISNULL(PrevWeeklyMinLow, CurrentCandleLow)
                AND CurrentCandleClose < ISNULL(PrevWeeklyMinClose, CurrentCandleClose)
            THEN 'S3'
            
            -- S5: Bias Failure Bear (Bearish)
            WHEN WeeklyBias = 'BULLISH'
                AND FirstCandleOpen < SupportZoneBottom
                AND FirstCandleClose < SupportZoneBottom
                AND FirstCandleClose < PrevWeekLow
                AND CurrentCandleClose < FirstCandleLow
            THEN 'S5'
            
            -- S6: Weakness Confirmed (Bearish) - Similar to S3
            WHEN CurrentCandleNum = 2
                AND WeeklyBias = 'BEARISH'
                AND FirstCandleHigh >= ResistanceZoneBottom
                AND FirstCandleClose <= ResistanceZoneTop
                AND FirstCandleClose <= PrevWeekHigh
                AND CurrentCandleClose < FirstCandleHigh
                AND CurrentCandleClose < ResistanceZoneBottom
            THEN 'S6'
            
            ELSE NULL
        END as SignalType,
        
        -- Stop Loss Calculation
        CASE
            WHEN CurrentCandleNum = 2 AND FirstCandleOpen >= SupportZoneBottom
                AND FirstCandleClose < SupportZoneBottom AND CurrentCandleClose > FirstCandleLow
            THEN FirstCandleLow - 5 -- S1
            
            WHEN CurrentCandleNum = 2 AND WeeklyBias = 'BULLISH' 
                AND FirstCandleClose >= SupportZoneBottom AND CurrentCandleClose > SupportZoneBottom
            THEN SupportZoneBottom -- S2
            
            WHEN WeeklyBias = 'BEARISH' AND CurrentCandleClose < ResistanceZoneBottom
            THEN PrevWeekHigh -- S3, S6
            
            WHEN WeeklyBias = 'BULLISH' AND CurrentCandleClose < FirstCandleLow
            THEN FirstCandleHigh -- S5
            
            ELSE NULL
        END as StopLossPrice
        
    FROM CandlePairs
),
SignalsWithStrikes AS (
    SELECT 
        *,
        -- Option Type
        CASE 
            WHEN SignalType IN ('S1', 'S2', 'S4', 'S7') THEN 'PE'
            WHEN SignalType IN ('S3', 'S5', 'S6', 'S8') THEN 'CE'
            ELSE NULL
        END as OptionType,
        
        -- Main Strike (rounded to 50)
        CASE 
            WHEN SignalType IN ('S1', 'S2', 'S4', 'S7') THEN FLOOR(StopLossPrice/50) * 50
            WHEN SignalType IN ('S3', 'S5', 'S6', 'S8') THEN CEILING(StopLossPrice/50) * 50
            ELSE NULL
        END as MainStrikePrice
        
    FROM SignalDetection
    WHERE SignalType IS NOT NULL
),
SignalsWithHedges AS (
    SELECT 
        *,
        -- Hedge Strikes
        CASE 
            WHEN OptionType = 'PE' THEN MainStrikePrice - 100
            WHEN OptionType = 'CE' THEN MainStrikePrice + 100
        END as HedgeStrike100Away,
        
        CASE 
            WHEN OptionType = 'PE' THEN MainStrikePrice - 150
            WHEN OptionType = 'CE' THEN MainStrikePrice + 150
        END as HedgeStrike150Away,
        
        CASE 
            WHEN OptionType = 'PE' THEN MainStrikePrice - 200
            WHEN OptionType = 'CE' THEN MainStrikePrice + 200
        END as HedgeStrike200Away,
        
        CASE 
            WHEN OptionType = 'PE' THEN MainStrikePrice - 300
            WHEN OptionType = 'CE' THEN MainStrikePrice + 300
        END as HedgeStrike300Away
        
    FROM SignalsWithStrikes
),
-- Get first signal per week (only one signal allowed per week)
FirstSignalPerWeek AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY WeekStart ORDER BY EntryTime) as SignalRank
    FROM SignalsWithHedges
),
-- Check for stop loss hits
StopLossCheck AS (
    SELECT 
        fs.*,
        sl.Timestamp as StopLossHitTime,
        sl.[Open] as StopLossHitCandleOpen,
        sl.High as StopLossHitCandleHigh,
        sl.Low as StopLossHitCandleLow,
        sl.[Close] as StopLossHitCandleClose,
        CASE 
            WHEN sl.Timestamp IS NOT NULL THEN 1 
            ELSE 0 
        END as StopLossHit
    FROM FirstSignalPerWeek fs
    OUTER APPLY (
        SELECT TOP 1 h.*
        FROM NiftyIndexDataHourly h
        WHERE h.Timestamp > fs.EntryTime
            AND h.Timestamp <= DATEADD(hour, 23, fs.WeekEnd)
            AND (
                -- Bullish stop loss: Close below stop
                (fs.OptionType = 'PE' AND h.[Close] < fs.StopLossPrice)
                OR
                -- Bearish stop loss: Close above stop
                (fs.OptionType = 'CE' AND h.[Close] > fs.StopLossPrice)
            )
        ORDER BY h.Timestamp
    ) sl
    WHERE fs.SignalRank = 1
)
-- Final insert into SignalAnalysis table
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
    FirstCandleTime, FirstCandleOpen, FirstCandleHigh, FirstCandleLow, FirstCandleClose,
    SignalType, EntryTime, EntryTime, EntryPrice,
    FirstCandleOpen, FirstCandleHigh, FirstCandleLow, FirstCandleClose,
    SecondCandleOpen, SecondCandleHigh, SecondCandleLow, SecondCandleClose,
    EntryCandleOpen, EntryCandleHigh, EntryCandleLow, EntryCandleClose,
    StopLossPrice, MainStrikePrice, OptionType,
    HedgeStrike100Away, HedgeStrike150Away, HedgeStrike200Away, HedgeStrike300Away,
    StopLossHit, StopLossHitTime,
    StopLossHitCandleOpen, StopLossHitCandleHigh, StopLossHitCandleLow, StopLossHitCandleClose,
    CASE 
        WHEN StopLossHit = 1 THEN 'LOSS'
        ELSE 'WIN'
    END as WeeklyOutcome
FROM StopLossCheck;

-- Show summary
SELECT 
    COUNT(*) as TotalSignals,
    SignalType,
    COUNT(CASE WHEN WeeklyOutcome = 'WIN' THEN 1 END) as Wins,
    COUNT(CASE WHEN WeeklyOutcome = 'LOSS' THEN 1 END) as Losses,
    CAST(COUNT(CASE WHEN WeeklyOutcome = 'WIN' THEN 1 END) * 100.0 / COUNT(*) as DECIMAL(5,2)) as WinRate
FROM SignalAnalysis
GROUP BY SignalType
ORDER BY SignalType;

-- Show recent signals
SELECT TOP 10 
    WeekStartDate,
    SignalType,
    EntryTime,
    EntryPrice,
    StopLossPrice,
    MainStrikePrice,
    OptionType,
    StopLossHit,
    WeeklyOutcome
FROM SignalAnalysis
ORDER BY EntryTime DESC;