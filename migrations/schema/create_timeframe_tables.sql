-- Migration Script: Create separate tables for each NIFTY timeframe
-- Date: 2025-07-29
-- Purpose: Split NiftyIndexData table into timeframe-specific tables for better performance

-- Create 5-Minute table
CREATE TABLE NiftyIndexData5Minute (
    id INT IDENTITY(1,1) PRIMARY KEY,
    symbol NVARCHAR(50) NOT NULL,
    timestamp DATETIME NOT NULL,
    [open] DECIMAL(18, 2) NOT NULL,
    [high] DECIMAL(18, 2) NOT NULL,
    [low] DECIMAL(18, 2) NOT NULL,
    [close] DECIMAL(18, 2) NOT NULL,
    volume BIGINT NOT NULL,
    LastPrice DECIMAL(18, 2) NOT NULL,
    LastUpdateTime DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_NiftyIndexData5Minute_Symbol_Timestamp UNIQUE (symbol, timestamp)
);

-- Create indexes for 5-Minute table
CREATE INDEX IX_NiftyIndexData5Minute_Symbol ON NiftyIndexData5Minute(symbol);
CREATE INDEX IX_NiftyIndexData5Minute_Timestamp ON NiftyIndexData5Minute(timestamp);
CREATE INDEX IX_NiftyIndexData5Minute_Symbol_Timestamp ON NiftyIndexData5Minute(symbol, timestamp);

-- Create 15-Minute table
CREATE TABLE NiftyIndexData15Minute (
    id INT IDENTITY(1,1) PRIMARY KEY,
    symbol NVARCHAR(50) NOT NULL,
    timestamp DATETIME NOT NULL,
    [open] DECIMAL(18, 2) NOT NULL,
    [high] DECIMAL(18, 2) NOT NULL,
    [low] DECIMAL(18, 2) NOT NULL,
    [close] DECIMAL(18, 2) NOT NULL,
    volume BIGINT NOT NULL,
    LastPrice DECIMAL(18, 2) NOT NULL,
    LastUpdateTime DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_NiftyIndexData15Minute_Symbol_Timestamp UNIQUE (symbol, timestamp)
);

-- Create indexes for 15-Minute table
CREATE INDEX IX_NiftyIndexData15Minute_Symbol ON NiftyIndexData15Minute(symbol);
CREATE INDEX IX_NiftyIndexData15Minute_Timestamp ON NiftyIndexData15Minute(timestamp);
CREATE INDEX IX_NiftyIndexData15Minute_Symbol_Timestamp ON NiftyIndexData15Minute(symbol, timestamp);

-- Create Hourly table
CREATE TABLE NiftyIndexDataHourly (
    id INT IDENTITY(1,1) PRIMARY KEY,
    symbol NVARCHAR(50) NOT NULL,
    timestamp DATETIME NOT NULL,
    [open] DECIMAL(18, 2) NOT NULL,
    [high] DECIMAL(18, 2) NOT NULL,
    [low] DECIMAL(18, 2) NOT NULL,
    [close] DECIMAL(18, 2) NOT NULL,
    volume BIGINT NOT NULL,
    LastPrice DECIMAL(18, 2) NOT NULL,
    LastUpdateTime DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_NiftyIndexDataHourly_Symbol_Timestamp UNIQUE (symbol, timestamp)
);

-- Create indexes for Hourly table
CREATE INDEX IX_NiftyIndexDataHourly_Symbol ON NiftyIndexDataHourly(symbol);
CREATE INDEX IX_NiftyIndexDataHourly_Timestamp ON NiftyIndexDataHourly(timestamp);
CREATE INDEX IX_NiftyIndexDataHourly_Symbol_Timestamp ON NiftyIndexDataHourly(symbol, timestamp);

-- Create 4-Hour table
CREATE TABLE NiftyIndexData4Hour (
    id INT IDENTITY(1,1) PRIMARY KEY,
    symbol NVARCHAR(50) NOT NULL,
    timestamp DATETIME NOT NULL,
    [open] DECIMAL(18, 2) NOT NULL,
    [high] DECIMAL(18, 2) NOT NULL,
    [low] DECIMAL(18, 2) NOT NULL,
    [close] DECIMAL(18, 2) NOT NULL,
    volume BIGINT NOT NULL,
    LastPrice DECIMAL(18, 2) NOT NULL,
    LastUpdateTime DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_NiftyIndexData4Hour_Symbol_Timestamp UNIQUE (symbol, timestamp)
);

-- Create indexes for 4-Hour table
CREATE INDEX IX_NiftyIndexData4Hour_Symbol ON NiftyIndexData4Hour(symbol);
CREATE INDEX IX_NiftyIndexData4Hour_Timestamp ON NiftyIndexData4Hour(timestamp);
CREATE INDEX IX_NiftyIndexData4Hour_Symbol_Timestamp ON NiftyIndexData4Hour(symbol, timestamp);

-- Create Daily table
CREATE TABLE NiftyIndexDataDaily (
    id INT IDENTITY(1,1) PRIMARY KEY,
    symbol NVARCHAR(50) NOT NULL,
    timestamp DATETIME NOT NULL,
    [open] DECIMAL(18, 2) NOT NULL,
    [high] DECIMAL(18, 2) NOT NULL,
    [low] DECIMAL(18, 2) NOT NULL,
    [close] DECIMAL(18, 2) NOT NULL,
    volume BIGINT NOT NULL,
    LastPrice DECIMAL(18, 2) NOT NULL,
    LastUpdateTime DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_NiftyIndexDataDaily_Symbol_Timestamp UNIQUE (symbol, timestamp)
);

-- Create indexes for Daily table
CREATE INDEX IX_NiftyIndexDataDaily_Symbol ON NiftyIndexDataDaily(symbol);
CREATE INDEX IX_NiftyIndexDataDaily_Timestamp ON NiftyIndexDataDaily(timestamp);
CREATE INDEX IX_NiftyIndexDataDaily_Symbol_Timestamp ON NiftyIndexDataDaily(symbol, timestamp);

-- Create Weekly table
CREATE TABLE NiftyIndexDataWeekly (
    id INT IDENTITY(1,1) PRIMARY KEY,
    symbol NVARCHAR(50) NOT NULL,
    timestamp DATETIME NOT NULL,
    [open] DECIMAL(18, 2) NOT NULL,
    [high] DECIMAL(18, 2) NOT NULL,
    [low] DECIMAL(18, 2) NOT NULL,
    [close] DECIMAL(18, 2) NOT NULL,
    volume BIGINT NOT NULL,
    LastPrice DECIMAL(18, 2) NOT NULL,
    LastUpdateTime DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_NiftyIndexDataWeekly_Symbol_Timestamp UNIQUE (symbol, timestamp)
);

-- Create indexes for Weekly table
CREATE INDEX IX_NiftyIndexDataWeekly_Symbol ON NiftyIndexDataWeekly(symbol);
CREATE INDEX IX_NiftyIndexDataWeekly_Timestamp ON NiftyIndexDataWeekly(timestamp);
CREATE INDEX IX_NiftyIndexDataWeekly_Symbol_Timestamp ON NiftyIndexDataWeekly(symbol, timestamp);

-- Create Monthly table
CREATE TABLE NiftyIndexDataMonthly (
    id INT IDENTITY(1,1) PRIMARY KEY,
    symbol NVARCHAR(50) NOT NULL,
    timestamp DATETIME NOT NULL,
    [open] DECIMAL(18, 2) NOT NULL,
    [high] DECIMAL(18, 2) NOT NULL,
    [low] DECIMAL(18, 2) NOT NULL,
    [close] DECIMAL(18, 2) NOT NULL,
    volume BIGINT NOT NULL,
    LastPrice DECIMAL(18, 2) NOT NULL,
    LastUpdateTime DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_NiftyIndexDataMonthly_Symbol_Timestamp UNIQUE (symbol, timestamp)
);

-- Create indexes for Monthly table
CREATE INDEX IX_NiftyIndexDataMonthly_Symbol ON NiftyIndexDataMonthly(symbol);
CREATE INDEX IX_NiftyIndexDataMonthly_Timestamp ON NiftyIndexDataMonthly(timestamp);
CREATE INDEX IX_NiftyIndexDataMonthly_Symbol_Timestamp ON NiftyIndexDataMonthly(symbol, timestamp);

-- Verify tables were created
SELECT 
    t.name AS TableName,
    COUNT(c.column_id) AS ColumnCount
FROM sys.tables t
INNER JOIN sys.columns c ON t.object_id = c.object_id
WHERE t.name LIKE 'NiftyIndexData%'
    AND t.name != 'NiftyIndexData'
GROUP BY t.name
ORDER BY t.name;