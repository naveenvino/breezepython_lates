-- Corrected TradingView Signal Detection with Fixed 4H Body Calculation
-- This implementation fixes all identified issues

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

-- First, let's verify specific weeks that should have signals
PRINT 'Analyzing specific weeks from TradingView results...';

-- Week 1: Jan 13, 2025 - Should have S7
DECLARE @Week1 DATE = '2025-01-13';
WITH Week1Data AS (
    SELECT 
        h.*,
        ROW_NUMBER() OVER (ORDER BY h.Timestamp) as CandleNum
    FROM NiftyIndexDataHourly h
    WHERE h.Timestamp >= @Week1 AND h.Timestamp < DATEADD(day, 5, @Week1)
),
PrevWeekData AS (
    SELECT 
        MAX(High) as PrevHigh,
        MIN(Low) as PrevLow,
        MAX(CASE WHEN DATEPART(hour, Timestamp) = 15 THEN [Close] END) as PrevClose
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= DATEADD(week, -1, @Week1) AND Timestamp < @Week1
),
-- CORRECTED 4H Body Calculation for Indian Market Hours
FourHourBodies AS (
    SELECT 
        CASE 
            WHEN DATEPART(hour, Timestamp) BETWEEN 9 AND 12 THEN 'Period1'  -- 9:15 AM - 1:15 PM
            ELSE 'Period2'  -- 1:15 PM - 3:30 PM
        END as Period,
        MAX(CASE WHEN [Open] > [Close] THEN [Open] ELSE [Close] END) as MaxBody,
        MIN(CASE WHEN [Open] < [Close] THEN [Open] ELSE [Close] END) as MinBody
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= DATEADD(week, -1, @Week1) AND Timestamp < @Week1
    GROUP BY CASE 
        WHEN DATEPART(hour, Timestamp) BETWEEN 9 AND 12 THEN 'Period1'
        ELSE 'Period2'
    END
),
MaxMinBodies AS (
    SELECT MAX(MaxBody) as Max4HBody, MIN(MinBody) as Min4HBody
    FROM FourHourBodies
),
BiasCalc AS (
    SELECT 
        p.PrevClose,
        b.Max4HBody,
        b.Min4HBody,
        ABS(p.PrevClose - b.Max4HBody) as DistToMax,
        ABS(p.PrevClose - b.Min4HBody) as DistToMin,
        CASE 
            WHEN ABS(p.PrevClose - b.Max4HBody) < ABS(p.PrevClose - b.Min4HBody) THEN 'BEARISH'
            WHEN ABS(p.PrevClose - b.Min4HBody) < ABS(p.PrevClose - b.Max4HBody) THEN 'BULLISH'
            ELSE 'NEUTRAL'
        END as Bias
    FROM PrevWeekData p, MaxMinBodies b
)
SELECT 
    'Week Jan 13' as Week,
    w1.CandleNum,
    w1.Timestamp,
    w1.[Close],
    p.PrevHigh,
    b.Bias,
    CASE 
        WHEN w1.CandleNum = 1 THEN 'First Hour'
        WHEN w1.[Close] > (SELECT High FROM Week1Data WHERE CandleNum = 1) THEN 'Above 1H High'
        ELSE ''
    END as Note
FROM Week1Data w1
CROSS JOIN PrevWeekData p
CROSS JOIN BiasCalc b
WHERE w1.CandleNum <= 7;

-- Now run the full corrected signal detection
PRINT '';
PRINT 'Running corrected signal detection...';

-- Process signals with corrected logic
DECLARE @StartDate DATE = '2025-01-01';
DECLARE @EndDate DATE = '2025-07-31';

-- Main signal detection with all fixes
WITH WeekBoundaries AS (
    SELECT DISTINCT
        DATEADD(day, 2 - DATEPART(dw, CAST(Timestamp as DATE)), CAST(Timestamp as DATE)) as WeekStart,
        DATEADD(day, 6 - DATEPART(dw, CAST(Timestamp as DATE)), CAST(Timestamp as DATE)) as WeekEnd
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= DATEADD(week, -1, @StartDate) AND Timestamp <= @EndDate
),
-- Get previous week stats with CORRECTED 4H bodies
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
            -- Get Friday close
            MAX(CASE WHEN DATEPART(dw, h.Timestamp) = 6 AND DATEPART(hour, h.Timestamp) = 15 THEN h.[Close] END) as ClosePrice,
            -- CORRECTED: Calculate 4H bodies properly
            MAX(bodies.MaxBody) as Max4HBody,
            MIN(bodies.MinBody) as Min4HBody
        FROM NiftyIndexDataHourly h
        CROSS APPLY (
            SELECT 
                MAX(CASE WHEN h2.[Open] > h2.[Close] THEN h2.[Open] ELSE h2.[Close] END) as MaxBody,
                MIN(CASE WHEN h2.[Open] < h2.[Close] THEN h2.[Open] ELSE h2.[Close] END) as MinBody
            FROM NiftyIndexDataHourly h2
            WHERE h2.Timestamp >= DATEADD(week, -1, wb.WeekStart)
              AND h2.Timestamp < wb.WeekStart
              AND CAST(h2.Timestamp as DATE) = CAST(h.Timestamp as DATE)
              AND CASE 
                    WHEN DATEPART(hour, h2.Timestamp) BETWEEN 9 AND 12 THEN 'Period1'
                    ELSE 'Period2'
                  END = CASE 
                    WHEN DATEPART(hour, h.Timestamp) BETWEEN 9 AND 12 THEN 'Period1'
                    ELSE 'Period2'
                  END
        ) bodies
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
        -- Margins (3x zone height or 0.05 minimum)
        CASE WHEN (ResistanceZoneTop - ResistanceZoneBottom) * 3 > 0.05 
             THEN (ResistanceZoneTop - ResistanceZoneBottom) * 3 
             ELSE 0.05 END as MarginHigh,
        CASE WHEN (SupportZoneTop - SupportZoneBottom) * 3 > 0.05 
             THEN (SupportZoneTop - SupportZoneBottom) * 3 
             ELSE 0.05 END as MarginLow,
        -- Weekly Bias (CORRECTED distance calculation)
        CASE 
            WHEN ABS(PrevWeekClose - PrevWeek4HMaxBody) < ABS(PrevWeekClose - PrevWeek4HMinBody) THEN 'BEARISH'
            WHEN ABS(PrevWeekClose - PrevWeek4HMinBody) < ABS(PrevWeekClose - PrevWeek4HMaxBody) THEN 'BULLISH'
            ELSE 'NEUTRAL'
        END as WeeklyBias
    FROM ZonesCalc
),
-- Get all week candles with CORRECTED weekly min/max tracking
WeekCandlesWithStats AS (
    SELECT 
        z.*,
        h.*,
        ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as CandleNum,
        -- FIXED: Use MAX instead of NULL for proper comparison
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) > 1
             THEN MAX(h.High) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
             ELSE 0 END as WeeklyMaxHighBefore,
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) > 1
             THEN MIN(h.Low) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
             ELSE 999999 END as WeeklyMinLowBefore,
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) > 1
             THEN MAX(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
             ELSE 0 END as WeeklyMaxCloseBefore,
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) > 1
             THEN MIN(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
             ELSE 999999 END as WeeklyMinCloseBefore,
        -- Track zone touches
        MAX(CASE WHEN h.High >= z.ResistanceZoneBottom THEN 1 ELSE 0 END) 
            OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as TouchedUpperZone,
        -- Get first hour data for easy access
        FIRST_VALUE(h.High) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as FirstHourHigh,
        FIRST_VALUE(h.Low) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as FirstHourLow,
        FIRST_VALUE(h.[Close]) OVER (PARTITION BY z.WeekStart ORDER BY h.Timestamp) as FirstHourClose
    FROM ZonesWithBias z
    INNER JOIN NiftyIndexDataHourly h 
        ON h.Timestamp >= z.WeekStart 
        AND h.Timestamp < DATEADD(day, 5, z.WeekStart)
),
-- CORRECTED S4 Breakout Tracking with proper state management
S4BreakoutTracking AS (
    SELECT 
        w.*,
        -- Track if we have a valid breakout candle in the week
        MAX(CASE 
            WHEN w.[Close] > w.FirstHourHigh 
                 AND w.High >= w.WeeklyMaxHighBefore 
                 AND w.[Close] > w.[Open] THEN w.High 
            ELSE NULL 
        END) OVER (PARTITION BY w.WeekStart ORDER BY w.Timestamp) as BreakoutCandleHigh,
        -- S4 triggers when conditions met
        CASE 
            WHEN w.WeeklyBias = 'BEARISH' 
                 AND w.CandleNum = 1 
                 AND w.[Open] > w.ResistanceZoneTop THEN 1
            ELSE 0
        END as S4Conditions
    FROM WeekCandlesWithStats w
),
-- Now detect all signals with FIXED logic
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
            
            -- S3: Resistance Hold - Scenario A (2nd candle) - FIXED NULL handling
            WHEN c2.CandleNum = 2
                AND c2.WeeklyBias = 'BEARISH'
                AND ABS(c2.PrevWeekClose - c2.ResistanceZoneBottom) <= c2.MarginHigh
                AND ABS(c1.[Open] - c2.ResistanceZoneBottom) <= c2.MarginHigh
                AND c1.[Close] <= c2.PrevWeekHigh
                AND c2.[Close] < c1.High
                AND c2.[Close] < c2.ResistanceZoneBottom
                AND (c1.High >= c2.ResistanceZoneBottom OR c2.High >= c2.ResistanceZoneBottom)
            THEN 'S3'
            
            -- S3: Resistance Hold - Scenario B (any candle) - FIXED NULL handling
            WHEN c2.WeeklyBias = 'BEARISH'
                AND ABS(c2.PrevWeekClose - c2.ResistanceZoneBottom) <= c2.MarginHigh
                AND ABS(c1.[Open] - c2.ResistanceZoneBottom) <= c2.MarginHigh
                AND c1.[Close] <= c2.PrevWeekHigh
                AND c2.[Close] < c1.Low
                AND c2.[Close] < c2.ResistanceZoneBottom
                AND c2.[Close] < c2.WeeklyMinLowBefore
                AND c2.[Close] < c2.WeeklyMinCloseBefore
            THEN 'S3'
            
            -- S4: Bias Failure Bull - With proper breakout tracking
            WHEN c2.S4Conditions = 1
                AND c2.[Close] > c2.FirstHourHigh
                AND (c2.CandleNum = 1 OR c2.BreakoutCandleHigh IS NOT NULL)
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
            
            -- S6: Weakness Confirmed - Scenario B - FIXED NULL handling
            WHEN c2.WeeklyBias = 'BEARISH'
                AND c1.High >= c2.ResistanceZoneBottom
                AND c1.[Close] <= c2.ResistanceZoneTop
                AND c1.[Close] <= c2.PrevWeekHigh
                AND c2.[Close] < c1.Low
                AND c2.[Close] < c2.ResistanceZoneBottom
                AND c2.[Close] < c2.WeeklyMinLowBefore
                AND c2.[Close] < c2.WeeklyMinCloseBefore
            THEN 'S6'
            
            -- S7: 1H Breakout Confirmed - Depends on S4
            WHEN c2.S4Conditions = 1
                AND c2.[Close] > c2.FirstHourHigh
                AND NOT (c2.[Close] < c2.PrevWeekHigh AND ((c2.PrevWeekHigh - c2.[Close]) / c2.[Close] * 100) < 0.40)
                AND c2.[Close] > c2.WeeklyMaxHighBefore
                AND c2.[Close] > c2.WeeklyMaxCloseBefore
            THEN 'S7'
            
            -- S8: 1H Breakdown Confirmed
            WHEN c2.WeeklyBias IN ('BEARISH', 'NEUTRAL')
                AND c1.[Open] < c2.SupportZoneBottom
                AND c2.[Close] < c2.FirstHourLow
                AND c2.TouchedUpperZone = 1
                AND c2.[Close] < c2.ResistanceZoneBottom
                AND c2.[Close] < c2.WeeklyMinLowBefore
                AND c2.[Close] < c2.WeeklyMinCloseBefore
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
            
            WHEN c2.S4Conditions = 1 AND c2.[Close] > c2.FirstHourHigh
            THEN c2.FirstHourLow  -- S4, S7
            
            WHEN c2.WeeklyBias = 'BULLISH' AND c2.[Close] < c2.FirstHourLow
            THEN c2.FirstHourHigh  -- S5
            
            WHEN c2.[Close] < c2.FirstHourLow AND c2.TouchedUpperZone = 1
            THEN c2.FirstHourHigh  -- S8
            
            ELSE NULL
        END as StopLossPrice
        
    FROM S4BreakoutTracking c2
    CROSS APPLY (
        SELECT TOP 1 * FROM S4BreakoutTracking c1 
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
        -- Round to 50 for NIFTY
        CASE 
            WHEN SignalType IN ('S1', 'S2', 'S4', 'S7') THEN ROUND(StopLossPrice/50, 0) * 50
            WHEN SignalType IN ('S3', 'S5', 'S6', 'S8') THEN ROUND(StopLossPrice/50, 0) * 50
        END as MainStrikePrice
    FROM SignalDetection
    WHERE SignalType IS NOT NULL
)
-- Show results
SELECT 
    'Year ' + CAST(YEAR(WeekStart) as VARCHAR) as Period,
    COUNT(*) as Total,
    SUM(CASE WHEN SignalType = 'S1' THEN 1 ELSE 0 END) as S1,
    SUM(CASE WHEN SignalType = 'S2' THEN 1 ELSE 0 END) as S2,
    SUM(CASE WHEN SignalType = 'S3' THEN 1 ELSE 0 END) as S3,
    SUM(CASE WHEN SignalType = 'S4' THEN 1 ELSE 0 END) as S4,
    SUM(CASE WHEN SignalType = 'S5' THEN 1 ELSE 0 END) as S5,
    SUM(CASE WHEN SignalType = 'S6' THEN 1 ELSE 0 END) as S6,
    SUM(CASE WHEN SignalType = 'S7' THEN 1 ELSE 0 END) as S7,
    SUM(CASE WHEN SignalType = 'S8' THEN 1 ELSE 0 END) as S8
FROM FirstSignalPerWeek
WHERE SignalRank = 1
GROUP BY YEAR(WeekStart)
ORDER BY YEAR(WeekStart);

-- Compare with TradingView
PRINT '';
PRINT 'Expected from TradingView (2025):';
PRINT 'S1: 1, S2: 1, S3: 5, S4: 3, S5: 2, S7: 7, S8: 1';
PRINT 'Total: 21 signals';

-- Show 2025 signals in detail
SELECT 
    WeekStart,
    SignalType,
    CAST(Timestamp as DATE) as EntryDate,
    WeeklyBias,
    ROUND(StopLossPrice, 2) as StopLoss,
    MainStrikePrice,
    OptionType
FROM FirstSignalPerWeek
WHERE YEAR(WeekStart) = 2025 AND SignalRank = 1
ORDER BY WeekStart;