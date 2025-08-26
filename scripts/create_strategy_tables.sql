-- Create tables for trading strategy management

-- Drop existing tables if they exist
IF OBJECT_ID('dbo.strategy_executions', 'U') IS NOT NULL 
    DROP TABLE dbo.strategy_executions;
    
IF OBJECT_ID('dbo.trading_strategies', 'U') IS NOT NULL 
    DROP TABLE dbo.trading_strategies;

-- Create trading_strategies table
CREATE TABLE trading_strategies (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    instrument NVARCHAR(20) NOT NULL,
    strategy_type NVARCHAR(20) NOT NULL CHECK (strategy_type IN ('intraday', 'positional')),
    signals NVARCHAR(MAX) NOT NULL, -- JSON array of signals
    main_lots INT NOT NULL,
    hedge_lots INT NOT NULL,
    hedge_strike_distance INT NOT NULL,
    
    stop_loss_enabled BIT DEFAULT 0,
    stop_loss_value FLOAT NULL,
    
    target_profit_enabled BIT DEFAULT 0,
    target_profit_value FLOAT NULL,
    
    trailing_enabled BIT DEFAULT 0,
    trailing_type NVARCHAR(20) DEFAULT 'none' CHECK (trailing_type IN ('none', 'points', 'percentage', 'dynamic')),
    trailing_value FLOAT NULL,
    
    status NVARCHAR(20) DEFAULT 'created' CHECK (status IN ('created', 'deployed', 'paused', 'stopped', 'completed')),
    created_at DATETIME DEFAULT GETUTCDATE(),
    deployed_at DATETIME NULL,
    stopped_at DATETIME NULL,
    
    current_pnl FLOAT DEFAULT 0.0,
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    
    strategy_metadata NVARCHAR(MAX) NULL -- JSON for additional metadata
);

-- Create strategy_executions table
CREATE TABLE strategy_executions (
    id INT IDENTITY(1,1) PRIMARY KEY,
    strategy_id INT NOT NULL,
    signal NVARCHAR(10) NOT NULL,
    entry_time DATETIME NOT NULL,
    exit_time DATETIME NULL,
    
    main_strike INT NOT NULL,
    main_entry_price FLOAT NOT NULL,
    main_exit_price FLOAT NULL,
    main_quantity INT NOT NULL,
    
    hedge_strike INT NULL,
    hedge_entry_price FLOAT NULL,
    hedge_exit_price FLOAT NULL,
    hedge_quantity INT NULL,
    
    pnl FLOAT DEFAULT 0.0,
    status NVARCHAR(20) DEFAULT 'open',
    exit_reason NVARCHAR(50) NULL,
    
    created_at DATETIME DEFAULT GETUTCDATE(),
    updated_at DATETIME DEFAULT GETUTCDATE(),
    
    FOREIGN KEY (strategy_id) REFERENCES trading_strategies(id)
);

-- Create indexes for better query performance
CREATE INDEX idx_strategies_status ON trading_strategies(status);
CREATE INDEX idx_strategies_instrument ON trading_strategies(instrument);
CREATE INDEX idx_executions_strategy_id ON strategy_executions(strategy_id);
CREATE INDEX idx_executions_status ON strategy_executions(status);
CREATE INDEX idx_executions_entry_time ON strategy_executions(entry_time);

PRINT 'Strategy tables created successfully';