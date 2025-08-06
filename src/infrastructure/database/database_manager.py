"""
Database Manager
Handles database connections and session management
"""
import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions"""
    
    def __init__(self):
        self.settings = get_settings()
        self._engine = None
        self._session_factory = None
    
    @property
    def engine(self):
        """Get or create database engine"""
        if self._engine is None:
            self._engine = create_engine(
                self.settings.database.connection_string,
                poolclass=QueuePool,  # Enable connection pooling
                pool_size=20,         # Number of persistent connections
                max_overflow=10,      # Maximum overflow connections
                pool_timeout=30,      # Timeout for getting connection
                pool_recycle=3600,    # Recycle connections after 1 hour
                pool_pre_ping=True,   # Test connections before use
                echo=self.settings.database.echo_sql,
                connect_args={
                    "timeout": 30,
                    "autocommit": False
                }
            )
            
            # Add event listeners
            @event.listens_for(self._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                # Set any connection-specific settings here
                pass
            
            logger.info("Database engine created")
        
        return self._engine
    
    @property
    def session_factory(self):
        """Get or create session factory"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
            logger.info("Session factory created")
        
        return self._session_factory
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup"""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_tables(self):
        """Create all database tables"""
        from .models.market_data_model import Base as MarketDataBase
        from .models.options_model import Base as OptionsBase
        from .models.trade_model import Base as TradeBase
        
        # Create all tables
        MarketDataBase.metadata.create_all(bind=self.engine)
        OptionsBase.metadata.create_all(bind=self.engine)
        TradeBase.metadata.create_all(bind=self.engine)
        
        logger.info("Database tables created")
    
    def drop_tables(self):
        """Drop all database tables"""
        from .models.market_data_model import Base as MarketDataBase
        from .models.options_model import Base as OptionsBase
        from .models.trade_model import Base as TradeBase
        
        # Drop all tables
        MarketDataBase.metadata.drop_all(bind=self.engine)
        OptionsBase.metadata.drop_all(bind=self.engine)
        TradeBase.metadata.drop_all(bind=self.engine)
        
        logger.info("Database tables dropped")
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def close(self):
        """Close database connections"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connections closed")


# Global database manager instance
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Get database session from global manager"""
    manager = get_db_manager()
    with manager.get_session() as session:
        yield session