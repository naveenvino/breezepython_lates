from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
import time
import hashlib
import logging
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import redis
import json

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Production-grade rate limiting middleware with multi-tier protection
    Implements token bucket algorithm with Redis support for distributed systems
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
        use_redis: bool = False,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        self.use_redis = use_redis
        
        if use_redis:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True
                )
                self.redis_client.ping()
            except:
                print("Redis not available, falling back to in-memory rate limiting")
                self.use_redis = False
                self.buckets = defaultdict(lambda: TokenBucket(requests_per_minute, burst_size))
        else:
            self.buckets = defaultdict(lambda: TokenBucket(requests_per_minute, burst_size))
            
        self.hour_counters = defaultdict(lambda: deque())
        
    def get_client_id(self, request: Request) -> str:
        """Get unique client identifier from request"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
            
        api_key = request.headers.get("X-API-Key", "")
        user_agent = request.headers.get("User-Agent", "")
        
        client_string = f"{client_ip}:{api_key}:{user_agent}"
        return hashlib.md5(client_string.encode()).hexdigest()
        
    async def check_rate_limit(self, request: Request) -> bool:
        """Check if request should be rate limited"""
        client_id = self.get_client_id(request)
        now = time.time()
        
        if self.use_redis:
            return await self._check_redis_rate_limit(client_id, now)
        else:
            return self._check_memory_rate_limit(client_id, now)
    
    def check_request(self, ip_address: str) -> tuple[bool, Optional[int]]:
        """Check if request from IP address is allowed"""
        return self.check_rate_limit_by_ip(ip_address)
    
    def check_rate_limit_by_ip(self, ip_address: str) -> tuple[bool, Optional[int]]:
        """Check rate limit for IP address"""
        bucket = self.buckets[ip_address]
        if bucket.consume(1):
            return True, None
        else:
            return False, 60  # Retry after 1 minute
            
    def _check_memory_rate_limit(self, client_id: str, now: float) -> bool:
        """Check rate limit using in-memory storage"""
        bucket = self.buckets[client_id]
        
        if not bucket.consume(1):
            return False
            
        hour_counter = self.hour_counters[client_id]
        hour_ago = now - 3600
        
        while hour_counter and hour_counter[0] < hour_ago:
            hour_counter.popleft()
            
        hour_counter.append(now)
        
        if len(hour_counter) > self.requests_per_hour:
            return False
            
        return True
        
    async def _check_redis_rate_limit(self, client_id: str, now: float) -> bool:
        """Check rate limit using Redis"""
        try:
            minute_key = f"rate_limit:minute:{client_id}"
            hour_key = f"rate_limit:hour:{client_id}"
            
            pipe = self.redis_client.pipeline()
            
            pipe.incr(minute_key)
            pipe.expire(minute_key, 60)
            minute_count = pipe.execute()[0]
            
            if minute_count > self.requests_per_minute:
                return False
                
            pipe = self.redis_client.pipeline()
            pipe.incr(hour_key)
            pipe.expire(hour_key, 3600)
            hour_count = pipe.execute()[0]
            
            if hour_count > self.requests_per_hour:
                return False
                
            return True
        except:
            return self._check_memory_rate_limit(client_id, now)
            
    def get_rate_limit_headers(self, client_id: str) -> Dict[str, str]:
        """Get rate limit headers for response"""
        if self.use_redis:
            try:
                minute_key = f"rate_limit:minute:{client_id}"
                hour_key = f"rate_limit:hour:{client_id}"
                
                minute_count = int(self.redis_client.get(minute_key) or 0)
                hour_count = int(self.redis_client.get(hour_key) or 0)
                
                return {
                    "X-RateLimit-Limit-Minute": str(self.requests_per_minute),
                    "X-RateLimit-Remaining-Minute": str(max(0, self.requests_per_minute - minute_count)),
                    "X-RateLimit-Limit-Hour": str(self.requests_per_hour),
                    "X-RateLimit-Remaining-Hour": str(max(0, self.requests_per_hour - hour_count))
                }
            except:
                pass
                
        bucket = self.buckets.get(client_id)
        if bucket:
            return {
                "X-RateLimit-Limit-Minute": str(self.requests_per_minute),
                "X-RateLimit-Remaining-Minute": str(int(bucket.tokens)),
                "X-RateLimit-Limit-Hour": str(self.requests_per_hour)
            }
        return {}


class TokenBucket:
    """Token bucket implementation for rate limiting"""
    
    def __init__(self, rate: float, capacity: float):
        self.rate = rate / 60.0
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        
    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens from the bucket"""
        now = time.time()
        elapsed = now - self.last_update
        
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class EndpointRateLimiter:
    """Rate limiter with per-endpoint configuration"""
    
    def __init__(self):
        self.endpoint_limits = {}
        self.default_limiter = RateLimiter()
        
    def configure_endpoint(
        self,
        path: str,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10
    ):
        """Configure rate limit for specific endpoint"""
        self.endpoint_limits[path] = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            burst_size=burst_size
        )
        
    def get_limiter(self, path: str) -> RateLimiter:
        """Get rate limiter for endpoint"""
        for endpoint_path, limiter in self.endpoint_limits.items():
            if path.startswith(endpoint_path):
                return limiter
        return self.default_limiter
        
    async def middleware(self, request: Request, call_next: Callable):
        """FastAPI middleware for rate limiting"""
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
            
        limiter = self.get_limiter(request.url.path)
        
        if not await limiter.check_rate_limit(request):
            client_id = limiter.get_client_id(request)
            headers = limiter.get_rate_limit_headers(client_id)
            
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers=headers
            )
            
        response = await call_next(request)
        
        client_id = limiter.get_client_id(request)
        headers = limiter.get_rate_limit_headers(client_id)
        for key, value in headers.items():
            response.headers[key] = value
            
        return response


def create_rate_limiter_middleware(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_size: int = 10,
    endpoint_configs: Optional[Dict[str, Dict]] = None
) -> EndpointRateLimiter:
    """Create configured rate limiter middleware"""
    limiter = EndpointRateLimiter()
    
    limiter.default_limiter = RateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        burst_size=burst_size
    )
    
    if endpoint_configs:
        for path, config in endpoint_configs.items():
            limiter.configure_endpoint(path, **config)
            
    critical_endpoints = {
        "/api/v1/broker/order": {
            "requests_per_minute": 30,
            "requests_per_hour": 500,
            "burst_size": 5
        },
        "/live/execute-signal": {
            "requests_per_minute": 20,
            "requests_per_hour": 300,
            "burst_size": 3
        },
        "/backtest": {
            "requests_per_minute": 10,
            "requests_per_hour": 100,
            "burst_size": 2
        }
    }
    
    for path, config in critical_endpoints.items():
        limiter.configure_endpoint(path, **config)
        
    return limiter