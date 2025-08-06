-- Strike Requirements Analysis
-- This script analyzes the SignalAnalysis table to determine optimal strike collection strategy

-- Overall Summary
SELECT 
    'Overall Signal Summary' as ReportType,
    COUNT(*) as TotalSignals,
    COUNT(CASE WHEN WeeklyOutcome = 'WIN' THEN 1 END) as TotalWins,
    COUNT(CASE WHEN WeeklyOutcome = 'LOSS' THEN 1 END) as TotalLosses,
    CAST(COUNT(CASE WHEN WeeklyOutcome = 'WIN' THEN 1 END) * 100.0 / COUNT(*) as DECIMAL(5,2)) as WinRate,
    MIN(CAST(EntryTime as DATE)) as FirstSignalDate,
    MAX(CAST(EntryTime as DATE)) as LastSignalDate
FROM SignalAnalysis
WHERE SignalType IS NOT NULL;

-- Signal Type Breakdown
SELECT 
    'Signal Performance' as ReportType,
    SignalType,
    OptionType,
    COUNT(*) as SignalCount,
    COUNT(CASE WHEN WeeklyOutcome = 'WIN' THEN 1 END) as Wins,
    COUNT(CASE WHEN WeeklyOutcome = 'LOSS' THEN 1 END) as Losses,
    CAST(COUNT(CASE WHEN WeeklyOutcome = 'WIN' THEN 1 END) * 100.0 / COUNT(*) as DECIMAL(5,2)) as WinRate,
    AVG(StopLossPrice) as AvgStopLoss,
    MIN(MainStrikePrice) as MinStrike,
    MAX(MainStrikePrice) as MaxStrike
FROM SignalAnalysis
WHERE SignalType IS NOT NULL
GROUP BY SignalType, OptionType
ORDER BY SignalType;

-- Strike Distribution Analysis
WITH StrikeStats AS (
    SELECT 
        MainStrikePrice,
        OptionType,
        COUNT(*) as UsageCount,
        COUNT(CASE WHEN WeeklyOutcome = 'WIN' THEN 1 END) as WinCount,
        MIN(EntryTime) as FirstUsed,
        MAX(EntryTime) as LastUsed
    FROM SignalAnalysis
    WHERE MainStrikePrice IS NOT NULL
    GROUP BY MainStrikePrice, OptionType
)
SELECT 
    'Strike Usage Distribution' as ReportType,
    MainStrikePrice,
    OptionType,
    UsageCount,
    WinCount,
    CAST(WinCount * 100.0 / UsageCount as DECIMAL(5,2)) as StrikeWinRate,
    FirstUsed,
    LastUsed
FROM StrikeStats
ORDER BY MainStrikePrice;

-- Weekly Strike Range Analysis
WITH WeeklyStrikeRange AS (
    SELECT 
        YEAR(EntryTime) as Year,
        DATEPART(week, EntryTime) as WeekNum,
        MIN(MainStrikePrice) as WeekMinStrike,
        MAX(MainStrikePrice) as WeekMaxStrike,
        MAX(MainStrikePrice) - MIN(MainStrikePrice) as WeekStrikeRange,
        AVG(EntryPrice) as WeekAvgSpot,
        COUNT(*) as SignalsInWeek
    FROM SignalAnalysis
    WHERE MainStrikePrice IS NOT NULL
    GROUP BY YEAR(EntryTime), DATEPART(week, EntryTime)
)
SELECT 
    'Weekly Strike Range Stats' as ReportType,
    AVG(WeekStrikeRange) as AvgWeeklyRange,
    MIN(WeekStrikeRange) as MinWeeklyRange,
    MAX(WeekStrikeRange) as MaxWeeklyRange,
    AVG(WeekMinStrike) as AvgMinStrike,
    AVG(WeekMaxStrike) as AvgMaxStrike,
    AVG(SignalsInWeek) as AvgSignalsPerWeek
FROM WeeklyStrikeRange;

-- Strike Distance from Spot Analysis
WITH StrikeDistance AS (
    SELECT 
        SignalType,
        OptionType,
        EntryPrice,
        MainStrikePrice,
        ABS(MainStrikePrice - EntryPrice) as DistanceFromSpot,
        CASE 
            WHEN OptionType = 'PE' THEN EntryPrice - MainStrikePrice
            WHEN OptionType = 'CE' THEN MainStrikePrice - EntryPrice
        END as OTMDistance,
        WeeklyOutcome
    FROM SignalAnalysis
    WHERE MainStrikePrice IS NOT NULL
)
SELECT 
    'Strike Distance Analysis' as ReportType,
    SignalType,
    OptionType,
    AVG(DistanceFromSpot) as AvgDistanceFromSpot,
    MIN(DistanceFromSpot) as MinDistance,
    MAX(DistanceFromSpot) as MaxDistance,
    AVG(OTMDistance) as AvgOTMDistance,
    COUNT(CASE WHEN OTMDistance < 0 THEN 1 END) as ITMCount,
    COUNT(CASE WHEN OTMDistance >= 0 THEN 1 END) as OTMCount
FROM StrikeDistance
GROUP BY SignalType, OptionType
ORDER BY SignalType;

-- Optimal Strike Collection Strategy
WITH MondaySpots AS (
    SELECT 
        sa.WeekStartDate,
        MIN(h.[Open]) as MondayOpen
    FROM SignalAnalysis sa
    INNER JOIN NiftyIndexDataHourly h ON CAST(h.Timestamp as DATE) = sa.WeekStartDate
        AND DATEPART(hour, h.Timestamp) = 9
    GROUP BY sa.WeekStartDate
),
StrikeRequirements AS (
    SELECT 
        sa.WeekStartDate,
        ms.MondayOpen,
        sa.MainStrikePrice,
        sa.HedgeStrike100Away,
        sa.HedgeStrike150Away,
        sa.HedgeStrike200Away,
        sa.HedgeStrike300Away,
        sa.MainStrikePrice - ms.MondayOpen as MainStrikeDistance,
        sa.OptionType
    FROM SignalAnalysis sa
    INNER JOIN MondaySpots ms ON ms.WeekStartDate = sa.WeekStartDate
    WHERE sa.MainStrikePrice IS NOT NULL
)
SELECT 
    'Optimal Collection Strategy' as ReportType,
    MIN(MainStrikeDistance) as MinDistanceFromMondayOpen,
    MAX(MainStrikeDistance) as MaxDistanceFromMondayOpen,
    AVG(MainStrikeDistance) as AvgDistanceFromMondayOpen,
    PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY MainStrikeDistance) OVER () as Percentile5,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY MainStrikeDistance) OVER () as Percentile95,
    'Collect strikes from MondayOpen-' + CAST(ABS(MIN(MainStrikeDistance)) as VARCHAR) + 
    ' to MondayOpen+' + CAST(MAX(MainStrikeDistance) as VARCHAR) as RecommendedRange
FROM StrikeRequirements;

-- Hedge Strike Analysis
WITH HedgeUsage AS (
    SELECT 
        'Hedge100' as HedgeType, COUNT(DISTINCT HedgeStrike100Away) as UniqueStrikes,
        MIN(HedgeStrike100Away) as MinStrike, MAX(HedgeStrike100Away) as MaxStrike
    FROM SignalAnalysis WHERE HedgeStrike100Away IS NOT NULL
    UNION ALL
    SELECT 
        'Hedge150', COUNT(DISTINCT HedgeStrike150Away),
        MIN(HedgeStrike150Away), MAX(HedgeStrike150Away)
    FROM SignalAnalysis WHERE HedgeStrike150Away IS NOT NULL
    UNION ALL
    SELECT 
        'Hedge200', COUNT(DISTINCT HedgeStrike200Away),
        MIN(HedgeStrike200Away), MAX(HedgeStrike200Away)
    FROM SignalAnalysis WHERE HedgeStrike200Away IS NOT NULL
    UNION ALL
    SELECT 
        'Hedge300', COUNT(DISTINCT HedgeStrike300Away),
        MIN(HedgeStrike300Away), MAX(HedgeStrike300Away)
    FROM SignalAnalysis WHERE HedgeStrike300Away IS NOT NULL
)
SELECT 
    'Hedge Strike Requirements' as ReportType,
    HedgeType,
    UniqueStrikes,
    MinStrike,
    MaxStrike,
    MaxStrike - MinStrike as StrikeRange
FROM HedgeUsage;

-- Monthly Signal Distribution
SELECT 
    'Monthly Distribution' as ReportType,
    YEAR(EntryTime) as Year,
    MONTH(EntryTime) as Month,
    COUNT(*) as SignalCount,
    COUNT(DISTINCT WeekStartDate) as WeeksWithSignals,
    COUNT(DISTINCT MainStrikePrice) as UniqueStrikesUsed,
    STRING_AGG(SignalType, ', ') as SignalTypes
FROM SignalAnalysis
WHERE SignalType IS NOT NULL
GROUP BY YEAR(EntryTime), MONTH(EntryTime)
ORDER BY Year, Month;

-- Final Recommendation
SELECT 
    'FINAL RECOMMENDATION' as ReportType,
    'Based on analysis of ' + CAST(COUNT(*) as VARCHAR) + ' signals from ' + 
    CAST(MIN(CAST(EntryTime as DATE)) as VARCHAR) + ' to ' + 
    CAST(MAX(CAST(EntryTime as DATE)) as VARCHAR) as Analysis,
    'Collect strikes: Monday Open ± 500 points (rounded to 50)' as Strategy,
    'This covers ' + 
    CAST(CAST(COUNT(CASE WHEN ABS(MainStrikePrice - EntryPrice) <= 500 THEN 1 END) * 100.0 / COUNT(*) as INT) as VARCHAR) + 
    '% of all signals' as Coverage,
    'Total unique strikes needed: ' + CAST(COUNT(DISTINCT MainStrikePrice) as VARCHAR) as UniqueStrikes,
    'Strike range: ' + CAST(MIN(MainStrikePrice) as VARCHAR) + ' to ' + CAST(MAX(MainStrikePrice) as VARCHAR) as StrikeRange
FROM SignalAnalysis
WHERE MainStrikePrice IS NOT NULL;