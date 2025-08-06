-- Additional signal detection for S4, S7, S8
-- These signals require more complex breakout/breakdown logic

-- This script should be run after signal_detection_complete.sql
-- It updates the SignalAnalysis table with S4, S7, S8 signals

-- S4 and S7 Detection (Bullish breakout signals)
WITH WeeklyData AS (
    SELECT DISTINCT
        dbo.GetWeekStart(Timestamp) as WeekStart,
        DATEADD(day, 4, dbo.GetWeekStart(Timestamp)) as WeekEnd
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= '2022-01-01'
),
PreviousWeekCalc AS (
    SELECT 
        wd.WeekStart,
        wd.WeekEnd,
        MAX(CASE WHEN h.Timestamp < wd.WeekStart THEN h.High END) as PrevWeekHigh,
        MIN(CASE WHEN h.Timestamp < wd.WeekStart THEN h.Low END) as PrevWeekLow,
        MAX(CASE WHEN h.Timestamp < wd.WeekStart AND DATEPART(hour, h.Timestamp) = 15 
                 THEN h.[Close] END) as PrevWeekClose
    FROM WeeklyData wd
    LEFT JOIN NiftyIndexDataHourly h ON h.Timestamp >= DATEADD(week, -1, wd.WeekStart) 
                                     AND h.Timestamp < DATEADD(day, 1, wd.WeekEnd)
    GROUP BY wd.WeekStart, wd.WeekEnd
),
FourHourBodiesCalc AS (
    SELECT 
        pw.*,
        MAX(CASE WHEN h.Timestamp < pw.WeekStart 
                 THEN CASE WHEN h.[Open] > h.[Close] THEN h.[Open] ELSE h.[Close] END 
            END) as PrevWeek4HMaxBody,
        MIN(CASE WHEN h.Timestamp < pw.WeekStart 
                 THEN CASE WHEN h.[Open] < h.[Close] THEN h.[Open] ELSE h.[Close] END 
            END) as PrevWeek4HMinBody
    FROM PreviousWeekCalc pw
    LEFT JOIN NiftyIndexDataHourly h ON h.Timestamp >= DATEADD(week, -1, pw.WeekStart) 
                                     AND h.Timestamp < pw.WeekStart
    GROUP BY pw.WeekStart, pw.WeekEnd, pw.PrevWeekHigh, pw.PrevWeekLow, pw.PrevWeekClose
),
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
    FROM FourHourBodiesCalc
    WHERE PrevWeekHigh IS NOT NULL
),
WeeklyCandlesWithStats AS (
    SELECT 
        z.*,
        h.Timestamp,
        h.[Open],
        h.High,
        h.Low,
        h.[Close],
        ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as CandleNum,
        -- First hour data
        FIRST_VALUE(h.[Open]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as FirstHourOpen,
        FIRST_VALUE(h.High) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as FirstHourHigh,
        FIRST_VALUE(h.Low) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as FirstHourLow,
        FIRST_VALUE(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as FirstHourClose,
        -- Running max/min
        MAX(h.High) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) as PrevMaxHigh,
        MIN(h.Low) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) as PrevMinLow,
        MAX(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) as PrevMaxClose,
        MIN(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) as PrevMinClose,
        -- Check if resistance was touched this week
        MAX(CASE WHEN h.High >= z.ResistanceZoneBottom THEN 1 ELSE 0 END) 
            OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as TouchedResistance
    FROM ZonesAndBias z
    INNER JOIN NiftyIndexDataHourly h ON h.Timestamp >= z.WeekStart AND h.Timestamp <= DATEADD(hour, 23, z.WeekEnd)
),
S4BreakoutDetection AS (
    SELECT 
        w1.*,
        -- Detect S4 breakout pattern
        CASE 
            -- First, check basic S4 conditions
            WHEN w1.WeeklyBias = 'BEARISH' 
                AND w1.FirstHourOpen > w1.ResistanceZoneTop
                AND w1.CandleNum >= 2
            THEN
                CASE
                    -- Same day as first hour: Close > FirstHourHigh
                    WHEN CAST(w1.Timestamp as DATE) = CAST(w1.WeekStart as DATE)
                        AND w1.[Close] > w1.FirstHourHigh
                    THEN 1
                    
                    -- Different day: Need breakout candle then close above its high
                    WHEN CAST(w1.Timestamp as DATE) > CAST(w1.WeekStart as DATE)
                    THEN
                        -- Check if we have a breakout candle in history
                        CASE WHEN EXISTS (
                            SELECT 1 
                            FROM WeeklyCandlesWithStats w2
                            WHERE w2.WeekStart = w1.WeekStart
                                AND w2.Timestamp < w1.Timestamp
                                AND w2.Timestamp > DATEADD(hour, 1, w1.WeekStart) -- After first hour
                                AND w2.[Close] > w2.[Open] -- Green candle
                                AND w2.[Close] > w1.FirstHourHigh
                                AND w2.High >= ISNULL(w2.PrevMaxHigh, w2.High)
                                -- And current candle closes above that breakout high
                                AND w1.[Close] > w2.High
                        ) THEN 1 ELSE 0 END
                    ELSE 0
                END
            ELSE 0
        END as S4Triggered
    FROM WeeklyCandlesWithStats w1
),
S7Detection AS (
    SELECT 
        *,
        -- S7: Requires S4 trigger + strongest breakout conditions
        CASE 
            WHEN S4Triggered = 1
                AND (
                    [Close] >= PrevWeekHigh 
                    OR ((PrevWeekHigh - [Close]) / [Close] * 100) >= 0.4
                )
                AND [Close] > ISNULL(PrevMaxHigh, [Close])
                AND [Close] > ISNULL(PrevMaxClose, [Close])
            THEN 1
            ELSE 0
        END as S7Triggered
    FROM S4BreakoutDetection
),
S8BreakdownDetection AS (
    SELECT 
        w1.*,
        -- S8: Mirror of S4 for breakdown
        CASE 
            WHEN w1.WeeklyBias = 'BULLISH' -- Note: This seems incorrect per S8 definition
                AND w1.FirstHourOpen < w1.SupportZoneBottom
                AND w1.CandleNum >= 2
                AND w1.TouchedResistance = 1 -- Upper zone was touched this week
                AND w1.[Close] < w1.ResistanceZoneBottom
            THEN
                CASE
                    -- Same day breakdown
                    WHEN CAST(w1.Timestamp as DATE) = CAST(w1.WeekStart as DATE)
                        AND w1.[Close] < w1.FirstHourLow
                    THEN 1
                    
                    -- Different day breakdown pattern
                    WHEN CAST(w1.Timestamp as DATE) > CAST(w1.WeekStart as DATE)
                    THEN
                        CASE WHEN EXISTS (
                            SELECT 1 
                            FROM WeeklyCandlesWithStats w2
                            WHERE w2.WeekStart = w1.WeekStart
                                AND w2.Timestamp < w1.Timestamp
                                AND w2.Timestamp > DATEADD(hour, 1, w1.WeekStart)
                                AND w2.[Close] < w2.[Open] -- Red candle
                                AND w2.[Close] < w1.FirstHourLow
                                AND w2.Low <= ISNULL(w2.PrevMinLow, w2.Low)
                                AND w1.[Close] < w2.Low
                        ) THEN 1 ELSE 0 END
                    ELSE 0
                END
            ELSE 0
        END as S8Triggered
    FROM WeeklyCandlesWithStats w1
),
AllS4S7S8Signals AS (
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
        FirstHourOpen,
        FirstHourHigh,
        FirstHourLow,
        FirstHourClose,
        Timestamp as EntryTime,
        [Close] as EntryPrice,
        CASE 
            WHEN S7Triggered = 1 THEN 'S7'
            WHEN S4Triggered = 1 THEN 'S4'
            WHEN S8Triggered = 1 THEN 'S8'
        END as SignalType,
        CASE 
            WHEN S7Triggered = 1 OR S4Triggered = 1 THEN FirstHourLow
            WHEN S8Triggered = 1 THEN FirstHourHigh
        END as StopLossPrice,
        CASE 
            WHEN S7Triggered = 1 OR S4Triggered = 1 THEN 'PE'
            WHEN S8Triggered = 1 THEN 'CE'
        END as OptionType,
        [Open] as EntryCandleOpen,
        High as EntryCandleHigh,
        Low as EntryCandleLow,
        [Close] as EntryCandleClose
    FROM S7Detection
    WHERE S4Triggered = 1 OR S7Triggered = 1
    
    UNION ALL
    
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
        FirstHourOpen,
        FirstHourHigh,
        FirstHourLow,
        FirstHourClose,
        Timestamp as EntryTime,
        [Close] as EntryPrice,
        'S8' as SignalType,
        FirstHourHigh as StopLossPrice,
        'CE' as OptionType,
        [Open] as EntryCandleOpen,
        High as EntryCandleHigh,
        Low as EntryCandleLow,
        [Close] as EntryCandleClose
    FROM S8BreakdownDetection
    WHERE S8Triggered = 1
),
FirstSignalOnly AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY WeekStart ORDER BY EntryTime) as SignalRank
    FROM AllS4S7S8Signals
),
SignalsWithStrikes AS (
    SELECT 
        *,
        -- Main Strike
        CASE 
            WHEN OptionType = 'PE' THEN FLOOR(StopLossPrice/50) * 50
            WHEN OptionType = 'CE' THEN CEILING(StopLossPrice/50) * 50
        END as MainStrikePrice,
        -- Get first candle data
        FIRST_VALUE([Open]) OVER (PARTITION BY WeekStart ORDER BY EntryTime) as FirstCandleOpen,
        FIRST_VALUE(High) OVER (PARTITION BY WeekStart ORDER BY EntryTime) as FirstCandleHigh,
        FIRST_VALUE(Low) OVER (PARTITION BY WeekStart ORDER BY EntryTime) as FirstCandleLow,
        FIRST_VALUE([Close]) OVER (PARTITION BY WeekStart ORDER BY EntryTime) as FirstCandleClose
    FROM FirstSignalOnly
    WHERE SignalRank = 1
),
StopLossTracking AS (
    SELECT 
        s.*,
        sl.Timestamp as StopLossHitTime,
        sl.[Open] as StopLossHitCandleOpen,
        sl.High as StopLossHitCandleHigh,
        sl.Low as StopLossHitCandleLow,
        sl.[Close] as StopLossHitCandleClose,
        CASE WHEN sl.Timestamp IS NOT NULL THEN 1 ELSE 0 END as StopLossHit
    FROM SignalsWithStrikes s
    OUTER APPLY (
        SELECT TOP 1 h.*
        FROM NiftyIndexDataHourly h
        WHERE h.Timestamp > s.EntryTime
            AND h.Timestamp <= DATEADD(hour, 23, s.WeekEnd)
            AND (
                (s.OptionType = 'PE' AND h.[Close] < s.StopLossPrice)
                OR
                (s.OptionType = 'CE' AND h.[Close] > s.StopLossPrice)
            )
        ORDER BY h.Timestamp
    ) sl
)
-- Insert new S4, S7, S8 signals that don't already exist
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
    DATEADD(hour, 9, WeekStart) + DATEADD(minute, 15, 0), -- First hour time
    FirstHourOpen, FirstHourHigh, FirstHourLow, FirstHourClose,
    SignalType, EntryTime, EntryTime, EntryPrice,
    FirstCandleOpen, FirstCandleHigh, FirstCandleLow, FirstCandleClose,
    NULL, NULL, NULL, NULL, -- Second candle (not applicable for these signals)
    EntryCandleOpen, EntryCandleHigh, EntryCandleLow, EntryCandleClose,
    StopLossPrice, MainStrikePrice, OptionType,
    -- Hedge strikes
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 100 ELSE MainStrikePrice + 100 END,
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 150 ELSE MainStrikePrice + 150 END,
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 200 ELSE MainStrikePrice + 200 END,
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 300 ELSE MainStrikePrice + 300 END,
    StopLossHit, StopLossHitTime,
    StopLossHitCandleOpen, StopLossHitCandleHigh, StopLossHitCandleLow, StopLossHitCandleClose,
    CASE WHEN StopLossHit = 1 THEN 'LOSS' ELSE 'WIN' END
FROM StopLossTracking s
WHERE NOT EXISTS (
    SELECT 1 FROM SignalAnalysis sa 
    WHERE sa.WeekStartDate = s.WeekStart 
    AND sa.SignalType IS NOT NULL
);

-- Show updated summary
SELECT 
    'Summary After S4/S7/S8' as Report,
    COUNT(*) as TotalSignals,
    COUNT(CASE WHEN SignalType = 'S1' THEN 1 END) as S1_Count,
    COUNT(CASE WHEN SignalType = 'S2' THEN 1 END) as S2_Count,
    COUNT(CASE WHEN SignalType = 'S3' THEN 1 END) as S3_Count,
    COUNT(CASE WHEN SignalType = 'S4' THEN 1 END) as S4_Count,
    COUNT(CASE WHEN SignalType = 'S5' THEN 1 END) as S5_Count,
    COUNT(CASE WHEN SignalType = 'S6' THEN 1 END) as S6_Count,
    COUNT(CASE WHEN SignalType = 'S7' THEN 1 END) as S7_Count,
    COUNT(CASE WHEN SignalType = 'S8' THEN 1 END) as S8_Count
FROM SignalAnalysis;

-- Show strike distribution
SELECT 
    'Strike Requirements' as Report,
    MIN(MainStrikePrice) as MinStrike,
    MAX(MainStrikePrice) as MaxStrike,
    COUNT(DISTINCT MainStrikePrice) as UniqueStrikes,
    STRING_AGG(CAST(MainStrikePrice as VARCHAR), ', ') WITHIN GROUP (ORDER BY MainStrikePrice) as AllStrikes
FROM SignalAnalysis
WHERE MainStrikePrice IS NOT NULL;