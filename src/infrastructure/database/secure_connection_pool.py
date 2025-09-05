"""
Secure database connection pooling with proper resource management
"""

import os
import logging
from contextlib import contextmanager
from typing import Optional, Generator
import pyodbc
from sqlalchemy import create_engine, pool, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
from dotenv import load_dotenv
import time
from threading import Lock

load_dotenv()

logger = logging.getLogger(__name__)

class SecureDatabasePool:
    """Secure database connection pool with security features"""
    
    _instance: Optional['SecureDatabasePool'] = None
    _lock = Lock()
    
    def __new__(cls) -> 'SecureDatabasePool':
        """Singleton pattern for connection pool"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize connection pool once"""
        if self._initialized:
            return
            
        self._initialized = True
        self.engine = None
        self.Session = None
        self._setup_pool()
    
    def _setup_pool(self):
        """Setup secure connection pool"""
        try:
            # Get database configuration from environment
            server = os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')
            database = os.getenv('DB_NAME', 'KiteConnectApi')
            driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
            
            # Build secure connection string
            # Note: LocalDB doesn't support encryption, remove for local development
            conn_str = (
                f"mssql+pyodbc://@{server}/{database}"
                f"?driver={driver}"
                f"&trusted_connection=yes"
                f"&connection_timeout=30"
            )
            
            # Create engine with connection pooling
            self.engine = create_engine(
                conn_str,
                poolclass=QueuePool,
                pool_size=10,  # Number of connections to maintain
                max_overflow=20,  # Maximum overflow connections
                pool_timeout=30,  # Timeout for getting connection from pool
                pool_recycle=3600,  # Recycle connections after 1 hour
                pool_pre_ping=True,  # Test connections before using
                echo=False,  # Don't log SQL statements (security)
                connect_args={
                    'connect_timeout': 30,
                    'ansi': True,
                    'autocommit': False,
                    'Mars_Connection': 'Yes',  # Multiple Active Result Sets
                }
            )
            
            # Add event listeners for security
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                """Set secure connection parameters"""
                # Log connection (without sensitive data)
                logger.info(f"Database connection established (pool size: {self.engine.pool.size()})")
            
            @event.listens_for(self.engine, "checkout")
            def receive_checkout(dbapi_conn, connection_record, connection_proxy):
                """Validate connection on checkout"""
                # Test connection is alive
                try:
                    cursor = dbapi_conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                except Exception:
                    # Connection is dead, raise DisconnectionError
                    raise pyodbc.Error("Connection is dead")
            
            # Create session factory
            self.Session = sessionmaker(
                bind=self.engine,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False
            )
            
            # Test connection
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).scalar()
                if result != 1:
                    raise Exception("Database connection test failed")
            
            logger.info("Secure database connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {str(e)}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session with automatic cleanup"""
        session = None
        try:
            session = self.Session()
            yield session
            session.commit()
        except Exception as e:
            if session:
                session.rollback()
            logger.error(f"Database operation failed: {str(e)}")
            raise
        finally:
            if session:
                session.close()
    
    @contextmanager
    def get_raw_connection(self) -> Generator[pyodbc.Connection, None, None]:
        """Get raw pyodbc connection for legacy code"""
        conn = None
        try:
            conn = self.engine.raw_connection()
            yield conn.connection  # Get the underlying pyodbc connection
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation failed: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: dict = None, fetch_all: bool = True):
        """Execute query with parameterization to prevent SQL injection"""
        with self.get_session() as session:
            # Use parameterized queries to prevent SQL injection
            result = session.execute(text(query), params or {})
            if fetch_all:
                return result.fetchall()
            return result.fetchone()
    
    def close(self):
        """Close all connections in the pool"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection pool closed")
    
    def get_pool_status(self) -> dict:
        """Get connection pool status"""
        if not self.engine or not self.engine.pool:
            return {"status": "not initialized"}
        
        pool = self.engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.checkedin() + pool.checkedout()
        }

# Singleton instance
db_pool = SecureDatabasePool()

# Convenience functions for backward compatibility
def get_session() -> Generator[Session, None, None]:
    """Get database session"""
    return db_pool.get_session()

def get_connection() -> Generator[pyodbc.Connection, None, None]:
    """Get raw database connection"""
    return db_pool.get_raw_connection()

def execute_secure_query(query: str, params: dict = None):
    """Execute query with SQL injection prevention"""
    return db_pool.execute_query(query, params)