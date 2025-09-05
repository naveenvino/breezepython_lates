"""
PostgreSQL Database Configuration
Handles connection to PostgreSQL with TimescaleDB
"""

import os
from typing import Optional
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import psycopg2
from psycopg2 import pool as pg_pool
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Base for SQLAlchemy models
Base = declarative_base()

class PostgreSQLConfig:
    """PostgreSQL database configuration"""
    
    def __init__(self):
        # Load from environment or use defaults
        self.host = os.getenv('PG_HOST', 'localhost')
        self.port = int(os.getenv('PG_PORT', 5432))
        self.database = os.getenv('PG_DATABASE', 'trading_system')
        self.user = os.getenv('PG_USER', 'trading_app')
        self.password = os.getenv('PG_PASSWORD', 'your_secure_password')
        
        # Connection pool settings
        self.pool_min_size = int(os.getenv('PG_POOL_MIN', 5))
        self.pool_max_size = int(os.getenv('PG_POOL_MAX', 20))
        self.pool_timeout = int(os.getenv('PG_POOL_TIMEOUT', 30))
        
        # Performance settings
        self.statement_timeout = int(os.getenv('PG_STATEMENT_TIMEOUT', 30000))  # ms
        self.lock_timeout = int(os.getenv('PG_LOCK_TIMEOUT', 10000))  # ms
        
    @property
    def connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_connection_string(self) -> str:
        """Get async PostgreSQL connection string"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

class DatabaseManager:
    """Manages PostgreSQL database connections and sessions"""
    
    def __init__(self, config: Optional[PostgreSQLConfig] = None):
        self.config = config or PostgreSQLConfig()
        self._engine = None
        self._session_factory = None
        self._connection_pool = None
    
    @property
    def engine(self):
        """Get or create SQLAlchemy engine"""
        if not self._engine:
            self._engine = create_engine(
                self.config.connection_string,
                poolclass=pool.QueuePool,
                pool_size=self.config.pool_min_size,
                max_overflow=self.config.pool_max_size - self.config.pool_min_size,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=3600,  # Recycle connections after 1 hour
                pool_pre_ping=True,  # Test connections before using
                connect_args={
                    'options': f'-c statement_timeout={self.config.statement_timeout} '
                              f'-c lock_timeout={self.config.lock_timeout}',
                    'connect_timeout': 10,
                }
            )
            logger.info("PostgreSQL engine created successfully")
        return self._engine
    
    @property
    def session_factory(self):
        """Get or create session factory"""
        if not self._session_factory:
            self._session_factory = sessionmaker(
                bind=self.engine,
                expire_on_commit=False,
                autoflush=False
            )
        return self._session_factory
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for database operations"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_connection_pool(self):
        """Get psycopg2 connection pool for raw queries"""
        if not self._connection_pool:
            self._connection_pool = pg_pool.ThreadedConnectionPool(
                self.config.pool_min_size,
                self.config.pool_max_size,
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                options=f'-c statement_timeout={self.config.statement_timeout}'
            )
            logger.info("PostgreSQL connection pool created")
        return self._connection_pool
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        pool = self.get_connection_pool()
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None):
        """Execute a raw SQL query"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
                return None
    
    def execute_many(self, query: str, data: list):
        """Execute many queries efficiently"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                psycopg2.extras.execute_batch(cursor, query, data, page_size=1000)
    
    def check_connection(self) -> bool:
        """Check if database connection is working"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    return result[0] == 1
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    def close(self):
        """Close all connections"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        
        if self._connection_pool:
            self._connection_pool.closeall()
            self._connection_pool = None
        
        logger.info("Database connections closed")

# Singleton instance
_db_manager: Optional[DatabaseManager] = None

def get_db_manager() -> DatabaseManager:
    """Get singleton database manager instance"""
    global _db_manager
    if not _db_manager:
        _db_manager = DatabaseManager()
    return _db_manager

def get_db_session() -> Session:
    """Get a database session"""
    return get_db_manager().get_session()

# Dependency for FastAPI
def get_db():
    """FastAPI dependency for database session"""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()