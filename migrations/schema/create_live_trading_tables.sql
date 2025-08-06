-- Create Live Trading Tables for Kite Integration
-- These tables track live trades executed through Zerodha Kite

-- Drop existing objects for clean setup
IF OBJECT_ID('dbo.UpdateLiveTradesTimestamp', 'TR') IS NOT NULL DROP TRIGGER dbo.UpdateLiveTradesTimestamp;
IF OBJECT_ID('dbo.ActiveTradesView', 'V') IS NOT NULL DROP VIEW dbo.ActiveTradesView;
IF OBJECT_ID('dbo.UpdateDailyPnLSummary', 'P') IS NOT NULL DROP PROCEDURE dbo.UpdateDailyPnLSummary;
IF OBJECT_ID('dbo.LivePositions', 'U') IS NOT NULL DROP TABLE dbo.LivePositions;
IF OBJECT_ID('dbo.DailyPnLSummary', 'U') IS NOT NULL DROP TABLE dbo.DailyPnLSummary;
IF OBJECT_ID('dbo.LiveTradingConfig', 'U') IS NOT NULL DROP TABLE dbo.LiveTradingConfig;
IF OBJECT_ID('dbo.LiveTrades', 'U') IS NOT NULL DROP TABLE dbo.LiveTrades;

-- Live Trades Table
-- Stores information about each trade executed
CREATE TABLE LiveTrades (
    id VARCHAR(50) PRIMARY KEY,                -- UUID for trade
    signal_type VARCHAR(10) NOT NULL,          -- S1-S8
    entry_time DATETIME NOT NULL,              -- When trade was entered
    exit_time DATETIME NULL,                   -- When trade was exited
    exit_reason VARCHAR(50) NULL,              -- 'STOPLOSS', 'EXPIRY_SQUAREOFF', 'MANUAL'
    main_order_id VARCHAR(50) NULL,            -- Kite order ID for main position
    hedge_order_id VARCHAR(50) NULL,           -- Kite order ID for hedge position
    exit_main_order_id VARCHAR(50) NULL,       -- Exit order ID for main
    exit_hedge_order_id VARCHAR(50) NULL,      -- Exit order ID for hedge
    status VARCHAR(20) NOT NULL,               -- 'PENDING', 'ACTIVE', 'CLOSED', 'FAILED'
    main_strike INT NOT NULL,                  -- Main option strike
    hedge_strike INT NULL,                     -- Hedge option strike
    option_type VARCHAR(2) NOT NULL,           -- CE or PE
    direction VARCHAR(10) NOT NULL,            -- BULLISH or BEARISH
    pnl DECIMAL(10,2) NULL,                   -- Final P&L
    error_message VARCHAR(500) NULL,           -- Error if failed
    created_at DATETIME DEFAULT GETDATE(),     -- Record creation time
    updated_at DATETIME DEFAULT GETDATE()      -- Last update time
);

-- Live Positions Table
-- Stores real-time position information
CREATE TABLE LivePositions (
    id INT PRIMARY KEY IDENTITY(1,1),
    trade_id VARCHAR(50) NULL,                 -- Link to LiveTrades
    order_id VARCHAR(50) NULL,                 -- Kite order ID
    symbol VARCHAR(50) NOT NULL,               -- Option symbol (e.g., NIFTY24DEC1925000CE)
    quantity INT NOT NULL,                     -- Position quantity (negative for sell)
    average_price DECIMAL(10,2) NOT NULL,      -- Average entry price
    current_price DECIMAL(10,2) NULL,          -- Current market price
    pnl DECIMAL(10,2) NULL,                   -- Current P&L
    updated_at DATETIME DEFAULT GETDATE(),     -- Last update time
    
    FOREIGN KEY (trade_id) REFERENCES LiveTrades(id)
);

-- Indexes for performance
CREATE INDEX IX_LiveTrades_Status ON LiveTrades(status);
CREATE INDEX IX_LiveTrades_EntryTime ON LiveTrades(entry_time);
CREATE INDEX IX_LiveTrades_SignalType ON LiveTrades(signal_type);
CREATE INDEX IX_LivePositions_TradeId ON LivePositions(trade_id);
CREATE INDEX IX_LivePositions_Symbol ON LivePositions(symbol);

-- Live Trading Configuration Table
CREATE TABLE LiveTradingConfig (
    id INT PRIMARY KEY IDENTITY(1,1),
    config_key VARCHAR(50) UNIQUE NOT NULL,
    config_value VARCHAR(255) NOT NULL,
    updated_at DATETIME DEFAULT GETDATE()
);

-- Insert default configuration
INSERT INTO LiveTradingConfig (config_key, config_value) VALUES
('enabled', 'false'),
('lot_size', '75'),
('num_lots', '10'),
('use_hedging', 'true'),
('max_positions', '1'),
('expiry_square_off_time', '15:15'),
('last_entry_time', '15:00'),
('max_loss_per_day', '50000'),
('max_loss_per_trade', '25000');

-- Daily P&L Summary Table
CREATE TABLE DailyPnLSummary (
    id INT PRIMARY KEY IDENTITY(1,1),
    trade_date DATE NOT NULL,
    total_trades INT NOT NULL DEFAULT 0,
    winning_trades INT NOT NULL DEFAULT 0,
    losing_trades INT NOT NULL DEFAULT 0,
    total_pnl DECIMAL(10,2) NOT NULL DEFAULT 0,
    max_profit DECIMAL(10,2) NULL,
    max_loss DECIMAL(10,2) NULL,
    stop_losses_hit INT NOT NULL DEFAULT 0,
    expiry_square_offs INT NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT GETDATE(),
    
    CONSTRAINT UQ_DailyPnL_Date UNIQUE(trade_date)
);

-- Create stored procedure to update daily summary
IF OBJECT_ID('dbo.UpdateDailyPnLSummary', 'P') IS NOT NULL
    DROP PROCEDURE dbo.UpdateDailyPnLSummary;
GO

CREATE PROCEDURE UpdateDailyPnLSummary
    @TradeDate DATE
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Delete existing record for the date
    DELETE FROM DailyPnLSummary WHERE trade_date = @TradeDate;
    
    -- Insert new summary
    INSERT INTO DailyPnLSummary (
        trade_date,
        total_trades,
        winning_trades,
        losing_trades,
        total_pnl,
        max_profit,
        max_loss,
        stop_losses_hit,
        expiry_square_offs
    )
    SELECT 
        @TradeDate,
        COUNT(*) as total_trades,
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
        ISNULL(SUM(pnl), 0) as total_pnl,
        MAX(CASE WHEN pnl > 0 THEN pnl ELSE NULL END) as max_profit,
        MIN(CASE WHEN pnl < 0 THEN pnl ELSE NULL END) as max_loss,
        SUM(CASE WHEN exit_reason = 'STOPLOSS' THEN 1 ELSE 0 END) as stop_losses_hit,
        SUM(CASE WHEN exit_reason = 'EXPIRY_SQUAREOFF' THEN 1 ELSE 0 END) as expiry_square_offs
    FROM LiveTrades
    WHERE CAST(entry_time AS DATE) = @TradeDate
    AND status = 'CLOSED';
END
GO

-- Create view for active trades with current P&L
IF OBJECT_ID('dbo.ActiveTradesView', 'V') IS NOT NULL
    DROP VIEW dbo.ActiveTradesView;
GO

CREATE VIEW ActiveTradesView AS
SELECT 
    t.id,
    t.signal_type,
    t.entry_time,
    t.main_strike,
    t.hedge_strike,
    t.option_type,
    t.direction,
    p1.symbol as main_symbol,
    p1.quantity as main_quantity,
    p1.average_price as main_avg_price,
    p1.current_price as main_current_price,
    p1.pnl as main_pnl,
    p2.symbol as hedge_symbol,
    p2.quantity as hedge_quantity,
    p2.average_price as hedge_avg_price,
    p2.current_price as hedge_current_price,
    p2.pnl as hedge_pnl,
    ISNULL(p1.pnl, 0) + ISNULL(p2.pnl, 0) as total_pnl
FROM LiveTrades t
LEFT JOIN LivePositions p1 ON p1.order_id = t.main_order_id
LEFT JOIN LivePositions p2 ON p2.order_id = t.hedge_order_id
WHERE t.status = 'ACTIVE'
GO

-- Create trigger to update timestamp
IF OBJECT_ID('dbo.UpdateLiveTradesTimestamp', 'TR') IS NOT NULL
    DROP TRIGGER dbo.UpdateLiveTradesTimestamp;
GO

CREATE TRIGGER UpdateLiveTradesTimestamp
ON LiveTrades
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE LiveTrades
    SET updated_at = GETDATE()
    WHERE id IN (SELECT DISTINCT id FROM Inserted);
END
GO

PRINT 'Live trading tables created successfully';