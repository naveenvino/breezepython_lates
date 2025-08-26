"""
Intelligent API Cache Manager
Reduces API calls by caching responses and managing rate limits
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from functools import wraps
import asyncio
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class APIRateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self):
        self.calls = defaultdict(list)
        self.limits = {
            'breeze': {'per_second': 5, 'per_minute': 100, 'per_day': 10000},
            'kite': {'per_second': 10, 'per_minute': 200, 'per_day': 20000},
            'default': {'per_second': 10, 'per_minute': 300, 'per_day': 50000}
        }
        
    def can_call(self, api_name: str) -> Tuple[bool, Optional[float]]:
        """Check if API call is allowed"""
        limits = self.limits.get(api_name, self.limits['default'])
        now = time.time()
        
        # Clean old calls
        self.calls[api_name] = [t for t in self.calls[api_name] if now - t < 86400]
        
        # Check per-second limit
        recent_second = [t for t in self.calls[api_name] if now - t < 1]
        if len(recent_second) >= limits['per_second']:
            return False, 1.0
            
        # Check per-minute limit
        recent_minute = [t for t in self.calls[api_name] if now - t < 60]
        if len(recent_minute) >= limits['per_minute']:
            return False, 60 - (now - recent_minute[0])
            
        # Check per-day limit
        recent_day = self.calls[api_name]
        if len(recent_day) >= limits['per_day']:
            oldest = min(recent_day)
            return False, 86400 - (now - oldest)
            
        return True, None
        
    def record_call(self, api_name: str):
        """Record an API call"""
        self.calls[api_name].append(time.time())

class CacheEntry:
    """Single cache entry with metadata"""
    
    def __init__(self, data: Any, ttl: int = 60):
        self.data = data
        self.timestamp = time.time()
        self.ttl = ttl
        self.hits = 0
        
    def is_valid(self) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - self.timestamp < self.ttl
        
    def get(self) -> Any:
        """Get cached data and record hit"""
        self.hits += 1
        return self.data

class APICacheManager:
    """Intelligent cache manager for API responses"""
    
    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}
        self.rate_limiter = APIRateLimiter()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'api_calls': 0,
            'rate_limited': 0
        }
        
        # Cache TTL settings (in seconds)
        self.ttl_settings = {
            'market_data': 5,      # 5 seconds for live prices
            'option_chain': 10,    # 10 seconds for option chain
            'positions': 30,       # 30 seconds for positions
            'orders': 30,          # 30 seconds for orders
            'historical': 3600,    # 1 hour for historical data
            'static': 86400,       # 24 hours for static data
            'default': 60          # 1 minute default
        }
        
    def _generate_key(self, api_name: str, params: Dict) -> str:
        """Generate unique cache key"""
        param_str = json.dumps(params, sort_keys=True)
        return f"{api_name}:{hashlib.md5(param_str.encode()).hexdigest()}"
        
    def get(self, api_name: str, params: Dict, cache_type: str = 'default') -> Optional[Any]:
        """Get cached data if available"""
        key = self._generate_key(api_name, params)
        
        if key in self.cache:
            entry = self.cache[key]
            if entry.is_valid():
                self.stats['hits'] += 1
                logger.debug(f"Cache hit for {api_name}")
                return entry.get()
            else:
                # Remove expired entry
                del self.cache[key]
                
        self.stats['misses'] += 1
        return None
        
    def set(self, api_name: str, params: Dict, data: Any, cache_type: str = 'default'):
        """Store data in cache"""
        key = self._generate_key(api_name, params)
        ttl = self.ttl_settings.get(cache_type, self.ttl_settings['default'])
        
        self.cache[key] = CacheEntry(data, ttl)
        logger.debug(f"Cached {api_name} for {ttl} seconds")
        
    async def call_with_cache(self, api_func, api_name: str, params: Dict, 
                              cache_type: str = 'default', force_refresh: bool = False):
        """Call API with caching and rate limiting"""
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached = self.get(api_name, params, cache_type)
            if cached is not None:
                return cached
                
        # Check rate limit
        can_call, wait_time = self.rate_limiter.can_call(api_name)
        
        if not can_call:
            self.stats['rate_limited'] += 1
            logger.warning(f"Rate limited for {api_name}, wait {wait_time:.1f}s")
            
            # Return cached data even if expired
            key = self._generate_key(api_name, params)
            if key in self.cache:
                logger.info("Returning expired cache due to rate limit")
                return self.cache[key].data
                
            # If no cache, wait and retry
            if wait_time < 5:
                await asyncio.sleep(wait_time)
                return await self.call_with_cache(api_func, api_name, params, cache_type)
            else:
                raise Exception(f"API rate limit exceeded. Wait {wait_time:.0f} seconds")
                
        # Make API call
        try:
            self.rate_limiter.record_call(api_name)
            self.stats['api_calls'] += 1
            
            result = await api_func(**params) if asyncio.iscoroutinefunction(api_func) else api_func(**params)
            
            # Cache successful result
            if result:
                self.set(api_name, params, result, cache_type)
                
            return result
            
        except Exception as e:
            logger.error(f"API call failed for {api_name}: {e}")
            
            # Return cached data on error
            key = self._generate_key(api_name, params)
            if key in self.cache:
                logger.info("Returning cached data due to API error")
                return self.cache[key].data
                
            raise
            
    def clear(self, api_name: Optional[str] = None):
        """Clear cache"""
        if api_name:
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{api_name}:")]
            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"Cleared {len(keys_to_remove)} cache entries for {api_name}")
        else:
            self.cache.clear()
            logger.info("Cleared all cache")
            
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'cache_hits': self.stats['hits'],
            'cache_misses': self.stats['misses'],
            'hit_rate': hit_rate,
            'api_calls': self.stats['api_calls'],
            'rate_limited': self.stats['rate_limited'],
            'cached_items': len(self.cache),
            'cache_size_kb': sum(len(str(e.data)) for e in self.cache.values()) / 1024
        }
        
    def cleanup_expired(self):
        """Remove expired cache entries"""
        expired_keys = [k for k, v in self.cache.items() if not v.is_valid()]
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

class SmartDataProvider:
    """Smart data provider with fallback strategies"""
    
    def __init__(self, cache_manager: APICacheManager):
        self.cache = cache_manager
        self.fallback_data = {}
        
    async def get_market_data(self, symbol: str, breeze_client=None, kite_client=None):
        """Get market data with multiple fallback options"""
        
        # Try Breeze first
        if breeze_client:
            try:
                data = await self.cache.call_with_cache(
                    lambda: breeze_client.get_quotes(stock_code=symbol, exchange_code="NSE"),
                    'breeze_quotes',
                    {'symbol': symbol},
                    'market_data'
                )
                if data and data.get('Success'):
                    return self._parse_breeze_data(data)
            except Exception as e:
                logger.warning(f"Breeze failed: {e}")
                
        # Try Kite as fallback
        if kite_client:
            try:
                data = await self.cache.call_with_cache(
                    lambda: kite_client.ltp(f"NSE:{symbol}"),
                    'kite_ltp',
                    {'symbol': symbol},
                    'market_data'
                )
                if data:
                    return self._parse_kite_data(data)
            except Exception as e:
                logger.warning(f"Kite failed: {e}")
                
        # Use last known good data
        if symbol in self.fallback_data:
            logger.info(f"Using fallback data for {symbol}")
            return self.fallback_data[symbol]
            
        # No data available - return error
        logger.error(f"No data available for {symbol}. Please connect to broker API.")
        raise Exception(f"No market data available for {symbol}. Broker APIs not connected.")
        
    def _parse_breeze_data(self, data: Dict) -> Dict:
        """Parse Breeze API response"""
        quote = data['Success'][0]
        parsed = {
            'symbol': quote['stock_code'],
            'ltp': float(quote['ltp']),
            'open': float(quote['open']),
            'high': float(quote['high']),
            'low': float(quote['low']),
            'close': float(quote['previous_close']),
            'timestamp': datetime.now().isoformat()
        }
        
        # Store as fallback
        self.fallback_data[quote['stock_code']] = parsed
        return parsed
        
    def _parse_kite_data(self, data: Dict) -> Dict:
        """Parse Kite API response"""
        symbol = list(data.keys())[0]
        quote = data[symbol]
        
        parsed = {
            'symbol': symbol.split(':')[1],
            'ltp': quote['last_price'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Store as fallback
        self.fallback_data[parsed['symbol']] = parsed
        return parsed
        

def cache_api_call(cache_type: str = 'default'):
    """Decorator for caching API calls"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get or create cache manager
            if not hasattr(wrapper, 'cache_manager'):
                wrapper.cache_manager = APICacheManager()
                
            # Generate cache key from function name and arguments
            api_name = func.__name__
            params = {'args': args, 'kwargs': kwargs}
            
            # Try to get from cache
            cached = wrapper.cache_manager.get(api_name, params, cache_type)
            if cached is not None:
                return cached
                
            # Call function and cache result
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            if result:
                wrapper.cache_manager.set(api_name, params, result, cache_type)
                
            return result
            
        return wrapper
    return decorator

# Singleton instance
_cache_manager = None

def get_cache_manager() -> APICacheManager:
    """Get or create cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = APICacheManager()
        
        # Start cleanup task
        async def cleanup_task():
            while True:
                await asyncio.sleep(300)  # Every 5 minutes
                _cache_manager.cleanup_expired()
                
        try:
            asyncio.create_task(cleanup_task())
        except:
            pass  # Ignore if no event loop
            
    return _cache_manager