"""
Universal Error Handler and Response Format
Implements consistent error responses across the API
"""

from typing import Dict, Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import uuid
import logging
import traceback
from enum import Enum

logger = logging.getLogger(__name__)

class ErrorCode(Enum):
    """Standard error codes for the trading system"""
    # Authentication & Session Errors (401-403)
    BREEZE_SESSION_EXPIRED = "BREEZE_SESSION_EXPIRED"
    KITE_SESSION_EXPIRED = "KITE_SESSION_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    
    # Client Errors (400-499)
    INVALID_REQUEST = "INVALID_REQUEST"
    MISSING_PARAMETERS = "MISSING_PARAMETERS"
    INVALID_SIGNAL = "INVALID_SIGNAL"
    INVALID_STRIKE = "INVALID_STRIKE"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    
    # Trading Errors (450-459)
    ORDER_PLACEMENT_FAILED = "ORDER_PLACEMENT_FAILED"
    ORDER_MODIFICATION_FAILED = "ORDER_MODIFICATION_FAILED"
    ORDER_CANCELLATION_FAILED = "ORDER_CANCELLATION_FAILED"
    INSUFFICIENT_MARGIN = "INSUFFICIENT_MARGIN"
    POSITION_NOT_FOUND = "POSITION_NOT_FOUND"
    
    # Data Errors (460-469)
    DATA_NOT_AVAILABLE = "DATA_NOT_AVAILABLE"
    OPTION_CHAIN_UNAVAILABLE = "OPTION_CHAIN_UNAVAILABLE"
    MARKET_DATA_ERROR = "MARKET_DATA_ERROR"
    HISTORICAL_DATA_ERROR = "HISTORICAL_DATA_ERROR"
    
    # System Errors (500-599)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    BROKER_CONNECTION_ERROR = "BROKER_CONNECTION_ERROR"
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
    
    # Circuit Breaker & Risk (550-559)
    KILL_SWITCH_TRIGGERED = "KILL_SWITCH_TRIGGERED"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    RISK_LIMIT_EXCEEDED = "RISK_LIMIT_EXCEEDED"
    MAX_LOSS_EXCEEDED = "MAX_LOSS_EXCEEDED"

class TradingException(Exception):
    """Base exception for trading system"""
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        user_action: Optional[str] = None
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.user_action = user_action
        super().__init__(message)

def create_error_response(
    error_code: ErrorCode,
    message: str,
    status_code: int = 500,
    details: Optional[Dict[str, Any]] = None,
    user_action: Optional[str] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """Create a standardized error response"""
    
    response_body = {
        "error_code": error_code.value,
        "message": message,
        "details": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": request_id or str(uuid.uuid4()),
            **(details or {})
        }
    }
    
    if user_action:
        response_body["user_action"] = user_action
    
    # Log error for monitoring
    logger.error(f"Error Response: {error_code.value} - {message}", extra={
        "error_code": error_code.value,
        "status_code": status_code,
        "request_id": response_body["details"]["request_id"]
    })
    
    return JSONResponse(
        status_code=status_code,
        content=response_body
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for the FastAPI application"""
    
    # Generate request ID if not present
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    # Handle TradingException
    if isinstance(exc, TradingException):
        return create_error_response(
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            user_action=exc.user_action,
            request_id=request_id
        )
    
    # Handle HTTPException
    if isinstance(exc, HTTPException):
        # Map status codes to error codes
        error_code = ErrorCode.INTERNAL_ERROR
        if exc.status_code == 401:
            error_code = ErrorCode.UNAUTHORIZED_ACCESS
        elif exc.status_code == 400:
            error_code = ErrorCode.INVALID_REQUEST
        elif exc.status_code == 404:
            error_code = ErrorCode.DATA_NOT_AVAILABLE
        
        return create_error_response(
            error_code=error_code,
            message=str(exc.detail),
            status_code=exc.status_code,
            request_id=request_id
        )
    
    # Handle database errors
    if "database" in str(exc).lower() or "sql" in str(exc).lower():
        return create_error_response(
            error_code=ErrorCode.DATABASE_ERROR,
            message="Database operation failed",
            status_code=503,
            details={"error_type": type(exc).__name__},
            user_action="Please try again later or contact support",
            request_id=request_id
        )
    
    # Handle broker connection errors
    if "breeze" in str(exc).lower():
        return create_error_response(
            error_code=ErrorCode.BREEZE_SESSION_EXPIRED,
            message="Breeze connection error",
            status_code=503,
            user_action="Please check your Breeze session and re-authenticate if needed",
            request_id=request_id
        )
    
    if "kite" in str(exc).lower():
        return create_error_response(
            error_code=ErrorCode.KITE_SESSION_EXPIRED,
            message="Kite connection error",
            status_code=503,
            user_action="Please check your Kite session and re-authenticate if needed",
            request_id=request_id
        )
    
    # Generic internal error (never expose stack trace in production)
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True, extra={
        "request_id": request_id,
        "traceback": traceback.format_exc() if logger.level <= logging.DEBUG else None
    })
    
    return create_error_response(
        error_code=ErrorCode.INTERNAL_ERROR,
        message="An unexpected error occurred",
        status_code=500,
        details={"error_type": type(exc).__name__},
        user_action="Please try again later or contact support",
        request_id=request_id
    )

# Utility functions for common errors
def raise_session_expired(broker: str = "Breeze"):
    """Raise session expired error"""
    if broker.lower() == "breeze":
        raise TradingException(
            error_code=ErrorCode.BREEZE_SESSION_EXPIRED,
            message="Breeze session has expired",
            status_code=401,
            user_action="Please refresh your Breeze session token in settings"
        )
    else:
        raise TradingException(
            error_code=ErrorCode.KITE_SESSION_EXPIRED,
            message="Kite session has expired",
            status_code=401,
            user_action="Please re-authenticate with Kite Connect"
        )

def raise_data_not_available(data_type: str = "option chain"):
    """Raise data not available error"""
    raise TradingException(
        error_code=ErrorCode.DATA_NOT_AVAILABLE,
        message=f"{data_type} data is not available",
        status_code=404,
        details={"data_type": data_type},
        user_action="Please check if market is open and try again"
    )

def raise_order_failed(reason: str, order_details: Optional[Dict] = None):
    """Raise order placement failed error"""
    raise TradingException(
        error_code=ErrorCode.ORDER_PLACEMENT_FAILED,
        message=f"Order placement failed: {reason}",
        status_code=400,
        details={"order": order_details} if order_details else {},
        user_action="Please check order parameters and margin requirements"
    )

def raise_kill_switch_triggered(reason: str):
    """Raise kill switch triggered error"""
    raise TradingException(
        error_code=ErrorCode.KILL_SWITCH_TRIGGERED,
        message=f"Trading halted: {reason}",
        status_code=503,
        user_action="Manual intervention required. Check system status and reset kill switch if safe"
    )