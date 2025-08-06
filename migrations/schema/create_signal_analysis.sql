-- Signal Analysis Table and Processing Script
-- This script analyzes NIFTY hourly data to detect all 8 signals and calculate exact strike requirements

-- Drop table if exists for fresh start
IF OBJECT_ID('SignalAnalysis', 'U') IS NOT NULL
    DROP TABLE SignalAnalysis;

-- Create Signal Analysis Table
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
    WeeklyBias VARCHAR(10), -- 'BULLISH', 'BEARISH', 'NEUTRAL'
    
    -- First Hour Candle (9:15-10:15)
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
    
    -- First Candle Details (9:15-10:15)
    FirstCandleOpen DECIMAL(18,2),
    FirstCandleHigh DECIMAL(18,2),
    FirstCandleLow DECIMAL(18,2),
    FirstCandleClose DECIMAL(18,2),
    
    -- Second Candle Details (10:15-11:15)
    SecondCandleOpen DECIMAL(18,2),
    SecondCandleHigh DECIMAL(18,2),
    SecondCandleLow DECIMAL(18,2),
    SecondCandleClose DECIMAL(18,2),
    
    -- Entry Candle Details (could be 2nd, 3rd, etc.)
    EntryCandleOpen DECIMAL(18,2),
    EntryCandleHigh DECIMAL(18,2),
    EntryCandleLow DECIMAL(18,2),
    EntryCandleClose DECIMAL(18,2),
    
    -- Stop Loss and Strike Information
    StopLossPrice DECIMAL(18,2),
    MainStrikePrice INT,
    OptionType VARCHAR(2), -- 'CE' or 'PE'
    
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
    WeeklyOutcome VARCHAR(10), -- 'WIN', 'LOSS', 'OPEN'
    
    -- Indexes
    INDEX IX_WeekStart (WeekStartDate),
    INDEX IX_SignalType (SignalType),
    INDEX IX_EntryTime (EntryTime)
);

-- Create helper function to get week boundaries
GO
CREATE OR ALTER FUNCTION GetWeekStart(@date DATETIME)
RETURNS DATE
AS
BEGIN
    -- Monday is start of week
    DECLARE @weekday INT = DATEPART(dw, @date);
    DECLARE @monday DATE = DATEADD(day, 2 - @weekday, @date);
    RETURN @monday;
END;
GO

-- Main processing script
DECLARE @StartDate DATE = '2022-01-01';
DECLARE @EndDate DATE = GETDATE();

-- Process all weeks
WITH WeekBoundaries AS (
    SELECT DISTINCT
        dbo.GetWeekStart(Timestamp) as WeekStart,
        DATEADD(day, 4, dbo.GetWeekStart(Timestamp)) as WeekEnd
    FROM NiftyIndexDataHourly
    WHERE Timestamp >= @StartDate
        AND Timestamp <= @EndDate
        AND DATEPART(dw, Timestamp) BETWEEN 2 AND 6 -- Monday to Friday
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
        -- Calculate 4H body max/min for previous week
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
        CASE WHEN PrevWeekHigh > PrevWeek4HMaxBody 
             THEN PrevWeekHigh 
             ELSE PrevWeek4HMaxBody END as ResistanceZoneTop,
        CASE WHEN PrevWeekHigh < PrevWeek4HMaxBody 
             THEN PrevWeekHigh 
             ELSE PrevWeek4HMaxBody END as ResistanceZoneBottom,
        -- Support Zone
        CASE WHEN PrevWeekLow > PrevWeek4HMinBody 
             THEN PrevWeekLow 
             ELSE PrevWeek4HMinBody END as SupportZoneTop,
        CASE WHEN PrevWeekLow < PrevWeek4HMinBody 
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
    WHERE PrevWeekHigh IS NOT NULL -- Ensure we have previous week data
),
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
    INNER JOIN NiftyIndexDataHourly h ON h.Timestamp >= wz.WeekStart 
                                      AND h.Timestamp <= DATEADD(hour, 23, wz.WeekEnd)
),
FirstHourData AS (
    SELECT 
        WeekStart,
        Timestamp as FirstHourTime,
        [Open] as FirstHourOpen,
        High as FirstHourHigh,
        Low as FirstHourLow,
        [Close] as FirstHourClose
    FROM CurrentWeekCandles
    WHERE CandleNum = 1
)
-- We'll continue with signal detection in the next part
SELECT 
    wz.WeekStart,
    wz.WeekEnd,
    wz.PrevWeekHigh,
    wz.PrevWeekLow,
    wz.PrevWeekClose,
    wz.PrevWeek4HMaxBody,
    wz.PrevWeek4HMinBody,
    wz.ResistanceZoneTop,
    wz.ResistanceZoneBottom,
    wz.SupportZoneTop,
    wz.SupportZoneBottom,
    wz.WeeklyBias,
    fh.FirstHourTime,
    fh.FirstHourOpen,
    fh.FirstHourHigh,
    fh.FirstHourLow,
    fh.FirstHourClose
FROM WeeklyZones wz
LEFT JOIN FirstHourData fh ON fh.WeekStart = wz.WeekStart
ORDER BY wz.WeekStart;