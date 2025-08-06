"""
Smart caching system for market data
"""
import time
import pickle
import hashlib
from typing import Any, Optional, Dict, Callable
from functools import wraps
from collections import OrderedDict
import threading

class LRUCache:
    """Thread-safe LRU cache implementation"""
    
    def __init__(self, max_size: int = 1000):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                value, expiry = self.cache[key]
                
                # Check expiry
                if expiry is None or time.time() < expiry:
                    return value
                else:
                    # Expired
                    del self.cache[key]
                    self.misses += 1
                    return None
            
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        with self.lock:
            # Remove oldest if at capacity
            if len(self.cache) >= self.max_size and key not in self.cache:
                self.cache.popitem(last=False)
            
            expiry = time.time() + ttl if ttl > 0 else None
            self.cache[key] = (value, expiry)
    
    def clear(self):
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> Dict:
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': f"{hit_rate:.1f}%"
            }

class SmartCache:
    """Multi-level caching system"""
    
    def __init__(self):
        # L1: Small, fast cache for hot data
        self.l1_cache = LRUCache(max_size=100)
        
        # L2: Larger cache for warm data
        self.l2_cache = LRUCache(max_size=1000)
        
        # L3: Disk cache (future implementation)
        self.disk_cache_enabled = False
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_data = f"{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get from cache (checks all levels)"""
        # Check L1
        value = self.l1_cache.get(key)
        if value is not None:
            return value
        
        # Check L2
        value = self.l2_cache.get(key)
        if value is not None:
            # Promote to L1
            self.l1_cache.set(key, value, ttl=300)  # 5 min in L1
            return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600, hot: bool = False):
        """Set in cache"""
        if hot:
            # Hot data goes to L1
            self.l1_cache.set(key, value, ttl=min(ttl, 300))
        
        # All data goes to L2
        self.l2_cache.set(key, value, ttl)
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'l1': self.l1_cache.get_stats(),
            'l2': self.l2_cache.get_stats()
        }

# Global cache instance
_smart_cache = SmartCache()

def cached(ttl: int = 3600, key_prefix: str = "", hot: bool = False):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{_smart_cache._generate_key(*args, **kwargs)}"
            
            # Try to get from cache
            result = _smart_cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            _smart_cache.set(cache_key, result, ttl, hot)
            
            return result
        
        # Add cache control methods
        wrapper.cache_clear = lambda: _smart_cache.l1_cache.clear() or _smart_cache.l2_cache.clear()
        wrapper.cache_stats = lambda: _smart_cache.get_stats()
        
        return wrapper
    return decorator

# Specific cache decorators
def cache_strike_range(ttl: int = 86400):  # 24 hours
    """Cache strike range calculations"""
    return cached(ttl=ttl, key_prefix="strike_range", hot=True)

def cache_market_data(ttl: int = 300):  # 5 minutes
    """Cache market data queries"""
    return cached(ttl=ttl, key_prefix="market_data", hot=True)

def cache_db_query(ttl: int = 3600):  # 1 hour
    """Cache database query results"""
    return cached(ttl=ttl, key_prefix="db_query")

# Cache management functions
def get_cache_stats():
    """Get global cache statistics"""
    return _smart_cache.get_stats()

def clear_all_caches():
    """Clear all caches"""
    _smart_cache.l1_cache.clear()
    _smart_cache.l2_cache.clear()

def prewarm_cache(dates: list, symbols: list):
    """Pre-warm cache with common queries"""
    # This would be implemented based on specific use cases
    pass