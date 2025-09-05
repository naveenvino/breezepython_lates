-- Fix Database Schema for Trading System
-- Run this script in SQL Server Management Studio or via sqlcmd

USE KiteConnectApi;
GO

-- Create LivePositions table if not exists
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='LivePositions' AND xtype='U')
BEGIN
    CREATE TABLE LivePositions (
        id INT IDENTITY(1,1) PRIMARY KEY,
        signal_type VARCHAR(10),
        main_strike INT,
        main_price DECIMAL(10,2),
        main_quantity INT,
        hedge_strike INT,
        hedge_price DECIMAL(10,2),
        hedge_quantity INT,
        entry_time DATETIME,
        exit_time DATETIME,
        pnl DECIMAL(10,2),
        status VARCHAR(20),
        created_at DATETIME DEFAULT GETDATE()
    );
    PRINT 'LivePositions table created';
END
ELSE
BEGIN
    PRINT 'LivePositions table already exists';
END
GO

-- Fix BacktestTrades table columns
IF EXISTS (SELECT * FROM sysobjects WHERE name='BacktestTrades' AND xtype='U')
BEGIN
    -- Add missing columns if they don't exist
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('BacktestTrades') AND name = 'TradeID')
    BEGIN
        EXEC sp_rename 'BacktestTrades.Id', 'TradeID', 'COLUMN';
        PRINT 'Renamed Id to TradeID';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('BacktestTrades') AND name = 'Strike')
    BEGIN
        ALTER TABLE BacktestTrades ADD Strike INT;
        PRINT 'Added Strike column';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('BacktestTrades') AND name = 'EntryPrice')
    BEGIN
        ALTER TABLE BacktestTrades ADD EntryPrice DECIMAL(10,2);
        PRINT 'Added EntryPrice column';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('BacktestTrades') AND name = 'ExitPrice')
    BEGIN
        ALTER TABLE BacktestTrades ADD ExitPrice DECIMAL(10,2);
        PRINT 'Added ExitPrice column';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('BacktestTrades') AND name = 'Quantity')
    BEGIN
        ALTER TABLE BacktestTrades ADD Quantity INT;
        PRINT 'Added Quantity column';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('BacktestTrades') AND name = 'PnL')
    BEGIN
        ALTER TABLE BacktestTrades ADD PnL DECIMAL(10,2);
        PRINT 'Added PnL column';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('BacktestTrades') AND name = 'Status')
    BEGIN
        ALTER TABLE BacktestTrades ADD Status VARCHAR(20);
        PRINT 'Added Status column';
    END
END
GO

-- Create Alerts table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Alerts' AND xtype='U')
BEGIN
    CREATE TABLE Alerts (
        alert_id VARCHAR(50) PRIMARY KEY,
        alert_type VARCHAR(20),
        priority VARCHAR(20),
        title VARCHAR(200),
        message TEXT,
        condition_json TEXT,
        created_at DATETIME,
        triggered_at DATETIME,
        is_triggered BIT DEFAULT 0,
        is_active BIT DEFAULT 1
    );
    PRINT 'Alerts table created';
END
GO

-- Create TradingLogs table for audit trail
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='TradingLogs' AND xtype='U')
BEGIN
    CREATE TABLE TradingLogs (
        log_id INT IDENTITY(1,1) PRIMARY KEY,
        log_type VARCHAR(50),
        message TEXT,
        details TEXT,
        created_at DATETIME DEFAULT GETDATE()
    );
    PRINT 'TradingLogs table created';
END
GO

-- Create WebhookSignals table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='WebhookSignals' AND xtype='U')
BEGIN
    CREATE TABLE WebhookSignals (
        signal_id INT IDENTITY(1,1) PRIMARY KEY,
        source VARCHAR(50),
        signal_type VARCHAR(10),
        symbol VARCHAR(20),
        action VARCHAR(20),
        price DECIMAL(10,2),
        quantity INT,
        raw_data TEXT,
        processed BIT DEFAULT 0,
        received_at DATETIME DEFAULT GETDATE(),
        processed_at DATETIME
    );
    PRINT 'WebhookSignals table created';
END
GO

-- Create RiskMetrics table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='RiskMetrics' AND xtype='U')
BEGIN
    CREATE TABLE RiskMetrics (
        metric_id INT IDENTITY(1,1) PRIMARY KEY,
        metric_date DATE,
        total_exposure DECIMAL(15,2),
        margin_used DECIMAL(15,2),
        daily_pnl DECIMAL(10,2),
        max_drawdown DECIMAL(10,2),
        win_rate DECIMAL(5,2),
        sharpe_ratio DECIMAL(5,2),
        var_95 DECIMAL(10,2),
        created_at DATETIME DEFAULT GETDATE()
    );
    PRINT 'RiskMetrics table created';
END
GO

PRINT 'Database schema fix completed';
GO