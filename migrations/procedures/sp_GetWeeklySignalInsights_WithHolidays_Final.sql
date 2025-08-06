-- This version returns EXACT same columns as original, with holiday logic added
CREATE OR ALTER PROCEDURE sp_GetWeeklySignalInsights_WithHolidays_Final
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

    -- SIMPLIFICATION: Just mark holidays in a temp table
    DECLARE @Holidays TABLE (HolidayDate DATE);
    INSERT INTO @Holidays
    SELECT HolidayDate 
    FROM TradingHolidays 
    WHERE HolidayDate BETWEEN @StartDate AND DATEADD(day, 7, @EndDate)
    AND IsTradingHoliday = 1;

    WITH
    -- Base hourly data with week information (Sunday as week start)
    HourlyDataWithWeekInfo AS (
        SELECT *,
            YEAR([timestamp]) AS yr,
            DATEPART(wk, [timestamp]) AS wk,
            DATEADD(wk, DATEDIFF(wk, 0, [timestamp]), 0) as WeekStartDate,
            ROW_NUMBER() OVER (
                PARTITION BY DATEADD(wk, DATEDIFF(wk, 0, [timestamp]), 0)
                ORDER BY [timestamp]
            ) AS BarNum,
            DATEPART(dw, [timestamp]) AS DayOfWeek,
            DATEADD(HOUR, 1, [timestamp]) as NextBarTimestamp,
            -- Simple holiday flag
            CASE WHEN EXISTS (SELECT 1 FROM @Holidays WHERE HolidayDate = CAST([timestamp] AS DATE))
                 THEN 1 ELSE 0 END as IsHoliday
        FROM NiftyIndexDataHourly 
        WHERE CAST([timestamp] AS DATE) BETWEEN @StartDate AND @EndDate
        -- Filter out weekends
        AND DATEPART(dw, [timestamp]) NOT IN (1, 7)
    ),
    
    -- Calculate adjusted expiry dates considering holidays
    AdjustedExpiryDates AS (
        SELECT DISTINCT
            WeekStartDate,
            DATEADD(dd, 5 - DATEPART(dw, WeekStartDate), WeekStartDate) as ThursdayDate,
            -- Simplified holiday check
            CASE 
                WHEN EXISTS (SELECT 1 FROM @Holidays WHERE HolidayDate = DATEADD(dd, 5 - DATEPART(dw, WeekStartDate), WeekStartDate))
                THEN DATEADD(dd, 4 - DATEPART(dw, WeekStartDate), WeekStartDate) -- Use Wednesday
                ELSE DATEADD(dd, 5 - DATEPART(dw, WeekStartDate), WeekStartDate) -- Use Thursday
            END as ActualExpiryDate,
            CASE 
                WHEN EXISTS (SELECT 1 FROM @Holidays WHERE HolidayDate = DATEADD(dd, 5 - DATEPART(dw, WeekStartDate), WeekStartDate))
                THEN 4  -- Wednesday
                ELSE 5  -- Thursday
            END as ExpiryDayOfWeek
        FROM HourlyDataWithWeekInfo
        WHERE IsHoliday = 0
    ),
    
    -- Weekly aggregates from hourly data
    WeeklyAggregates AS (
        SELECT 
            WeekStartDate, 
            MAX([high]) as WeekHigh, 
            MIN([low]) as WeekLow, 
            (SELECT TOP 1 [close] 
             FROM HourlyDataWithWeekInfo sub 
             WHERE sub.WeekStartDate = main.WeekStartDate 
             AND sub.IsHoliday = 0
             ORDER BY [timestamp] DESC) as WeekClose
        FROM HourlyDataWithWeekInfo main 
        WHERE IsHoliday = 0
        GROUP BY WeekStartDate
    ),
    
    -- Previous week context including 4H data
    WeeklyContext AS (
        SELECT 
            WeekStartDate, 
            LAG(WeekHigh, 1, 0) OVER (ORDER BY WeekStartDate) as PrevWeekHigh, 
            LAG(WeekLow, 1, 0) OVER (ORDER BY WeekStartDate) as PrevWeekLow, 
            LAG(WeekClose, 1, 0) OVER (ORDER BY WeekStartDate) as PrevWeekClose,
            (SELECT MAX(CASE WHEN f.[Open] > f.[Close] THEN f.[Open] ELSE f.[Close] END) 
             FROM NiftyIndexData4Hour f 
             WHERE f.[timestamp] >= DATEADD(wk, -1, WeekStartDate) 
             AND f.[timestamp] < WeekStartDate
             AND CAST(f.[timestamp] AS DATE) NOT IN (SELECT HolidayDate FROM @Holidays)
            ) as PrevWeek4HMaxBody,
            (SELECT MIN(CASE WHEN f.[Open] < f.[Close] THEN f.[Open] ELSE f.[Close] END) 
             FROM NiftyIndexData4Hour f 
             WHERE f.[timestamp] >= DATEADD(wk, -1, WeekStartDate) 
             AND f.[timestamp] < WeekStartDate
             AND CAST(f.[timestamp] AS DATE) NOT IN (SELECT HolidayDate FROM @Holidays)
            ) as PrevWeek4HMinBody
        FROM WeeklyAggregates
    ),
    
    -- First hour data for each week
    FirstHourData AS (
        SELECT DISTINCT
            WeekStartDate,
            FIRST_VALUE([high]) OVER (PARTITION BY WeekStartDate ORDER BY [timestamp]) as FirstHourHigh,
            FIRST_VALUE([low]) OVER (PARTITION BY WeekStartDate ORDER BY [timestamp]) as FirstHourLow,
            FIRST_VALUE([close]) OVER (PARTITION BY WeekStartDate ORDER BY [timestamp]) as FirstHourClose
        FROM HourlyDataWithWeekInfo
        WHERE BarNum = 1 AND IsHoliday = 0
    ),
    
    -- Weekly running min/max values (for S3, S6, S7, S8 scenarios)
    WeeklyMinMaxTracking AS (
        SELECT 
            h.*,
            MAX(h.[high]) OVER (
                PARTITION BY h.WeekStartDate 
                ORDER BY h.[timestamp] 
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) as MaxHighBeforeThisBar,
            MAX(h.[close]) OVER (
                PARTITION BY h.WeekStartDate 
                ORDER BY h.[timestamp] 
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) as MaxCloseBeforeThisBar,
            MIN(h.[low]) OVER (
                PARTITION BY h.WeekStartDate 
                ORDER BY h.[timestamp] 
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) as MinLowBeforeThisBar,
            MIN(h.[close]) OVER (
                PARTITION BY h.WeekStartDate 
                ORDER BY h.[timestamp] 
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) as MinCloseBeforeThisBar
        FROM HourlyDataWithWeekInfo h
        WHERE h.IsHoliday = 0
    ),
    
    -- S4 Logic Implementation with breakout candle tracking
    S4_Logic AS (
        SELECT 
            h.*,
            fh.FirstHourHigh,
            fh.FirstHourLow,
            MAX(h.[high]) OVER (
                PARTITION BY h.WeekStartDate 
                ORDER BY h.[timestamp] 
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) as HighestHighBeforeThisBar,
            MIN(h.DayOfWeek) OVER (PARTITION BY h.WeekStartDate) as FirstDayOfWeek,
            CASE 
                WHEN h.[close] > h.[open]
                     AND h.[close] > fh.FirstHourHigh
                     AND h.[high] >= ISNULL(
                         MAX(h.[high]) OVER (
                             PARTITION BY h.WeekStartDate 
                             ORDER BY h.[timestamp] 
                             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                         ), 0)
                THEN h.[high]
                ELSE NULL
            END as PotentialBreakoutCandleHigh
        FROM HourlyDataWithWeekInfo h
        JOIN FirstHourData fh ON h.WeekStartDate = fh.WeekStartDate
        WHERE h.IsHoliday = 0
    ),
    
    S4_Triggers AS (
        SELECT 
            *,
            CASE 
                WHEN DayOfWeek = FirstDayOfWeek AND [close] > FirstHourHigh 
                THEN 1
                WHEN DayOfWeek > FirstDayOfWeek 
                     AND EXISTS (
                         SELECT 1 FROM S4_Logic s4_prev
                         WHERE s4_prev.WeekStartDate = S4_Logic.WeekStartDate
                         AND s4_prev.[timestamp] < S4_Logic.[timestamp]
                         AND s4_prev.PotentialBreakoutCandleHigh IS NOT NULL
                     )
                     AND [close] > (
                         SELECT MAX(PotentialBreakoutCandleHigh) 
                         FROM S4_Logic s4_prev
                         WHERE s4_prev.WeekStartDate = S4_Logic.WeekStartDate
                         AND s4_prev.[timestamp] < S4_Logic.[timestamp]
                         AND s4_prev.PotentialBreakoutCandleHigh IS NOT NULL
                     )
                THEN 1
                ELSE 0
            END as S4_Trigger
        FROM S4_Logic
    ),
    
    -- S8 Logic Implementation (1H breakdown logic)
    S8_Logic AS (
        SELECT 
            h.*,
            fh.FirstHourLow,
            fh.FirstHourHigh,
            MIN(h.[low]) OVER (
                PARTITION BY h.WeekStartDate 
                ORDER BY h.[timestamp] 
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) as LowestLowBeforeThisBar,
            MIN(h.DayOfWeek) OVER (PARTITION BY h.WeekStartDate) as FirstDayOfWeek,
            CASE 
                WHEN h.[close] < h.[open]
                     AND h.[close] < fh.FirstHourLow
                     AND h.[low] <= ISNULL(
                         MIN(h.[low]) OVER (
                             PARTITION BY h.WeekStartDate 
                             ORDER BY h.[timestamp] 
                             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                         ), 999999)
                THEN h.[low]
                ELSE NULL
            END as PotentialBreakdownCandleLow
        FROM HourlyDataWithWeekInfo h
        JOIN FirstHourData fh ON h.WeekStartDate = fh.WeekStartDate
        WHERE h.IsHoliday = 0
    ),
    
    S8_Triggers AS (
        SELECT 
            *,
            CASE 
                WHEN DayOfWeek = FirstDayOfWeek AND [close] < FirstHourLow 
                THEN 1
                WHEN DayOfWeek > FirstDayOfWeek 
                     AND EXISTS (
                         SELECT 1 FROM S8_Logic s8_prev
                         WHERE s8_prev.WeekStartDate = S8_Logic.WeekStartDate
                         AND s8_prev.[timestamp] < S8_Logic.[timestamp]
                         AND s8_prev.PotentialBreakdownCandleLow IS NOT NULL
                     )
                     AND [close] < (
                         SELECT MIN(PotentialBreakdownCandleLow) 
                         FROM S8_Logic s8_prev
                         WHERE s8_prev.WeekStartDate = S8_Logic.WeekStartDate
                         AND s8_prev.[timestamp] < S8_Logic.[timestamp]
                         AND s8_prev.PotentialBreakdownCandleLow IS NOT NULL
                     )
                THEN 1
                ELSE 0
            END as S8_Trigger
        FROM S8_Logic
    ),
    
    -- Main signal evaluation with all necessary data
    SignalEvaluation AS (
        SELECT 
            h.*,
            wc.PrevWeekHigh,
            wc.PrevWeekLow,
            wc.PrevWeekClose,
            wc.PrevWeek4HMaxBody,
            wc.PrevWeek4HMinBody,
            fh.FirstHourHigh,
            fh.FirstHourLow,
            fh.FirstHourClose,
            wmt.MaxHighBeforeThisBar,
            wmt.MaxCloseBeforeThisBar,
            wmt.MinLowBeforeThisBar,
            wmt.MinCloseBeforeThisBar,
            LAG(wmt.MinLowBeforeThisBar, 1) OVER (PARTITION BY h.WeekStartDate ORDER BY h.[timestamp]) as PrevBarWeeklyMinLow,
            LAG(wmt.MinCloseBeforeThisBar, 1) OVER (PARTITION BY h.WeekStartDate ORDER BY h.[timestamp]) as PrevBarWeeklyMinClose,
            LAG(wmt.MaxHighBeforeThisBar, 1) OVER (PARTITION BY h.WeekStartDate ORDER BY h.[timestamp]) as PrevBarWeeklyMaxHigh,
            LAG(wmt.MaxCloseBeforeThisBar, 1) OVER (PARTITION BY h.WeekStartDate ORDER BY h.[timestamp]) as PrevBarWeeklyMaxClose,
            
            -- Zone calculations
            CASE WHEN wc.PrevWeekHigh > wc.PrevWeek4HMaxBody 
                 THEN wc.PrevWeekHigh 
                 ELSE wc.PrevWeek4HMaxBody END AS ResistanceZoneTop,
            CASE WHEN wc.PrevWeekHigh < wc.PrevWeek4HMaxBody 
                 THEN wc.PrevWeekHigh 
                 ELSE wc.PrevWeek4HMaxBody END AS ResistanceZoneBottom,
            CASE WHEN wc.PrevWeekLow > wc.PrevWeek4HMinBody 
                 THEN wc.PrevWeekLow 
                 ELSE wc.PrevWeek4HMinBody END AS SupportZoneTop,
            CASE WHEN wc.PrevWeekLow < wc.PrevWeek4HMinBody 
                 THEN wc.PrevWeekLow 
                 ELSE wc.PrevWeek4HMinBody END AS SupportZoneBottom,
            
            -- Weekly bias
            CASE 
                WHEN ABS(wc.PrevWeekClose - wc.PrevWeek4HMaxBody) < ABS(wc.PrevWeekClose - wc.PrevWeek4HMinBody) 
                THEN 'Bearish'
                WHEN ABS(wc.PrevWeekClose - wc.PrevWeek4HMinBody) < ABS(wc.PrevWeekClose - wc.PrevWeek4HMaxBody) 
                THEN 'Bullish'
                ELSE 'Neutral' 
            END as WeeklyBias,
            
            -- First bar data
            FIRST_VALUE(h.[open]) OVER (PARTITION BY h.WeekStartDate ORDER BY h.BarNum) as FirstBarOpen,
            FIRST_VALUE(h.[high]) OVER (PARTITION BY h.WeekStartDate ORDER BY h.BarNum) as FirstBarHigh,
            FIRST_VALUE(h.[low]) OVER (PARTITION BY h.WeekStartDate ORDER BY h.BarNum) as FirstBarLow,
            FIRST_VALUE(h.[close]) OVER (PARTITION BY h.WeekStartDate ORDER BY h.BarNum) as FirstBarClose,
            
            -- Margins
            CASE 
                WHEN ((CASE WHEN wc.PrevWeekHigh > wc.PrevWeek4HMaxBody THEN wc.PrevWeekHigh ELSE wc.PrevWeek4HMaxBody END) - 
                      (CASE WHEN wc.PrevWeekHigh < wc.PrevWeek4HMaxBody THEN wc.PrevWeekHigh ELSE wc.PrevWeek4HMaxBody END)) * 3 > 0.05 
                THEN ((CASE WHEN wc.PrevWeekHigh > wc.PrevWeek4HMaxBody THEN wc.PrevWeekHigh ELSE wc.PrevWeek4HMaxBody END) - 
                      (CASE WHEN wc.PrevWeekHigh < wc.PrevWeek4HMaxBody THEN wc.PrevWeekHigh ELSE wc.PrevWeek4HMaxBody END)) * 3 
                ELSE 0.05 
            END as MarginHigh,
            CASE 
                WHEN ((CASE WHEN wc.PrevWeekLow > wc.PrevWeek4HMinBody THEN wc.PrevWeekLow ELSE wc.PrevWeek4HMinBody END) - 
                      (CASE WHEN wc.PrevWeekLow < wc.PrevWeek4HMinBody THEN wc.PrevWeekLow ELSE wc.PrevWeek4HMinBody END)) * 3 > 0.05 
                THEN ((CASE WHEN wc.PrevWeekLow > wc.PrevWeek4HMinBody THEN wc.PrevWeekLow ELSE wc.PrevWeek4HMinBody END) - 
                      (CASE WHEN wc.PrevWeekLow < wc.PrevWeek4HMinBody THEN wc.PrevWeekLow ELSE wc.PrevWeek4HMinBody END)) * 3 
                ELSE 0.05 
            END as MarginLow,
            
            -- S4 and S8 trigger status
            CASE 
                WHEN s4.S4_Trigger = 1 AND NOT EXISTS (
                    SELECT 1 FROM S4_Triggers s4_prev 
                    WHERE s4_prev.WeekStartDate = s4.WeekStartDate 
                    AND s4_prev.[timestamp] < s4.[timestamp] 
                    AND s4_prev.S4_Trigger = 1
                ) THEN 1 ELSE 0 
            END as S4_FirstTrigger,
            
            CASE 
                WHEN s8.S8_Trigger = 1 AND NOT EXISTS (
                    SELECT 1 FROM S8_Triggers s8_prev 
                    WHERE s8_prev.WeekStartDate = s8.WeekStartDate 
                    AND s8_prev.[timestamp] < s8.[timestamp] 
                    AND s8_prev.S8_Trigger = 1
                ) THEN 1 ELSE 0 
            END as S8_FirstTrigger,
            
            -- Add expiry info
            aed.ActualExpiryDate,
            aed.ExpiryDayOfWeek
            
        FROM HourlyDataWithWeekInfo h
        JOIN WeeklyContext wc ON h.WeekStartDate = wc.WeekStartDate
        JOIN FirstHourData fh ON h.WeekStartDate = fh.WeekStartDate
        JOIN WeeklyMinMaxTracking wmt ON h.WeekStartDate = wmt.WeekStartDate AND h.[timestamp] = wmt.[timestamp]
        JOIN AdjustedExpiryDates aed ON h.WeekStartDate = aed.WeekStartDate
        LEFT JOIN S4_Triggers s4 ON h.WeekStartDate = s4.WeekStartDate AND h.[timestamp] = s4.[timestamp]
        LEFT JOIN S8_Triggers s8 ON h.WeekStartDate = s8.WeekStartDate AND h.[timestamp] = s8.[timestamp]
        WHERE wc.PrevWeekHigh > 0 AND h.IsHoliday = 0
    ),
    
    -- Signal Triggers (S1-S8) - Same logic as original
    SignalTriggers AS (
        -- S1: Bear Trap
        SELECT s.*, 'S1' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.BarNum = 2 
        AND s.FirstBarOpen >= s.SupportZoneBottom 
        AND s.FirstBarClose < s.SupportZoneBottom 
        AND s.[Close] > s.FirstBarLow
        
        UNION ALL
        
        -- S2: Support Hold (Bullish)
        SELECT s.*, 'S2' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.BarNum = 2 
        AND s.WeeklyBias = 'Bullish' 
        AND s.FirstBarOpen > s.PrevWeekLow 
        AND ABS(s.PrevWeekClose - s.SupportZoneBottom) <= s.MarginLow 
        AND ABS(s.FirstBarOpen - s.SupportZoneBottom) <= s.MarginLow 
        AND s.FirstBarClose >= s.SupportZoneBottom 
        AND s.FirstBarClose >= s.PrevWeekClose
        AND s.[Close] >= s.FirstBarLow
        AND s.[Close] > s.PrevWeekClose
        AND s.[Close] > s.SupportZoneBottom
        
        UNION ALL
        
        -- S3: Resistance Hold (Bearish) - Scenario A
        SELECT s.*, 'S3' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.BarNum = 2
        AND s.WeeklyBias = 'Bearish' 
        AND ABS(s.PrevWeekClose - s.ResistanceZoneBottom) <= s.MarginHigh 
        AND ABS(s.FirstBarOpen - s.ResistanceZoneBottom) <= s.MarginHigh 
        AND s.FirstBarClose <= s.PrevWeekHigh
        AND s.[Close] < s.FirstBarHigh
        AND s.[Close] < s.ResistanceZoneBottom
        AND (s.FirstBarHigh >= s.ResistanceZoneBottom OR s.[high] >= s.ResistanceZoneBottom)
        
        UNION ALL
        
        -- S3: Resistance Hold (Bearish) - Scenario B
        SELECT s.*, 'S3' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.WeeklyBias = 'Bearish' 
        AND ABS(s.PrevWeekClose - s.ResistanceZoneBottom) <= s.MarginHigh 
        AND ABS(s.FirstBarOpen - s.ResistanceZoneBottom) <= s.MarginHigh 
        AND s.FirstBarClose <= s.PrevWeekHigh
        AND s.[Close] < s.FirstBarLow 
        AND s.[Close] < s.ResistanceZoneBottom
        AND s.[Close] < ISNULL(s.PrevBarWeeklyMinLow, s.[low])
        AND s.[Close] < ISNULL(s.PrevBarWeeklyMinClose, s.[close])
        
        UNION ALL
        
        -- S4: Bias Failure (Bullish)
        SELECT s.*, 'S4' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.WeeklyBias = 'Bearish' 
        AND s.FirstBarOpen > s.ResistanceZoneTop
        AND s.S4_FirstTrigger = 1
        
        UNION ALL
        
        -- S5: Bias Failure (Bearish)
        SELECT s.*, 'S5' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.WeeklyBias = 'Bullish' 
        AND s.FirstBarOpen < s.SupportZoneBottom 
        AND s.FirstHourClose < s.SupportZoneBottom
        AND s.FirstHourClose < s.PrevWeekLow
        AND s.[Close] < s.FirstHourLow
        
        UNION ALL
        
        -- S6: Weakness Confirmed - Scenario A
        SELECT s.*, 'S6' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.BarNum = 2
        AND s.WeeklyBias = 'Bearish' 
        AND s.FirstBarHigh >= s.ResistanceZoneBottom 
        AND s.FirstBarClose <= s.ResistanceZoneTop
        AND s.FirstBarClose <= s.PrevWeekHigh
        AND s.[Close] < s.FirstBarHigh
        AND s.[Close] < s.ResistanceZoneBottom
        
        UNION ALL
        
        -- S6: Weakness Confirmed - Scenario B
        SELECT s.*, 'S6' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.WeeklyBias = 'Bearish' 
        AND s.FirstBarHigh >= s.ResistanceZoneBottom 
        AND s.FirstBarClose <= s.ResistanceZoneTop
        AND s.FirstBarClose <= s.PrevWeekHigh
        AND s.[Close] < s.FirstBarLow 
        AND s.[Close] < s.ResistanceZoneBottom
        AND s.[Close] < ISNULL(s.PrevBarWeeklyMinLow, s.[low])
        AND s.[Close] < ISNULL(s.PrevBarWeeklyMinClose, s.[close])
        
        UNION ALL
        
        -- S7: 1H Breakout Confirmed
        SELECT s.*, 'S7' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.S4_FirstTrigger = 1
        AND NOT (s.[close] < s.PrevWeekHigh AND ((s.PrevWeekHigh - s.[close]) / s.[close] * 100) < 0.40)
        AND s.[close] > ISNULL(s.PrevBarWeeklyMaxHigh, 0)
        AND s.[close] > ISNULL(s.PrevBarWeeklyMaxClose, 0)
        
        UNION ALL
        
        -- S8: 1H Breakdown Confirmed
        SELECT s.*, 'S8' as SignalType 
        FROM SignalEvaluation s 
        WHERE s.S8_FirstTrigger = 1
        AND s.[high] >= s.ResistanceZoneBottom
        AND s.[close] < s.ResistanceZoneBottom
        AND s.[close] < ISNULL(s.PrevBarWeeklyMinLow, s.[low])
        AND s.[close] < ISNULL(s.PrevBarWeeklyMinClose, s.[close])
    ),
    
    -- Final trades - only one signal per week with priority
    FinalTrades AS (
        SELECT *, 
            ROW_NUMBER() OVER (
                PARTITION BY WeekStartDate 
                ORDER BY 
                    CASE SignalType 
                        WHEN 'S1' THEN 1 
                        WHEN 'S2' THEN 2 
                        WHEN 'S3' THEN 3 
                        WHEN 'S4' THEN 4 
                        WHEN 'S5' THEN 5 
                        WHEN 'S6' THEN 6 
                        WHEN 'S7' THEN 7 
                        WHEN 'S8' THEN 8 
                        ELSE 99 
                    END, 
                    [timestamp]
            ) as rn
        FROM SignalTriggers
    ),
    
    -- Trade outcomes with correct stop loss calculations
    TradeOutcomes AS (
        SELECT 
            ft.*,
            CASE 
                WHEN ft.SignalType = 'S1' 
                    THEN FLOOR((ft.FirstBarLow - ABS(ft.FirstBarOpen - ft.FirstBarClose)) / 50) * 50
                WHEN ft.SignalType = 'S2' 
                    THEN FLOOR(ft.SupportZoneBottom / 50) * 50
                WHEN ft.SignalType IN ('S4', 'S7') 
                    THEN FLOOR(ft.FirstHourLow / 50) * 50
                WHEN ft.SignalType IN ('S3', 'S6') 
                    THEN CEILING(ft.PrevWeekHigh / 50) * 50
                WHEN ft.SignalType IN ('S5', 'S8') 
                    THEN CEILING(ft.FirstHourHigh / 50) * 50
            END AS StopLossPrice,
            sl_hit.StopLossHitTime,
            sl_hit.SLHitCandleOpen,
            sl_hit.SLHitCandleClose
        FROM FinalTrades ft
        OUTER APPLY (
            SELECT TOP 1 
                h.NextBarTimestamp AS StopLossHitTime,
                h.[open] AS SLHitCandleOpen,
                h.[close] AS SLHitCandleClose
            FROM HourlyDataWithWeekInfo h 
            WHERE h.yr = ft.yr 
            AND h.wk = ft.wk 
            AND h.[timestamp] > ft.[timestamp]
            -- Check until actual expiry
            AND CAST(h.[timestamp] AS DATE) <= ft.ActualExpiryDate
            AND h.IsHoliday = 0  -- Simple holiday check
            AND (
                (ft.SignalType IN ('S1','S2','S4','S7') AND h.[close] <= 
                    CASE 
                        WHEN ft.SignalType = 'S1' 
                            THEN FLOOR((ft.FirstBarLow - ABS(ft.FirstBarOpen - ft.FirstBarClose)) / 50) * 50
                        WHEN ft.SignalType = 'S2' 
                            THEN FLOOR(ft.SupportZoneBottom / 50) * 50
                        WHEN ft.SignalType IN ('S4', 'S7') 
                            THEN FLOOR(ft.FirstHourLow / 50) * 50
                    END
                ) 
                OR 
                (ft.SignalType IN ('S3','S5','S6','S8') AND h.[close] >= 
                    CASE 
                        WHEN ft.SignalType IN ('S3', 'S6') 
                            THEN CEILING(ft.PrevWeekHigh / 50) * 50
                        WHEN ft.SignalType IN ('S5', 'S8') 
                            THEN CEILING(ft.FirstHourHigh / 50) * 50
                    END
                )
            ) 
            ORDER BY h.[timestamp]
        ) AS sl_hit
        WHERE ft.rn = 1
    ),
    
    -- Option signal details
    OptionSignalDetails AS (
        SELECT 
            t.*,
            t.NextBarTimestamp as ActualEntryTime,
            t.ActualExpiryDate as ExpiryDate,
            -- Calculate signal candle details
            t.[timestamp] as SignalCandleTime,
            t.NextBarTimestamp as SignalCandleCloseTime,
            t.[open] as SignalCandleOpen,
            t.[close] as SignalCandleClose
        FROM TradeOutcomes t
    ),
    
    -- Final signal details with option types
    FinalSignalDetails AS (
        SELECT 
            s.*, 
            ROUND(s.StopLossPrice / 100, 0) * 100 AS MainStrikePrice, 
            CASE 
                WHEN s.SignalType IN ('S1','S2','S4','S7') THEN 'PE' 
                ELSE 'CE' 
            END AS MainOptionType, 
            ISNULL(s.StopLossHitTime, 
                (SELECT TOP 1 h.[timestamp] 
                 FROM HourlyDataWithWeekInfo h 
                 WHERE h.yr = s.yr 
                 AND h.wk = s.wk 
                 AND CAST(h.[timestamp] AS DATE) <= s.ExpiryDate
                 AND h.IsHoliday = 0
                 ORDER BY h.[timestamp] DESC)) as ExitTime
        FROM OptionSignalDetails s
    ),
    
    -- Option leg data with P&L calculation
    OptionLegData AS (
        SELECT 
            s.*, 
            main_entry.[Close] as MainLegEntryPrice, 
            main_exit.[Close] as MainLegExitPrice, 
            CASE 
                WHEN s.StopLossHitTime IS NOT NULL 
                THEN 'SL Hit at ' + CAST(CAST(s.StopLossPrice AS INT) AS VARCHAR) 
                ELSE 'Held to Expiry' 
            END as ReasonForExit
        FROM FinalSignalDetails s
        OUTER APPLY (
            SELECT TOP 1 oh.[Close] 
            FROM OptionsHistoricalData oh 
            WHERE oh.Strike = s.MainStrikePrice 
            AND oh.OptionType = s.MainOptionType 
            AND CAST(oh.ExpiryDate as DATE) = s.ExpiryDate 
            AND oh.[Timestamp] >= s.ActualEntryTime 
            ORDER BY oh.[Timestamp]
        ) AS main_entry
        OUTER APPLY (
            SELECT TOP 1 oh.[Close] 
            FROM OptionsHistoricalData oh 
            WHERE oh.Strike = s.MainStrikePrice 
            AND oh.OptionType = s.MainOptionType 
            AND CAST(oh.ExpiryDate as DATE) = s.ExpiryDate 
            AND oh.[Timestamp] >= CASE 
                WHEN CAST(s.ExitTime AS DATE) > s.ExpiryDate 
                THEN DATEADD(HOUR, 15, CAST(s.ExpiryDate AS DATETIME)) + DATEADD(MINUTE, 15, 0)
                ELSE s.ExitTime 
            END
            AND oh.[Timestamp] <= DATEADD(HOUR, 15, CAST(s.ExpiryDate AS DATETIME)) + DATEADD(MINUTE, 30, 0)
            ORDER BY oh.[Timestamp] DESC
        ) AS main_exit
    )
    SELECT * INTO #TradeResults FROM OptionLegData;

    -- Check hedge strikes availability
    CREATE TABLE #HedgeStrikeAvailability (
        WeekStartDate DATETIME,
        SignalType VARCHAR(2),
        MainStrikePrice FLOAT,
        MainOptionType VARCHAR(2),
        ExpiryDate DATE,
        ActualEntryTime DATETIME,
        ExitTime DATETIME,
        HedgeDistance INT,
        HedgeStrike FLOAT,
        HedgeEntryPrice FLOAT,
        HedgeExitPrice FLOAT,
        Available BIT
    );

    -- Insert hedge strike checks
    INSERT INTO #HedgeStrikeAvailability
    SELECT 
        t.WeekStartDate,
        t.SignalType,
        t.MainStrikePrice,
        t.MainOptionType,
        t.ExpiryDate,
        t.ActualEntryTime,
        t.ExitTime,
        hd.Distance,
        t.MainStrikePrice + (CASE 
            WHEN t.SignalType IN ('S1','S2','S4','S7') THEN -hd.Distance
            ELSE hd.Distance
        END),
        hedge_entry.[Close],
        hedge_exit.[Close],
        CASE WHEN hedge_entry.[Close] IS NOT NULL AND hedge_exit.[Close] IS NOT NULL THEN 1 ELSE 0 END
    FROM #TradeResults t
    CROSS JOIN (VALUES (100), (150), (200), (300)) AS hd(Distance)
    OUTER APPLY (
        SELECT TOP 1 oh.[Close] 
        FROM OptionsHistoricalData oh 
        WHERE oh.Strike = t.MainStrikePrice + (CASE 
            WHEN t.SignalType IN ('S1','S2','S4','S7') THEN -hd.Distance
            ELSE hd.Distance
        END)
        AND oh.OptionType = t.MainOptionType
        AND CAST(oh.ExpiryDate as DATE) = t.ExpiryDate 
        AND oh.[Timestamp] >= t.ActualEntryTime 
        ORDER BY oh.[Timestamp]
    ) AS hedge_entry
    OUTER APPLY (
        SELECT TOP 1 oh.[Close] 
        FROM OptionsHistoricalData oh 
        WHERE oh.Strike = t.MainStrikePrice + (CASE 
            WHEN t.SignalType IN ('S1','S2','S4','S7') THEN -hd.Distance
            ELSE hd.Distance
        END)
        AND oh.OptionType = t.MainOptionType
        AND CAST(oh.ExpiryDate as DATE) = t.ExpiryDate 
        AND oh.[Timestamp] >= CASE 
            WHEN CAST(t.ExitTime AS DATE) > t.ExpiryDate 
            THEN DATEADD(HOUR, 15, CAST(t.ExpiryDate AS DATETIME)) + DATEADD(MINUTE, 15, 0)
            ELSE t.ExitTime 
        END
        AND oh.[Timestamp] <= DATEADD(HOUR, 15, CAST(t.ExpiryDate AS DATETIME)) + DATEADD(MINUTE, 30, 0)
        ORDER BY oh.[Timestamp] DESC
    ) AS hedge_exit;

    -- Return results in EXACT format as original SP
    SELECT 
        -- Missing option strikes
        STUFF((
            SELECT ', ' + CAST(CAST(h.HedgeStrike AS INT) AS VARCHAR) + h.MainOptionType
            FROM #HedgeStrikeAvailability h
            WHERE h.WeekStartDate = t.WeekStartDate
            AND h.SignalType = t.SignalType
            AND h.Available = 0
            FOR XML PATH('')
        ), 1, 2, '') as MissingOptionStrikes,
        
        t.SignalType,
        
        -- Weekly outcome calculation
        CASE 
            WHEN (t.MainLegEntryPrice - ISNULL(t.MainLegExitPrice, 0)) * @LotSize * @LotsToTrade > 0 THEN 'PROFIT'
            WHEN (t.MainLegEntryPrice - ISNULL(t.MainLegExitPrice, 0)) * @LotSize * @LotsToTrade < 0 THEN 'LOSS'
            ELSE 'BREAKEVEN'
        END as WeeklyOutcome,
        
        -- Profit/Loss amounts
        CASE 
            WHEN (t.MainLegEntryPrice - ISNULL(t.MainLegExitPrice, 0)) * @LotSize * @LotsToTrade > 0 
            THEN (t.MainLegEntryPrice - ISNULL(t.MainLegExitPrice, 0)) * @LotSize * @LotsToTrade
            ELSE 0
        END as ProfitAmount,
        
        CASE 
            WHEN (t.MainLegEntryPrice - ISNULL(t.MainLegExitPrice, 0)) * @LotSize * @LotsToTrade < 0 
            THEN ABS((t.MainLegEntryPrice - ISNULL(t.MainLegExitPrice, 0)) * @LotSize * @LotsToTrade)
            ELSE 0
        END as LossAmount,
        
        t.ActualEntryTime as EntryTime,
        t.ExitTime,
        t.WeeklyBias,
        t.ResistanceZoneTop,
        t.ResistanceZoneBottom,
        t.SupportZoneTop,
        t.SupportZoneBottom,
        t.SignalCandleTime,
        t.SignalCandleCloseTime,
        t.SignalCandleOpen,
        t.SignalCandleClose,
        t.StopLossPrice,
        t.StopLossHitTime,
        t.SLHitCandleOpen,
        t.SLHitCandleClose,
        t.ReasonForExit,
        t.MainStrikePrice,
        t.MainOptionType,
        t.MainLegEntryPrice,
        
        -- Hedge 100 details
        t.MainStrikePrice + (CASE WHEN t.SignalType IN ('S1','S2','S4','S7') THEN -100 ELSE 100 END) as Hedge100Strike,
        CAST(ISNULL(h100.Available, 0) AS BIT) as Hedge100Available,
        h100.HedgeEntryPrice as Hedge100EntryPrice,
        
        -- Hedge 150 details
        t.MainStrikePrice + (CASE WHEN t.SignalType IN ('S1','S2','S4','S7') THEN -150 ELSE 150 END) as Hedge150Strike,
        CAST(ISNULL(h150.Available, 0) AS BIT) as Hedge150Available,
        h150.HedgeEntryPrice as Hedge150EntryPrice,
        
        -- Hedge 200 details
        t.MainStrikePrice + (CASE WHEN t.SignalType IN ('S1','S2','S4','S7') THEN -200 ELSE 200 END) as Hedge200Strike,
        CAST(ISNULL(h200.Available, 0) AS BIT) as Hedge200Available,
        h200.HedgeEntryPrice as Hedge200EntryPrice,
        
        -- Hedge 300 details
        t.MainStrikePrice + (CASE WHEN t.SignalType IN ('S1','S2','S4','S7') THEN -300 ELSE 300 END) as Hedge300Strike,
        CAST(ISNULL(h300.Available, 0) AS BIT) as Hedge300Available,
        h300.HedgeEntryPrice as Hedge300EntryPrice,
        
        t.MainLegExitPrice,
        h100.HedgeExitPrice as Hedge100ExitPrice,
        h150.HedgeExitPrice as Hedge150ExitPrice,
        h200.HedgeExitPrice as Hedge200ExitPrice,
        h300.HedgeExitPrice as Hedge300ExitPrice,
        
        t.ExpiryDate as WeeklyExpiryDate,
        t.yr,
        t.wk,
        t.WeekStartDate
        
    FROM #TradeResults t
    LEFT JOIN #HedgeStrikeAvailability h100 ON 
        t.WeekStartDate = h100.WeekStartDate AND 
        t.SignalType = h100.SignalType AND 
        h100.HedgeDistance = 100
    LEFT JOIN #HedgeStrikeAvailability h150 ON 
        t.WeekStartDate = h150.WeekStartDate AND 
        t.SignalType = h150.SignalType AND 
        h150.HedgeDistance = 150
    LEFT JOIN #HedgeStrikeAvailability h200 ON 
        t.WeekStartDate = h200.WeekStartDate AND 
        t.SignalType = h200.SignalType AND 
        h200.HedgeDistance = 200
    LEFT JOIN #HedgeStrikeAvailability h300 ON 
        t.WeekStartDate = h300.WeekStartDate AND 
        t.SignalType = h300.SignalType AND 
        h300.HedgeDistance = 300
    ORDER BY t.[timestamp];
    
    -- Cleanup
    DROP TABLE #TradeResults;
    DROP TABLE #HedgeStrikeAvailability;
END;