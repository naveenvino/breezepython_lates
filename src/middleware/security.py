from typing import Optional, List, Dict, Callable
from datetime import datetime, timedelta
import secrets
import hashlib
import hmac
import base64
from fastapi import Request, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from fastapi.responses import JSONResponse
import jwt
from passlib.context import CryptContext
from argon2 import PasswordHasher
import re
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    """Comprehensive security middleware for API protection"""
    
    def __init__(
        self,
        secret_key: str = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7,
        enable_csrf: bool = True,
        enable_api_key: bool = True,
        enable_jwt: bool = True,
        allowed_origins: List[str] = None,
        secure_headers: bool = True
    ):
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.enable_csrf = enable_csrf
        self.enable_api_key = enable_api_key
        self.enable_jwt = enable_jwt
        self.allowed_origins = allowed_origins or ["*"]
        self.secure_headers = secure_headers
        
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.argon2_hasher = PasswordHasher()
        self.bearer_scheme = HTTPBearer(auto_error=False)
        self.api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
        
        self.csrf_tokens = {}
        self.api_keys = {}
        self.revoked_tokens = set()
        
    def hash_password(self, password: str, use_argon2: bool = True) -> str:
        """Hash password using bcrypt or argon2"""
        if use_argon2:
            return self.argon2_hasher.hash(password)
        return self.pwd_context.hash(password)
        
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            if hashed_password.startswith("$argon2"):
                self.argon2_hasher.verify(hashed_password, plain_password)
                return True
            else:
                return self.pwd_context.verify(plain_password, hashed_password)
        except:
            return False
            
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
            
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
        
    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
        
    def verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token"""
        try:
            if token in self.revoked_tokens:
                return None
                
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
            
    def revoke_token(self, token: str):
        """Revoke a token"""
        self.revoked_tokens.add(token)
        
    def generate_csrf_token(self, session_id: str) -> str:
        """Generate CSRF token for session"""
        token = secrets.token_urlsafe(32)
        self.csrf_tokens[session_id] = token
        return token
        
    def verify_csrf_token(self, session_id: str, token: str) -> bool:
        """Verify CSRF token"""
        stored_token = self.csrf_tokens.get(session_id)
        if not stored_token:
            return False
        return hmac.compare_digest(stored_token, token)
        
    def generate_api_key(self, user_id: str, description: str = "") -> str:
        """Generate API key for user"""
        key = secrets.token_urlsafe(32)
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        
        self.api_keys[hashed_key] = {
            "user_id": user_id,
            "description": description,
            "created_at": datetime.utcnow(),
            "last_used": None,
            "is_active": True
        }
        
        return key
        
    def verify_api_key(self, api_key: str) -> Optional[dict]:
        """Verify API key"""
        hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
        key_data = self.api_keys.get(hashed_key)
        
        if key_data and key_data["is_active"]:
            key_data["last_used"] = datetime.utcnow()
            return key_data
            
        return None
        
    def validate_input(self, data: str, input_type: str = "general") -> bool:
        """Validate input to prevent injection attacks"""
        patterns = {
            "general": r"^[a-zA-Z0-9\s\-_.,!?@#$%^&*()+=\[\]{}|;:'\"/\\<>]*$",
            "alphanumeric": r"^[a-zA-Z0-9]+$",
            "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "phone": r"^[0-9\-\+\(\)\s]+$",
            "url": r"^https?://[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=]+$"
        }
        
        pattern = patterns.get(input_type, patterns["general"])
        return bool(re.match(pattern, data))
        
    def sanitize_input(self, data: str) -> str:
        """Sanitize input to remove potentially harmful content"""
        dangerous_patterns = [
            r"<script.*?>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe.*?>.*?</iframe>",
            r"--",
            r";",
            r"union\s+select",
            r"drop\s+table"
        ]
        
        sanitized = data
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
            
        return sanitized.strip()
        
    def add_security_headers(self, response):
        """Add security headers to response"""
        if self.secure_headers:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' https: data:;"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
            
        return response
        
    async def middleware(self, request: Request, call_next: Callable):
        """Security middleware for FastAPI"""
        if request.url.path in ["/docs", "/redoc", "/openapi.json", "/health"]:
            return await call_next(request)
            
        origin = request.headers.get("origin")
        if origin and self.allowed_origins != ["*"]:
            if origin not in self.allowed_origins:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Origin not allowed"}
                )
                
        if self.enable_csrf and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            csrf_token = request.headers.get("X-CSRF-Token")
            session_id = request.cookies.get("session_id")
            
            if session_id and not self.verify_csrf_token(session_id, csrf_token or ""):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed"}
                )
                
        if self.enable_api_key or self.enable_jwt:
            authenticated = False
            
            if self.enable_api_key:
                api_key = request.headers.get("X-API-Key")
                if api_key and self.verify_api_key(api_key):
                    authenticated = True
                    
            if not authenticated and self.enable_jwt:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                    if self.verify_token(token):
                        authenticated = True
                        
            public_paths = ["/auth/login", "/auth/register", "/api/v1/public"]
            is_public = any(request.url.path.startswith(path) for path in public_paths)
            
            if not authenticated and not is_public:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required"}
                )
                
        response = await call_next(request)
        
        return self.add_security_headers(response)


class IPWhitelist:
    """IP whitelist/blacklist middleware"""
    
    def __init__(
        self,
        whitelist: List[str] = None,
        blacklist: List[str] = None,
        allow_private: bool = True
    ):
        self.whitelist = set(whitelist or [])
        self.blacklist = set(blacklist or [])
        self.allow_private = allow_private
        
    def is_private_ip(self, ip: str) -> bool:
        """Check if IP is private"""
        private_ranges = [
            "10.",
            "172.16.", "172.17.", "172.18.", "172.19.",
            "172.20.", "172.21.", "172.22.", "172.23.",
            "172.24.", "172.25.", "172.26.", "172.27.",
            "172.28.", "172.29.", "172.30.", "172.31.",
            "192.168.",
            "127."
        ]
        
        return any(ip.startswith(range_) for range_ in private_ranges)
        
    async def middleware(self, request: Request, call_next: Callable):
        """IP filtering middleware"""
        client_ip = request.client.host if request.client else None
        
        if not client_ip:
            return JSONResponse(
                status_code=400,
                content={"detail": "Could not determine client IP"}
            )
            
        if client_ip in self.blacklist:
            return JSONResponse(
                status_code=403,
                content={"detail": "IP address blocked"}
            )
            
        if self.whitelist:
            if client_ip not in self.whitelist:
                if not (self.allow_private and self.is_private_ip(client_ip)):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "IP address not whitelisted"}
                    )
                    
        return await call_next(request)


def create_security_middleware(
    secret_key: Optional[str] = None,
    enable_csrf: bool = False,
    enable_api_key: bool = False,
    enable_jwt: bool = False,
    secure_headers: bool = True
) -> SecurityMiddleware:
    """Create configured security middleware"""
    import os
    
    secret_key = secret_key or os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    
    return SecurityMiddleware(
        secret_key=secret_key,
        enable_csrf=enable_csrf,
        enable_api_key=enable_api_key,
        enable_jwt=enable_jwt,
        secure_headers=secure_headers
    )