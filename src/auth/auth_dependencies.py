"""
Authentication Dependencies for FastAPI
Provides reusable dependencies for securing API endpoints
"""

from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from typing import Optional, List
from src.auth.auth_service import get_auth_service, TokenData, User
import logging

logger = logging.getLogger(__name__)

# Security schemes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
security_bearer = HTTPBearer()

class AuthenticationError(HTTPException):
    """Custom authentication exception"""
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

class AuthorizationError(HTTPException):
    """Custom authorization exception"""
    def __init__(self, detail: str = "Not enough permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

async def get_current_user_token(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Validate token and return token data"""
    auth_service = get_auth_service()
    
    token_data = auth_service.verify_token(token)
    if token_data is None:
        raise AuthenticationError()
        
    return token_data

async def get_current_user(token_data: TokenData = Depends(get_current_user_token)) -> User:
    """Get current user from token"""
    auth_service = get_auth_service()
    
    user = auth_service.get_user(username=token_data.username)
    if user is None:
        raise AuthenticationError()
        
    if user.disabled:
        raise AuthenticationError(detail="User account is disabled")
        
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure user is active"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(required_role: str):
    """Dependency to require specific role"""
    async def role_checker(current_user: User = Depends(get_current_active_user)):
        if "admin" in current_user.roles:
            return current_user  # Admin has all permissions
            
        if required_role not in current_user.roles:
            raise AuthorizationError(
                detail=f"User does not have required role: {required_role}"
            )
        return current_user
    return role_checker

def require_any_role(roles: List[str]):
    """Dependency to require any of the specified roles"""
    async def role_checker(current_user: User = Depends(get_current_active_user)):
        if "admin" in current_user.roles:
            return current_user  # Admin has all permissions
            
        if not any(role in current_user.roles for role in roles):
            raise AuthorizationError(
                detail=f"User does not have any of required roles: {roles}"
            )
        return current_user
    return role_checker

def require_all_roles(roles: List[str]):
    """Dependency to require all specified roles"""
    async def role_checker(current_user: User = Depends(get_current_active_user)):
        if "admin" in current_user.roles:
            return current_user  # Admin has all permissions
            
        if not all(role in current_user.roles for role in roles):
            missing_roles = [r for r in roles if r not in current_user.roles]
            raise AuthorizationError(
                detail=f"User missing required roles: {missing_roles}"
            )
        return current_user
    return role_checker

async def get_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Ensure user is admin"""
    if "admin" not in current_user.roles:
        raise AuthorizationError(detail="Admin access required")
    return current_user

async def get_trader_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Ensure user has trader role"""
    if "trader" not in current_user.roles and "admin" not in current_user.roles:
        raise AuthorizationError(detail="Trader access required")
    return current_user

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security_bearer)) -> TokenData:
    """Verify API key from Bearer token"""
    auth_service = get_auth_service()
    
    token = credentials.credentials
    token_data = auth_service.verify_token(token, token_type="api_key")
    
    if token_data is None:
        raise AuthenticationError(detail="Invalid API key")
        
    return token_data

async def get_optional_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[User]:
    """Get current user if token is provided, otherwise return None"""
    if not token:
        return None
        
    try:
        auth_service = get_auth_service()
        token_data = auth_service.verify_token(token)
        
        if token_data:
            user = auth_service.get_user(username=token_data.username)
            if user and not user.disabled:
                return user
    except Exception:
        pass
        
    return None

class RateLimitChecker:
    """Rate limiting dependency"""
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # Simple in-memory storage
        
    async def __call__(self, current_user: User = Depends(get_current_active_user)):
        """Check rate limit for user"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        username = current_user.username
        
        # Clean old requests
        if username in self.requests:
            cutoff = now - timedelta(seconds=self.window_seconds)
            self.requests[username] = [
                req_time for req_time in self.requests[username]
                if req_time > cutoff
            ]
        else:
            self.requests[username] = []
            
        # Check limit
        if len(self.requests[username]) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds} seconds"
            )
            
        # Record request
        self.requests[username].append(now)
        return current_user

# Create rate limiters with different limits
rate_limit_standard = RateLimitChecker(max_requests=100, window_seconds=60)
rate_limit_strict = RateLimitChecker(max_requests=10, window_seconds=60)
rate_limit_lenient = RateLimitChecker(max_requests=1000, window_seconds=60)