-- Exact TradingView Signal Detection Implementation
-- Based on the actual Pine Script indicator

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

-- Process signals with exact TradingView logic
DECLARE @StartDate DATE = '2022-01-01';
DECLARE @EndDate DATE = GETDATE();

-- Step 1: Calculate weekly data
WITH WeekBoundaries AS (
    SELECT DISTINCT
        DATEADD(day, 2 - DATEPART(dw, CAST(Timestamp as DATE)), CAST(Timestamp as DATE)) as WeekStart,
        DATEADD(day, 6 - DATEPART(dw, CAST(Timestamp as DATE)), CAST(Timestamp as DATE)) as WeekEnd
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= @StartDate
),
-- Get previous week stats with 4H bodies
PrevWeekCalc AS (
    SELECT 
        wb.WeekStart,
        wb.WeekEnd,
        pw.High as PrevWeekHigh,
        pw.Low as PrevWeekLow,
        pw.ClosePrice as PrevWeekClose,
        pw.Max4HBody as PrevWeek4HMaxBody,
        pw.Min4HBody as PrevWeek4HMinBody
    FROM WeekBoundaries wb
    OUTER APPLY (
        SELECT 
            MAX(h.High) as High,
            MIN(h.Low) as Low,
            -- Get Friday close (last hour of week)
            MAX(CASE WHEN DATEPART(dw, h.Timestamp) = 6 AND DATEPART(hour, h.Timestamp) = 15 THEN h.[Close] END) as ClosePrice,
            -- Calculate 4H bodies (max/min of open/close for each 4H period)
            MAX(CASE WHEN h.[Open] > h.[Close] THEN h.[Open] ELSE h.[Close] END) as Max4HBody,
            MIN(CASE WHEN h.[Open] < h.[Close] THEN h.[Open] ELSE h.[Close] END) as Min4HBody
        FROM NiftyIndexDataHourly h
        WHERE h.Timestamp >= DATEADD(week, -1, wb.WeekStart)
          AND h.Timestamp < wb.WeekStart
    ) pw
),
-- Calculate zones and bias
ZonesCalc AS (
    SELECT 
        *,
        -- Upper Zone (resistance)
        CASE WHEN PrevWeekHigh > PrevWeek4HMaxBody THEN PrevWeekHigh ELSE PrevWeek4HMaxBody END as ResistanceZoneTop,
        CASE WHEN PrevWeekHigh < PrevWeek4HMaxBody THEN PrevWeekHigh ELSE PrevWeek4HMaxBody END as ResistanceZoneBottom,
        -- Lower Zone (support)
        CASE WHEN PrevWeekLow > PrevWeek4HMinBody THEN PrevWeekLow ELSE PrevWeek4HMinBody END as SupportZoneTop,
        CASE WHEN PrevWeekLow < PrevWeek4HMinBody THEN PrevWeekLow ELSE PrevWeek4HMinBody END as SupportZoneBottom
    FROM PrevWeekCalc
    WHERE PrevWeekHigh IS NOT NULL
),
ZonesWithBias AS (
    SELECT 
        *,
        -- Margins (3x zone height or 5 ticks minimum)
        CASE WHEN (ResistanceZoneTop - ResistanceZoneBottom) * 3 > 0.05 
             THEN (ResistanceZoneTop - ResistanceZoneBottom) * 3 
             ELSE 0.05 END as MarginHigh,
        CASE WHEN (SupportZoneTop - SupportZoneBottom) * 3 > 0.05 
             THEN (SupportZoneTop - SupportZoneBottom) * 3 
             ELSE 0.05 END as MarginLow,
        -- Weekly Bias (based on distance from close to zones)
        CASE 
            WHEN ABS(PrevWeekClose - PrevWeek4HMaxBody) < ABS(PrevWeekClose - PrevWeek4HMinBody) THEN 'BEARISH'
            WHEN ABS(PrevWeekClose - PrevWeek4HMinBody) < ABS(PrevWeekClose - PrevWeek4HMaxBody) THEN 'BULLISH'
            ELSE 'NEUTRAL'
        END as WeeklyBias
    FROM ZonesCalc
),
-- Get all week candles with stats
WeekCandlesRaw AS (
    SELECT 
        z.*,
        h.*,
        ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as CandleNum,
        -- Track weekly highs/lows/closes BEFORE current candle
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) > 1
             THEN MAX(h.High) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
             ELSE NULL END as WeeklyMaxHighBefore,
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) > 1
             THEN MIN(h.Low) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
             ELSE NULL END as WeeklyMinLowBefore,
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) > 1
             THEN MAX(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
             ELSE NULL END as WeeklyMaxCloseBefore,
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) > 1
             THEN MIN(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
             ELSE NULL END as WeeklyMinCloseBefore,
        -- Track if upper zone was touched this week
        MAX(CASE WHEN h.High >= z.ResistanceZoneBottom THEN 1 ELSE 0 END) 
            OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as TouchedUpperZone
    FROM ZonesWithBias z
    INNER JOIN NiftyIndexDataHourly h 
        ON h.Timestamp >= z.WeekStart 
        AND h.Timestamp < DATEADD(day, 5, z.WeekStart)
),
-- Add S4/S7 breakout tracking
S4Tracking AS (
    SELECT 
        w.*,
        -- S4 breakout logic (tracks first hour high breakout)
        CASE 
            WHEN w.CandleNum = 1 THEN NULL  -- Initialize
            -- Same day (Monday): Close > First Hour High
            WHEN CAST(w.Timestamp as DATE) = w.WeekStart AND w.[Close] > fh.High THEN 1
            -- Different day: Look for breakout pattern
            WHEN CAST(w.Timestamp as DATE) > w.WeekStart THEN
                CASE 
                    -- Check if we have a valid breakout candle before this
                    WHEN EXISTS (
                        SELECT 1 FROM WeekCandlesRaw w2
                        WHERE w2.WeekStart = w.WeekStart
                          AND w2.Timestamp < w.Timestamp
                          AND w2.Timestamp > DATEADD(hour, 1, w.WeekStart)
                          AND w2.[Close] > w2.[Open]  -- Green candle
                          AND w2.[Close] > fh.High     -- Closes above first hour high
                          AND w2.High >= ISNULL(w2.WeeklyMaxHighBefore, w2.High)  -- New weekly high
                          AND w.[Close] > w2.High      -- Current closes above breakout candle high
                    ) THEN 1
                    ELSE 0
                END
            ELSE 0
        END as S4Breakout,
        fh.High as FirstHourHigh,
        fh.Low as FirstHourLow,
        fh.[Close] as FirstHourClose
    FROM WeekCandlesRaw w
    CROSS APPLY (
        SELECT TOP 1 High, Low, [Close] 
        FROM WeekCandlesRaw w2 
        WHERE w2.WeekStart = w.WeekStart AND w2.CandleNum = 1
    ) fh
),
-- Similar for S8 breakdown
S8Tracking AS (
    SELECT 
        s4.*,
        -- S8 breakdown logic (mirror of S4)
        CASE 
            WHEN s4.CandleNum = 1 THEN NULL
            WHEN CAST(s4.Timestamp as DATE) = s4.WeekStart AND s4.[Close] < s4.FirstHourLow THEN 1
            WHEN CAST(s4.Timestamp as DATE) > s4.WeekStart THEN
                CASE 
                    WHEN EXISTS (
                        SELECT 1 FROM S4Tracking s2
                        WHERE s2.WeekStart = s4.WeekStart
                          AND s2.Timestamp < s4.Timestamp
                          AND s2.Timestamp > DATEADD(hour, 1, s4.WeekStart)
                          AND s2.[Close] < s2.[Open]  -- Red candle
                          AND s2.[Close] < s4.FirstHourLow
                          AND s2.Low <= ISNULL(s2.WeeklyMinLowBefore, s2.Low)
                          AND s4.[Close] < s2.Low
                    ) THEN 1
                    ELSE 0
                END
            ELSE 0
        END as S8Breakdown
    FROM S4Tracking s4
),
-- Check if S4/S8 just triggered (not previously triggered)
BreakoutTriggers AS (
    SELECT 
        *,
        CASE 
            WHEN S4Breakout = 1 AND LAG(S4Breakout, 1, 0) OVER (PARTITION BY WeekStart ORDER BY Timestamp) = 0 
            THEN 1 ELSE 0 
        END as S4JustTriggered,
        CASE 
            WHEN S8Breakdown = 1 AND LAG(S8Breakdown, 1, 0) OVER (PARTITION BY WeekStart ORDER BY Timestamp) = 0 
            THEN 1 ELSE 0 
        END as S8JustTriggered
    FROM S8Tracking
),
-- Now detect all signals
SignalDetection AS (
    SELECT 
        c2.*,
        c1.[Open] as FirstBarOpen,
        c1.High as FirstBarHigh,
        c1.Low as FirstBarLow,
        c1.[Close] as FirstBarClose,
        -- Detect signals
        CASE
            -- S1: Bear Trap (2nd candle only)
            WHEN c2.CandleNum = 2 
                AND c1.[Open] >= c2.SupportZoneBottom
                AND c1.[Close] < c2.SupportZoneBottom
                AND c2.[Close] > c1.Low
            THEN 'S1'
            
            -- S2: Support Hold (2nd candle, bullish bias, proximity checks)
            WHEN c2.CandleNum = 2
                AND c2.WeeklyBias = 'BULLISH'
                AND c1.[Open] > c2.PrevWeekLow
                AND ABS(c2.PrevWeekClose - c2.SupportZoneBottom) <= c2.MarginLow
                AND ABS(c1.[Open] - c2.SupportZoneBottom) <= c2.MarginLow
                AND c1.[Close] >= c2.SupportZoneBottom
                AND c1.[Close] >= c2.PrevWeekClose
                AND c2.[Close] >= c1.Low
                AND c2.[Close] > c2.PrevWeekClose
                AND c2.[Close] > c2.SupportZoneBottom
            THEN 'S2'
            
            -- S3: Resistance Hold - Scenario A (2nd candle)
            WHEN c2.CandleNum = 2
                AND c2.WeeklyBias = 'BEARISH'
                AND ABS(c2.PrevWeekClose - c2.ResistanceZoneBottom) <= c2.MarginHigh
                AND ABS(c1.[Open] - c2.ResistanceZoneBottom) <= c2.MarginHigh
                AND c1.[Close] <= c2.PrevWeekHigh
                AND c2.[Close] < c1.High
                AND c2.[Close] < c2.ResistanceZoneBottom
                AND (c1.High >= c2.ResistanceZoneBottom OR c2.High >= c2.ResistanceZoneBottom)
            THEN 'S3'
            
            -- S3: Resistance Hold - Scenario B (any candle)
            WHEN c2.WeeklyBias = 'BEARISH'
                AND ABS(c2.PrevWeekClose - c2.ResistanceZoneBottom) <= c2.MarginHigh
                AND ABS(c1.[Open] - c2.ResistanceZoneBottom) <= c2.MarginHigh
                AND c1.[Close] <= c2.PrevWeekHigh
                AND c2.[Close] < c1.Low
                AND c2.[Close] < c2.ResistanceZoneBottom
                AND c2.[Close] < ISNULL(c2.WeeklyMinLowBefore, c2.Low)
                AND c2.[Close] < ISNULL(c2.WeeklyMinCloseBefore, c2.[Close])
            THEN 'S3'
            
            -- S4: Bias Failure Bull
            WHEN c2.S4JustTriggered = 1
                AND c2.WeeklyBias = 'BEARISH'
                AND c1.[Open] > c2.ResistanceZoneTop
            THEN 'S4'
            
            -- S5: Bias Failure Bear
            WHEN c2.WeeklyBias = 'BULLISH'
                AND c1.[Open] < c2.SupportZoneBottom
                AND c2.FirstHourClose < c2.SupportZoneBottom
                AND c2.FirstHourClose < c2.PrevWeekLow
                AND c2.[Close] < c2.FirstHourLow
            THEN 'S5'
            
            -- S6: Weakness Confirmed - Scenario A (2nd candle)
            WHEN c2.CandleNum = 2
                AND c2.WeeklyBias = 'BEARISH'
                AND c1.High >= c2.ResistanceZoneBottom
                AND c1.[Close] <= c2.ResistanceZoneTop
                AND c1.[Close] <= c2.PrevWeekHigh
                AND c2.[Close] < c1.High
                AND c2.[Close] < c2.ResistanceZoneBottom
            THEN 'S6'
            
            -- S6: Weakness Confirmed - Scenario B
            WHEN c2.WeeklyBias = 'BEARISH'
                AND c1.High >= c2.ResistanceZoneBottom
                AND c1.[Close] <= c2.ResistanceZoneTop
                AND c1.[Close] <= c2.PrevWeekHigh
                AND c2.[Close] < c1.Low
                AND c2.[Close] < c2.ResistanceZoneBottom
                AND c2.[Close] < ISNULL(c2.WeeklyMinLowBefore, c2.Low)
                AND c2.[Close] < ISNULL(c2.WeeklyMinCloseBefore, c2.[Close])
            THEN 'S6'
            
            -- S7: 1H Breakout Confirmed
            WHEN c2.S4JustTriggered = 1
                AND NOT (c2.[Close] < c2.PrevWeekHigh AND ((c2.PrevWeekHigh - c2.[Close]) / c2.[Close] * 100) < 0.40)
                AND c2.[Close] > ISNULL(c2.WeeklyMaxHighBefore, 0)
                AND c2.[Close] > ISNULL(c2.WeeklyMaxCloseBefore, 0)
            THEN 'S7'
            
            -- S8: 1H Breakdown Confirmed
            WHEN c2.S8JustTriggered = 1
                AND c2.TouchedUpperZone = 1
                AND c2.[Close] < c2.ResistanceZoneBottom
                AND c2.[Close] < ISNULL(c2.WeeklyMinLowBefore, c2.Low)
                AND c2.[Close] < ISNULL(c2.WeeklyMinCloseBefore, c2.[Close])
            THEN 'S8'
            
            ELSE NULL
        END as SignalType,
        
        -- Calculate stop loss based on signal
        CASE
            WHEN c2.CandleNum = 2 AND c1.[Open] >= c2.SupportZoneBottom AND c1.[Close] < c2.SupportZoneBottom AND c2.[Close] > c1.Low
            THEN c1.Low - ABS(c1.[Open] - c1.[Close])  -- S1
            
            WHEN c2.CandleNum = 2 AND c2.WeeklyBias = 'BULLISH' AND c2.[Close] > c2.SupportZoneBottom
            THEN c2.SupportZoneBottom  -- S2
            
            WHEN c2.WeeklyBias = 'BEARISH' AND c2.[Close] < c2.ResistanceZoneBottom
            THEN c2.PrevWeekHigh  -- S3, S6
            
            WHEN c2.S4JustTriggered = 1 OR c2.[Close] > ISNULL(c2.WeeklyMaxHighBefore, 0)
            THEN c2.FirstHourLow  -- S4, S7
            
            WHEN c2.WeeklyBias = 'BULLISH' AND c2.[Close] < c2.FirstHourLow
            THEN c2.FirstHourHigh  -- S5
            
            WHEN c2.S8JustTriggered = 1
            THEN c2.FirstHourHigh  -- S8
            
            ELSE NULL
        END as StopLossPrice
        
    FROM BreakoutTriggers c2
    CROSS APPLY (
        SELECT TOP 1 * FROM BreakoutTriggers c1 
        WHERE c1.WeekStart = c2.WeekStart AND c1.CandleNum = 1
    ) c1
    WHERE c2.CandleNum >= 2  -- Signals start from 2nd candle
),
-- Get first signal per week only
FirstSignalPerWeek AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY WeekStart ORDER BY Timestamp) as SignalRank,
        -- Option type and strike calculation
        CASE 
            WHEN SignalType IN ('S1', 'S2', 'S4', 'S7') THEN 'PE'
            WHEN SignalType IN ('S3', 'S5', 'S6', 'S8') THEN 'CE'
        END as OptionType,
        -- Round to 100 (not 50 as in your original)
        CASE 
            WHEN SignalType IN ('S1', 'S2', 'S4', 'S7') THEN ROUND(StopLossPrice/100, 0) * 100
            WHEN SignalType IN ('S3', 'S5', 'S6', 'S8') THEN ROUND(StopLossPrice/100, 0) * 100
        END as MainStrikePrice
    FROM SignalDetection
    WHERE SignalType IS NOT NULL
)
-- Insert final results with stop loss tracking
INSERT INTO SignalAnalysis
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
    MarginHigh,
    MarginLow,
    WeeklyBias,
    DATEADD(hour, 9, DATEADD(minute, 15, CAST(WeekStart as DATETIME))) as FirstHourTime,
    FirstBarOpen as FirstHourOpen,
    FirstBarHigh as FirstHourHigh,
    FirstBarLow as FirstHourLow,
    FirstBarClose as FirstHourClose,
    SignalType,
    Timestamp as SignalTriggeredTime,
    Timestamp as EntryTime,
    [Close] as EntryPrice,
    FirstBarOpen as FirstCandleOpen,
    FirstBarHigh as FirstCandleHigh,
    FirstBarLow as FirstCandleLow,
    FirstBarClose as FirstCandleClose,
    CASE WHEN CandleNum = 2 THEN [Open] END as SecondCandleOpen,
    CASE WHEN CandleNum = 2 THEN High END as SecondCandleHigh,
    CASE WHEN CandleNum = 2 THEN Low END as SecondCandleLow,
    CASE WHEN CandleNum = 2 THEN [Close] END as SecondCandleClose,
    [Open] as EntryCandleOpen,
    High as EntryCandleHigh,
    Low as EntryCandleLow,
    [Close] as EntryCandleClose,
    StopLossPrice,
    MainStrikePrice,
    OptionType,
    -- Hedge strikes
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 100 ELSE MainStrikePrice + 100 END as HedgeStrike100Away,
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 150 ELSE MainStrikePrice + 150 END as HedgeStrike150Away,
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 200 ELSE MainStrikePrice + 200 END as HedgeStrike200Away,
    CASE WHEN OptionType = 'PE' THEN MainStrikePrice - 300 ELSE MainStrikePrice + 300 END as HedgeStrike300Away,
    0 as StopLossHit,
    NULL as StopLossHitTime,
    NULL as StopLossHitCandleOpen,
    NULL as StopLossHitCandleHigh,
    NULL as StopLossHitCandleLow,
    NULL as StopLossHitCandleClose,
    'PENDING' as WeeklyOutcome
FROM FirstSignalPerWeek
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
    WeeklyOutcome = CASE 
        WHEN sl.Timestamp IS NOT NULL THEN 'LOSS'
        WHEN DATEPART(dw, GETDATE()) > 5 OR CAST(GETDATE() as DATE) > sa.WeekEndDate THEN 'WIN'
        ELSE 'OPEN'
    END
FROM SignalAnalysis sa
OUTER APPLY (
    SELECT TOP 1 *
    FROM NiftyIndexDataHourly h
    WHERE h.Timestamp > sa.EntryTime
        AND h.Timestamp <= DATEADD(day, 1, sa.WeekEndDate)  -- Till Friday
        AND (
            (sa.OptionType = 'PE' AND h.[Close] <= sa.StopLossPrice)
            OR
            (sa.OptionType = 'CE' AND h.[Close] >= sa.StopLossPrice)
        )
    ORDER BY h.Timestamp
) sl;

-- Show results
PRINT 'Signal Detection Complete!';
PRINT '';

SELECT 
    'Year ' + CAST(YEAR(WeekStartDate) as VARCHAR) as Period,
    COUNT(*) as Total,
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

-- Compare with TradingView
PRINT '';
PRINT 'Expected from TradingView (2025):';
PRINT 'S1: 1, S2: 1, S3: 5, S4: 3, S5: 2, S7: 7, S8: 1';

-- Show 2025 signals in detail
SELECT 
    WeekStartDate,
    SignalType,
    CAST(EntryTime as DATE) as EntryDate,
    WeeklyBias,
    StopLossPrice,
    MainStrikePrice,
    OptionType,
    WeeklyOutcome
FROM SignalAnalysis
WHERE YEAR(WeekStartDate) = 2025
ORDER BY WeekStartDate;