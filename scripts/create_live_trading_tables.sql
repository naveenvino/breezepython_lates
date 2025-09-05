-- Create Live Trading Tables for TradingView Pro System
-- Run this in SQL Server Management Studio on (localdb)\mssqllocaldb

USE KiteConnectApi;
GO

-- Drop tables if they exist (for clean setup)
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'LivePositions')
    DROP TABLE LivePositions;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'TradingViewSignals')
    DROP TABLE TradingViewSignals;
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'LiveHourlyCandles')
    DROP TABLE LiveHourlyCandles;
GO

-- Create TradingView signals table
CREATE TABLE TradingViewSignals (
    id INT PRIMARY KEY IDENTITY(1,1),
    signal_type VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,
    strike INT NOT NULL,
    option_type VARCHAR(2) NOT NULL,
    timestamp DATETIME NOT NULL,
    price DECIMAL(10,2),
    processed BIT DEFAULT 0,
    execution_id INT,
    created_at DATETIME DEFAULT GETDATE(),
    INDEX idx_signal_timestamp (timestamp),
    INDEX idx_signal_type (signal_type)
);
GO

-- Create Live hourly candles table
CREATE TABLE LiveHourlyCandles (
    timestamp DATETIME PRIMARY KEY,
    [open] DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    [close] DECIMAL(10,2) NOT NULL,
    volume DECIMAL(15,2),
    tick_count INT,
    created_at DATETIME DEFAULT GETDATE(),
    INDEX idx_candle_time (timestamp DESC)
);
GO

-- Create Live positions table
CREATE TABLE LivePositions (
    id INT PRIMARY KEY IDENTITY(1,1),
    signal_type VARCHAR(10) NOT NULL,
    main_strike INT NOT NULL,
    main_price DECIMAL(10,2) NOT NULL,
    main_quantity INT NOT NULL,
    hedge_strike INT,
    hedge_price DECIMAL(10,2),
    hedge_quantity INT,
    breakeven DECIMAL(10,2),
    entry_time DATETIME NOT NULL,
    exit_time DATETIME,
    pnl DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'open',
    created_at DATETIME DEFAULT GETDATE(),
    INDEX idx_position_status (status),
    INDEX idx_position_entry (entry_time DESC)
);
GO

-- Create position price history table (for tracking)
CREATE TABLE PositionPriceHistory (
    id INT PRIMARY KEY IDENTITY(1,1),
    position_id INT NOT NULL,
    main_price DECIMAL(10,2) NOT NULL,
    hedge_price DECIMAL(10,2),
    spot_price DECIMAL(10,2),
    pnl DECIMAL(10,2),
    timestamp DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (position_id) REFERENCES LivePositions(id),
    INDEX idx_price_history (position_id, timestamp DESC)
);
GO

-- Create stop loss triggers table
CREATE TABLE StopLossTriggers (
    id INT PRIMARY KEY IDENTITY(1,1),
    position_id INT NOT NULL,
    trigger_type VARCHAR(20) NOT NULL, -- 'strike_based', 'profit_lock', 'time_based', 'hourly_close'
    trigger_price DECIMAL(10,2),
    spot_price DECIMAL(10,2),
    pnl_at_trigger DECIMAL(10,2),
    reason VARCHAR(200),
    triggered_at DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (position_id) REFERENCES LivePositions(id),
    INDEX idx_stoploss_position (position_id)
);
GO

-- Create system status table
CREATE TABLE SystemStatus (
    id INT PRIMARY KEY IDENTITY(1,1),
    component VARCHAR(50) NOT NULL, -- 'websocket', 'webhook', 'breeze', 'database'
    status VARCHAR(20) NOT NULL, -- 'active', 'inactive', 'error'
    last_heartbeat DATETIME,
    error_message VARCHAR(500),
    updated_at DATETIME DEFAULT GETDATE()
);
GO

-- Insert initial system status
INSERT INTO SystemStatus (component, status, last_heartbeat)
VALUES 
    ('websocket', 'inactive', NULL),
    ('webhook', 'active', GETDATE()),
    ('breeze', 'inactive', NULL),
    ('database', 'active', GETDATE());
GO

PRINT 'Live Trading tables created successfully!';

-- Verify tables
SELECT 
    t.name AS TableName,
    p.rows AS [RowCount]
FROM sys.tables t
INNER JOIN sys.partitions p ON t.object_id = p.object_id
WHERE t.name IN ('TradingViewSignals', 'LiveHourlyCandles', 'LivePositions', 
                 'PositionPriceHistory', 'StopLossTriggers', 'SystemStatus')
    AND p.index_id IN (0, 1)
ORDER BY t.name;
GO