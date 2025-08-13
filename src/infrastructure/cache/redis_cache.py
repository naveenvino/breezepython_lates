"""
Redis Caching Layer for High-Performance Data Access
Provides distributed caching for option prices and frequently accessed data
"""

import redis
import json
import pickle
import hashlib
from typing import Any, Optional, Union, List, Dict
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache manager for trading system"""
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = False,
        socket_connect_timeout: int = 5,
        socket_timeout: int = 5,
        connection_pool_kwargs: Optional[dict] = None
    ):
        """
        Initialize Redis connection with connection pooling
        
        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password if required
            decode_responses: Whether to decode responses
            socket_connect_timeout: Connection timeout
            socket_timeout: Socket timeout
            connection_pool_kwargs: Additional connection pool parameters
        """
        try:
            pool_kwargs = connection_pool_kwargs or {}
            pool_kwargs.update({
                'host': host,
                'port': port,
                'db': db,
                'password': password,
                'decode_responses': decode_responses,
                'socket_connect_timeout': socket_connect_timeout,
                'socket_timeout': socket_timeout,
                'max_connections': 50,
                'socket_keepalive': True,
                'socket_keepalive_options': {
                    1: 1,  # TCP_KEEPIDLE
                    2: 15, # TCP_KEEPINTVL
                    3: 3,  # TCP_KEEPCNT
                }
            })
            
            self.pool = redis.ConnectionPool(**pool_kwargs)
            self.redis_client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            self.redis_client.ping()
            self.connected = True
            logger.info("Redis cache connected successfully")
            
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis not available, falling back to in-memory cache: {e}")
            self.connected = False
            self.memory_cache = {}
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments"""
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, (datetime, pd.Timestamp)):
                key_parts.append(arg.strftime('%Y%m%d_%H%M%S'))
            elif isinstance(arg, (list, tuple)):
                key_parts.append('_'.join(str(x) for x in arg))
            else:
                key_parts.append(str(arg))
        
        # Add keyword arguments
        for k, v in sorted(kwargs.items()):
            if isinstance(v, (datetime, pd.Timestamp)):
                key_parts.append(f"{k}_{v.strftime('%Y%m%d_%H%M%S')}")
            else:
                key_parts.append(f"{k}_{v}")
        
        return ':'.join(key_parts)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.connected:
            return self.memory_cache.get(key)
        
        try:
            value = self.redis_client.get(key)
            if value:
                return pickle.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = 3600
    ) -> bool:
        """
        Set value in cache with optional TTL
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default 1 hour)
        """
        if not self.connected:
            self.memory_cache[key] = value
            return True
        
        try:
            serialized = pickle.dumps(value)
            if ttl:
                return self.redis_client.setex(key, ttl, serialized)
            else:
                return self.redis_client.set(key, serialized)
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.connected:
            if key in self.memory_cache:
                del self.memory_cache[key]
                return True
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.connected:
            return key in self.memory_cache
        
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False
    
    def get_option_prices(
        self,
        timestamp: datetime,
        strike_prices: List[float],
        option_types: List[str],
        expiry_date: Optional[datetime] = None
    ) -> Optional[pd.DataFrame]:
        """Get cached option prices"""
        key = self._generate_key(
            'options',
            timestamp,
            strike_prices,
            option_types,
            expiry=expiry_date
        )
        
        cached_data = self.get(key)
        if cached_data is not None:
            logger.debug(f"Cache hit for option prices: {key}")
            return pd.DataFrame(cached_data)
        
        return None
    
    def set_option_prices(
        self,
        timestamp: datetime,
        strike_prices: List[float],
        option_types: List[str],
        data: pd.DataFrame,
        expiry_date: Optional[datetime] = None,
        ttl: int = 3600
    ) -> bool:
        """Cache option prices data"""
        key = self._generate_key(
            'options',
            timestamp,
            strike_prices,
            option_types,
            expiry=expiry_date
        )
        
        # Convert DataFrame to dict for serialization
        data_dict = data.to_dict('records')
        
        success = self.set(key, data_dict, ttl)
        if success:
            logger.debug(f"Cached option prices: {key}")
        
        return success
    
    def get_nifty_data(
        self,
        start_time: datetime,
        end_time: datetime,
        interval: str = '5min'
    ) -> Optional[pd.DataFrame]:
        """Get cached NIFTY data"""
        key = self._generate_key('nifty', start_time, end_time, interval)
        
        cached_data = self.get(key)
        if cached_data is not None:
            logger.debug(f"Cache hit for NIFTY data: {key}")
            return pd.DataFrame(cached_data)
        
        return None
    
    def set_nifty_data(
        self,
        start_time: datetime,
        end_time: datetime,
        interval: str,
        data: pd.DataFrame,
        ttl: int = 3600
    ) -> bool:
        """Cache NIFTY data"""
        key = self._generate_key('nifty', start_time, end_time, interval)
        
        data_dict = data.to_dict('records')
        success = self.set(key, data_dict, ttl)
        
        if success:
            logger.debug(f"Cached NIFTY data: {key}")
        
        return success
    
    def cache_calculation(
        self,
        func_name: str,
        args: tuple,
        kwargs: dict,
        result: Any,
        ttl: int = 1800
    ) -> bool:
        """Cache expensive calculation results"""
        key = self._generate_key('calc', func_name, *args, **kwargs)
        return self.set(key, result, ttl)
    
    def get_calculation(
        self,
        func_name: str,
        args: tuple,
        kwargs: dict
    ) -> Optional[Any]:
        """Get cached calculation result"""
        key = self._generate_key('calc', func_name, *args, **kwargs)
        return self.get(key)
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self.connected:
            # For memory cache, clear matching keys
            keys_to_delete = [k for k in self.memory_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self.memory_cache[key]
            return len(keys_to_delete)
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Clear pattern error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.connected:
            return {
                'type': 'memory',
                'keys': len(self.memory_cache),
                'connected': False
            }
        
        try:
            info = self.redis_client.info()
            return {
                'type': 'redis',
                'connected': True,
                'used_memory': info.get('used_memory_human', 'N/A'),
                'keys': self.redis_client.dbsize(),
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
                'hit_rate': info.get('keyspace_hits', 0) / 
                           (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1))
            }
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            return {'error': str(e)}


def cache_result(ttl: int = 3600, prefix: str = 'func'):
    """
    Decorator to cache function results
    
    Args:
        ttl: Time to live in seconds
        prefix: Cache key prefix
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get or create cache instance
            if not hasattr(wrapper, '_cache'):
                wrapper._cache = RedisCache()
            
            # Generate cache key
            cache_key = f"{prefix}:{func.__name__}:" + \
                       hashlib.md5(f"{args}{kwargs}".encode()).hexdigest()
            
            # Try to get from cache
            result = wrapper._cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            wrapper._cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# Global cache instance
_cache = None


def get_cache() -> RedisCache:
    """Get or create global cache instance"""
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache


def reset_cache():
    """Reset global cache instance"""
    global _cache
    if _cache:
        if hasattr(_cache, 'redis_client'):
            _cache.redis_client.close()
        _cache = None