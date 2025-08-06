-- Add missing columns to timeframe tables
-- These columns exist in the models but were not in the initial migration

-- Function to add columns if they don't exist
DECLARE @sql NVARCHAR(MAX)

-- List of tables to update
DECLARE @tables TABLE (TableName NVARCHAR(50))
INSERT INTO @tables VALUES 
    ('NiftyIndexData5Minute'),
    ('NiftyIndexData15Minute'),
    ('NiftyIndexDataHourly'),
    ('NiftyIndexData4Hour'),
    ('NiftyIndexDataDaily'),
    ('NiftyIndexDataWeekly'),
    ('NiftyIndexDataMonthly')

DECLARE @tableName NVARCHAR(50)
DECLARE table_cursor CURSOR FOR SELECT TableName FROM @tables

OPEN table_cursor
FETCH NEXT FROM table_cursor INTO @tableName

WHILE @@FETCH_STATUS = 0
BEGIN
    -- Add OpenInterest column if it doesn't exist
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(@tableName) AND name = 'OpenInterest')
    BEGIN
        SET @sql = 'ALTER TABLE ' + @tableName + ' ADD OpenInterest BIGINT NOT NULL DEFAULT 0'
        EXEC sp_executesql @sql
        PRINT 'Added OpenInterest to ' + @tableName
    END
    
    -- Add ChangePercent column if it doesn't exist
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(@tableName) AND name = 'ChangePercent')
    BEGIN
        SET @sql = 'ALTER TABLE ' + @tableName + ' ADD ChangePercent DECIMAL(18, 2) NOT NULL DEFAULT 0'
        EXEC sp_executesql @sql
        PRINT 'Added ChangePercent to ' + @tableName
    END
    
    -- Add BidPrice column if it doesn't exist
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(@tableName) AND name = 'BidPrice')
    BEGIN
        SET @sql = 'ALTER TABLE ' + @tableName + ' ADD BidPrice DECIMAL(18, 2) NOT NULL DEFAULT 0'
        EXEC sp_executesql @sql
        PRINT 'Added BidPrice to ' + @tableName
    END
    
    -- Add AskPrice column if it doesn't exist
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(@tableName) AND name = 'AskPrice')
    BEGIN
        SET @sql = 'ALTER TABLE ' + @tableName + ' ADD AskPrice DECIMAL(18, 2) NOT NULL DEFAULT 0'
        EXEC sp_executesql @sql
        PRINT 'Added AskPrice to ' + @tableName
    END
    
    -- Add BidQuantity column if it doesn't exist
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(@tableName) AND name = 'BidQuantity')
    BEGIN
        SET @sql = 'ALTER TABLE ' + @tableName + ' ADD BidQuantity BIGINT NOT NULL DEFAULT 0'
        EXEC sp_executesql @sql
        PRINT 'Added BidQuantity to ' + @tableName
    END
    
    -- Add AskQuantity column if it doesn't exist
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(@tableName) AND name = 'AskQuantity')
    BEGIN
        SET @sql = 'ALTER TABLE ' + @tableName + ' ADD AskQuantity BIGINT NOT NULL DEFAULT 0'
        EXEC sp_executesql @sql
        PRINT 'Added AskQuantity to ' + @tableName
    END
    
    -- Add CreatedAt column if it doesn't exist
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(@tableName) AND name = 'CreatedAt')
    BEGIN
        SET @sql = 'ALTER TABLE ' + @tableName + ' ADD CreatedAt DATETIME NOT NULL DEFAULT GETDATE()'
        EXEC sp_executesql @sql
        PRINT 'Added CreatedAt to ' + @tableName
    END
    
    FETCH NEXT FROM table_cursor INTO @tableName
END

CLOSE table_cursor
DEALLOCATE table_cursor

PRINT 'Column update completed!'