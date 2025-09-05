"""
Hybrid Database Connection Manager
Supports both SQL Server (legacy) and PostgreSQL (new) during migration
"""

import os
from typing import Optional, Union
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class HybridDatabaseManager:
    """
    Manages database connections for both SQL Server and PostgreSQL
    Allows gradual migration from SQL Server to PostgreSQL
    """
    
    def __init__(self):
        self.db_type = os.getenv('DATABASE_TYPE', 'sqlserver').lower()
        self.sql_engine = None
        self.pg_engine = None
        self.sql_session_factory = None
        self.pg_session_factory = None
        
        logger.info(f"Initializing HybridDatabaseManager with {self.db_type}")
    
    def get_sqlserver_connection_string(self) -> str:
        """Get SQL Server connection string"""
        server = os.getenv('DB_SERVER', r'(localdb)\mssqllocaldb')
        database = os.getenv('DB_NAME', 'KiteConnectApi')
        driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        trusted = os.getenv('DB_TRUSTED_CONNECTION', 'true').lower() == 'true'
        
        if trusted:
            return f"mssql+pyodbc://{server}/{database}?driver={driver}&trusted_connection=yes"
        else:
            username = os.getenv('DB_USER', '')
            password = os.getenv('DB_PASSWORD', '')
            return f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver={driver}"
    
    def get_postgresql_connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        host = os.getenv('PG_HOST', 'localhost')
        port = os.getenv('PG_PORT', '5432')
        database = os.getenv('PG_DATABASE', 'trading_system')
        user = os.getenv('PG_USER', 'trading_app')
        password = os.getenv('PG_PASSWORD', 'your_secure_password')
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    def get_engine(self, force_type: Optional[str] = None):
        """Get database engine based on configuration or force_type"""
        db_type = force_type or self.db_type
        
        if db_type == 'postgresql':
            if not self.pg_engine:
                conn_str = self.get_postgresql_connection_string()
                self.pg_engine = create_engine(
                    conn_str,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False
                )
                logger.info("PostgreSQL engine created")
            return self.pg_engine
        else:
            if not self.sql_engine:
                conn_str = self.get_sqlserver_connection_string()
                self.sql_engine = create_engine(
                    conn_str,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False
                )
                logger.info("SQL Server engine created")
            return self.sql_engine
    
    def get_session_factory(self, force_type: Optional[str] = None):
        """Get session factory for the database"""
        db_type = force_type or self.db_type
        
        if db_type == 'postgresql':
            if not self.pg_session_factory:
                self.pg_session_factory = sessionmaker(
                    bind=self.get_engine('postgresql'),
                    expire_on_commit=False,
                    autoflush=False
                )
            return self.pg_session_factory
        else:
            if not self.sql_session_factory:
                self.sql_session_factory = sessionmaker(
                    bind=self.get_engine('sqlserver'),
                    expire_on_commit=False,
                    autoflush=False
                )
            return self.sql_session_factory
    
    def get_session(self, force_type: Optional[str] = None) -> Session:
        """Get a database session"""
        factory = self.get_session_factory(force_type)
        return factory()
    
    @contextmanager
    def session_scope(self, force_type: Optional[str] = None):
        """Provide a transactional scope for database operations"""
        session = self.get_session(force_type)
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def execute_query(self, query: str, params: dict = None, force_type: Optional[str] = None):
        """Execute a raw SQL query"""
        with self.session_scope(force_type) as session:
            result = session.execute(query, params or {})
            if result.returns_rows:
                return result.fetchall()
            return None
    
    def migrate_table_data(self, table_name: str, batch_size: int = 1000):
        """
        Migrate data from SQL Server to PostgreSQL for a specific table
        Used during gradual migration
        """
        logger.info(f"Migrating table: {table_name}")
        
        with self.session_scope('sqlserver') as sql_session:
            # Get data from SQL Server
            query = f"SELECT * FROM {table_name}"
            result = sql_session.execute(query)
            
            rows = []
            for row in result:
                rows.append(dict(row))
                
                if len(rows) >= batch_size:
                    # Insert batch into PostgreSQL
                    self._insert_batch_postgresql(table_name, rows)
                    rows = []
            
            # Insert remaining rows
            if rows:
                self._insert_batch_postgresql(table_name, rows)
        
        logger.info(f"Migration completed for table: {table_name}")
    
    def _insert_batch_postgresql(self, table_name: str, rows: list):
        """Insert batch of rows into PostgreSQL"""
        if not rows:
            return
        
        with self.session_scope('postgresql') as pg_session:
            # Build insert statement
            columns = list(rows[0].keys())
            placeholders = ', '.join([f":{col}" for col in columns])
            column_names = ', '.join(columns)
            
            insert_sql = f"""
                INSERT INTO {table_name} ({column_names})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            
            for row in rows:
                pg_session.execute(insert_sql, row)
    
    def check_connection(self, db_type: Optional[str] = None) -> bool:
        """Check if database connection is working"""
        db_type = db_type or self.db_type
        
        try:
            with self.session_scope(db_type) as session:
                if db_type == 'postgresql':
                    result = session.execute("SELECT 1")
                else:
                    result = session.execute("SELECT 1 AS test")
                
                return result.fetchone() is not None
        except Exception as e:
            logger.error(f"Connection check failed for {db_type}: {e}")
            return False
    
    def close(self):
        """Close all database connections"""
        if self.sql_engine:
            self.sql_engine.dispose()
            self.sql_engine = None
        
        if self.pg_engine:
            self.pg_engine.dispose()
            self.pg_engine = None
        
        logger.info("All database connections closed")

# Singleton instance
_db_manager: Optional[HybridDatabaseManager] = None

def get_db_manager() -> HybridDatabaseManager:
    """Get singleton database manager"""
    global _db_manager
    if not _db_manager:
        _db_manager = HybridDatabaseManager()
    return _db_manager

def get_db_session(force_type: Optional[str] = None) -> Session:
    """Get a database session"""
    return get_db_manager().get_session(force_type)

def get_db():
    """FastAPI dependency for database session"""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

# Compatibility functions for existing code
def get_sqlserver_session() -> Session:
    """Get SQL Server session (legacy support)"""
    return get_db_session('sqlserver')

def get_postgresql_session() -> Session:
    """Get PostgreSQL session"""
    return get_db_session('postgresql')