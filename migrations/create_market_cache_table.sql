-- Market Data Cache Table for storing real-time and historical market data
-- This table enables 24/7 availability of market data for strategy builder

USE KiteConnectApi;
GO

-- Drop table if exists (for clean migration)
IF EXISTS (SELECT * FROM sysobjects WHERE name='MarketDataCache' AND xtype='U')
DROP TABLE MarketDataCache;
GO

-- Create Market Data Cache Table
CREATE TABLE MarketDataCache (
    id INT PRIMARY KEY IDENTITY(1,1),
    symbol VARCHAR(50) NOT NULL,               -- NIFTY, or full option symbol like NIFTY25AUG24800CE
    instrument_type VARCHAR(20) NOT NULL,      -- SPOT, CE, PE
    underlying VARCHAR(20) NULL,               -- NIFTY for options
    strike INT NULL,                          -- Strike price for options
    expiry_date DATE NULL,                    -- Expiry for options
    
    -- Price data
    spot_price DECIMAL(10,2) NULL,            -- Current NIFTY spot price
    last_price DECIMAL(10,2) NOT NULL,        -- Last traded price
    bid_price DECIMAL(10,2) NULL,             -- Best bid
    ask_price DECIMAL(10,2) NULL,             -- Best ask
    open_price DECIMAL(10,2) NULL,            -- Day open
    high_price DECIMAL(10,2) NULL,            -- Day high
    low_price DECIMAL(10,2) NULL,             -- Day low
    close_price DECIMAL(10,2) NULL,           -- Previous close
    
    -- Volume and OI
    volume BIGINT NULL,                       -- Volume traded
    open_interest INT NULL,                   -- Open interest for options
    oi_change INT NULL,                       -- OI change from previous day
    
    -- Greeks (for options)
    iv DECIMAL(10,4) NULL,                    -- Implied volatility
    delta DECIMAL(10,4) NULL,                 -- Delta
    gamma DECIMAL(10,4) NULL,                 -- Gamma
    theta DECIMAL(10,4) NULL,                 -- Theta
    vega DECIMAL(10,4) NULL,                  -- Vega
    
    -- Metadata
    timestamp DATETIME NOT NULL,              -- When data was captured
    source VARCHAR(20) NOT NULL,              -- 'websocket', 'historical', 'manual', 'api'
    is_stale BIT DEFAULT 0,                   -- Mark if data is outdated
    created_at DATETIME DEFAULT GETDATE(),
    updated_at DATETIME DEFAULT GETDATE()
);
GO

-- Create indexes for performance
CREATE INDEX IX_MarketDataCache_Symbol_Timestamp 
ON MarketDataCache(symbol, timestamp DESC);

CREATE INDEX IX_MarketDataCache_Strike_Expiry 
ON MarketDataCache(strike, expiry_date, instrument_type) 
WHERE strike IS NOT NULL;

CREATE INDEX IX_MarketDataCache_UpdatedAt 
ON MarketDataCache(updated_at DESC);

CREATE INDEX IX_MarketDataCache_Source_Timestamp
ON MarketDataCache(source, timestamp DESC);

-- Index for quick spot price retrieval
CREATE INDEX IX_MarketDataCache_Spot
ON MarketDataCache(instrument_type, timestamp DESC)
WHERE instrument_type = 'SPOT';
GO

-- Create stored procedure for efficient cache updates
CREATE OR ALTER PROCEDURE sp_UpdateMarketDataCache
    @Symbol VARCHAR(50),
    @InstrumentType VARCHAR(20),
    @LastPrice DECIMAL(10,2),
    @SpotPrice DECIMAL(10,2) = NULL,
    @Strike INT = NULL,
    @ExpiryDate DATE = NULL,
    @Source VARCHAR(20) = 'websocket'
AS
BEGIN
    -- Check if record exists for current minute
    DECLARE @CurrentMinute DATETIME = DATEADD(SECOND, -DATEPART(SECOND, GETDATE()), GETDATE());
    
    IF EXISTS (
        SELECT 1 FROM MarketDataCache 
        WHERE symbol = @Symbol 
        AND timestamp >= @CurrentMinute 
        AND timestamp < DATEADD(MINUTE, 1, @CurrentMinute)
    )
    BEGIN
        -- Update existing record
        UPDATE MarketDataCache
        SET last_price = @LastPrice,
            spot_price = COALESCE(@SpotPrice, spot_price),
            updated_at = GETDATE()
        WHERE symbol = @Symbol 
        AND timestamp >= @CurrentMinute 
        AND timestamp < DATEADD(MINUTE, 1, @CurrentMinute);
    END
    ELSE
    BEGIN
        -- Insert new record
        INSERT INTO MarketDataCache (
            symbol, instrument_type, strike, expiry_date,
            spot_price, last_price, timestamp, source
        ) VALUES (
            @Symbol, @InstrumentType, @Strike, @ExpiryDate,
            @SpotPrice, @LastPrice, GETDATE(), @Source
        );
    END
END
GO

-- Create function to get latest market data
CREATE OR ALTER FUNCTION fn_GetLatestMarketData(@Symbol VARCHAR(50))
RETURNS TABLE
AS
RETURN
(
    SELECT TOP 1 *
    FROM MarketDataCache
    WHERE symbol = @Symbol
    AND is_stale = 0
    ORDER BY timestamp DESC
);
GO

-- Create function to get option chain snapshot
CREATE OR ALTER FUNCTION fn_GetOptionChainSnapshot(
    @Underlying VARCHAR(20),
    @ExpiryDate DATE
)
RETURNS TABLE
AS
RETURN
(
    SELECT *
    FROM MarketDataCache mc1
    WHERE underlying = @Underlying
    AND expiry_date = @ExpiryDate
    AND instrument_type IN ('CE', 'PE')
    AND timestamp = (
        SELECT MAX(timestamp)
        FROM MarketDataCache mc2
        WHERE mc2.symbol = mc1.symbol
        AND mc2.timestamp >= DATEADD(HOUR, -1, GETDATE())
    )
);
GO

-- Clean up procedure to remove old data
CREATE OR ALTER PROCEDURE sp_CleanupMarketDataCache
    @DaysToKeep INT = 30
AS
BEGIN
    DELETE FROM MarketDataCache
    WHERE timestamp < DATEADD(DAY, -@DaysToKeep, GETDATE());
    
    -- Mark data older than 1 hour as stale
    UPDATE MarketDataCache
    SET is_stale = 1
    WHERE timestamp < DATEADD(HOUR, -1, GETDATE())
    AND is_stale = 0;
END
GO

PRINT 'MarketDataCache table and procedures created successfully';
GO