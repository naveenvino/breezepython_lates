"""
JWT Authentication Service
Handles user authentication, token generation, and validation
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import secrets
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Security Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Token(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Token payload data"""
    username: Optional[str] = None
    user_id: Optional[str] = None
    scopes: list = []

class User(BaseModel):
    """User model"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    roles: list = []
    created_at: Optional[datetime] = None

class UserInDB(User):
    """User model with hashed password"""
    hashed_password: str

class LoginRequest(BaseModel):
    """Login request model"""
    username: str
    password: str

class RegisterRequest(BaseModel):
    """Registration request model"""
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None

class AuthService:
    """Authentication service for managing users and tokens"""
    
    def __init__(self, users_file: Optional[str] = None):
        self.users_file = users_file or "users.json"
        self.users_db = self._load_users()
        
        # Create default admin user if no users exist
        if not self.users_db:
            self._create_default_admin()
            
    def _load_users(self) -> Dict[str, Dict]:
        """Load users from JSON file"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading users: {e}")
        return {}
        
    def _save_users(self):
        """Save users to JSON file"""
        try:
            with open(self.users_file, 'w') as f:
                json.dump(self.users_db, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
            
    def _create_default_admin(self):
        """Create default admin user"""
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        admin_user = {
            "username": "admin",
            "email": "admin@tradingsystem.local",
            "full_name": "System Administrator",
            "hashed_password": self.get_password_hash(admin_password),
            "disabled": False,
            "roles": ["admin", "trader"],
            "created_at": datetime.now().isoformat()
        }
        self.users_db["admin"] = admin_user
        self._save_users()
        logger.info("Default admin user created")
        
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
        
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
        
    def get_user(self, username: str) -> Optional[UserInDB]:
        """Get user by username"""
        if username in self.users_db:
            user_dict = self.users_db[username]
            return UserInDB(**user_dict)
        return None
        
    def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """Authenticate user with username and password"""
        user = self.get_user(username)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        if user.disabled:
            return None
        return user
        
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
        
    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
        
    def verify_token(self, token: str, token_type: str = "access") -> Optional[TokenData]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            # Check token type
            if payload.get("type") != token_type:
                return None
                
            username: str = payload.get("sub")
            user_id: str = payload.get("user_id")
            scopes: list = payload.get("scopes", [])
            
            if username is None:
                return None
                
            return TokenData(username=username, user_id=user_id, scopes=scopes)
            
        except JWTError as e:
            logger.error(f"Token verification failed: {e}")
            return None
            
    def register_user(self, register_data: RegisterRequest) -> Optional[User]:
        """Register a new user"""
        # Check if user already exists
        if register_data.username in self.users_db:
            return None
            
        # Create new user
        user_dict = {
            "username": register_data.username,
            "email": register_data.email,
            "full_name": register_data.full_name,
            "hashed_password": self.get_password_hash(register_data.password),
            "disabled": False,
            "roles": ["trader"],  # Default role
            "created_at": datetime.now().isoformat()
        }
        
        self.users_db[register_data.username] = user_dict
        self._save_users()
        
        return User(**user_dict)
        
    def update_user_password(self, username: str, new_password: str) -> bool:
        """Update user password"""
        if username not in self.users_db:
            return False
            
        self.users_db[username]["hashed_password"] = self.get_password_hash(new_password)
        self._save_users()
        return True
        
    def disable_user(self, username: str) -> bool:
        """Disable a user account"""
        if username not in self.users_db:
            return False
            
        self.users_db[username]["disabled"] = True
        self._save_users()
        return True
        
    def enable_user(self, username: str) -> bool:
        """Enable a user account"""
        if username not in self.users_db:
            return False
            
        self.users_db[username]["disabled"] = False
        self._save_users()
        return True
        
    def add_user_role(self, username: str, role: str) -> bool:
        """Add role to user"""
        if username not in self.users_db:
            return False
            
        roles = self.users_db[username].get("roles", [])
        if role not in roles:
            roles.append(role)
            self.users_db[username]["roles"] = roles
            self._save_users()
        return True
        
    def remove_user_role(self, username: str, role: str) -> bool:
        """Remove role from user"""
        if username not in self.users_db:
            return False
            
        roles = self.users_db[username].get("roles", [])
        if role in roles:
            roles.remove(role)
            self.users_db[username]["roles"] = roles
            self._save_users()
        return True
        
    def has_permission(self, username: str, required_role: str) -> bool:
        """Check if user has required role"""
        user = self.get_user(username)
        if not user:
            return False
            
        # Admin has all permissions
        if "admin" in user.roles:
            return True
            
        return required_role in user.roles
        
    def list_users(self) -> list:
        """List all users (without passwords)"""
        users = []
        for username, user_data in self.users_db.items():
            user_copy = user_data.copy()
            user_copy.pop("hashed_password", None)
            users.append(user_copy)
        return users
        
    def generate_api_key(self, username: str) -> str:
        """Generate API key for user"""
        # Create a long-lived token for API access
        data = {
            "sub": username,
            "type": "api_key",
            "created": datetime.now().isoformat()
        }
        
        # API keys don't expire (or have very long expiry)
        expire = datetime.utcnow() + timedelta(days=365)
        data["exp"] = expire
        
        api_key = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
        
        # Store API key reference
        if username in self.users_db:
            if "api_keys" not in self.users_db[username]:
                self.users_db[username]["api_keys"] = []
            
            self.users_db[username]["api_keys"].append({
                "key_id": api_key[-8:],  # Last 8 chars as ID
                "created": datetime.now().isoformat(),
                "active": True
            })
            self._save_users()
            
        return api_key
        
    def revoke_api_key(self, username: str, key_id: str) -> bool:
        """Revoke an API key"""
        if username not in self.users_db:
            return False
            
        api_keys = self.users_db[username].get("api_keys", [])
        for key in api_keys:
            if key["key_id"] == key_id:
                key["active"] = False
                self._save_users()
                return True
        return False

# Singleton instance
_auth_service = None

def get_auth_service() -> AuthService:
    """Get or create auth service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service