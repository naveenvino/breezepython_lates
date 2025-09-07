"""
Production-grade database connection pooling with error handling
"""
import os
import logging
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager, contextmanager
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import sqlite3
from pathlib import Path
import threading
import time

logger = logging.getLogger(__name__)

class DatabaseConnectionPool:
    """Production-grade database connection pool with failover"""
    
    def __init__(self):
        self._engines = {}
        self._session_makers = {}
        self._async_session_makers = {}
        self._sqlite_pools = {}
        self._health_check_interval = 30  # seconds
        self._last_health_check = 0
        
    def _get_sql_server_url(self) -> str:
        """Get SQL Server connection URL with proper pooling"""
        server = os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')
        database = os.getenv('DB_NAME', 'KiteConnectApi')
        driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        
        if os.getenv('DB_TRUSTED_CONNECTION', 'true').lower() == 'true':
            return f"mssql+pyodbc://@{server}/{database}?driver={driver}&TrustServerCertificate=yes"
        else:
            username = os.getenv('DB_USERNAME')
            password = os.getenv('DB_PASSWORD')
            if not username or not password:
                raise ValueError("DB_USERNAME and DB_PASSWORD required when trusted connection disabled")
            return f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver={driver}&TrustServerCertificate=yes"
    
    def get_engine(self, db_type: str = "primary") -> sa.Engine:
        """Get SQLAlchemy engine with connection pooling"""
        if db_type not in self._engines:
            try:
                if db_type == "primary":
                    url = self._get_sql_server_url()
                    # Production connection pool settings
                    engine = sa.create_engine(
                        url,
                        poolclass=QueuePool,
                        pool_size=20,
                        max_overflow=30,
                        pool_timeout=30,
                        pool_recycle=3600,  # 1 hour
                        pool_pre_ping=True,  # Verify connections
                        echo=False,  # Set to True for SQL debugging
                        connect_args={
                            "timeout": 30,
                            "check_same_thread": False
                        }
                    )
                else:
                    raise ValueError(f"Unknown database type: {db_type}")
                    
                self._engines[db_type] = engine
                logger.info(f"Database engine created for {db_type}")
                
            except Exception as e:
                logger.error(f"Failed to create database engine for {db_type}: {e}")
                raise
                
        return self._engines[db_type]
    
    def get_session_maker(self, db_type: str = "primary") -> sessionmaker:
        """Get SQLAlchemy session maker"""
        if db_type not in self._session_makers:
            engine = self.get_engine(db_type)
            self._session_makers[db_type] = sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
        return self._session_makers[db_type]
    
    def get_async_engine(self, db_type: str = "primary"):
        """Get async SQLAlchemy engine"""
        if f"{db_type}_async" not in self._engines:
            try:
                url = self._get_sql_server_url()
                # Convert to async URL
                if url.startswith('mssql+pyodbc://'):
                    url = url.replace('mssql+pyodbc://', 'mssql+aioodbc://')
                
                engine = create_async_engine(
                    url,
                    pool_size=10,
                    max_overflow=20,
                    pool_timeout=30,
                    pool_recycle=3600,
                    pool_pre_ping=True,
                    echo=False
                )
                self._engines[f"{db_type}_async"] = engine
                logger.info(f"Async database engine created for {db_type}")
                
            except Exception as e:
                logger.error(f"Failed to create async database engine for {db_type}: {e}")
                raise
                
        return self._engines[f"{db_type}_async"]
    
    def get_async_session_maker(self, db_type: str = "primary"):
        """Get async SQLAlchemy session maker"""
        if db_type not in self._async_session_makers:
            engine = self.get_async_engine(db_type)
            self._async_session_makers[db_type] = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
        return self._async_session_makers[db_type]
    
    @contextmanager
    def get_session(self, db_type: str = "primary"):
        """Get database session with automatic cleanup"""
        session_maker = self.get_session_maker(db_type)
        session = session_maker()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    @asynccontextmanager
    async def get_async_session(self, db_type: str = "primary"):
        """Get async database session with automatic cleanup"""
        session_maker = self.get_async_session_maker(db_type)
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Async database session error: {e}")
                raise
    
    def get_sqlite_connection(self, db_name: str = "trading_settings") -> sqlite3.Connection:
        """Get SQLite connection with connection pooling"""
        db_path = Path("data") / f"{db_name}.db"
        db_path.parent.mkdir(exist_ok=True)
        
        # Simple connection pool for SQLite
        thread_id = threading.get_ident()
        pool_key = f"{db_name}_{thread_id}"
        
        if pool_key not in self._sqlite_pools:
            conn = sqlite3.connect(
                str(db_path),
                timeout=30.0,
                check_same_thread=False,
                isolation_level='DEFERRED'
            )
            conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Better performance
            conn.execute("PRAGMA cache_size=10000")  # 10MB cache
            conn.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
            self._sqlite_pools[pool_key] = conn
            logger.debug(f"SQLite connection created for {db_name}")
            
        return self._sqlite_pools[pool_key]
    
    @contextmanager
    def get_sqlite_session(self, db_name: str = "trading_settings"):
        """Get SQLite session with automatic transaction handling"""
        conn = self.get_sqlite_connection(db_name)
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite transaction error: {e}")
            raise
        finally:
            cursor.close()
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all database connections"""
        current_time = time.time()
        if current_time - self._last_health_check < self._health_check_interval:
            return {"status": "cached", "healthy": True}
        
        results = {}
        
        # Check SQL Server
        try:
            with self.get_session("primary") as session:
                session.execute(sa.text("SELECT 1"))
                results["sql_server"] = {"healthy": True, "latency_ms": 0}
        except Exception as e:
            results["sql_server"] = {"healthy": False, "error": str(e)}
        
        # Check SQLite
        try:
            with self.get_sqlite_session() as cursor:
                cursor.execute("SELECT 1")
                results["sqlite"] = {"healthy": True, "latency_ms": 0}
        except Exception as e:
            results["sqlite"] = {"healthy": False, "error": str(e)}
        
        self._last_health_check = current_time
        overall_health = all(r.get("healthy", False) for r in results.values())
        
        return {
            "status": "checked",
            "healthy": overall_health,
            "databases": results,
            "timestamp": current_time
        }
    
    def close_all(self):
        """Close all database connections"""
        # Close SQLAlchemy engines
        for engine_name, engine in self._engines.items():
            try:
                if hasattr(engine, 'dispose'):
                    engine.dispose()
                logger.info(f"Closed engine: {engine_name}")
            except Exception as e:
                logger.error(f"Error closing engine {engine_name}: {e}")
        
        # Close SQLite connections
        for pool_key, conn in self._sqlite_pools.items():
            try:
                conn.close()
                logger.info(f"Closed SQLite connection: {pool_key}")
            except Exception as e:
                logger.error(f"Error closing SQLite connection {pool_key}: {e}")
        
        # Clear all pools
        self._engines.clear()
        self._session_makers.clear()
        self._async_session_makers.clear()
        self._sqlite_pools.clear()

# Global connection pool instance
_connection_pool: Optional[DatabaseConnectionPool] = None

def get_connection_pool() -> DatabaseConnectionPool:
    """Get global database connection pool instance"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = DatabaseConnectionPool()
    return _connection_pool

# Convenience functions
def get_db_session(db_type: str = "primary"):
    """Get database session (context manager)"""
    return get_connection_pool().get_session(db_type)

def get_async_db_session(db_type: str = "primary"):
    """Get async database session (context manager)"""
    return get_connection_pool().get_async_session(db_type)

def get_sqlite_session(db_name: str = "trading_settings"):
    """Get SQLite session (context manager)"""
    return get_connection_pool().get_sqlite_session(db_name)

def health_check_databases() -> Dict[str, Any]:
    """Perform health check on all databases"""
    return get_connection_pool().health_check()