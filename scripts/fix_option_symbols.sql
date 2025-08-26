-- Script to fix option symbols by adding day component to the date
-- This updates existing records to match the new format: NIFTY25AUG2124000PE

-- First, let's check what we have
SELECT TOP 10 TradingSymbol, Strike, OptionType, ExpiryDate 
FROM OptionsHistoricalData 
WHERE TradingSymbol LIKE 'NIFTY25%'
ORDER BY Timestamp DESC;

-- Update OptionsHistoricalData table
BEGIN TRANSACTION;

UPDATE OptionsHistoricalData
SET TradingSymbol = 
    CASE 
        -- August 2025 expiries
        WHEN TradingSymbol LIKE 'NIFTY25AUG%' AND DAY(ExpiryDate) = 7 THEN
            REPLACE(TradingSymbol, 'NIFTY25AUG', 'NIFTY25AUG07')
        WHEN TradingSymbol LIKE 'NIFTY25AUG%' AND DAY(ExpiryDate) = 14 THEN
            REPLACE(TradingSymbol, 'NIFTY25AUG', 'NIFTY25AUG14')
        WHEN TradingSymbol LIKE 'NIFTY25AUG%' AND DAY(ExpiryDate) = 21 THEN
            REPLACE(TradingSymbol, 'NIFTY25AUG', 'NIFTY25AUG21')
        WHEN TradingSymbol LIKE 'NIFTY25AUG%' AND DAY(ExpiryDate) = 28 THEN
            REPLACE(TradingSymbol, 'NIFTY25AUG', 'NIFTY25AUG28')
            
        -- July 2025 expiries
        WHEN TradingSymbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 3 THEN
            REPLACE(TradingSymbol, 'NIFTY25JUL', 'NIFTY25JUL03')
        WHEN TradingSymbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 10 THEN
            REPLACE(TradingSymbol, 'NIFTY25JUL', 'NIFTY25JUL10')
        WHEN TradingSymbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 17 THEN
            REPLACE(TradingSymbol, 'NIFTY25JUL', 'NIFTY25JUL17')
        WHEN TradingSymbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 24 THEN
            REPLACE(TradingSymbol, 'NIFTY25JUL', 'NIFTY25JUL24')
        WHEN TradingSymbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 31 THEN
            REPLACE(TradingSymbol, 'NIFTY25JUL', 'NIFTY25JUL31')
            
        -- June 2025 expiries
        WHEN TradingSymbol LIKE 'NIFTY25JUN%' AND DAY(ExpiryDate) = 5 THEN
            REPLACE(TradingSymbol, 'NIFTY25JUN', 'NIFTY25JUN05')
        WHEN TradingSymbol LIKE 'NIFTY25JUN%' AND DAY(ExpiryDate) = 12 THEN
            REPLACE(TradingSymbol, 'NIFTY25JUN', 'NIFTY25JUN12')
        WHEN TradingSymbol LIKE 'NIFTY25JUN%' AND DAY(ExpiryDate) = 19 THEN
            REPLACE(TradingSymbol, 'NIFTY25JUN', 'NIFTY25JUN19')
        WHEN TradingSymbol LIKE 'NIFTY25JUN%' AND DAY(ExpiryDate) = 26 THEN
            REPLACE(TradingSymbol, 'NIFTY25JUN', 'NIFTY25JUN26')
            
        -- May 2025 expiries
        WHEN TradingSymbol LIKE 'NIFTY25MAY%' AND DAY(ExpiryDate) = 1 THEN
            REPLACE(TradingSymbol, 'NIFTY25MAY', 'NIFTY25MAY01')
        WHEN TradingSymbol LIKE 'NIFTY25MAY%' AND DAY(ExpiryDate) = 8 THEN
            REPLACE(TradingSymbol, 'NIFTY25MAY', 'NIFTY25MAY08')
        WHEN TradingSymbol LIKE 'NIFTY25MAY%' AND DAY(ExpiryDate) = 15 THEN
            REPLACE(TradingSymbol, 'NIFTY25MAY', 'NIFTY25MAY15')
        WHEN TradingSymbol LIKE 'NIFTY25MAY%' AND DAY(ExpiryDate) = 22 THEN
            REPLACE(TradingSymbol, 'NIFTY25MAY', 'NIFTY25MAY22')
        WHEN TradingSymbol LIKE 'NIFTY25MAY%' AND DAY(ExpiryDate) = 29 THEN
            REPLACE(TradingSymbol, 'NIFTY25MAY', 'NIFTY25MAY29')
            
        ELSE TradingSymbol
    END
WHERE TradingSymbol LIKE 'NIFTY25%' 
  AND TradingSymbol NOT LIKE 'NIFTY25___[0-9][0-9]%';  -- Only update if day not already present

-- Check the number of records updated
PRINT 'Records updated in OptionsHistoricalData: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

-- Update OptionsData table if it exists
IF OBJECT_ID('dbo.OptionsData', 'U') IS NOT NULL
BEGIN
    UPDATE OptionsData
    SET Symbol = 
        CASE 
            -- August 2025 expiries
            WHEN Symbol LIKE 'NIFTY25AUG%' AND DAY(ExpiryDate) = 7 THEN
                REPLACE(Symbol, 'NIFTY25AUG', 'NIFTY25AUG07')
            WHEN Symbol LIKE 'NIFTY25AUG%' AND DAY(ExpiryDate) = 14 THEN
                REPLACE(Symbol, 'NIFTY25AUG', 'NIFTY25AUG14')
            WHEN Symbol LIKE 'NIFTY25AUG%' AND DAY(ExpiryDate) = 21 THEN
                REPLACE(Symbol, 'NIFTY25AUG', 'NIFTY25AUG21')
            WHEN Symbol LIKE 'NIFTY25AUG%' AND DAY(ExpiryDate) = 28 THEN
                REPLACE(Symbol, 'NIFTY25AUG', 'NIFTY25AUG28')
                
            -- July 2025 expiries
            WHEN Symbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 3 THEN
                REPLACE(Symbol, 'NIFTY25JUL', 'NIFTY25JUL03')
            WHEN Symbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 10 THEN
                REPLACE(Symbol, 'NIFTY25JUL', 'NIFTY25JUL10')
            WHEN Symbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 17 THEN
                REPLACE(Symbol, 'NIFTY25JUL', 'NIFTY25JUL17')
            WHEN Symbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 24 THEN
                REPLACE(Symbol, 'NIFTY25JUL', 'NIFTY25JUL24')
            WHEN Symbol LIKE 'NIFTY25JUL%' AND DAY(ExpiryDate) = 31 THEN
                REPLACE(Symbol, 'NIFTY25JUL', 'NIFTY25JUL31')
                
            ELSE Symbol
        END
    WHERE Symbol LIKE 'NIFTY25%' 
      AND Symbol NOT LIKE 'NIFTY25___[0-9][0-9]%';
      
    PRINT 'Records updated in OptionsData: ' + CAST(@@ROWCOUNT AS VARCHAR(10));
END

-- Verify the updates
SELECT TOP 10 TradingSymbol, Strike, OptionType, ExpiryDate 
FROM OptionsHistoricalData 
WHERE TradingSymbol LIKE 'NIFTY25%'
ORDER BY Timestamp DESC;

-- Commit the transaction if everything looks good
-- COMMIT TRANSACTION;

-- Or rollback if there are issues
-- ROLLBACK TRANSACTION;

PRINT 'Script completed. Review the results and then COMMIT or ROLLBACK the transaction.'