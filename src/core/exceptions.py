"""
Comprehensive exception handling system for trading application
"""
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high" 
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for better classification"""
    DATABASE = "database"
    API = "api"
    TRADING = "trading"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    BUSINESS_LOGIC = "business_logic"

class BaseAppException(Exception):
    """Base exception class for all application exceptions"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = None,
        category: ErrorCategory = ErrorCategory.API,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Dict[str, Any] = None,
        user_message: str = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.user_message = user_message or "An error occurred. Please try again."
        self.retry_after = retry_after
        self.timestamp = datetime.utcnow()
        
        # Log the exception
        log_level = {
            ErrorSeverity.LOW: logging.DEBUG,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }.get(severity, logging.ERROR)
        
        logger.log(log_level, f"[{self.error_code}] {message}", extra={
            "category": category.value,
            "severity": severity.value,
            "details": details,
            "error_code": self.error_code
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.user_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "retry_after": self.retry_after,
            "details": self.details if logger.level <= logging.DEBUG else {}
        }

# =============================================================================
# DATABASE EXCEPTIONS
# =============================================================================

class DatabaseException(BaseAppException):
    """Base database exception"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message, 
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            user_message="Database operation failed. Please try again.",
            **kwargs
        )

class DatabaseConnectionException(DatabaseException):
    """Database connection failure"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="DB_CONNECTION_FAILED",
            severity=ErrorSeverity.CRITICAL,
            user_message="Unable to connect to database. Please contact support.",
            retry_after=60,
            **kwargs
        )

class DatabaseTimeoutException(DatabaseException):
    """Database operation timeout"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="DB_TIMEOUT",
            user_message="Database operation timed out. Please try again.",
            retry_after=30,
            **kwargs
        )

class DataIntegrityException(DatabaseException):
    """Data integrity violation"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="DATA_INTEGRITY_ERROR",
            severity=ErrorSeverity.CRITICAL,
            user_message="Data integrity error. Please contact support.",
            **kwargs
        )

# =============================================================================
# TRADING EXCEPTIONS
# =============================================================================

class TradingException(BaseAppException):
    """Base trading exception"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.TRADING,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )

class OrderPlacementException(TradingException):
    """Order placement failure"""
    def __init__(self, message: str, order_details: Dict = None, **kwargs):
        super().__init__(
            message,
            error_code="ORDER_PLACEMENT_FAILED",
            severity=ErrorSeverity.CRITICAL,
            user_message="Failed to place order. Please check your positions.",
            details={"order_details": order_details} if order_details else {},
            **kwargs
        )

class PositionLimitExceededException(TradingException):
    """Position limit exceeded"""
    def __init__(self, message: str, current_positions: int, limit: int, **kwargs):
        super().__init__(
            message,
            error_code="POSITION_LIMIT_EXCEEDED",
            severity=ErrorSeverity.HIGH,
            user_message=f"Position limit exceeded. Current: {current_positions}, Limit: {limit}",
            details={"current_positions": current_positions, "limit": limit},
            **kwargs
        )

class RiskLimitException(TradingException):
    """Risk limit exceeded"""
    def __init__(self, message: str, risk_type: str, current_value: float, limit: float, **kwargs):
        super().__init__(
            message,
            error_code="RISK_LIMIT_EXCEEDED",
            severity=ErrorSeverity.CRITICAL,
            user_message=f"Risk limit exceeded for {risk_type}",
            details={
                "risk_type": risk_type,
                "current_value": current_value,
                "limit": limit
            },
            **kwargs
        )

class MarketClosedException(TradingException):
    """Market is closed"""
    def __init__(self, message: str = "Market is currently closed", **kwargs):
        super().__init__(
            message,
            error_code="MARKET_CLOSED",
            severity=ErrorSeverity.MEDIUM,
            user_message="Market is currently closed. Trading not available.",
            **kwargs
        )

class InsufficientFundsException(TradingException):
    """Insufficient funds for trade"""
    def __init__(self, message: str, required: float, available: float, **kwargs):
        super().__init__(
            message,
            error_code="INSUFFICIENT_FUNDS",
            severity=ErrorSeverity.HIGH,
            user_message="Insufficient funds for this trade",
            details={"required": required, "available": available},
            **kwargs
        )

# =============================================================================
# API EXCEPTIONS
# =============================================================================

class APIException(BaseAppException):
    """Base API exception"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.API,
            **kwargs
        )

class BrokerAPIException(APIException):
    """Broker API failure"""
    def __init__(self, message: str, broker: str, status_code: int = None, **kwargs):
        super().__init__(
            message,
            error_code="BROKER_API_ERROR",
            severity=ErrorSeverity.HIGH,
            user_message=f"{broker} API is currently unavailable. Please try again.",
            details={"broker": broker, "status_code": status_code},
            retry_after=30,
            **kwargs
        )

class RateLimitException(APIException):
    """Rate limit exceeded"""
    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(
            message,
            error_code="RATE_LIMIT_EXCEEDED",
            severity=ErrorSeverity.MEDIUM,
            user_message="Rate limit exceeded. Please wait before retrying.",
            retry_after=retry_after,
            **kwargs
        )

class AuthenticationException(BaseAppException):
    """Authentication failure"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="AUTHENTICATION_FAILED",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            user_message="Authentication failed. Please login again.",
            **kwargs
        )

class AuthorizationException(BaseAppException):
    """Authorization failure"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="AUTHORIZATION_FAILED",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            user_message="Access denied. Insufficient permissions.",
            **kwargs
        )

# =============================================================================
# VALIDATION EXCEPTIONS
# =============================================================================

class ValidationException(BaseAppException):
    """Input validation exception"""
    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            user_message="Invalid input provided. Please check your data.",
            details={"field": field, "value": str(value) if value else None},
            **kwargs
        )

class ConfigurationException(BaseAppException):
    """Configuration error"""
    def __init__(self, message: str, config_key: str = None, **kwargs):
        super().__init__(
            message,
            error_code="CONFIGURATION_ERROR",
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.CRITICAL,
            user_message="System configuration error. Please contact support.",
            details={"config_key": config_key} if config_key else {},
            **kwargs
        )

# =============================================================================
# NETWORK EXCEPTIONS
# =============================================================================

class NetworkException(BaseAppException):
    """Network-related exception"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            user_message="Network error occurred. Please check your connection.",
            retry_after=30,
            **kwargs
        )

class TimeoutException(NetworkException):
    """Request timeout exception"""
    def __init__(self, message: str, timeout_duration: int = None, **kwargs):
        super().__init__(
            message,
            error_code="REQUEST_TIMEOUT",
            user_message="Request timed out. Please try again.",
            details={"timeout_duration": timeout_duration} if timeout_duration else {},
            **kwargs
        )

# =============================================================================
# BUSINESS LOGIC EXCEPTIONS
# =============================================================================

class BusinessLogicException(BaseAppException):
    """Business logic violation"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )

class InvalidSignalException(BusinessLogicException):
    """Invalid trading signal"""
    def __init__(self, message: str, signal: str = None, **kwargs):
        super().__init__(
            message,
            error_code="INVALID_SIGNAL",
            user_message="Invalid trading signal received",
            details={"signal": signal} if signal else {},
            **kwargs
        )

class CircuitBreakerException(TradingException):
    """Circuit breaker triggered"""
    def __init__(self, message: str, breaker_name: str, **kwargs):
        super().__init__(
            message,
            error_code="CIRCUIT_BREAKER_TRIGGERED",
            severity=ErrorSeverity.CRITICAL,
            user_message="Trading suspended due to circuit breaker activation",
            details={"breaker_name": breaker_name},
            **kwargs
        )

# =============================================================================
# EXCEPTION HANDLER CLASS
# =============================================================================

class ExceptionHandler:
    """Centralized exception handling"""
    
    def __init__(self):
        self.error_counts = {}
        
    def handle_exception(self, exc: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle any exception and return standardized response"""
        
        # Count errors for monitoring
        exc_type = type(exc).__name__
        self.error_counts[exc_type] = self.error_counts.get(exc_type, 0) + 1
        
        # Handle our custom exceptions
        if isinstance(exc, BaseAppException):
            return exc.to_dict()
        
        # Handle common Python exceptions
        error_mappings = {
            ValueError: ("INVALID_VALUE", ErrorSeverity.LOW, "Invalid value provided"),
            KeyError: ("MISSING_KEY", ErrorSeverity.MEDIUM, "Required field missing"),
            TypeError: ("TYPE_ERROR", ErrorSeverity.MEDIUM, "Invalid data type"),
            ConnectionError: ("CONNECTION_ERROR", ErrorSeverity.HIGH, "Connection failed"),
            TimeoutError: ("TIMEOUT_ERROR", ErrorSeverity.MEDIUM, "Operation timed out"),
            PermissionError: ("PERMISSION_ERROR", ErrorSeverity.HIGH, "Permission denied"),
            FileNotFoundError: ("FILE_NOT_FOUND", ErrorSeverity.MEDIUM, "File not found")
        }
        
        exc_type = type(exc)
        if exc_type in error_mappings:
            error_code, severity, user_message = error_mappings[exc_type]
        else:
            error_code = "UNEXPECTED_ERROR"
            severity = ErrorSeverity.HIGH
            user_message = "An unexpected error occurred"
        
        # Log the unhandled exception
        logger.error(f"Unhandled exception: {exc}", exc_info=True, extra={
            "error_code": error_code,
            "context": context or {}
        })
        
        return {
            "error": True,
            "error_code": error_code,
            "message": user_message,
            "severity": severity.value,
            "timestamp": datetime.utcnow().isoformat(),
            "details": {"original_error": str(exc)} if logger.level <= logging.DEBUG else {}
        }
    
    def get_error_stats(self) -> Dict[str, int]:
        """Get error statistics for monitoring"""
        return self.error_counts.copy()

# Global exception handler instance
exception_handler = ExceptionHandler()