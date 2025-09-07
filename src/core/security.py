"""
Production-grade security and session management system
"""
import os
import jwt
import bcrypt
import secrets
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import threading
from functools import wraps
import ipaddress
from urllib.parse import urlparse

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

class SessionStatus(Enum):
    """Session status enumeration"""
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    SUSPICIOUS = "suspicious"

@dataclass
class Session:
    """User session data"""
    session_id: str
    user_id: str
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    status: SessionStatus
    permissions: List[str]
    metadata: Dict[str, Any]

@dataclass
class SecurityEvent:
    """Security event data"""
    event_type: str
    user_id: Optional[str]
    ip_address: str
    timestamp: datetime
    details: Dict[str, Any]
    severity: str

class SecurityManager:
    """Comprehensive security and session management"""
    
    def __init__(self):
        # JWT Configuration
        self.jwt_secret = os.getenv('JWT_SECRET_KEY', self._generate_secret())
        self.jwt_algorithm = 'HS256'
        self.jwt_expiry_hours = int(os.getenv('JWT_EXPIRY_HOURS', '24'))
        
        # Session Configuration
        self.session_timeout_minutes = int(os.getenv('SESSION_TIMEOUT_MINUTES', '120'))
        self.max_sessions_per_user = int(os.getenv('MAX_SESSIONS_PER_USER', '3'))
        
        # Security Configuration
        self.max_login_attempts = int(os.getenv('MAX_LOGIN_ATTEMPTS', '5'))
        self.lockout_duration_minutes = int(os.getenv('LOCKOUT_DURATION_MINUTES', '30'))
        self.rate_limit_per_minute = int(os.getenv('RATE_LIMIT_PER_MINUTE', '60'))
        
        # IP Whitelisting
        self.allowed_ips = self._parse_allowed_ips()
        
        # Data structures
        self._sessions: Dict[str, Session] = {}
        self._user_sessions: Dict[str, List[str]] = {}  # user_id -> session_ids
        self._login_attempts: Dict[str, List[datetime]] = {}  # ip -> attempt times
        self._security_events: List[SecurityEvent] = []
        self._api_calls: Dict[str, List[datetime]] = {}  # ip -> call times
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Cleanup thread
        self._start_cleanup_thread()
        
        logger.info("Security manager initialized")
    
    def _generate_secret(self) -> str:
        """Generate a secure random secret"""
        return secrets.token_urlsafe(32)
    
    def _parse_allowed_ips(self) -> List[ipaddress.IPv4Network]:
        """Parse allowed IP addresses from environment"""
        allowed_ips_str = os.getenv('ALLOWED_IPS', '')
        if not allowed_ips_str:
            return []
        
        networks = []
        for ip_str in allowed_ips_str.split(','):
            ip_str = ip_str.strip()
            if ip_str:
                try:
                    if '/' not in ip_str:
                        ip_str += '/32'  # Single IP
                    networks.append(ipaddress.IPv4Network(ip_str))
                except ValueError as e:
                    logger.warning(f"Invalid IP address in ALLOWED_IPS: {ip_str} - {e}")
        
        return networks
    
    def _start_cleanup_thread(self):
        """Start background thread for session cleanup"""
        def cleanup_loop():
            while True:
                try:
                    self.cleanup_expired_sessions()
                    self.cleanup_old_events()
                    time.sleep(300)  # Clean up every 5 minutes
                except Exception as e:
                    logger.error(f"Cleanup thread error: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_loop)
        cleanup_thread.daemon = True
        cleanup_thread.start()
    
    def _log_security_event(self, event_type: str, user_id: str = None, 
                           ip_address: str = None, details: Dict[str, Any] = None,
                           severity: str = "INFO"):
        """Log security event"""
        event = SecurityEvent(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address or "unknown",
            timestamp=datetime.utcnow(),
            details=details or {},
            severity=severity
        )
        
        with self._lock:
            self._security_events.append(event)
            # Keep only last 1000 events
            if len(self._security_events) > 1000:
                self._security_events = self._security_events[-1000:]
        
        log_level = {
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }.get(severity, logging.INFO)
        
        logger.log(log_level, f"Security event: {event_type} - {details}")
    
    def check_ip_whitelist(self, ip_address: str) -> bool:
        """Check if IP address is in whitelist"""
        if not self.allowed_ips:
            return True  # No whitelist configured
        
        try:
            client_ip = ipaddress.IPv4Address(ip_address)
            for network in self.allowed_ips:
                if client_ip in network:
                    return True
            return False
        except ValueError:
            logger.warning(f"Invalid IP address format: {ip_address}")
            return False
    
    def check_rate_limit(self, ip_address: str) -> bool:
        """Check if IP address is within rate limits"""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        with self._lock:
            if ip_address not in self._api_calls:
                self._api_calls[ip_address] = []
            
            # Clean old calls
            self._api_calls[ip_address] = [
                call_time for call_time in self._api_calls[ip_address]
                if call_time > minute_ago
            ]
            
            # Check limit
            if len(self._api_calls[ip_address]) >= self.rate_limit_per_minute:
                self._log_security_event(
                    "RATE_LIMIT_EXCEEDED",
                    ip_address=ip_address,
                    details={"calls_per_minute": len(self._api_calls[ip_address])},
                    severity="WARNING"
                )
                return False
            
            # Record this call
            self._api_calls[ip_address].append(now)
            return True
    
    def check_login_attempts(self, ip_address: str) -> bool:
        """Check if IP address has exceeded login attempts"""
        now = datetime.utcnow()
        lockout_time = now - timedelta(minutes=self.lockout_duration_minutes)
        
        with self._lock:
            if ip_address not in self._login_attempts:
                self._login_attempts[ip_address] = []
            
            # Clean old attempts
            self._login_attempts[ip_address] = [
                attempt_time for attempt_time in self._login_attempts[ip_address]
                if attempt_time > lockout_time
            ]
            
            # Check if locked out
            return len(self._login_attempts[ip_address]) < self.max_login_attempts
    
    def record_failed_login(self, ip_address: str, user_id: str = None):
        """Record a failed login attempt"""
        now = datetime.utcnow()
        
        with self._lock:
            if ip_address not in self._login_attempts:
                self._login_attempts[ip_address] = []
            
            self._login_attempts[ip_address].append(now)
        
        self._log_security_event(
            "FAILED_LOGIN",
            user_id=user_id,
            ip_address=ip_address,
            details={"attempts": len(self._login_attempts[ip_address])},
            severity="WARNING"
        )
    
    def create_session(self, user_id: str, ip_address: str, user_agent: str,
                      permissions: List[str] = None) -> Session:
        """Create a new user session"""
        
        # Check existing sessions for user
        with self._lock:
            if user_id in self._user_sessions:
                # Remove oldest session if at limit
                if len(self._user_sessions[user_id]) >= self.max_sessions_per_user:
                    oldest_session_id = self._user_sessions[user_id].pop(0)
                    if oldest_session_id in self._sessions:
                        del self._sessions[oldest_session_id]
        
        # Create new session
        session_id = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self.jwt_expiry_hours)
        
        session = Session(
            session_id=session_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now,
            last_activity=now,
            expires_at=expires_at,
            status=SessionStatus.ACTIVE,
            permissions=permissions or [],
            metadata={}
        )
        
        with self._lock:
            self._sessions[session_id] = session
            
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = []
            self._user_sessions[user_id].append(session_id)
        
        self._log_security_event(
            "SESSION_CREATED",
            user_id=user_id,
            ip_address=ip_address,
            details={"session_id": session_id}
        )
        
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        with self._lock:
            return self._sessions.get(session_id)
    
    def validate_session(self, session_id: str, ip_address: str = None) -> Optional[Session]:
        """Validate and update session"""
        with self._lock:
            session = self._sessions.get(session_id)
            
            if not session:
                return None
            
            now = datetime.utcnow()
            
            # Check if expired
            if now > session.expires_at:
                session.status = SessionStatus.EXPIRED
                self._log_security_event(
                    "SESSION_EXPIRED",
                    user_id=session.user_id,
                    ip_address=session.ip_address,
                    details={"session_id": session_id}
                )
                return None
            
            # Check for IP change (security concern)
            if ip_address and session.ip_address != ip_address:
                self._log_security_event(
                    "SESSION_IP_CHANGE",
                    user_id=session.user_id,
                    ip_address=ip_address,
                    details={
                        "session_id": session_id,
                        "original_ip": session.ip_address,
                        "new_ip": ip_address
                    },
                    severity="WARNING"
                )
                # Optionally terminate session for security
                # session.status = SessionStatus.SUSPICIOUS
                # return None
            
            # Check for inactivity timeout
            timeout = timedelta(minutes=self.session_timeout_minutes)
            if now - session.last_activity > timeout:
                session.status = SessionStatus.EXPIRED
                self._log_security_event(
                    "SESSION_TIMEOUT",
                    user_id=session.user_id,
                    ip_address=session.ip_address,
                    details={"session_id": session_id}
                )
                return None
            
            # Update last activity
            session.last_activity = now
            return session
    
    def terminate_session(self, session_id: str):
        """Terminate a specific session"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = SessionStatus.TERMINATED
                
                # Remove from user sessions
                if session.user_id in self._user_sessions:
                    try:
                        self._user_sessions[session.user_id].remove(session_id)
                    except ValueError:
                        pass
                
                # Remove from sessions
                del self._sessions[session_id]
                
                self._log_security_event(
                    "SESSION_TERMINATED",
                    user_id=session.user_id,
                    ip_address=session.ip_address,
                    details={"session_id": session_id}
                )
    
    def terminate_user_sessions(self, user_id: str):
        """Terminate all sessions for a user"""
        with self._lock:
            if user_id in self._user_sessions:
                session_ids = self._user_sessions[user_id].copy()
                for session_id in session_ids:
                    self.terminate_session(session_id)
    
    def create_jwt_token(self, session: Session) -> str:
        """Create JWT token for session"""
        payload = {
            'session_id': session.session_id,
            'user_id': session.user_id,
            'permissions': session.permissions,
            'exp': int(session.expires_at.timestamp()),
            'iat': int(session.created_at.timestamp())
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Validate session still exists
            session = self.get_session(payload['session_id'])
            if not session or session.status != SessionStatus.ACTIVE:
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            self._log_security_event(
                "JWT_EXPIRED",
                details={"token": token[:20] + "..."},
                severity="WARNING"
            )
            return None
        except jwt.InvalidTokenError as e:
            self._log_security_event(
                "JWT_INVALID",
                details={"error": str(e)},
                severity="WARNING"
            )
            return None
    
    def hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def validate_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Validate webhook signature"""
        try:
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Webhook signature validation error: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        now = datetime.utcnow()
        expired_sessions = []
        
        with self._lock:
            for session_id, session in list(self._sessions.items()):
                if (now > session.expires_at or 
                    session.status in [SessionStatus.EXPIRED, SessionStatus.TERMINATED]):
                    expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.terminate_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def cleanup_old_events(self, days_to_keep: int = 7):
        """Clean up old security events"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with self._lock:
            original_count = len(self._security_events)
            self._security_events = [
                event for event in self._security_events
                if event.timestamp > cutoff_time
            ]
            removed_count = original_count - len(self._security_events)
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old security events")
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get security system status"""
        with self._lock:
            active_sessions = len([s for s in self._sessions.values() 
                                 if s.status == SessionStatus.ACTIVE])
            
            recent_events = [
                event for event in self._security_events
                if event.timestamp > datetime.utcnow() - timedelta(hours=1)
            ]
            
            return {
                'active_sessions': active_sessions,
                'total_sessions': len(self._sessions),
                'recent_security_events': len(recent_events),
                'failed_login_ips': len(self._login_attempts),
                'rate_limited_ips': len(self._api_calls),
                'ip_whitelist_enabled': bool(self.allowed_ips),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_security_events(self, limit: int = 100, 
                           event_type: str = None, 
                           severity: str = None) -> List[SecurityEvent]:
        """Get security events with filtering"""
        with self._lock:
            events = self._security_events.copy()
        
        # Filter by type
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        # Filter by severity
        if severity:
            events = [e for e in events if e.severity == severity]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]

# Global security manager
_security_manager: Optional[SecurityManager] = None

def get_security_manager() -> SecurityManager:
    """Get global security manager instance"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager

# FastAPI Security Dependencies
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security),
                    request: Request = None) -> Dict[str, Any]:
    """FastAPI dependency to get current authenticated user"""
    try:
        security_manager = get_security_manager()
        
        # Validate JWT token
        payload = security_manager.validate_jwt_token(credentials.credentials)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Validate session
        session = security_manager.validate_session(
            payload['session_id'],
            request.client.host if request and request.client else None
        )
        
        if not session:
            raise HTTPException(status_code=401, detail="Session expired")
        
        return {
            'user_id': payload['user_id'],
            'session_id': payload['session_id'],
            'permissions': payload['permissions']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get('current_user')
            if not user or permission not in user.get('permissions', []):
                raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
            return func(*args, **kwargs)
        return wrapper
    return decorator