"""
Database index optimization for faster queries
"""
from sqlalchemy import create_engine, text

def optimize_database_indexes(database_url: str):
    """Add optimal indexes for our query patterns"""
    
    engine = create_engine(database_url)
    
    # Indexes for NiftyIndexData
    nifty_indexes = [
        # Primary lookup pattern
        "CREATE INDEX IF NOT EXISTS idx_nifty_symbol_timestamp ON NiftyIndexData(Symbol, Timestamp)",
        
        # Date range queries
        "CREATE INDEX IF NOT EXISTS idx_nifty_timestamp ON NiftyIndexData(Timestamp)",
        
        # Interval filtering
        "CREATE INDEX IF NOT EXISTS idx_nifty_interval ON NiftyIndexData(Interval)",
        
        # Composite for common query
        "CREATE INDEX IF NOT EXISTS idx_nifty_composite ON NiftyIndexData(Symbol, Interval, Timestamp)",
    ]
    
    # Indexes for OptionsHistoricalData
    options_indexes = [
        # Primary lookup pattern
        "CREATE INDEX IF NOT EXISTS idx_options_symbol_timestamp ON OptionsHistoricalData(TradingSymbol, Timestamp)",
        
        # Strike queries
        "CREATE INDEX IF NOT EXISTS idx_options_strike ON OptionsHistoricalData(Strike, OptionType)",
        
        # Date range with underlying
        "CREATE INDEX IF NOT EXISTS idx_options_underlying_date ON OptionsHistoricalData(Underlying, Timestamp)",
        
        # Composite for completeness checks
        "CREATE INDEX IF NOT EXISTS idx_options_complete_check ON OptionsHistoricalData(Underlying, Timestamp, Strike, OptionType)",
        
        # Expiry queries
        "CREATE INDEX IF NOT EXISTS idx_options_expiry ON OptionsHistoricalData(ExpiryDate)",
    ]
    
    # Execute all indexes
    with engine.connect() as conn:
        for index_sql in nifty_indexes + options_indexes:
            print(f"Creating index: {index_sql[:50]}...")
            conn.execute(text(index_sql))
            conn.commit()
    
    # Analyze tables for query optimization (SQLite specific)
    with engine.connect() as conn:
        conn.execute(text("ANALYZE"))
        conn.commit()
    
    print("Database indexes optimized!")

# Query optimization tips
def get_optimized_queries():
    """Return optimized query patterns"""
    
    return {
        "check_existing_strikes": """
            SELECT DISTINCT Strike, OptionType
            FROM OptionsHistoricalData WITH (NOLOCK)  -- SQL Server
            WHERE Underlying = :symbol
                AND Timestamp >= :from_date
                AND Timestamp <= :to_date
                AND Strike BETWEEN :min_strike AND :max_strike
            ORDER BY Strike, OptionType
        """,
        
        "bulk_existence_check": """
            SELECT TradingSymbol, MIN(Timestamp) as first_ts, MAX(Timestamp) as last_ts, COUNT(*) as record_count
            FROM OptionsHistoricalData
            WHERE TradingSymbol IN :symbols
                AND Timestamp >= :from_date
                AND Timestamp <= :to_date
            GROUP BY TradingSymbol
        """,
        
        "efficient_date_range": """
            -- Use date functions for better index usage
            SELECT * FROM NiftyIndexData
            WHERE Symbol = :symbol
                AND DATE(Timestamp) BETWEEN DATE(:from_date) AND DATE(:to_date)
                AND Interval = '5minute'
            ORDER BY Timestamp
        """
    }

# Connection string optimization
def get_optimized_connection_string(base_url: str) -> str:
    """Add performance parameters to connection string"""
    
    if 'sqlite' in base_url:
        # SQLite optimizations
        return f"{base_url}?check_same_thread=False&timeout=30&journal_mode=WAL&synchronous=NORMAL&cache_size=-64000"
    
    elif 'postgresql' in base_url:
        # PostgreSQL optimizations
        return f"{base_url}?pool_size=20&max_overflow=10&pool_pre_ping=true&pool_recycle=3600"
    
    elif 'mysql' in base_url:
        # MySQL optimizations
        return f"{base_url}?pool_size=20&max_overflow=10&pool_pre_ping=true&pool_recycle=3600&charset=utf8mb4"
    
    return base_url