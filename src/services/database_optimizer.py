"""
Database Query Optimizer
Optimizes database queries with caching, indexing, and query planning
"""

import logging
import time
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pyodbc
from contextlib import contextmanager
import threading
from collections import OrderedDict, defaultdict

logger = logging.getLogger(__name__)

class QueryType(Enum):
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    BULK_INSERT = "bulk_insert"

@dataclass
class QueryMetrics:
    """Metrics for query performance"""
    query_hash: str
    query_type: QueryType
    execution_count: int = 0
    total_time_ms: float = 0
    avg_time_ms: float = 0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0
    rows_affected: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    last_executed: Optional[datetime] = None

@dataclass
class IndexSuggestion:
    """Suggested database index"""
    table_name: str
    columns: List[str]
    index_type: str  # CLUSTERED, NONCLUSTERED, UNIQUE
    reason: str
    estimated_improvement: float  # Percentage

@dataclass 
class QueryPlan:
    """Optimized query execution plan"""
    original_query: str
    optimized_query: str
    use_cache: bool
    cache_ttl: int  # seconds
    batch_size: Optional[int] = None
    parallel_execution: bool = False
    estimated_time_ms: float = 0

class DatabaseOptimizer:
    """
    Optimizes database operations with intelligent caching and query optimization
    """
    
    def __init__(self, connection_string: str):
        self.conn_str = connection_string
        
        # Connection pooling
        self.connection_pool = []
        self.max_pool_size = 10
        self.active_connections = 0
        
        # Query cache
        self.cache = OrderedDict()
        self.max_cache_size = 1000
        self.cache_ttl = {}
        
        # Query metrics
        self.query_metrics: Dict[str, QueryMetrics] = {}
        self.slow_query_threshold_ms = 1000
        
        # Batch processing
        self.batch_queues: Dict[str, List] = defaultdict(list)
        self.batch_timers: Dict[str, float] = {}
        self.batch_size_limit = 1000
        
        # Index suggestions
        self.index_suggestions: List[IndexSuggestion] = []
        self.analyzed_tables = set()
        
        # Query rewriting rules
        self.rewrite_rules = {
            "SELECT * FROM": self._optimize_select_star,
            "IN (": self._optimize_in_clause,
            "OR ": self._optimize_or_conditions,
            "LIKE '%": self._optimize_wildcard_like,
        }
        
        # Initialize connection pool
        self._initialize_pool()
        
        # Start background tasks
        self._start_background_tasks()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        for _ in range(min(3, self.max_pool_size)):
            try:
                conn = pyodbc.connect(self.conn_str)
                conn.autocommit = False
                self.connection_pool.append(conn)
            except Exception as e:
                logger.error(f"Error creating connection: {e}")
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool"""
        conn = None
        try:
            # Try to get from pool
            if self.connection_pool:
                conn = self.connection_pool.pop()
            else:
                # Create new connection if under limit
                if self.active_connections < self.max_pool_size:
                    conn = pyodbc.connect(self.conn_str)
                    conn.autocommit = False
                else:
                    # Wait for available connection
                    while not self.connection_pool and self.active_connections >= self.max_pool_size:
                        time.sleep(0.1)
                    conn = self.connection_pool.pop()
            
            self.active_connections += 1
            yield conn
            
        finally:
            if conn:
                self.active_connections -= 1
                # Return to pool if healthy
                try:
                    conn.execute("SELECT 1").fetchone()
                    self.connection_pool.append(conn)
                except:
                    conn.close()
    
    def execute_optimized(self, query: str, params: Tuple = None, cache_ttl: int = 60) -> Any:
        """
        Execute query with optimization
        
        Args:
            query: SQL query
            params: Query parameters
            cache_ttl: Cache time-to-live in seconds
        
        Returns:
            Query results
        """
        # Generate query hash for caching
        query_hash = self._generate_query_hash(query, params)
        
        # Check cache
        cached_result = self._get_cached_result(query_hash)
        if cached_result is not None:
            self._update_metrics(query_hash, QueryType.SELECT, 0, cache_hit=True)
            return cached_result
        
        # Optimize query
        optimized_query = self._optimize_query(query)
        
        # Execute query
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if params:
                    cursor.execute(optimized_query, params)
                else:
                    cursor.execute(optimized_query)
                
                # Determine query type
                query_type = self._determine_query_type(query)
                
                if query_type == QueryType.SELECT:
                    results = cursor.fetchall()
                    # Cache results
                    self._cache_result(query_hash, results, cache_ttl)
                else:
                    conn.commit()
                    results = cursor.rowcount
                
                execution_time = (time.time() - start_time) * 1000
                
                # Update metrics
                self._update_metrics(query_hash, query_type, execution_time, rows=len(results) if query_type == QueryType.SELECT else results)
                
                # Check for slow query
                if execution_time > self.slow_query_threshold_ms:
                    self._analyze_slow_query(query, execution_time)
                
                return results
                
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            raise
    
    def bulk_insert_optimized(self, table: str, data: List[Dict], batch_size: int = 1000) -> int:
        """
        Optimized bulk insert with batching
        
        Args:
            table: Table name
            data: List of dictionaries to insert
            batch_size: Batch size for insertion
        
        Returns:
            Number of rows inserted
        """
        if not data:
            return 0
        
        total_inserted = 0
        columns = list(data[0].keys())
        
        # Create parameterized query
        placeholders = ','.join(['?' for _ in columns])
        query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Process in batches
                for i in range(0, len(data), batch_size):
                    batch = data[i:i + batch_size]
                    
                    # Prepare batch data
                    batch_data = []
                    for row in batch:
                        batch_data.append(tuple(row.get(col) for col in columns))
                    
                    # Execute batch insert
                    cursor.executemany(query, batch_data)
                    conn.commit()
                    
                    total_inserted += len(batch)
                    
                    # Small delay between batches to avoid overwhelming the database
                    if i + batch_size < len(data):
                        time.sleep(0.01)
                
                execution_time = (time.time() - start_time) * 1000
                
                # Update metrics
                query_hash = self._generate_query_hash(query, None)
                self._update_metrics(query_hash, QueryType.BULK_INSERT, execution_time, rows=total_inserted)
                
                logger.info(f"Bulk inserted {total_inserted} rows into {table} in {execution_time:.2f}ms")
                
                return total_inserted
                
        except Exception as e:
            logger.error(f"Bulk insert error: {e}")
            raise
    
    def _optimize_query(self, query: str) -> str:
        """Apply query optimization rules"""
        optimized = query
        
        # Apply rewrite rules
        for pattern, optimizer in self.rewrite_rules.items():
            if pattern in query.upper():
                optimized = optimizer(optimized)
        
        # Add query hints for SQL Server
        if "SELECT" in optimized.upper() and "WITH (NOLOCK)" not in optimized.upper():
            # Add NOLOCK hint for read queries to avoid blocking
            optimized = optimized.replace("FROM", "FROM").replace("FROM", "WITH (NOLOCK) FROM", 1)
        
        return optimized
    
    def _optimize_select_star(self, query: str) -> str:
        """Optimize SELECT * queries"""
        # In production, would analyze table schema and select only needed columns
        # For now, just log a warning
        logger.warning("SELECT * detected - consider specifying columns")
        return query
    
    def _optimize_in_clause(self, query: str) -> str:
        """Optimize IN clauses with many values"""
        import re
        
        # Find IN clauses with more than 10 values
        pattern = r'IN\s*\(([^)]+)\)'
        matches = re.findall(pattern, query, re.IGNORECASE)
        
        for match in matches:
            values = match.split(',')
            if len(values) > 100:
                # For large IN clauses, consider using temp table
                logger.warning(f"Large IN clause with {len(values)} values - consider using temp table")
        
        return query
    
    def _optimize_or_conditions(self, query: str) -> str:
        """Optimize OR conditions"""
        # Count OR conditions
        or_count = query.upper().count(' OR ')
        if or_count > 5:
            logger.warning(f"Query has {or_count} OR conditions - consider using UNION or redesigning")
        return query
    
    def _optimize_wildcard_like(self, query: str) -> str:
        """Optimize leading wildcard LIKE queries"""
        if "LIKE '%" in query.upper():
            logger.warning("Leading wildcard in LIKE clause - cannot use index")
        return query
    
    def analyze_table_for_indexes(self, table: str) -> List[IndexSuggestion]:
        """
        Analyze table and suggest indexes
        
        Args:
            table: Table name to analyze
        
        Returns:
            List of index suggestions
        """
        if table in self.analyzed_tables:
            return []
        
        suggestions = []
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get table statistics
                cursor.execute(f"""
                    SELECT 
                        col.name as column_name,
                        stat.rows as row_count,
                        stat.rows_sampled,
                        stat.modification_counter
                    FROM sys.stats stat
                    INNER JOIN sys.stats_columns statcol 
                        ON stat.object_id = statcol.object_id 
                        AND stat.stats_id = statcol.stats_id
                    INNER JOIN sys.columns col 
                        ON statcol.object_id = col.object_id 
                        AND statcol.column_id = col.column_id
                    WHERE stat.object_id = OBJECT_ID(?)
                """, (table,))
                
                stats = cursor.fetchall()
                
                # Analyze foreign key columns without indexes
                cursor.execute(f"""
                    SELECT 
                        fk.name as fk_name,
                        col.name as column_name
                    FROM sys.foreign_keys fk
                    INNER JOIN sys.foreign_key_columns fkc 
                        ON fk.object_id = fkc.constraint_object_id
                    INNER JOIN sys.columns col 
                        ON fkc.parent_object_id = col.object_id 
                        AND fkc.parent_column_id = col.column_id
                    WHERE fk.parent_object_id = OBJECT_ID(?)
                    AND NOT EXISTS (
                        SELECT 1 FROM sys.index_columns ic
                        WHERE ic.object_id = col.object_id 
                        AND ic.column_id = col.column_id
                    )
                """, (table,))
                
                unindexed_fks = cursor.fetchall()
                
                # Suggest indexes for foreign keys
                for fk_name, column_name in unindexed_fks:
                    suggestions.append(IndexSuggestion(
                        table_name=table,
                        columns=[column_name],
                        index_type="NONCLUSTERED",
                        reason=f"Foreign key {fk_name} is not indexed",
                        estimated_improvement=30.0
                    ))
                
                # Analyze query patterns from metrics
                for query_hash, metrics in self.query_metrics.items():
                    if table.upper() in metrics.query_hash.upper():
                        if metrics.avg_time_ms > 100:
                            # Suggest index based on WHERE clause columns
                            # This is simplified - in production would parse query properly
                            suggestions.append(IndexSuggestion(
                                table_name=table,
                                columns=["DateTime", "SignalType"],  # Common columns
                                index_type="NONCLUSTERED",
                                reason=f"Slow query pattern detected (avg {metrics.avg_time_ms:.0f}ms)",
                                estimated_improvement=50.0
                            ))
                
                self.analyzed_tables.add(table)
                self.index_suggestions.extend(suggestions)
                
                return suggestions
                
        except Exception as e:
            logger.error(f"Error analyzing table {table}: {e}")
            return []
    
    def get_query_statistics(self) -> Dict[str, Any]:
        """Get comprehensive query statistics"""
        stats = {
            "total_queries": sum(m.execution_count for m in self.query_metrics.values()),
            "cache_hit_rate": 0,
            "slow_queries": [],
            "most_frequent": [],
            "slowest_queries": []
        }
        
        # Calculate cache hit rate
        total_cache_checks = sum(m.cache_hits + m.cache_misses for m in self.query_metrics.values())
        if total_cache_checks > 0:
            total_hits = sum(m.cache_hits for m in self.query_metrics.values())
            stats["cache_hit_rate"] = (total_hits / total_cache_checks) * 100
        
        # Find slow queries
        for query_hash, metrics in self.query_metrics.items():
            if metrics.avg_time_ms > self.slow_query_threshold_ms:
                stats["slow_queries"].append({
                    "query_type": metrics.query_type.value,
                    "avg_time_ms": metrics.avg_time_ms,
                    "execution_count": metrics.execution_count
                })
        
        # Sort by frequency
        sorted_by_frequency = sorted(
            self.query_metrics.items(),
            key=lambda x: x[1].execution_count,
            reverse=True
        )[:5]
        
        stats["most_frequent"] = [
            {
                "query_type": m.query_type.value,
                "execution_count": m.execution_count,
                "avg_time_ms": m.avg_time_ms
            }
            for _, m in sorted_by_frequency
        ]
        
        # Sort by slowness
        sorted_by_time = sorted(
            self.query_metrics.items(),
            key=lambda x: x[1].avg_time_ms,
            reverse=True
        )[:5]
        
        stats["slowest_queries"] = [
            {
                "query_type": m.query_type.value,
                "avg_time_ms": m.avg_time_ms,
                "max_time_ms": m.max_time_ms,
                "execution_count": m.execution_count
            }
            for _, m in sorted_by_time
        ]
        
        return stats
    
    def _generate_query_hash(self, query: str, params: Tuple) -> str:
        """Generate hash for query and parameters"""
        query_str = query + str(params) if params else query
        return hashlib.md5(query_str.encode()).hexdigest()
    
    def _determine_query_type(self, query: str) -> QueryType:
        """Determine the type of query"""
        query_upper = query.upper().strip()
        
        if query_upper.startswith("SELECT"):
            return QueryType.SELECT
        elif query_upper.startswith("INSERT"):
            return QueryType.INSERT
        elif query_upper.startswith("UPDATE"):
            return QueryType.UPDATE
        elif query_upper.startswith("DELETE"):
            return QueryType.DELETE
        else:
            return QueryType.SELECT
    
    def _get_cached_result(self, query_hash: str) -> Optional[Any]:
        """Get cached query result"""
        if query_hash in self.cache:
            # Check TTL
            if query_hash in self.cache_ttl:
                if time.time() < self.cache_ttl[query_hash]:
                    # Move to end (LRU)
                    self.cache.move_to_end(query_hash)
                    return self.cache[query_hash]
                else:
                    # Expired
                    del self.cache[query_hash]
                    del self.cache_ttl[query_hash]
        return None
    
    def _cache_result(self, query_hash: str, result: Any, ttl: int):
        """Cache query result"""
        # Limit cache size
        if len(self.cache) >= self.max_cache_size:
            # Remove oldest (LRU)
            oldest = next(iter(self.cache))
            del self.cache[oldest]
            if oldest in self.cache_ttl:
                del self.cache_ttl[oldest]
        
        self.cache[query_hash] = result
        self.cache_ttl[query_hash] = time.time() + ttl
    
    def _update_metrics(self, query_hash: str, query_type: QueryType, execution_time: float, 
                       rows: int = 0, cache_hit: bool = False):
        """Update query metrics"""
        if query_hash not in self.query_metrics:
            self.query_metrics[query_hash] = QueryMetrics(
                query_hash=query_hash,
                query_type=query_type
            )
        
        metrics = self.query_metrics[query_hash]
        
        if cache_hit:
            metrics.cache_hits += 1
        else:
            metrics.cache_misses += 1
            metrics.execution_count += 1
            metrics.total_time_ms += execution_time
            metrics.avg_time_ms = metrics.total_time_ms / metrics.execution_count
            metrics.min_time_ms = min(metrics.min_time_ms, execution_time)
            metrics.max_time_ms = max(metrics.max_time_ms, execution_time)
            metrics.rows_affected += rows
        
        metrics.last_executed = datetime.now()
    
    def _analyze_slow_query(self, query: str, execution_time: float):
        """Analyze slow query and suggest optimizations"""
        logger.warning(f"Slow query detected ({execution_time:.0f}ms): {query[:100]}...")
        
        # Extract table names from query
        import re
        tables = re.findall(r'FROM\s+(\w+)', query, re.IGNORECASE)
        
        # Analyze tables for index suggestions
        for table in tables:
            self.analyze_table_for_indexes(table)
    
    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        # Cache cleanup
        threading.Thread(target=self._cleanup_cache, daemon=True).start()
        
        # Metrics reporting
        threading.Thread(target=self._report_metrics, daemon=True).start()
        
        # Connection pool health check
        threading.Thread(target=self._check_connection_health, daemon=True).start()
    
    def _cleanup_cache(self):
        """Periodically clean up expired cache entries"""
        while True:
            try:
                time.sleep(60)  # Check every minute
                
                expired = []
                current_time = time.time()
                
                for query_hash, expiry in self.cache_ttl.items():
                    if current_time > expiry:
                        expired.append(query_hash)
                
                for query_hash in expired:
                    if query_hash in self.cache:
                        del self.cache[query_hash]
                    del self.cache_ttl[query_hash]
                
                if expired:
                    logger.info(f"Cleaned up {len(expired)} expired cache entries")
                    
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def _report_metrics(self):
        """Periodically report database metrics"""
        while True:
            try:
                time.sleep(300)  # Report every 5 minutes
                
                stats = self.get_query_statistics()
                logger.info(f"Database statistics: {json.dumps(stats, indent=2)}")
                
                if self.index_suggestions:
                    logger.info(f"Index suggestions: {len(self.index_suggestions)} available")
                    
            except Exception as e:
                logger.error(f"Metrics reporting error: {e}")
    
    def _check_connection_health(self):
        """Check health of connection pool"""
        while True:
            try:
                time.sleep(30)  # Check every 30 seconds
                
                unhealthy = []
                for conn in self.connection_pool:
                    try:
                        conn.execute("SELECT 1").fetchone()
                    except:
                        unhealthy.append(conn)
                
                # Remove unhealthy connections
                for conn in unhealthy:
                    self.connection_pool.remove(conn)
                    try:
                        conn.close()
                    except:
                        pass
                
                # Replenish pool
                while len(self.connection_pool) < min(3, self.max_pool_size):
                    try:
                        conn = pyodbc.connect(self.conn_str)
                        conn.autocommit = False
                        self.connection_pool.append(conn)
                    except Exception as e:
                        logger.error(f"Error creating connection: {e}")
                        break
                        
            except Exception as e:
                logger.error(f"Connection health check error: {e}")

# Singleton instance
_instance = None

def get_database_optimizer(connection_string: str = None) -> DatabaseOptimizer:
    """Get singleton instance"""
    global _instance
    if _instance is None:
        if connection_string is None:
            connection_string = (
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=(localdb)\\mssqllocaldb;"
                "DATABASE=KiteConnectApi;"
                "Trusted_Connection=yes;"
            )
        _instance = DatabaseOptimizer(connection_string)
    return _instance