-- Production Tables for Stable Application State Management
-- Execute this in your KiteConnectApi database

-- Set required options for index creation
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

-- 1. AUTH SESSIONS TABLE (Store Breeze & Kite tokens)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AuthSessions' AND xtype='U')
CREATE TABLE AuthSessions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    service_type NVARCHAR(50) NOT NULL, -- 'breeze', 'kite'
    session_token NVARCHAR(500),
    access_token NVARCHAR(500),
    refresh_token NVARCHAR(500),
    api_key NVARCHAR(255),
    api_secret NVARCHAR(500),
    user_id NVARCHAR(100),
    user_name NVARCHAR(255),
    expires_at DATETIME2,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    is_active BIT DEFAULT 1,
    metadata NVARCHAR(MAX) -- JSON for additional data
);

-- Index for fast lookups
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AuthSessions_ServiceType')
CREATE INDEX IX_AuthSessions_ServiceType ON AuthSessions(service_type, is_active);

-- 2. USER SESSIONS TABLE (Web UI login sessions)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='UserSessions' AND xtype='U')
CREATE TABLE UserSessions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    username NVARCHAR(100) NOT NULL,
    session_token NVARCHAR(500) NOT NULL UNIQUE,
    role NVARCHAR(50) DEFAULT 'user',
    ip_address NVARCHAR(50),
    user_agent NVARCHAR(500),
    created_at DATETIME2 DEFAULT GETDATE(),
    last_activity DATETIME2 DEFAULT GETDATE(),
    expires_at DATETIME2,
    is_active BIT DEFAULT 1
);

-- Index for session lookups
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_UserSessions_Token')
CREATE INDEX IX_UserSessions_Token ON UserSessions(session_token) WHERE is_active = 1;

-- 3. BACKGROUND JOBS TABLE (Track all async tasks)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='BackgroundJobs' AND xtype='U')
CREATE TABLE BackgroundJobs (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    job_id NVARCHAR(100) NOT NULL UNIQUE,
    job_type NVARCHAR(100) NOT NULL, -- 'data_collection', 'ml_validation', 'backtest'
    status NVARCHAR(50) NOT NULL, -- 'pending', 'running', 'completed', 'failed'
    message NVARCHAR(MAX),
    progress_percent INT DEFAULT 0,
    created_by NVARCHAR(100),
    created_at DATETIME2 DEFAULT GETDATE(),
    started_at DATETIME2,
    updated_at DATETIME2 DEFAULT GETDATE(),
    completed_at DATETIME2,
    result_data NVARCHAR(MAX), -- JSON storage for results
    error_details NVARCHAR(MAX)
);

-- Index for job status queries
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_BackgroundJobs_Status')
CREATE INDEX IX_BackgroundJobs_Status ON BackgroundJobs(status, job_type);

-- 4. SYSTEM CONFIGURATIONS TABLE (Replace JSON files)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SystemConfigurations' AND xtype='U')
CREATE TABLE SystemConfigurations (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    config_type NVARCHAR(100) NOT NULL, -- 'scheduler', 'auth', 'trading', 'ml'
    config_key NVARCHAR(100) NOT NULL,
    config_value NVARCHAR(MAX) NOT NULL, -- JSON or simple value
    description NVARCHAR(500),
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    updated_by NVARCHAR(100),
    is_active BIT DEFAULT 1,
    version INT DEFAULT 1,
    CONSTRAINT UQ_SystemConfig UNIQUE(config_type, config_key)
);

-- 5. SCHEDULER EXECUTION HISTORY (Track all scheduled job runs)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SchedulerExecutions' AND xtype='U')
CREATE TABLE SchedulerExecutions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    job_id NVARCHAR(100) NOT NULL,
    job_name NVARCHAR(255),
    platform NVARCHAR(50) NOT NULL, -- 'breeze', 'kite'
    execution_time DATETIME2 DEFAULT GETDATE(),
    success BIT NOT NULL,
    result_message NVARCHAR(MAX),
    error_details NVARCHAR(MAX),
    execution_duration_ms INT,
    retry_count INT DEFAULT 0
);

-- Index for execution history queries
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_SchedulerExecutions_JobPlatform')
CREATE INDEX IX_SchedulerExecutions_JobPlatform ON SchedulerExecutions(job_id, platform, execution_time DESC);

-- 6. ML VALIDATION RUNS TABLE (Store ML model validation results)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='MLValidationRuns' AND xtype='U')
CREATE TABLE MLValidationRuns (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    validation_id NVARCHAR(100) NOT NULL UNIQUE,
    model_type NVARCHAR(100),
    signal_type NVARCHAR(50),
    date_range_start DATE,
    date_range_end DATE,
    status NVARCHAR(50) NOT NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    started_at DATETIME2,
    completed_at DATETIME2,
    accuracy DECIMAL(5,2),
    precision_score DECIMAL(5,2),
    recall_score DECIMAL(5,2),
    f1_score DECIMAL(5,2),
    output_data NVARCHAR(MAX), -- JSON storage for detailed results
    error_message NVARCHAR(MAX),
    created_by NVARCHAR(100)
);

-- 7. AUDIT LOG TABLE (Track all important changes)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AuditLogs' AND xtype='U')
CREATE TABLE AuditLogs (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    entity_type NVARCHAR(100) NOT NULL, -- 'auth', 'config', 'trade', 'job'
    entity_id NVARCHAR(100),
    action NVARCHAR(50) NOT NULL, -- 'create', 'update', 'delete', 'login', 'logout'
    old_value NVARCHAR(MAX),
    new_value NVARCHAR(MAX),
    user_id NVARCHAR(100),
    ip_address NVARCHAR(50),
    timestamp DATETIME2 DEFAULT GETDATE(),
    details NVARCHAR(MAX)
);

-- Index for audit queries
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AuditLogs_EntityType')
CREATE INDEX IX_AuditLogs_EntityType ON AuditLogs(entity_type, timestamp DESC);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AuditLogs_UserId')
CREATE INDEX IX_AuditLogs_UserId ON AuditLogs(user_id, timestamp DESC);

-- 8. CACHE ENTRIES TABLE (Optional - for persistent caching)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='CacheEntries' AND xtype='U')
CREATE TABLE CacheEntries (
    cache_key NVARCHAR(255) PRIMARY KEY,
    cache_value NVARCHAR(MAX),
    cache_type NVARCHAR(50), -- 'market_data', 'calculation', 'api_response'
    expires_at DATETIME2,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    access_count INT DEFAULT 0,
    last_accessed DATETIME2 DEFAULT GETDATE()
);

-- Index for cache expiry cleanup
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_CacheEntries_ExpiresAt')
CREATE INDEX IX_CacheEntries_ExpiresAt ON CacheEntries(expires_at) WHERE expires_at IS NOT NULL;

-- 9. API RATE LIMITS TABLE (Track API usage)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ApiRateLimits' AND xtype='U')
CREATE TABLE ApiRateLimits (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    api_name NVARCHAR(100) NOT NULL, -- 'breeze', 'kite'
    endpoint NVARCHAR(255),
    user_id NVARCHAR(100),
    request_count INT DEFAULT 1,
    window_start DATETIME2 DEFAULT GETDATE(),
    window_end DATETIME2,
    limit_exceeded BIT DEFAULT 0
);

-- Index for rate limit checks
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_ApiRateLimits_Window')
CREATE INDEX IX_ApiRateLimits_Window ON ApiRateLimits(api_name, user_id, window_start, window_end);

-- 10. SYSTEM HEALTH TABLE (Monitor application health)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SystemHealth' AND xtype='U')
CREATE TABLE SystemHealth (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    component NVARCHAR(100) NOT NULL, -- 'api', 'database', 'scheduler', 'auth'
    status NVARCHAR(50) NOT NULL, -- 'healthy', 'degraded', 'unhealthy'
    last_check DATETIME2 DEFAULT GETDATE(),
    response_time_ms INT,
    error_count INT DEFAULT 0,
    details NVARCHAR(MAX)
);

-- Create stored procedure for session cleanup
GO
CREATE OR ALTER PROCEDURE sp_CleanupExpiredSessions
AS
BEGIN
    -- Cleanup expired auth sessions
    UPDATE AuthSessions 
    SET is_active = 0 
    WHERE expires_at < GETDATE() AND is_active = 1;
    
    -- Cleanup expired user sessions
    UPDATE UserSessions 
    SET is_active = 0 
    WHERE expires_at < GETDATE() AND is_active = 1;
    
    -- Cleanup old cache entries
    DELETE FROM CacheEntries 
    WHERE expires_at < GETDATE();
    
    -- Return cleanup stats
    SELECT 
        'Sessions Cleaned' as Operation,
        @@ROWCOUNT as RecordsAffected;
END;
GO

-- Create stored procedure for getting active sessions
CREATE OR ALTER PROCEDURE sp_GetActiveSession
    @ServiceType NVARCHAR(50)
AS
BEGIN
    SELECT TOP 1 
        id,
        service_type,
        session_token,
        access_token,
        user_id,
        user_name,
        expires_at,
        metadata
    FROM AuthSessions
    WHERE service_type = @ServiceType 
        AND is_active = 1
        AND (expires_at IS NULL OR expires_at > GETDATE())
    ORDER BY updated_at DESC;
END;
GO

-- Create stored procedure for updating session
CREATE OR ALTER PROCEDURE sp_UpdateAuthSession
    @ServiceType NVARCHAR(50),
    @SessionToken NVARCHAR(500) = NULL,
    @AccessToken NVARCHAR(500) = NULL,
    @UserId NVARCHAR(100) = NULL,
    @UserName NVARCHAR(255) = NULL,
    @ExpiresAt DATETIME2 = NULL,
    @Metadata NVARCHAR(MAX) = NULL
AS
BEGIN
    -- Deactivate old sessions
    UPDATE AuthSessions 
    SET is_active = 0 
    WHERE service_type = @ServiceType AND is_active = 1;
    
    -- Insert new session
    INSERT INTO AuthSessions (
        service_type, 
        session_token, 
        access_token, 
        user_id, 
        user_name, 
        expires_at, 
        metadata,
        is_active
    ) VALUES (
        @ServiceType,
        @SessionToken,
        @AccessToken,
        @UserId,
        @UserName,
        @ExpiresAt,
        @Metadata,
        1
    );
    
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS SessionId;
END;
GO

-- Initial configuration data (only insert if not exists)
IF NOT EXISTS (SELECT 1 FROM SystemConfigurations WHERE config_type = 'scheduler' AND config_key = 'breeze_login_times')
INSERT INTO SystemConfigurations (config_type, config_key, config_value, description)
VALUES 
    ('scheduler', 'breeze_login_times', '["05:30", "08:30"]', 'Breeze auto-login schedule'),
    ('scheduler', 'kite_login_times', '["05:45", "08:45"]', 'Kite auto-login schedule'),
    ('scheduler', 'weekdays_only', 'true', 'Run scheduler only on weekdays'),
    ('trading', 'default_lot_size', '75', 'Default NIFTY lot size'),
    ('trading', 'max_positions', '10', 'Maximum open positions'),
    ('auth', 'session_timeout_minutes', '1440', '24 hour session timeout'),
    ('api', 'rate_limit_per_minute', '60', 'API rate limit per minute');

-- Grant permissions (adjust user as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.AuthSessions TO [your_app_user];
-- GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.UserSessions TO [your_app_user];
-- GRANT EXECUTE ON dbo.sp_GetActiveSession TO [your_app_user];
-- GRANT EXECUTE ON dbo.sp_UpdateAuthSession TO [your_app_user];
-- GRANT EXECUTE ON dbo.sp_CleanupExpiredSessions TO [your_app_user];

PRINT 'Production tables created successfully!'
PRINT 'Run stored procedures periodically:'
PRINT '  - sp_CleanupExpiredSessions: Every hour'
PRINT '  - sp_GetActiveSession: To retrieve active sessions'
PRINT '  - sp_UpdateAuthSession: To update auth tokens'