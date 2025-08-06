"""
Optimized database manager with connection pooling
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class OptimizedDatabaseManager:
    """Enhanced database manager with connection pooling"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            
            # Get connection string from environment
            connection_string = os.getenv('DATABASE_CONNECTION_STRING', 
                                        'mssql+pyodbc://BreezeUser:BreezePassword@DESKTOP-D2FUIVJ\\SQLEXPRESS01/BreezeMasterDb?driver=ODBC+Driver+17+for+SQL+Server')
            
            # Optimize connection string
            if 'mssql' in connection_string or 'sqlserver' in connection_string:
                # SQL Server optimizations
                if '?' not in connection_string:
                    connection_string += '?'
                else:
                    connection_string += '&'
                
                # Add performance parameters
                connection_string += 'fast_executemany=True&timeout=30'
            
            # Create engine with optimized pooling
            self.engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=20,           # Number of connections to maintain
                max_overflow=10,        # Maximum overflow connections
                pool_timeout=30,        # Timeout for getting connection
                pool_recycle=3600,      # Recycle connections after 1 hour
                pool_pre_ping=True,     # Test connections before using
                echo=False,
                future=True
            )
            
            # Create session factory
            self.Session = sessionmaker(
                bind=self.engine,
                expire_on_commit=False,  # Don't expire objects after commit
                autoflush=False         # Don't auto-flush (we'll control it)
            )
            
            logger.info(f"Optimized database manager initialized with pool_size=20")
    
    @contextmanager
    def get_session(self):
        """Get a database session from the pool"""
        session = self.Session()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def bulk_insert_mappings(self, model_class, mappings, batch_size=1000):
        """Optimized bulk insert using mappings"""
        if not mappings:
            return 0
        
        inserted = 0
        with self.get_session() as session:
            # Process in batches
            for i in range(0, len(mappings), batch_size):
                batch = mappings[i:i + batch_size]
                session.bulk_insert_mappings(model_class, batch)
                session.commit()
                inserted += len(batch)
        
        return inserted
    
    def execute_many(self, query, params_list):
        """Execute many queries efficiently"""
        with self.engine.connect() as conn:
            result = conn.execute(query, params_list)
            conn.commit()
            return result.rowcount
    
    def get_pool_status(self):
        """Get connection pool status"""
        pool = self.engine.pool
        return {
            'size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'total': pool.size() + pool.overflow()
        }

# Singleton instance
_optimized_db_manager = None

def get_optimized_db_manager():
    """Get the optimized database manager instance"""
    global _optimized_db_manager
    if _optimized_db_manager is None:
        _optimized_db_manager = OptimizedDatabaseManager()
    return _optimized_db_manager