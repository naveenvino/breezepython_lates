-- User Authentication Tables for Trading Platform
-- Execute in KiteConnectApi database

USE KiteConnectApi;
GO

-- 1. USERS TABLE
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Users' AND xtype='U')
CREATE TABLE Users (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    username NVARCHAR(50) NOT NULL UNIQUE,
    email NVARCHAR(255) NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    full_name NVARCHAR(100),
    phone_number NVARCHAR(20),
    role NVARCHAR(50) DEFAULT 'trader', -- admin, trader, viewer
    is_active BIT DEFAULT 1,
    is_verified BIT DEFAULT 0,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    last_login DATETIME2,
    login_count INT DEFAULT 0,
    failed_login_attempts INT DEFAULT 0,
    account_locked_until DATETIME2,
    profile_image NVARCHAR(500),
    settings NVARCHAR(MAX) -- JSON for user preferences
);

-- Indexes for performance
CREATE INDEX IX_Users_Username ON Users(username);
CREATE INDEX IX_Users_Email ON Users(email);
CREATE INDEX IX_Users_IsActive ON Users(is_active, is_verified);

-- 2. EMAIL VERIFICATION TABLE
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='EmailVerifications' AND xtype='U')
CREATE TABLE EmailVerifications (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    verification_token NVARCHAR(255) NOT NULL UNIQUE,
    expires_at DATETIME2 NOT NULL,
    verified_at DATETIME2,
    created_at DATETIME2 DEFAULT GETDATE(),
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);

CREATE INDEX IX_EmailVerifications_Token ON EmailVerifications(verification_token);
CREATE INDEX IX_EmailVerifications_UserId ON EmailVerifications(user_id);

-- 3. PASSWORD RESET TABLE
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='PasswordResets' AND xtype='U')
CREATE TABLE PasswordResets (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    reset_token NVARCHAR(255) NOT NULL UNIQUE,
    expires_at DATETIME2 NOT NULL,
    used_at DATETIME2,
    created_at DATETIME2 DEFAULT GETDATE(),
    ip_address NVARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);

CREATE INDEX IX_PasswordResets_Token ON PasswordResets(reset_token);
CREATE INDEX IX_PasswordResets_UserId ON PasswordResets(user_id);

-- 4. USER SESSIONS TABLE (Track active sessions)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='UserSessions' AND xtype='U')
CREATE TABLE UserSessions (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL,
    session_token NVARCHAR(500) NOT NULL UNIQUE,
    refresh_token NVARCHAR(500),
    ip_address NVARCHAR(50),
    user_agent NVARCHAR(500),
    created_at DATETIME2 DEFAULT GETDATE(),
    last_activity DATETIME2 DEFAULT GETDATE(),
    expires_at DATETIME2 NOT NULL,
    is_active BIT DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);

CREATE INDEX IX_UserSessions_Token ON UserSessions(session_token);
CREATE INDEX IX_UserSessions_UserId ON UserSessions(user_id, is_active);

-- 5. AUDIT LOG TABLE (Track user actions)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='UserAuditLog' AND xtype='U')
CREATE TABLE UserAuditLog (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER,
    action_type NVARCHAR(100) NOT NULL, -- login, logout, password_change, profile_update, etc.
    action_details NVARCHAR(MAX),
    ip_address NVARCHAR(50),
    user_agent NVARCHAR(500),
    success BIT DEFAULT 1,
    error_message NVARCHAR(MAX),
    created_at DATETIME2 DEFAULT GETDATE(),
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE SET NULL
);

CREATE INDEX IX_UserAuditLog_UserId ON UserAuditLog(user_id);
CREATE INDEX IX_UserAuditLog_ActionType ON UserAuditLog(action_type, created_at);

-- Insert default admin user (password: Admin@123 - needs to be changed on first login)
-- Password hash is for 'Admin@123' using bcrypt
INSERT INTO Users (
    username, 
    email, 
    password_hash, 
    full_name, 
    role, 
    is_active, 
    is_verified
) VALUES (
    'admin',
    'admin@tradingplatform.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5v2oFu5fUB4uC', -- This is just a placeholder, will be updated
    'System Administrator',
    'admin',
    1,
    1
);

-- Create stored procedures for common operations

-- SP: Register New User
IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sp_RegisterUser]') AND type in (N'P', N'PC'))
DROP PROCEDURE [dbo].[sp_RegisterUser]
GO

CREATE PROCEDURE sp_RegisterUser
    @Username NVARCHAR(50),
    @Email NVARCHAR(255),
    @PasswordHash NVARCHAR(255),
    @FullName NVARCHAR(100) = NULL,
    @PhoneNumber NVARCHAR(20) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Check if username or email already exists
    IF EXISTS (SELECT 1 FROM Users WHERE username = @Username OR email = @Email)
    BEGIN
        RAISERROR('Username or email already exists', 16, 1);
        RETURN;
    END
    
    -- Insert new user
    DECLARE @UserId UNIQUEIDENTIFIER = NEWID();
    
    INSERT INTO Users (id, username, email, password_hash, full_name, phone_number)
    VALUES (@UserId, @Username, @Email, @PasswordHash, @FullName, @PhoneNumber);
    
    -- Return the new user ID
    SELECT @UserId as UserId;
END
GO

-- SP: Validate User Login
IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sp_ValidateLogin]') AND type in (N'P', N'PC'))
DROP PROCEDURE [dbo].[sp_ValidateLogin]
GO

CREATE PROCEDURE sp_ValidateLogin
    @UsernameOrEmail NVARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        id,
        username,
        email,
        password_hash,
        full_name,
        role,
        is_active,
        is_verified,
        failed_login_attempts,
        account_locked_until
    FROM Users
    WHERE (username = @UsernameOrEmail OR email = @UsernameOrEmail);
END
GO

-- SP: Update Login Success
IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sp_UpdateLoginSuccess]') AND type in (N'P', N'PC'))
DROP PROCEDURE [dbo].[sp_UpdateLoginSuccess]
GO

CREATE PROCEDURE sp_UpdateLoginSuccess
    @UserId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE Users
    SET 
        last_login = GETDATE(),
        login_count = login_count + 1,
        failed_login_attempts = 0,
        account_locked_until = NULL
    WHERE id = @UserId;
END
GO

-- SP: Update Login Failure
IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sp_UpdateLoginFailure]') AND type in (N'P', N'PC'))
DROP PROCEDURE [dbo].[sp_UpdateLoginFailure]
GO

CREATE PROCEDURE sp_UpdateLoginFailure
    @UserId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @FailedAttempts INT;
    
    -- Get current failed attempts
    SELECT @FailedAttempts = failed_login_attempts FROM Users WHERE id = @UserId;
    
    SET @FailedAttempts = @FailedAttempts + 1;
    
    -- Lock account after 5 failed attempts (for 15 minutes)
    IF @FailedAttempts >= 5
    BEGIN
        UPDATE Users
        SET 
            failed_login_attempts = @FailedAttempts,
            account_locked_until = DATEADD(MINUTE, 15, GETDATE())
        WHERE id = @UserId;
    END
    ELSE
    BEGIN
        UPDATE Users
        SET failed_login_attempts = @FailedAttempts
        WHERE id = @UserId;
    END
END
GO

PRINT 'User authentication tables created successfully!';
PRINT 'Default admin user created (username: admin, password: needs to be set)';
PRINT 'Run this script in SQL Server Management Studio or via sqlcmd';