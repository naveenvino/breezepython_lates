-- Create UserSettings table for storing trading configuration
-- This ensures settings persist across sessions

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='UserSettings' AND xtype='U')
BEGIN
    CREATE TABLE UserSettings (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL DEFAULT 'default',
        setting_key VARCHAR(100) NOT NULL,
        setting_value NVARCHAR(MAX),
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE(),
        UNIQUE(user_id, setting_key)
    );
    
    PRINT 'UserSettings table created successfully';
END
ELSE
BEGIN
    PRINT 'UserSettings table already exists';
END

-- Insert default settings if not exist
IF NOT EXISTS (SELECT 1 FROM UserSettings WHERE user_id = 'default' AND setting_key = 'position_size')
BEGIN
    INSERT INTO UserSettings (user_id, setting_key, setting_value) VALUES
    ('default', 'position_size', '10'),
    ('default', 'lot_quantity', '75'),
    ('default', 'entry_timing', 'immediate'),
    ('default', 'stop_loss_points', '200'),
    ('default', 'enable_hedging', 'true'),
    ('default', 'hedge_offset', '200'),
    ('default', 'auto_trade_enabled', 'false'),
    ('default', 'trading_mode', 'LIVE'),
    ('default', 'signals_enabled', 'S1,S2,S3,S4,S5,S6,S7,S8'),
    ('default', 'max_drawdown', '50000'),
    ('default', 'max_positions', '5'),
    ('default', 'start_time', '09:15'),
    ('default', 'end_time', '15:15'),
    ('default', 'square_off_time', '15:15');
    
    PRINT 'Default settings inserted';
END

-- View current settings
SELECT * FROM UserSettings WHERE user_id = 'default';