-- Trade Journal Database Schema
-- For tracking all trading activity, performance metrics, and analytics

USE KiteConnectApi;
GO

-- ============= CORE TRADING TABLES =============

-- Trade Journal Master Table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='TradeJournal' AND xtype='U')
CREATE TABLE TradeJournal (
    trade_id NVARCHAR(50) PRIMARY KEY,
    order_id NVARCHAR(50),
    symbol NVARCHAR(50) NOT NULL,
    trade_type NVARCHAR(10) CHECK (trade_type IN ('BUY', 'SELL')),
    quantity INT NOT NULL,
    entry_price DECIMAL(18, 2) NOT NULL,
    exit_price DECIMAL(18, 2),
    entry_time DATETIME NOT NULL,
    exit_time DATETIME,
    pnl DECIMAL(18, 2),
    pnl_percentage DECIMAL(10, 4),
    commission DECIMAL(18, 2) DEFAULT 0,
    strategy_name NVARCHAR(100),
    signal_type NVARCHAR(10),
    notes TEXT,
    status NVARCHAR(20) DEFAULT 'OPEN',
    created_at DATETIME DEFAULT GETDATE(),
    updated_at DATETIME DEFAULT GETDATE()
);
GO

-- Daily Performance Summary
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='DailyPerformance' AND xtype='U')
CREATE TABLE DailyPerformance (
    date DATE PRIMARY KEY,
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    gross_pnl DECIMAL(18, 2),
    net_pnl DECIMAL(18, 2),
    commission_paid DECIMAL(18, 2),
    max_drawdown DECIMAL(18, 2),
    sharpe_ratio DECIMAL(10, 4),
    win_rate DECIMAL(10, 4),
    avg_win DECIMAL(18, 2),
    avg_loss DECIMAL(18, 2),
    best_trade DECIMAL(18, 2),
    worst_trade DECIMAL(18, 2),
    total_volume DECIMAL(18, 2),
    created_at DATETIME DEFAULT GETDATE()
);
GO

-- Strategy Performance
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='StrategyPerformance' AND xtype='U')
CREATE TABLE StrategyPerformance (
    strategy_id INT IDENTITY(1,1) PRIMARY KEY,
    strategy_name NVARCHAR(100) NOT NULL,
    signal_type NVARCHAR(10),
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    total_pnl DECIMAL(18, 2),
    win_rate DECIMAL(10, 4),
    avg_pnl_per_trade DECIMAL(18, 2),
    max_consecutive_wins INT DEFAULT 0,
    max_consecutive_losses INT DEFAULT 0,
    last_updated DATETIME DEFAULT GETDATE()
);
GO

-- Risk Metrics
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='RiskMetrics' AND xtype='U')
CREATE TABLE RiskMetrics (
    metric_id INT IDENTITY(1,1) PRIMARY KEY,
    date DATE NOT NULL,
    portfolio_value DECIMAL(18, 2),
    var_95 DECIMAL(18, 2), -- Value at Risk 95%
    var_99 DECIMAL(18, 2), -- Value at Risk 99%
    max_position_size DECIMAL(18, 2),
    total_exposure DECIMAL(18, 2),
    leverage_ratio DECIMAL(10, 4),
    beta DECIMAL(10, 4),
    correlation_to_nifty DECIMAL(10, 4),
    created_at DATETIME DEFAULT GETDATE()
);
GO

-- ============= PAPER TRADING TABLES =============

-- Paper Trading Accounts
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='PaperTradingAccounts' AND xtype='U')
CREATE TABLE PaperTradingAccounts (
    account_id NVARCHAR(50) PRIMARY KEY,
    account_name NVARCHAR(100),
    initial_capital DECIMAL(18, 2) NOT NULL,
    current_capital DECIMAL(18, 2) NOT NULL,
    total_pnl DECIMAL(18, 2),
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    status NVARCHAR(20) DEFAULT 'ACTIVE',
    created_at DATETIME DEFAULT GETDATE(),
    last_activity DATETIME DEFAULT GETDATE()
);
GO

-- Paper Trading Trades
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='PaperTrades' AND xtype='U')
CREATE TABLE PaperTrades (
    paper_trade_id INT IDENTITY(1,1) PRIMARY KEY,
    account_id NVARCHAR(50) FOREIGN KEY REFERENCES PaperTradingAccounts(account_id),
    trade_id NVARCHAR(50) NOT NULL,
    symbol NVARCHAR(50) NOT NULL,
    side NVARCHAR(10) CHECK (side IN ('BUY', 'SELL')),
    quantity INT NOT NULL,
    entry_price DECIMAL(18, 2) NOT NULL,
    exit_price DECIMAL(18, 2),
    entry_time DATETIME NOT NULL,
    exit_time DATETIME,
    pnl DECIMAL(18, 2),
    status NVARCHAR(20) DEFAULT 'OPEN',
    strategy_used NVARCHAR(100),
    created_at DATETIME DEFAULT GETDATE()
);
GO

-- ============= SIGNAL TRACKING TABLES =============

-- Signal History
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SignalHistory' AND xtype='U')
CREATE TABLE SignalHistory (
    signal_id INT IDENTITY(1,1) PRIMARY KEY,
    signal_type NVARCHAR(10) NOT NULL,
    signal_time DATETIME NOT NULL,
    spot_price DECIMAL(18, 2) NOT NULL,
    strike_price INT,
    option_type NVARCHAR(10),
    confidence DECIMAL(10, 4),
    executed BIT DEFAULT 0,
    trade_id NVARCHAR(50),
    reason NVARCHAR(500),
    created_at DATETIME DEFAULT GETDATE()
);
GO

-- Signal Performance
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SignalPerformance' AND xtype='U')
CREATE TABLE SignalPerformance (
    signal_type NVARCHAR(10) PRIMARY KEY,
    total_signals INT DEFAULT 0,
    executed_signals INT DEFAULT 0,
    successful_signals INT DEFAULT 0,
    total_pnl DECIMAL(18, 2),
    success_rate DECIMAL(10, 4),
    avg_pnl DECIMAL(18, 2),
    last_signal_time DATETIME,
    last_updated DATETIME DEFAULT GETDATE()
);
GO

-- ============= ANALYTICS TABLES =============

-- Trade Analytics
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='TradeAnalytics' AND xtype='U')
CREATE TABLE TradeAnalytics (
    analytics_id INT IDENTITY(1,1) PRIMARY KEY,
    trade_id NVARCHAR(50) FOREIGN KEY REFERENCES TradeJournal(trade_id),
    entry_reason NVARCHAR(500),
    exit_reason NVARCHAR(500),
    market_condition NVARCHAR(50),
    time_in_trade INT, -- minutes
    max_profit DECIMAL(18, 2),
    max_loss DECIMAL(18, 2),
    r_multiple DECIMAL(10, 4), -- Risk reward ratio
    expectancy DECIMAL(18, 2),
    created_at DATETIME DEFAULT GETDATE()
);
GO

-- Monthly Performance
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='MonthlyPerformance' AND xtype='U')
CREATE TABLE MonthlyPerformance (
    year INT NOT NULL,
    month INT NOT NULL,
    total_trading_days INT,
    profitable_days INT,
    total_trades INT,
    gross_pnl DECIMAL(18, 2),
    net_pnl DECIMAL(18, 2),
    roi DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(18, 2),
    best_day DECIMAL(18, 2),
    worst_day DECIMAL(18, 2),
    created_at DATETIME DEFAULT GETDATE(),
    PRIMARY KEY (year, month)
);
GO

-- ============= STORED PROCEDURES =============

-- Insert Trade
IF EXISTS (SELECT * FROM sysobjects WHERE name='sp_InsertTrade' AND xtype='P')
    DROP PROCEDURE sp_InsertTrade
GO

CREATE PROCEDURE sp_InsertTrade
    @trade_id NVARCHAR(50),
    @symbol NVARCHAR(50),
    @trade_type NVARCHAR(10),
    @quantity INT,
    @entry_price DECIMAL(18, 2),
    @strategy_name NVARCHAR(100) = NULL,
    @signal_type NVARCHAR(10) = NULL
AS
BEGIN
    INSERT INTO TradeJournal (
        trade_id, symbol, trade_type, quantity, entry_price, 
        entry_time, strategy_name, signal_type, status
    )
    VALUES (
        @trade_id, @symbol, @trade_type, @quantity, @entry_price,
        GETDATE(), @strategy_name, @signal_type, 'OPEN'
    );
    
    -- Update strategy performance
    IF @strategy_name IS NOT NULL
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM StrategyPerformance WHERE strategy_name = @strategy_name)
        BEGIN
            INSERT INTO StrategyPerformance (strategy_name, signal_type, total_trades)
            VALUES (@strategy_name, @signal_type, 1);
        END
        ELSE
        BEGIN
            UPDATE StrategyPerformance 
            SET total_trades = total_trades + 1,
                last_updated = GETDATE()
            WHERE strategy_name = @strategy_name;
        END
    END
END
GO

-- Close Trade
IF EXISTS (SELECT * FROM sysobjects WHERE name='sp_CloseTrade' AND xtype='P')
    DROP PROCEDURE sp_CloseTrade
GO

CREATE PROCEDURE sp_CloseTrade
    @trade_id NVARCHAR(50),
    @exit_price DECIMAL(18, 2),
    @commission DECIMAL(18, 2) = 0
AS
BEGIN
    DECLARE @quantity INT, @entry_price DECIMAL(18, 2), @trade_type NVARCHAR(10);
    DECLARE @pnl DECIMAL(18, 2), @pnl_percentage DECIMAL(10, 4);
    
    SELECT @quantity = quantity, @entry_price = entry_price, @trade_type = trade_type
    FROM TradeJournal
    WHERE trade_id = @trade_id;
    
    -- Calculate PnL
    IF @trade_type = 'BUY'
        SET @pnl = (@exit_price - @entry_price) * @quantity - @commission;
    ELSE
        SET @pnl = (@entry_price - @exit_price) * @quantity - @commission;
    
    SET @pnl_percentage = (@pnl / (@entry_price * @quantity)) * 100;
    
    -- Update trade
    UPDATE TradeJournal
    SET exit_price = @exit_price,
        exit_time = GETDATE(),
        pnl = @pnl,
        pnl_percentage = @pnl_percentage,
        commission = @commission,
        status = 'CLOSED',
        updated_at = GETDATE()
    WHERE trade_id = @trade_id;
    
    -- Update daily performance
    DECLARE @today DATE = CAST(GETDATE() AS DATE);
    
    IF NOT EXISTS (SELECT 1 FROM DailyPerformance WHERE date = @today)
    BEGIN
        INSERT INTO DailyPerformance (date, total_trades, gross_pnl, net_pnl)
        VALUES (@today, 1, @pnl + @commission, @pnl);
    END
    ELSE
    BEGIN
        UPDATE DailyPerformance
        SET total_trades = total_trades + 1,
            gross_pnl = gross_pnl + @pnl + @commission,
            net_pnl = net_pnl + @pnl,
            commission_paid = commission_paid + @commission,
            winning_trades = winning_trades + CASE WHEN @pnl > 0 THEN 1 ELSE 0 END,
            losing_trades = losing_trades + CASE WHEN @pnl < 0 THEN 1 ELSE 0 END
        WHERE date = @today;
    END
END
GO

-- Get Performance Summary
IF EXISTS (SELECT * FROM sysobjects WHERE name='sp_GetPerformanceSummary' AND xtype='P')
    DROP PROCEDURE sp_GetPerformanceSummary
GO

CREATE PROCEDURE sp_GetPerformanceSummary
    @from_date DATE = NULL,
    @to_date DATE = NULL
AS
BEGIN
    IF @from_date IS NULL
        SET @from_date = DATEADD(MONTH, -1, GETDATE());
    
    IF @to_date IS NULL
        SET @to_date = GETDATE();
    
    SELECT 
        COUNT(*) as total_trades,
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
        SUM(pnl) as total_pnl,
        AVG(pnl) as avg_pnl,
        MAX(pnl) as best_trade,
        MIN(pnl) as worst_trade,
        AVG(pnl_percentage) as avg_return,
        CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / 
            NULLIF(COUNT(*), 0) * 100 as win_rate
    FROM TradeJournal
    WHERE entry_time BETWEEN @from_date AND @to_date
        AND status = 'CLOSED';
END
GO

-- ============= INDEXES =============

CREATE INDEX idx_trade_journal_entry_time ON TradeJournal(entry_time);
CREATE INDEX idx_trade_journal_status ON TradeJournal(status);
CREATE INDEX idx_trade_journal_symbol ON TradeJournal(symbol);
CREATE INDEX idx_daily_performance_date ON DailyPerformance(date);
CREATE INDEX idx_signal_history_time ON SignalHistory(signal_time);

PRINT 'Trade Journal tables and procedures created successfully!';