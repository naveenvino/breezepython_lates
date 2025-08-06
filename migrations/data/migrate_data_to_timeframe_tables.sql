-- Data Migration Script: Copy data from NiftyIndexData to timeframe-specific tables
-- Date: 2025-07-29
-- Purpose: Migrate existing data based on interval column value

-- Start transaction for data integrity
BEGIN TRANSACTION;

-- Migrate 5-minute data
INSERT INTO NiftyIndexData5Minute (symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime)
SELECT symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime
FROM NiftyIndexData
WHERE interval = '5minute';

PRINT 'Migrated 5-minute data. Rows affected: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

-- Migrate 15-minute data
INSERT INTO NiftyIndexData15Minute (symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime)
SELECT symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime
FROM NiftyIndexData
WHERE interval = '15minute';

PRINT 'Migrated 15-minute data. Rows affected: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

-- Migrate hourly data
INSERT INTO NiftyIndexDataHourly (symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime)
SELECT symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime
FROM NiftyIndexData
WHERE interval = 'hourly';

PRINT 'Migrated hourly data. Rows affected: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

-- Migrate 4-hour data
INSERT INTO NiftyIndexData4Hour (symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime)
SELECT symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime
FROM NiftyIndexData
WHERE interval = '4hour';

PRINT 'Migrated 4-hour data. Rows affected: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

-- Migrate daily data
INSERT INTO NiftyIndexDataDaily (symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime)
SELECT symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime
FROM NiftyIndexData
WHERE interval = 'daily';

PRINT 'Migrated daily data. Rows affected: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

-- Migrate weekly data
INSERT INTO NiftyIndexDataWeekly (symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime)
SELECT symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime
FROM NiftyIndexData
WHERE interval = 'weekly';

PRINT 'Migrated weekly data. Rows affected: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

-- Migrate monthly data
INSERT INTO NiftyIndexDataMonthly (symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime)
SELECT symbol, timestamp, [open], [high], [low], [close], volume, LastPrice, LastUpdateTime
FROM NiftyIndexData
WHERE interval = 'monthly';

PRINT 'Migrated monthly data. Rows affected: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

-- Verify migration counts
PRINT '';
PRINT 'Migration Summary:';
PRINT '==================';

SELECT 
    'Original NiftyIndexData' AS TableName,
    interval,
    COUNT(*) AS RecordCount
FROM NiftyIndexData
GROUP BY interval
UNION ALL
SELECT 
    'NiftyIndexData5Minute' AS TableName,
    '5minute' AS interval,
    COUNT(*) AS RecordCount
FROM NiftyIndexData5Minute
UNION ALL
SELECT 
    'NiftyIndexData15Minute' AS TableName,
    '15minute' AS interval,
    COUNT(*) AS RecordCount
FROM NiftyIndexData15Minute
UNION ALL
SELECT 
    'NiftyIndexDataHourly' AS TableName,
    'hourly' AS interval,
    COUNT(*) AS RecordCount
FROM NiftyIndexDataHourly
UNION ALL
SELECT 
    'NiftyIndexData4Hour' AS TableName,
    '4hour' AS interval,
    COUNT(*) AS RecordCount
FROM NiftyIndexData4Hour
UNION ALL
SELECT 
    'NiftyIndexDataDaily' AS TableName,
    'daily' AS interval,
    COUNT(*) AS RecordCount
FROM NiftyIndexDataDaily
UNION ALL
SELECT 
    'NiftyIndexDataWeekly' AS TableName,
    'weekly' AS interval,
    COUNT(*) AS RecordCount
FROM NiftyIndexDataWeekly
UNION ALL
SELECT 
    'NiftyIndexDataMonthly' AS TableName,
    'monthly' AS interval,
    COUNT(*) AS RecordCount
FROM NiftyIndexDataMonthly
ORDER BY TableName;

-- Commit transaction if everything is successful
COMMIT TRANSACTION;

PRINT '';
PRINT 'Data migration completed successfully!';
PRINT 'Original NiftyIndexData table has been preserved for backup.';
PRINT 'To remove it after verification, run: DROP TABLE NiftyIndexData;';