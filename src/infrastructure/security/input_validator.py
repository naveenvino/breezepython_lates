"""
Input validation and SQL injection prevention
"""

import re
import html
import logging
from typing import Any, List, Dict, Optional, Union
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, validator, Field, ValidationError
from enum import Enum

logger = logging.getLogger(__name__)

# SQL injection patterns to detect
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|CREATE|ALTER)\b)",  # SQL keywords
    r"(--|#|\/\*|\*\/)",  # SQL comments
    r"(\bOR\b\s*\d+\s*=\s*\d+)",  # OR 1=1 patterns
    r"(;|\||&&)",  # Command separators
    r"(xp_|sp_)",  # SQL Server system procedures
    r"(EXEC(\s|\()|EXECUTE(\s|\())",  # Execute statements
    r"(<script|javascript:|onerror=)",  # XSS patterns
]

class SecurityValidator:
    """Security validator for input sanitization"""
    
    @staticmethod
    def is_safe_string(value: str, max_length: int = 1000, allow_special: bool = False) -> bool:
        """Check if string is safe from injection attacks"""
        if not value or len(value) > max_length:
            return False
        
        # Check for SQL injection patterns
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {value[:50]}...")
                return False
        
        # Additional checks for special characters if not allowed
        if not allow_special:
            if re.search(r"[<>&\"']", value):
                return False
        
        return True
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """Sanitize string for safe use"""
        if not value:
            return ""
        
        # HTML escape
        value = html.escape(value)
        
        # Remove any null bytes
        value = value.replace('\x00', '')
        
        # Limit length
        return value[:1000]
    
    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """Validate filename safety"""
        if not filename:
            return False
        
        # Check for path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            return False
        
        # Check for valid filename pattern
        if not re.match(r"^[\w\-. ]+$", filename):
            return False
        
        # Check for dangerous extensions
        dangerous_extensions = ['.exe', '.dll', '.bat', '.cmd', '.sh', '.ps1']
        for ext in dangerous_extensions:
            if filename.lower().endswith(ext):
                return False
        
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_date(date_str: str) -> bool:
        """Validate date string"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

# Pydantic models for request validation

class SignalType(str, Enum):
    """Valid signal types"""
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    S5 = "S5"
    S6 = "S6"
    S7 = "S7"
    S8 = "S8"

class SecureBacktestRequest(BaseModel):
    """Secure backtest request with validation"""
    from_date: date = Field(..., description="Start date for backtest")
    to_date: date = Field(..., description="End date for backtest")
    signals_to_test: List[SignalType] = Field(..., min_items=1, max_items=8)
    initial_capital: Optional[float] = Field(500000, ge=10000, le=10000000)
    position_size: Optional[int] = Field(10, ge=1, le=100)
    stop_loss_points: Optional[float] = Field(None, ge=10, le=500)
    
    @validator('from_date', 'to_date')
    def validate_dates(cls, v):
        """Ensure dates are reasonable"""
        if v < date(2020, 1, 1) or v > date(2030, 12, 31):
            raise ValueError("Date must be between 2020 and 2030")
        return v
    
    @validator('to_date')
    def validate_date_range(cls, v, values):
        """Ensure to_date is after from_date"""
        if 'from_date' in values and v <= values['from_date']:
            raise ValueError("to_date must be after from_date")
        
        # Limit backtest period to 1 year
        if 'from_date' in values:
            delta = v - values['from_date']
            if delta.days > 365:
                raise ValueError("Backtest period cannot exceed 365 days")
        
        return v

class SecureOrderRequest(BaseModel):
    """Secure order placement request"""
    symbol: str = Field(..., min_length=1, max_length=50)
    quantity: int = Field(..., ge=1, le=10000)
    order_type: str = Field(..., pattern="^(BUY|SELL)$")
    price: Optional[float] = Field(None, ge=0, le=1000000)
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate trading symbol"""
        if not re.match(r"^[A-Z0-9\-]+$", v):
            raise ValueError("Invalid symbol format")
        
        # Check against SQL injection
        if not SecurityValidator.is_safe_string(v):
            raise ValueError("Invalid symbol")
        
        return v

class SecureDataRequest(BaseModel):
    """Secure data fetch request"""
    start_date: date
    end_date: date
    symbol: Optional[str] = Field("NIFTY", max_length=20)
    interval: Optional[str] = Field("5min", pattern="^(1min|5min|15min|1hour|1day)$")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate symbol safety"""
        if v and not SecurityValidator.is_safe_string(v):
            raise ValueError("Invalid symbol")
        return v

class SecureLoginRequest(BaseModel):
    """Secure login request"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username"""
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username can only contain alphanumeric characters and underscores")
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """Basic password validation (actual hashing done elsewhere)"""
        # Don't log passwords!
        if len(v) < 8:
            raise ValueError("Password too short")
        return v

def validate_request_params(params: Dict[str, Any], allowed_params: List[str]) -> Dict[str, Any]:
    """Validate and sanitize request parameters"""
    validated = {}
    
    for key, value in params.items():
        # Only allow expected parameters
        if key not in allowed_params:
            logger.warning(f"Unexpected parameter received: {key}")
            continue
        
        # Sanitize based on type
        if isinstance(value, str):
            if not SecurityValidator.is_safe_string(value):
                raise ValueError(f"Invalid value for parameter {key}")
            validated[key] = SecurityValidator.sanitize_string(value)
        elif isinstance(value, (int, float)):
            # Ensure numbers are within reasonable ranges
            if abs(value) > 1e10:
                raise ValueError(f"Value out of range for parameter {key}")
            validated[key] = value
        elif isinstance(value, list):
            # Validate list items
            validated_list = []
            for item in value[:100]:  # Limit list size
                if isinstance(item, str):
                    if SecurityValidator.is_safe_string(item):
                        validated_list.append(SecurityValidator.sanitize_string(item))
            validated[key] = validated_list
        else:
            validated[key] = value
    
    return validated

def create_safe_sql_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create safe parameters for SQL queries"""
    safe_params = {}
    
    for key, value in params.items():
        if isinstance(value, str):
            # Escape special SQL characters
            value = value.replace("'", "''")
            value = value.replace("%", "\\%")
            value = value.replace("_", "\\_")
            safe_params[key] = value
        else:
            safe_params[key] = value
    
    return safe_params

# Middleware for automatic validation
class ValidationMiddleware:
    """Middleware for automatic request validation"""
    
    @staticmethod
    async def validate_json_request(request_body: dict, model: BaseModel):
        """Validate JSON request against Pydantic model"""
        try:
            validated = model(**request_body)
            return validated.dict()
        except ValidationError as e:
            logger.warning(f"Request validation failed: {e}")
            raise ValueError(f"Invalid request: {e.errors()}")
    
    @staticmethod
    def validate_query_params(query_params: dict, allowed: List[str]):
        """Validate query parameters"""
        return validate_request_params(query_params, allowed)