"""
Database connection pooling for faster DB operations
"""
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import os

class OptimizedDatabaseManager:
    """Database manager with connection pooling"""
    
    def __init__(self):
        # Create engine with connection pooling
        self.engine = create_engine(
            os.getenv('DATABASE_URL', 'sqlite:///market_data.db'),
            poolclass=QueuePool,
            pool_size=20,  # Number of connections to maintain
            max_overflow=10,  # Maximum overflow connections
            pool_pre_ping=True,  # Check connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False
        )
        
    @contextmanager
    def get_session(self):
        """Get a session from the pool"""
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()
    
    def bulk_insert_optimized(self, model_class, records: list, batch_size: int = 1000):
        """Optimized bulk insert with batching"""
        from sqlalchemy.dialects.sqlite import insert
        
        with self.get_session() as session:
            # Process in batches
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                
                # Use bulk_insert_mappings for maximum speed
                session.bulk_insert_mappings(model_class, batch)
                
                # Commit after each batch
                session.commit()
    
    def execute_raw_sql(self, query: str, params: dict = None):
        """Execute raw SQL for maximum performance"""
        with self.engine.connect() as conn:
            result = conn.execute(query, params or {})
            conn.commit()
            return result

# Optimized bulk insert with COPY (PostgreSQL) or multi-row INSERT
def ultra_fast_bulk_insert(db_manager, table_name: str, records: list):
    """Ultra-fast bulk insert using database-specific optimizations"""
    
    if not records:
        return
    
    # For SQLite: Use multi-row INSERT
    columns = list(records[0].keys())
    placeholders = ','.join(['?' for _ in columns])
    
    query = f"""
    INSERT OR IGNORE INTO {table_name} ({','.join(columns)})
    VALUES ({placeholders})
    """
    
    # Execute in batches
    batch_size = 500
    with db_manager.engine.connect() as conn:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            values = [tuple(record[col] for col in columns) for record in batch]
            conn.execute(query, values)
        conn.commit()