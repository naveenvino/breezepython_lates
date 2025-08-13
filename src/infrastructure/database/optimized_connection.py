"""
Optimized Database Connection with Connection Pooling
Improves concurrent request handling and reduces connection overhead
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool, NullPool
import logging
from contextlib import contextmanager
from typing import Optional
import os

logger = logging.getLogger(__name__)


class OptimizedDatabaseConnection:
    """Database connection with optimized pooling and performance settings"""
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        pool_size: int = 20,
        max_overflow: int = 40,
        pool_timeout: int = 30,
        pool_recycle: int = 3600
    ):
        """
        Initialize optimized database connection
        
        Args:
            connection_string: Database connection string
            pool_size: Number of connections to maintain in pool
            max_overflow: Maximum overflow connections allowed
            pool_timeout: Timeout for getting connection from pool
            pool_recycle: Time to recycle connections (seconds)
        """
        if not connection_string:
            # Build from environment variables
            server = os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')
            database = os.getenv('DB_NAME', 'KiteConnectApi')
            connection_string = (
                f"mssql+pyodbc://{server}/{database}"
                "?driver=ODBC+Driver+17+for+SQL+Server"
                "&trusted_connection=yes"
                "&fast_executemany=true"  # Bulk insert optimization
            )
        
        # Create engine with connection pooling
        self.engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for debugging
            connect_args={
                "connect_timeout": 10,
                "options": "-c statement_timeout=60000"  # 60 second statement timeout
            }
        )
        
        # Add event listeners for performance monitoring
        self._setup_event_listeners()
        
        # Create session factory
        self.SessionFactory = scoped_session(
            sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False  # Prevent unnecessary reloads
            )
        )
        
        logger.info(f"Database connection pool created with size={pool_size}, max_overflow={max_overflow}")
    
    def _setup_event_listeners(self):
        """Setup event listeners for monitoring and optimization"""
        
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            """Set connection pragmas for better performance"""
            cursor = dbapi_conn.cursor()
            
            # Set SQL Server specific optimizations
            try:
                cursor.execute("SET NOCOUNT ON")  # Reduce network traffic
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                cursor.execute("SET LOCK_TIMEOUT 5000")  # 5 second lock timeout
                cursor.execute("SET QUERY_GOVERNOR_COST_LIMIT 0")  # No query cost limit
            except Exception as e:
                logger.warning(f"Could not set connection pragmas: {e}")
            
            cursor.close()
        
        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Log when connection is checked out from pool"""
            logger.debug(f"Connection checked out from pool")
        
        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            """Log when connection is returned to pool"""
            logger.debug(f"Connection returned to pool")
    
    @contextmanager
    def get_session(self):
        """
        Context manager for database sessions with automatic cleanup
        """
        session = self.SessionFactory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {e}")
            raise
        finally:
            session.close()
    
    def get_async_session(self):
        """Get session for async operations (for future async implementation)"""
        return self.SessionFactory()
    
    def execute_query(self, query: str, params: dict = None):
        """
        Execute raw SQL query with connection pooling
        """
        with self.engine.connect() as conn:
            result = conn.execute(query, params or {})
            return result.fetchall()
    
    def bulk_insert(self, table_class, records: list):
        """
        Optimized bulk insert using bulk_insert_mappings
        """
        with self.get_session() as session:
            try:
                session.bulk_insert_mappings(table_class, records)
                logger.info(f"Bulk inserted {len(records)} records into {table_class.__name__}")
                return True
            except Exception as e:
                logger.error(f"Bulk insert failed: {e}")
                return False
    
    def get_pool_status(self) -> dict:
        """Get current connection pool status"""
        pool = self.engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.size() + pool.overflow()
        }
    
    def close(self):
        """Close all connections and dispose of the engine"""
        self.SessionFactory.remove()
        self.engine.dispose()
        logger.info("Database connections closed")


# Global instance for reuse
_db_connection = None


def get_optimized_connection() -> OptimizedDatabaseConnection:
    """Get or create singleton database connection"""
    global _db_connection
    if _db_connection is None:
        _db_connection = OptimizedDatabaseConnection()
    return _db_connection


def reset_connection():
    """Reset the database connection"""
    global _db_connection
    if _db_connection:
        _db_connection.close()
        _db_connection = None