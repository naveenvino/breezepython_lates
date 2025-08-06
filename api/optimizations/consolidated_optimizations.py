"""
Consolidated optimization utilities for the trading system.
Combines the best features from all optimization modules.
"""

import asyncio
import functools
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker, scoped_session
import redis
import pickle
import hashlib
import logging

logger = logging.getLogger(__name__)

# Database Connection Pool
class DatabasePool:
    """Optimized database connection pooling"""
    
    def __init__(self, connection_string: str, pool_size: int = 20, max_overflow: int = 40):
        self.engine = create_engine(
            connection_string,
            poolclass=pool.QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
        self.SessionLocal = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )
    
    def get_session(self):
        """Get a database session from the pool"""
        return self.SessionLocal()
    
    def close_session(self, session):
        """Return session to pool"""
        session.close()
    
    def execute_bulk_insert(self, table_name: str, data: List[Dict]):
        """Execute bulk insert with optimal batch size"""
        if not data:
            return
        
        session = self.get_session()
        try:
            # Convert to DataFrame for efficient bulk operations
            df = pd.DataFrame(data)
            df.to_sql(table_name, self.engine, if_exists='append', index=False, method='multi', chunksize=1000)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Bulk insert failed: {e}")
            raise
        finally:
            self.close_session(session)

# Smart Caching System
class SmartCache:
    """Intelligent caching with TTL and memory management"""
    
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379, 
                 redis_db: int = 0, use_redis: bool = False):
        self.use_redis = use_redis and self._check_redis_available(redis_host, redis_port)
        
        if self.use_redis:
            self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
        else:
            self.memory_cache = {}
            self.cache_timestamps = {}
    
    def _check_redis_available(self, host: str, port: int) -> bool:
        """Check if Redis is available"""
        try:
            r = redis.Redis(host=host, port=port)
            r.ping()
            return True
        except:
            return False
    
    def _generate_key(self, prefix: str, params: Dict) -> str:
        """Generate cache key from parameters"""
        param_str = str(sorted(params.items()))
        hash_obj = hashlib.md5(param_str.encode())
        return f"{prefix}:{hash_obj.hexdigest()}"
    
    def get(self, key: str, ttl: int = 300) -> Optional[Any]:
        """Get value from cache with TTL check"""
        if self.use_redis:
            try:
                value = self.redis_client.get(key)
                if value:
                    return pickle.loads(value)
            except Exception as e:
                logger.error(f"Redis get failed: {e}")
        else:
            if key in self.memory_cache:
                timestamp = self.cache_timestamps.get(key, 0)
                if time.time() - timestamp < ttl:
                    return self.memory_cache[key]
                else:
                    del self.memory_cache[key]
                    del self.cache_timestamps[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache with TTL"""
        if self.use_redis:
            try:
                self.redis_client.setex(key, ttl, pickle.dumps(value))
            except Exception as e:
                logger.error(f"Redis set failed: {e}")
        else:
            self.memory_cache[key] = value
            self.cache_timestamps[key] = time.time()
    
    def cache_decorator(self, ttl: int = 300, prefix: str = "func"):
        """Decorator for caching function results"""
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self._generate_key(
                    f"{prefix}:{func.__name__}",
                    {"args": str(args), "kwargs": str(kwargs)}
                )
                
                # Check cache
                cached_value = self.get(cache_key, ttl)
                if cached_value is not None:
                    return cached_value
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Store in cache
                self.set(cache_key, result, ttl)
                
                return result
            return wrapper
        return decorator

# Parallel Processing Utilities
class ParallelProcessor:
    """Utilities for parallel and async processing"""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or 4
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=self.max_workers)
    
    def parallel_map(self, func: Callable, items: List, use_processes: bool = False) -> List:
        """Execute function in parallel for list of items"""
        executor = self.process_executor if use_processes else self.thread_executor
        
        with executor as ex:
            results = list(ex.map(func, items))
        
        return results
    
    async def async_gather(self, *coros):
        """Gather multiple async coroutines"""
        return await asyncio.gather(*coros)
    
    def batch_process(self, func: Callable, items: List, batch_size: int = 100) -> List:
        """Process items in batches"""
        results = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = self.parallel_map(func, batch)
            results.extend(batch_results)
        return results

# Performance Monitoring
class PerformanceMonitor:
    """Monitor and optimize performance"""
    
    def __init__(self):
        self.metrics = {}
    
    def timer(self, name: str):
        """Context manager for timing operations"""
        class Timer:
            def __init__(self, monitor, name):
                self.monitor = monitor
                self.name = name
                self.start_time = None
            
            def __enter__(self):
                self.start_time = time.time()
                return self
            
            def __exit__(self, *args):
                elapsed = time.time() - self.start_time
                if self.name not in self.monitor.metrics:
                    self.monitor.metrics[self.name] = []
                self.monitor.metrics[self.name].append(elapsed)
        
        return Timer(self, name)
    
    def get_stats(self, name: str) -> Dict:
        """Get statistics for a metric"""
        if name not in self.metrics:
            return {}
        
        times = self.metrics[name]
        return {
            'count': len(times),
            'total': sum(times),
            'mean': np.mean(times),
            'median': np.median(times),
            'min': min(times),
            'max': max(times)
        }
    
    def log_all_stats(self):
        """Log all performance statistics"""
        for name in self.metrics:
            stats = self.get_stats(name)
            logger.info(f"Performance - {name}: {stats}")

# Data Processing Optimizations
class DataOptimizer:
    """Optimizations for data processing"""
    
    @staticmethod
    def optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Optimize DataFrame memory usage"""
        for col in df.columns:
            col_type = df[col].dtype
            
            if col_type != 'object':
                c_min = df[col].min()
                c_max = df[col].max()
                
                if str(col_type)[:3] == 'int':
                    if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                        df[col] = df[col].astype(np.int8)
                    elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                        df[col] = df[col].astype(np.int16)
                    elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                        df[col] = df[col].astype(np.int32)
                else:
                    if c_min > np.finfo(np.float16).min and c_max < np.finfo(np.float16).max:
                        df[col] = df[col].astype(np.float16)
                    elif c_min > np.finfo(np.float32).min and c_max < np.finfo(np.float32).max:
                        df[col] = df[col].astype(np.float32)
        
        return df
    
    @staticmethod
    def vectorized_calculation(df: pd.DataFrame, func: Callable, columns: List[str]) -> pd.Series:
        """Apply vectorized calculations for better performance"""
        return df[columns].apply(func, axis=1, raw=True)

# Singleton instances for global use
_db_pool = None
_cache = None
_processor = None
_monitor = None

def get_db_pool(connection_string: str = None) -> DatabasePool:
    """Get singleton database pool"""
    global _db_pool
    if _db_pool is None and connection_string:
        _db_pool = DatabasePool(connection_string)
    return _db_pool

def get_cache(use_redis: bool = False) -> SmartCache:
    """Get singleton cache instance"""
    global _cache
    if _cache is None:
        _cache = SmartCache(use_redis=use_redis)
    return _cache

def get_processor(max_workers: int = None) -> ParallelProcessor:
    """Get singleton parallel processor"""
    global _processor
    if _processor is None:
        _processor = ParallelProcessor(max_workers)
    return _processor

def get_monitor() -> PerformanceMonitor:
    """Get singleton performance monitor"""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor