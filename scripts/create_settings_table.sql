-- Create SystemSettings table for storing application settings
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SystemSettings' AND xtype='U')
CREATE TABLE SystemSettings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value NVARCHAR(MAX),
    category VARCHAR(50),
    updated_at DATETIME DEFAULT GETDATE()
);

-- Insert default settings
IF NOT EXISTS (SELECT * FROM SystemSettings)
BEGIN
    -- General settings
    INSERT INTO SystemSettings (setting_key, setting_value, category) VALUES
    ('general_theme', 'dark', 'general'),
    ('general_language', 'en', 'general'),
    ('general_timezone', 'Asia/Kolkata', 'general'),
    ('general_auto_refresh', '30', 'general'),
    
    -- Trading settings
    ('trading_default_lots', '10', 'trading'),
    ('trading_slippage_tolerance', '0.5', 'trading'),
    ('trading_auto_trade_enabled', 'false', 'trading'),
    ('trading_order_type', 'MARKET', 'trading'),
    ('trading_sound_alerts', 'true', 'trading'),
    
    -- API settings (will be encrypted when saved)
    ('api_breeze_api_key', '', 'api'),
    ('api_breeze_api_secret', '', 'api'),
    ('api_kite_api_key', '', 'api'),
    ('api_kite_access_token', '', 'api'),
    
    -- Notification settings
    ('notifications_browser_enabled', 'false', 'notifications'),
    ('notifications_email_enabled', 'false', 'notifications'),
    ('notifications_sms_enabled', 'false', 'notifications'),
    ('notifications_alert_threshold', '5000', 'notifications'),
    
    -- Risk management settings
    ('risk_max_daily_loss', '50000', 'risk'),
    ('risk_max_positions', '5', 'risk'),
    ('risk_position_size_limit', '100', 'risk'),
    ('risk_stop_loss_percent', '2', 'risk'),
    ('risk_stop_loss_enabled', 'true', 'risk'),
    ('risk_trailing_stop', 'false', 'risk'),
    
    -- Data settings
    ('data_cache_ttl', '300', 'data'),
    ('data_retention_days', '90', 'data'),
    ('data_auto_backup', 'true', 'data'),
    ('data_optimization_schedule', 'weekly', 'data');
END;