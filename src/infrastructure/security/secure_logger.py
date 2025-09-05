"""
Secure logging implementation that filters sensitive information
"""

import logging
import re
import json
from typing import Any, Dict, List, Union
from functools import wraps
import traceback

# Patterns to detect sensitive information
SENSITIVE_PATTERNS = {
    'password': r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^"\'\s,;}]+)',
    'api_key': r'(?i)(api[_-]?key|apikey|api_secret|secret)\s*[:=]\s*["\']?([A-Za-z0-9+/=\-_]{20,})',
    'token': r'(?i)(token|access_token|auth_token|bearer)\s*[:=]\s*["\']?([A-Za-z0-9+/=\-_\.]{20,})',
    'session': r'(?i)(session[_-]?id|sessionid|session_token)\s*[:=]\s*["\']?([A-Za-z0-9+/=\-_]{20,})',
    'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'jwt': r'eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+',
    'sql_server': r'(?i)server\s*=\s*[^;]+',
    'connection_string': r'(?i)(data source|server|user id|password|initial catalog)\s*=\s*[^;]+',
}

# Headers to filter in HTTP requests
SENSITIVE_HEADERS = [
    'authorization',
    'x-api-key',
    'x-auth-token',
    'cookie',
    'set-cookie',
    'x-csrf-token',
    'x-forwarded-for',
    'x-real-ip'
]

class SecureFormatter(logging.Formatter):
    """Custom formatter that sanitizes sensitive data"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redaction_text = "[REDACTED]"
    
    def format(self, record):
        """Format log record with sensitive data redaction"""
        # Format the basic message
        formatted = super().format(record)
        
        # Redact sensitive information
        formatted = self._redact_sensitive_data(formatted)
        
        return formatted
    
    def _redact_sensitive_data(self, text: str) -> str:
        """Redact sensitive data from text"""
        if not text:
            return text
        
        # Apply each sensitive pattern
        for pattern_name, pattern in SENSITIVE_PATTERNS.items():
            if pattern_name in ['email']:
                # For emails, partially redact
                text = re.sub(pattern, lambda m: self._partial_redact_email(m.group()), text)
            else:
                # Full redaction for other sensitive data
                text = re.sub(pattern, lambda m: self._create_redaction(m.group(), pattern_name), text, flags=re.IGNORECASE)
        
        return text
    
    def _create_redaction(self, match: str, data_type: str) -> str:
        """Create a redaction placeholder"""
        # Keep the key/label but redact the value
        if '=' in match or ':' in match:
            separator = '=' if '=' in match else ':'
            parts = match.split(separator, 1)
            if len(parts) == 2:
                return f"{parts[0]}{separator}[{data_type.upper()}_REDACTED]"
        
        return f"[{data_type.upper()}_REDACTED]"
    
    def _partial_redact_email(self, email: str) -> str:
        """Partially redact email address"""
        if '@' in email:
            parts = email.split('@')
            username = parts[0]
            if len(username) > 2:
                username = username[0] + '*' * (len(username) - 2) + username[-1]
            else:
                username = '*' * len(username)
            return f"{username}@{parts[1]}"
        return email

class SecureLogger:
    """Secure logger that filters sensitive information"""
    
    def __init__(self, name: str, level=logging.INFO):
        """Initialize secure logger"""
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Create secure handler with formatting
        handler = logging.StreamHandler()
        formatter = SecureFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize dictionary by removing sensitive keys"""
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        sensitive_keys = ['password', 'token', 'secret', 'api_key', 'access_token', 
                         'session', 'cookie', 'authorization', 'pwd', 'passwd']
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive words
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def log_request(self, method: str, path: str, headers: dict = None, body: Any = None):
        """Log HTTP request with sensitive data filtered"""
        safe_headers = {}
        if headers:
            for key, value in headers.items():
                if key.lower() in SENSITIVE_HEADERS:
                    safe_headers[key] = "[REDACTED]"
                else:
                    safe_headers[key] = value
        
        safe_body = None
        if body:
            if isinstance(body, dict):
                safe_body = self._sanitize_dict(body)
            elif isinstance(body, str):
                # Try to parse as JSON
                try:
                    parsed = json.loads(body)
                    safe_body = json.dumps(self._sanitize_dict(parsed))
                except:
                    safe_body = self._redact_from_string(body)
            else:
                safe_body = str(body)
        
        self.logger.info(f"Request: {method} {path}")
        if safe_headers:
            self.logger.debug(f"Headers: {safe_headers}")
        if safe_body:
            self.logger.debug(f"Body: {safe_body}")
    
    def log_response(self, status_code: int, body: Any = None, duration_ms: float = None):
        """Log HTTP response with sensitive data filtered"""
        message = f"Response: {status_code}"
        if duration_ms:
            message += f" ({duration_ms:.2f}ms)"
        
        self.logger.info(message)
        
        if body and self.logger.isEnabledFor(logging.DEBUG):
            safe_body = None
            if isinstance(body, dict):
                safe_body = self._sanitize_dict(body)
            elif isinstance(body, str):
                safe_body = self._redact_from_string(body)
            else:
                safe_body = str(body)
            
            self.logger.debug(f"Response body: {safe_body}")
    
    def log_error(self, error: Exception, context: str = None):
        """Log error without exposing sensitive details"""
        error_type = type(error).__name__
        
        # Create safe error message
        safe_message = str(error)
        safe_message = self._redact_from_string(safe_message)
        
        if context:
            self.logger.error(f"Error in {context}: {error_type} - {safe_message}")
        else:
            self.logger.error(f"Error: {error_type} - {safe_message}")
        
        # Log traceback at debug level with sanitization
        if self.logger.isEnabledFor(logging.DEBUG):
            tb = traceback.format_exc()
            safe_tb = self._redact_from_string(tb)
            self.logger.debug(f"Traceback:\n{safe_tb}")
    
    def log_database_query(self, query: str, params: dict = None, duration_ms: float = None):
        """Log database query with parameters sanitized"""
        # Sanitize query
        safe_query = self._redact_from_string(query)
        
        # Sanitize parameters
        safe_params = self._sanitize_dict(params) if params else None
        
        message = f"Database query"
        if duration_ms:
            message += f" ({duration_ms:.2f}ms)"
        
        self.logger.debug(f"{message}: {safe_query}")
        if safe_params:
            self.logger.debug(f"Parameters: {safe_params}")
    
    def _redact_from_string(self, text: str) -> str:
        """Redact sensitive data from string"""
        formatter = SecureFormatter()
        return formatter._redact_sensitive_data(text)
    
    # Standard logging methods
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(message, **kwargs)

def secure_log_decorator(logger: SecureLogger):
    """Decorator to automatically log function calls securely"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Log function call (without arguments to avoid leaking sensitive data)
            logger.debug(f"Calling function: {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Function {func.__name__} completed successfully")
                return result
            except Exception as e:
                logger.log_error(e, f"function {func.__name__}")
                raise
        
        return wrapper
    return decorator

# Create a global secure logger instance
secure_logger = SecureLogger(__name__)