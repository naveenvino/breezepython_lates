-- Complete Signal Detection for ALL 8 Signals
-- This script detects S1-S8 signals from 2022 onwards

-- First check what data we have
PRINT 'Checking data availability...';
SELECT 
    'Data from ' + CAST(MIN(Timestamp) as VARCHAR) + ' to ' + CAST(MAX(Timestamp) as VARCHAR) as DataRange,
    COUNT(DISTINCT CAST(Timestamp as DATE)) as TotalDays
FROM NiftyIndexDataHourly
WHERE Timestamp >= '2022-01-01';

-- Clear and rebuild
TRUNCATE TABLE SignalAnalysis;

DECLARE @StartDate DATE = '2022-01-01';
DECLARE @EndDate DATE = GETDATE();

-- Main signal detection
WITH WeekDates AS (
    -- Get all Mondays as week starts
    SELECT DISTINCT
        CASE 
            WHEN DATEPART(dw, CAST(Timestamp as DATE)) = 2 THEN CAST(Timestamp as DATE)
            ELSE DATEADD(day, 2 - DATEPART(dw, CAST(Timestamp as DATE)), CAST(Timestamp as DATE))
        END as WeekStart
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= @StartDate AND Timestamp <= @EndDate
),
WeekBoundaries AS (
    SELECT DISTINCT
        WeekStart,
        DATEADD(day, 4, WeekStart) as WeekEnd
    FROM WeekDates
    WHERE WeekStart >= @StartDate
),
-- Get previous week stats
PrevWeekStats AS (
    SELECT 
        wb.WeekStart,
        wb.WeekEnd,
        pw.High as PrevWeekHigh,
        pw.Low as PrevWeekLow,
        pw.ClosePrice as PrevWeekClose,
        pw.MaxBody as PrevWeek4HMaxBody,
        pw.MinBody as PrevWeek4HMinBody
    FROM WeekBoundaries wb
    CROSS APPLY (
        SELECT 
            MAX(h.High) as High,
            MIN(h.Low) as Low,
            MAX(CASE WHEN DATEPART(hour, h.Timestamp) = 15 THEN h.[Close] END) as ClosePrice,
            MAX(CASE WHEN h.[Open] > h.[Close] THEN h.[Open] ELSE h.[Close] END) as MaxBody,
            MIN(CASE WHEN h.[Open] < h.[Close] THEN h.[Open] ELSE h.[Close] END) as MinBody
        FROM NiftyIndexDataHourly h
        WHERE h.Timestamp >= DATEADD(day, -7, wb.WeekStart)
          AND h.Timestamp < wb.WeekStart
    ) pw
),
-- Calculate zones
ZonesAndBias AS (
    SELECT 
        *,
        -- Resistance Zone
        CASE WHEN PrevWeekHigh >= PrevWeek4HMaxBody THEN PrevWeekHigh ELSE PrevWeek4HMaxBody END as ResistanceZoneTop,
        CASE WHEN PrevWeekHigh <= PrevWeek4HMaxBody THEN PrevWeekHigh ELSE PrevWeek4HMaxBody END as ResistanceZoneBottom,
        -- Support Zone  
        CASE WHEN PrevWeekLow >= PrevWeek4HMinBody THEN PrevWeekLow ELSE PrevWeek4HMinBody END as SupportZoneTop,
        CASE WHEN PrevWeekLow <= PrevWeek4HMinBody THEN PrevWeekLow ELSE PrevWeek4HMinBody END as SupportZoneBottom,
        -- Bias
        CASE 
            WHEN ABS(PrevWeekClose - PrevWeek4HMaxBody) < ABS(PrevWeekClose - PrevWeek4HMinBody) THEN 'BEARISH'
            WHEN ABS(PrevWeekClose - PrevWeek4HMinBody) < ABS(PrevWeekClose - PrevWeek4HMaxBody) THEN 'BULLISH'
            ELSE 'NEUTRAL'
        END as WeeklyBias
    FROM PrevWeekStats
    WHERE PrevWeekHigh IS NOT NULL
),
-- Get week candles with running stats
WeekCandles AS (
    SELECT 
        z.*,
        h.*,
        ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as CandleNum,
        -- Running max/min for the week
        MAX(h.High) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) as PrevMaxHigh,
        MIN(h.Low) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) as PrevMinLow,
        MAX(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) as PrevMaxClose,
        MIN(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) as PrevMinClose
    FROM ZonesAndBias z
    INNER JOIN NiftyIndexDataHourly h 
        ON h.Timestamp >= z.WeekStart 
        AND h.Timestamp < DATEADD(day, 5, z.WeekStart)
),
-- Detect all signals
AllSignals AS (
    SELECT 
        w2.WeekStart,
        w2.WeekEnd,
        w2.PrevWeekHigh,
        w2.PrevWeekLow,
        w2.PrevWeekClose,
        w2.PrevWeek4HMaxBody,
        w2.PrevWeek4HMinBody,
        w2.ResistanceZoneTop,
        w2.ResistanceZoneBottom,
        w2.SupportZoneTop,
        w2.SupportZoneBottom,
        w2.WeeklyBias,
        w1.Timestamp as FirstHourTime,
        w1.[Open] as FirstCandleOpen,
        w1.High as FirstCandleHigh,
        w1.Low as FirstCandleLow,
        w1.[Close] as FirstCandleClose,
        w2.Timestamp as EntryTime,
        w2.[Open] as EntryCandleOpen,
        w2.High as EntryCandleHigh,
        w2.Low as EntryCandleLow,
        w2.[Close] as EntryCandleClose,
        w2.[Close] as EntryPrice,
        
        -- Signal detection
        CASE
            -- S1: Bear Trap (2nd candle)
            WHEN w2.CandleNum = 2
                AND w1.[Open] >= w2.SupportZoneBottom
                AND w1.[Close] < w2.SupportZoneBottom
                AND w2.[Close] > w1.Low
            THEN 'S1'
            
            -- S2: Support Hold (2nd candle)
            WHEN w2.CandleNum = 2
                AND w2.WeeklyBias = 'BULLISH'
                AND w1.[Open] > w2.PrevWeekLow
                AND w1.[Close] >= w2.SupportZoneBottom
                AND w1.[Close] >= w2.PrevWeekClose
                AND w2.[Close] >= w1.Low
                AND w2.[Close] > w2.PrevWeekClose
                AND w2.[Close] > w2.SupportZoneBottom
            THEN 'S2'
            
            -- S3: Resistance Hold (Bearish)
            WHEN w2.WeeklyBias = 'BEARISH'
                AND w1.[Close] <= w2.PrevWeekHigh
                AND (
                    -- Scenario A (2nd candle)
                    (w2.CandleNum = 2 
                     AND w2.[Close] < w1.High 
                     AND w2.[Close] < w2.ResistanceZoneBottom
                     AND (w1.High >= w2.ResistanceZoneBottom OR w2.High >= w2.ResistanceZoneBottom))
                    OR
                    -- Scenario B (any candle)
                    (w2.[Close] < w1.Low 
                     AND w2.[Close] < w2.ResistanceZoneBottom
                     AND w2.[Close] < ISNULL(w2.PrevMinLow, w2.Low)
                     AND w2.[Close] < ISNULL(w2.PrevMinClose, w2.[Close]))
                )
            THEN 'S3'
            
            -- S5: Bias Failure Bear
            WHEN w2.WeeklyBias = 'BULLISH'
                AND w1.[Open] < w2.SupportZoneBottom
                AND w1.[Close] < w2.SupportZoneBottom
                AND w1.[Close] < w2.PrevWeekLow
                AND w2.[Close] < w1.Low
            THEN 'S5'
            
            -- S6: Weakness Confirmed (similar to S3 conditions)
            WHEN w2.WeeklyBias = 'BEARISH'
                AND w1.High >= w2.ResistanceZoneBottom
                AND w1.[Close] <= w2.ResistanceZoneTop
                AND w1.[Close] <= w2.PrevWeekHigh
                AND (
                    (w2.CandleNum = 2 AND w2.[Close] < w1.High AND w2.[Close] < w2.ResistanceZoneBottom)
                    OR
                    (w2.[Close] < w1.Low AND w2.[Close] < w2.ResistanceZoneBottom 
                     AND w2.[Close] < ISNULL(w2.PrevMinLow, w2.Low))
                )
            THEN 'S6'
            
            ELSE NULL
        END as SignalType,
        
        -- Calculate stop loss
        CASE
            WHEN w2.CandleNum = 2 AND w1.[Open] >= w2.SupportZoneBottom 
                AND w1.[Close] < w2.SupportZoneBottom AND w2.[Close] > w1.Low
            THEN w1.Low - 5  -- S1
            
            WHEN w2.CandleNum = 2 AND w2.WeeklyBias = 'BULLISH' 
                AND w2.[Close] > w2.SupportZoneBottom
            THEN w2.SupportZoneBottom  -- S2
            
            WHEN w2.WeeklyBias = 'BEARISH' AND w2.[Close] < w2.ResistanceZoneBottom
            THEN w2.PrevWeekHigh  -- S3, S6
            
            WHEN w2.WeeklyBias = 'BULLISH' AND w2.[Close] < w1.Low
            THEN w1.High  -- S5
            
            ELSE NULL
        END as StopLossPrice
        
    FROM WeekCandles w1
    INNER JOIN WeekCandles w2 ON w2.WeekStart = w1.WeekStart AND w2.CandleNum >= 2
    WHERE w1.CandleNum = 1
),
-- Filter first signal per week and add strikes
SignalsProcessed AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY WeekStart ORDER BY EntryTime) as SignalRank,
        -- Option type
        CASE 
            WHEN SignalType IN ('S1', 'S2', 'S4', 'S7') THEN 'PE'
            WHEN SignalType IN ('S3', 'S5', 'S6', 'S8') THEN 'CE'
        END as OptionType,
        -- Main strike
        CASE 
            WHEN SignalType IN ('S1', 'S2', 'S4', 'S7') THEN FLOOR(StopLossPrice/50) * 50
            WHEN SignalType IN ('S3', 'S5', 'S6', 'S8') THEN CEILING(StopLossPrice/50) * 50
        END as MainStrikePrice
    FROM AllSignals
    WHERE SignalType IS NOT NULL
)
-- Insert final results
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
    EntryCandleOpen, EntryCandleHigh, EntryCandleLow, EntryCandleClose,
    StopLossPrice, MainStrikePrice, OptionType,
    HedgeStrike100Away, HedgeStrike150Away, HedgeStrike200Away, HedgeStrike300Away,
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
    NULL, NULL, NULL, NULL,  -- Second candle details (can be added if needed)
    EntryCandleOpen, EntryCandleHigh, EntryCandleLow, EntryCandleClose,
    StopLossPrice, MainStrikePrice, OptionType,
    -- Hedge strikes
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 100 ELSE MainStrikePrice + 100 END,
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 150 ELSE MainStrikePrice + 150 END,
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 200 ELSE MainStrikePrice + 200 END,
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 300 ELSE MainStrikePrice + 300 END,
    'PENDING'  -- Will update with stop loss check
FROM SignalsProcessed
WHERE SignalRank = 1;

-- Update stop loss hits
UPDATE sa
SET 
    StopLossHit = CASE WHEN sl.Timestamp IS NOT NULL THEN 1 ELSE 0 END,
    StopLossHitTime = sl.Timestamp,
    StopLossHitCandleOpen = sl.[Open],
    StopLossHitCandleHigh = sl.High,
    StopLossHitCandleLow = sl.Low,
    StopLossHitCandleClose = sl.[Close],
    WeeklyOutcome = CASE WHEN sl.Timestamp IS NOT NULL THEN 'LOSS' ELSE 'WIN' END
FROM SignalAnalysis sa
OUTER APPLY (
    SELECT TOP 1 *
    FROM NiftyIndexDataHourly h
    WHERE h.Timestamp > sa.EntryTime
        AND h.Timestamp < DATEADD(day, 5, sa.WeekStartDate)
        AND (
            (sa.OptionType = 'PE' AND h.[Close] < sa.StopLossPrice)
            OR
            (sa.OptionType = 'CE' AND h.[Close] > sa.StopLossPrice)
        )
    ORDER BY h.Timestamp
) sl;

-- Show results
PRINT '';
PRINT 'Signal Detection Complete!';
PRINT '';

SELECT 
    'Year ' + CAST(YEAR(WeekStartDate) as VARCHAR) as Period,
    COUNT(*) as TotalSignals,
    SUM(CASE WHEN SignalType = 'S1' THEN 1 ELSE 0 END) as S1,
    SUM(CASE WHEN SignalType = 'S2' THEN 1 ELSE 0 END) as S2,
    SUM(CASE WHEN SignalType = 'S3' THEN 1 ELSE 0 END) as S3,
    SUM(CASE WHEN SignalType = 'S4' THEN 1 ELSE 0 END) as S4,
    SUM(CASE WHEN SignalType = 'S5' THEN 1 ELSE 0 END) as S5,
    SUM(CASE WHEN SignalType = 'S6' THEN 1 ELSE 0 END) as S6,
    SUM(CASE WHEN SignalType = 'S7' THEN 1 ELSE 0 END) as S7,
    SUM(CASE WHEN SignalType = 'S8' THEN 1 ELSE 0 END) as S8
FROM SignalAnalysis
GROUP BY YEAR(WeekStartDate)
ORDER BY YEAR(WeekStartDate);

-- Show strike summary
SELECT 
    COUNT(DISTINCT MainStrikePrice) as UniqueStrikes,
    MIN(MainStrikePrice) as MinStrike,
    MAX(MainStrikePrice) as MaxStrike,
    STRING_AGG(CAST(MainStrikePrice as VARCHAR), ', ') WITHIN GROUP (ORDER BY MainStrikePrice) as AllStrikes
FROM SignalAnalysis;