-- Optimized version that pre-filters holiday data to reduce complexity

CREATE OR ALTER PROCEDURE sp_GetWeeklySignalInsights_Optimized
    @StartDate DATE,
    @EndDate DATE,
    @LotSize INT = 75,
    @LotsToTrade INT = 10,
    @CommissionPerLot DECIMAL(10,2) = 40
AS
BEGIN
    SET NOCOUNT ON;

    IF OBJECT_ID('tempdb..#TradeResults') IS NOT NULL DROP TABLE #TradeResults;
    IF OBJECT_ID('tempdb..#HedgeStrikeAvailability') IS NOT NULL DROP TABLE #HedgeStrikeAvailability;
    IF OBJECT_ID('tempdb..#TradingDays') IS NOT NULL DROP TABLE #TradingDays;
    IF OBJECT_ID('tempdb..#FilteredHourlyData') IS NOT NULL DROP TABLE #FilteredHourlyData;

    -- Step 1: Create a list of trading days (excluding holidays)
    CREATE TABLE #TradingDays (
        TradingDate DATE PRIMARY KEY
    );
    
    -- Populate trading days
    WITH DateRange AS (
        SELECT @StartDate as dt
        UNION ALL
        SELECT DATEADD(day, 1, dt)
        FROM DateRange
        WHERE dt < @EndDate
    )
    INSERT INTO #TradingDays
    SELECT dt
    FROM DateRange
    WHERE DATEPART(dw, dt) NOT IN (1, 7) -- Exclude weekends
      AND NOT EXISTS (
          SELECT 1 FROM TradingHolidays th
          WHERE th.HolidayDate = dt
          AND th.IsTradingHoliday = 1
      )
    OPTION (MAXRECURSION 366);

    -- Step 2: Create filtered hourly data (only trading days)
    SELECT h.*,
        YEAR(h.[timestamp]) AS yr,
        DATEPART(wk, h.[timestamp]) AS wk,
        DATEADD(wk, DATEDIFF(wk, 0, h.[timestamp]), 0) as WeekStartDate,
        ROW_NUMBER() OVER (
            PARTITION BY DATEADD(wk, DATEDIFF(wk, 0, h.[timestamp]), 0)
            ORDER BY h.[timestamp]
        ) AS BarNum,
        DATEPART(dw, h.[timestamp]) AS DayOfWeek,
        DATEADD(HOUR, 1, h.[timestamp]) as NextBarTimestamp
    INTO #FilteredHourlyData
    FROM NiftyIndexDataHourly h
    INNER JOIN #TradingDays td ON CAST(h.[timestamp] AS DATE) = td.TradingDate;

    -- Now use #FilteredHourlyData in all CTEs instead of filtering in each query
    WITH
    HourlyDataWithWeekInfo AS (
        SELECT * FROM #FilteredHourlyData
    ),
    
    -- Calculate expiry dates simply (Thursday of each week)
    ExpiryDates AS (
        SELECT DISTINCT
            WeekStartDate,
            -- Simple Thursday calculation (no holiday logic for now)
            DATEADD(dd, 5 - DATEPART(dw, WeekStartDate), WeekStartDate) as ExpiryDate
        FROM HourlyDataWithWeekInfo
    ),
    
    -- Rest of your logic continues with simplified queries...
    WeeklyAggregates AS (
        SELECT 
            WeekStartDate, 
            MAX([high]) as WeekHigh, 
            MIN([low]) as WeekLow, 
            (SELECT TOP 1 [close] 
             FROM HourlyDataWithWeekInfo sub 
             WHERE sub.WeekStartDate = main.WeekStartDate 
             ORDER BY [timestamp] DESC) as WeekClose
        FROM HourlyDataWithWeekInfo main 
        GROUP BY WeekStartDate
    )
    
    -- Continue with rest of procedure...
    SELECT 'Optimized version' as Note;
    
    -- Cleanup
    DROP TABLE #TradingDays;
    DROP TABLE #FilteredHourlyData;
END;