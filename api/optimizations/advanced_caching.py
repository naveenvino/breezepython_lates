"""
Advanced caching strategies for maximum speed
"""
import redis
import pickle
import hashlib
from functools import wraps
from typing import Any, Optional
import json

class AdvancedCache:
    """Multi-level caching system"""
    
    def __init__(self):
        # L1 Cache: In-memory (fastest)
        self.memory_cache = {}
        self.memory_cache_size = 1000
        
        # L2 Cache: Redis (fast)
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=False,
                connection_pool_kwargs={
                    'max_connections': 50,
                    'socket_keepalive': True
                }
            )
            self.redis_available = True
        except:
            self.redis_available = False
        
        # L3 Cache: Local disk (persistent)
        self.disk_cache_dir = "cache/"
        
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key from function and arguments"""
        key_data = f"{func_name}:{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get from cache (checks all levels)"""
        # L1: Memory
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # L2: Redis
        if self.redis_available:
            try:
                value = self.redis_client.get(key)
                if value:
                    deserialized = pickle.loads(value)
                    # Promote to L1
                    self._add_to_memory_cache(key, deserialized)
                    return deserialized
            except:
                pass
        
        # L3: Disk
        # ... disk implementation
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set in all cache levels"""
        # L1: Memory
        self._add_to_memory_cache(key, value)
        
        # L2: Redis
        if self.redis_available:
            try:
                serialized = pickle.dumps(value)
                self.redis_client.setex(key, ttl, serialized)
            except:
                pass
        
        # L3: Disk
        # ... disk implementation
    
    def _add_to_memory_cache(self, key: str, value: Any):
        """Add to memory cache with LRU eviction"""
        if len(self.memory_cache) >= self.memory_cache_size:
            # Remove oldest item (simple LRU)
            oldest = next(iter(self.memory_cache))
            del self.memory_cache[oldest]
        
        self.memory_cache[key] = value

# Decorator for automatic caching
cache = AdvancedCache()

def cached(ttl: int = 3600):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache._generate_key(func.__name__, args, kwargs)
            
            # Check cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

# Example usage
@cached(ttl=86400)  # Cache for 24 hours
def get_strike_range_for_date(date, symbol):
    """This will be cached automatically"""
    # Expensive calculation
    return calculate_strikes(date, symbol)

# Pre-warming cache
def prewarm_cache(dates: list, symbols: list):
    """Pre-warm cache with likely queries"""
    import concurrent.futures
    
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for date in dates:
            for symbol in symbols:
                task = executor.submit(get_strike_range_for_date, date, symbol)
                tasks.append(task)
        
        # Wait for all to complete
        concurrent.futures.wait(tasks)