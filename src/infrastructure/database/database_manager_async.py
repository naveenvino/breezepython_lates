"""
Asynchronous Database Manager
Handles asynchronous database connections and session management
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class AsyncDatabaseManager:
    """Manages asynchronous database connections and sessions"""
    
    def __init__(self):
        self.settings = get_settings()
        self._engine = None
        self._session_factory = None
    
    @property
    def engine(self):
        """Get or create asynchronous database engine"""
        if self._engine is None:
            self._engine = create_async_engine(
                self.settings.database.connection_string_async,
                poolclass=NullPool,
                echo=self.settings.database.echo_sql,
            )
            logger.info("Asynchronous database engine created")
        
        return self._engine
    
    @property
    def session_factory(self):
        """Get or create asynchronous session factory"""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
                class_=AsyncSession
            )
            logger.info("Asynchronous session factory created")
        
        return self._session_factory
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an asynchronous database session with automatic cleanup"""
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def create_tables(self):
        """Create all database tables"""
        from .models.market_data_model import Base as MarketDataBase
        from .models.options_model import Base as OptionsBase
        from .models.trade_model import Base as TradeBase
        
        async with self.engine.begin() as conn:
            await conn.run_sync(MarketDataBase.metadata.create_all)
            await conn.run_sync(OptionsBase.metadata.create_all)
            await conn.run_sync(TradeBase.metadata.create_all)
        
        logger.info("Database tables created")
    
    async def drop_tables(self):
        """Drop all database tables"""
        from .models.market_data_model import Base as MarketDataBase
        from .models.options_model import Base as OptionsBase
        from .models.trade_model import Base as TradeBase
        
        async with self.engine.begin() as conn:
            await conn.run_sync(MarketDataBase.metadata.drop_all)
            await conn.run_sync(OptionsBase.metadata.drop_all)
            await conn.run_sync(TradeBase.metadata.drop_all)
        
        logger.info("Database tables dropped")
    
    async def test_connection(self) -> bool:
        """Test asynchronous database connection"""
        try:
            from sqlalchemy import text
            async with self.engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                await result.fetchone()
            logger.info("Asynchronous database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Asynchronous database connection test failed: {e}")
            return False
    
    async def close(self):
        """Close database connections"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Asynchronous database connections closed")


# Global asynchronous database manager instance
_async_db_manager = None


def get_async_db_manager() -> AsyncDatabaseManager:
    """Get global asynchronous database manager instance"""
    global _async_db_manager
    if _async_db_manager is None:
        _async_db_manager = AsyncDatabaseManager()
    return _async_db_manager


@asynccontextmanager
async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get asynchronous database session from global manager"""
    manager = get_async_db_manager()
    async with manager.get_session() as session:
        yield session
