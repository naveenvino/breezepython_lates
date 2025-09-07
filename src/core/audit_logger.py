"""
Comprehensive audit logging system for trading operations
"""
import os
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from pathlib import Path
import threading
import sqlite3
from contextlib import contextmanager

class AuditEventType(Enum):
    """Types of audit events"""
    TRADE_ENTRY = "trade_entry"
    TRADE_EXIT = "trade_exit"
    ORDER_PLACED = "order_placed"
    ORDER_MODIFIED = "order_modified"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    RISK_LIMIT_HIT = "risk_limit_hit"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    CONFIG_CHANGED = "config_changed"
    API_ACCESS = "api_access"
    ERROR_OCCURRED = "error_occurred"
    ALERT_RECEIVED = "alert_received"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"

class AuditSeverity(Enum):
    """Audit event severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AuditLogger:
    """Comprehensive audit logging system"""
    
    def __init__(self, db_path: str = None, enable_file_logging: bool = True):
        self.db_path = db_path or str(Path("data") / "audit_log.db")
        self.enable_file_logging = enable_file_logging
        self._lock = threading.Lock()
        
        # Setup database
        self._init_database()
        
        # Setup file logging if enabled
        if enable_file_logging:
            self._setup_file_logging()
        
        logger = logging.getLogger(__name__)
        logger.info("Audit logging system initialized")
    
    def _init_database(self):
        """Initialize audit database"""
        Path(self.db_path).parent.mkdir(exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    event_data TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    success BOOLEAN,
                    error_message TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_log(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_log(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON audit_log(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_severity ON audit_log(severity)")
            
            conn.commit()
    
    def _setup_file_logging(self):
        """Setup file-based logging"""
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Audit log file handler
        audit_file = logs_dir / "audit.log"
        file_handler = logging.FileHandler(audit_file)
        file_handler.setLevel(logging.INFO)
        
        # JSON formatter for structured logging
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": %(message)s}'
        )
        file_handler.setFormatter(formatter)
        
        # Add to audit logger
        audit_logger = logging.getLogger("audit")
        audit_logger.setLevel(logging.INFO)
        audit_logger.addHandler(file_handler)
        
        # Prevent propagation to avoid duplicate logs
        audit_logger.propagate = False
    
    @contextmanager
    def _get_db_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
        except Exception as e:
            logging.getLogger(__name__).error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def log_event(
        self,
        event_type: AuditEventType,
        event_data: Dict[str, Any],
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log an audit event"""
        
        timestamp = datetime.utcnow().isoformat()
        
        # Prepare data for database
        db_event_data = {
            'timestamp': timestamp,
            'event_type': event_type.value,
            'severity': severity.value,
            'user_id': user_id,
            'session_id': session_id,
            'event_data': json.dumps(event_data, default=str),
            'ip_address': ip_address,
            'user_agent': user_agent,
            'success': success,
            'error_message': error_message,
            'metadata': json.dumps(metadata or {}, default=str)
        }
        
        # Store in database
        with self._lock:
            try:
                with self._get_db_connection() as conn:
                    conn.execute("""
                        INSERT INTO audit_log 
                        (timestamp, event_type, severity, user_id, session_id, 
                         event_data, ip_address, user_agent, success, error_message, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        timestamp, event_type.value, severity.value, user_id, session_id,
                        db_event_data['event_data'], ip_address, user_agent, 
                        success, error_message, db_event_data['metadata']
                    ))
                    conn.commit()
            except Exception as e:
                logging.getLogger(__name__).error(f"Failed to write audit log to database: {e}")
        
        # Also log to file if enabled
        if self.enable_file_logging:
            log_entry = {
                'timestamp': timestamp,
                'event_type': event_type.value,
                'severity': severity.value,
                'user_id': user_id,
                'success': success,
                'event_data': event_data,
                'error_message': error_message
            }
            
            audit_logger = logging.getLogger("audit")
            log_level = {
                AuditSeverity.INFO: logging.INFO,
                AuditSeverity.WARNING: logging.WARNING,
                AuditSeverity.ERROR: logging.ERROR,
                AuditSeverity.CRITICAL: logging.CRITICAL
            }.get(severity, logging.INFO)
            
            audit_logger.log(log_level, json.dumps(log_entry, default=str))
    
    # Convenience methods for common events
    
    def log_trade_entry(self, symbol: str, quantity: int, price: float, 
                       signal: str, user_id: str = None, success: bool = True, 
                       error_message: str = None):
        """Log trade entry event"""
        self.log_event(
            AuditEventType.TRADE_ENTRY,
            {
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'signal': signal,
                'trade_value': abs(quantity * price)
            },
            severity=AuditSeverity.INFO if success else AuditSeverity.ERROR,
            user_id=user_id,
            success=success,
            error_message=error_message
        )
    
    def log_trade_exit(self, symbol: str, quantity: int, entry_price: float,
                      exit_price: float, pnl: float, reason: str,
                      user_id: str = None, success: bool = True,
                      error_message: str = None):
        """Log trade exit event"""
        self.log_event(
            AuditEventType.TRADE_EXIT,
            {
                'symbol': symbol,
                'quantity': quantity,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'reason': reason
            },
            severity=AuditSeverity.INFO if success else AuditSeverity.ERROR,
            user_id=user_id,
            success=success,
            error_message=error_message
        )
    
    def log_order(self, order_type: str, symbol: str, quantity: int, 
                 price: float, order_id: str = None, user_id: str = None,
                 success: bool = True, error_message: str = None):
        """Log order events"""
        event_type_map = {
            'placed': AuditEventType.ORDER_PLACED,
            'modified': AuditEventType.ORDER_MODIFIED,
            'cancelled': AuditEventType.ORDER_CANCELLED
        }
        
        self.log_event(
            event_type_map.get(order_type.lower(), AuditEventType.ORDER_PLACED),
            {
                'order_id': order_id,
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'order_type': order_type
            },
            severity=AuditSeverity.INFO if success else AuditSeverity.ERROR,
            user_id=user_id,
            success=success,
            error_message=error_message
        )
    
    def log_risk_event(self, event_type: str, details: Dict[str, Any],
                      severity: AuditSeverity = AuditSeverity.WARNING):
        """Log risk management events"""
        event_map = {
            'stop_loss': AuditEventType.STOP_LOSS_TRIGGERED,
            'risk_limit': AuditEventType.RISK_LIMIT_HIT,
            'circuit_breaker': AuditEventType.CIRCUIT_BREAKER_TRIGGERED
        }
        
        self.log_event(
            event_map.get(event_type, AuditEventType.ERROR_OCCURRED),
            details,
            severity=severity
        )
    
    def log_user_activity(self, action: str, user_id: str, ip_address: str = None,
                         user_agent: str = None, success: bool = True,
                         details: Dict[str, Any] = None):
        """Log user activity"""
        event_map = {
            'login': AuditEventType.USER_LOGIN,
            'logout': AuditEventType.USER_LOGOUT
        }
        
        self.log_event(
            event_map.get(action.lower(), AuditEventType.API_ACCESS),
            details or {'action': action},
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success
        )
    
    def log_config_change(self, config_key: str, old_value: Any, new_value: Any,
                         user_id: str = None):
        """Log configuration changes"""
        self.log_event(
            AuditEventType.CONFIG_CHANGED,
            {
                'config_key': config_key,
                'old_value': str(old_value),
                'new_value': str(new_value)
            },
            severity=AuditSeverity.WARNING,
            user_id=user_id
        )
    
    def log_api_access(self, endpoint: str, method: str, status_code: int,
                      user_id: str = None, ip_address: str = None,
                      user_agent: str = None, response_time: float = None):
        """Log API access"""
        self.log_event(
            AuditEventType.API_ACCESS,
            {
                'endpoint': endpoint,
                'method': method,
                'status_code': status_code,
                'response_time': response_time
            },
            severity=AuditSeverity.ERROR if status_code >= 400 else AuditSeverity.INFO,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=status_code < 400
        )
    
    def log_error(self, error_message: str, details: Dict[str, Any] = None,
                 user_id: str = None, severity: AuditSeverity = AuditSeverity.ERROR):
        """Log error events"""
        self.log_event(
            AuditEventType.ERROR_OCCURRED,
            details or {'error': error_message},
            severity=severity,
            user_id=user_id,
            success=False,
            error_message=error_message
        )
    
    def log_alert_received(self, alert_data: Dict[str, Any], source: str = "tradingview"):
        """Log received trading alerts"""
        self.log_event(
            AuditEventType.ALERT_RECEIVED,
            {
                'source': source,
                'alert_data': alert_data
            },
            severity=AuditSeverity.INFO
        )
    
    def log_system_event(self, event: str, details: Dict[str, Any] = None):
        """Log system events"""
        event_map = {
            'start': AuditEventType.SYSTEM_START,
            'stop': AuditEventType.SYSTEM_STOP
        }
        
        self.log_event(
            event_map.get(event.lower(), AuditEventType.API_ACCESS),
            details or {'event': event},
            severity=AuditSeverity.INFO
        )
    
    def get_audit_logs(self, 
                      event_type: str = None,
                      user_id: str = None,
                      start_date: str = None,
                      end_date: str = None,
                      severity: str = None,
                      limit: int = 100,
                      offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve audit logs with filters"""
        
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    record = dict(zip(columns, row))
                    # Parse JSON fields
                    try:
                        record['event_data'] = json.loads(record['event_data'])
                        record['metadata'] = json.loads(record['metadata'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                    results.append(record)
                
                return results
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to retrieve audit logs: {e}")
            return []
    
    def get_audit_summary(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Get audit log summary statistics"""
        
        query = """
            SELECT 
                event_type,
                severity,
                COUNT(*) as count,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
            FROM audit_log 
            WHERE 1=1
        """
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " GROUP BY event_type, severity ORDER BY count DESC"
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'event_type': row[0],
                        'severity': row[1],
                        'count': row[2],
                        'success_count': row[3],
                        'error_count': row[4]
                    })
                
                return {
                    'summary': results,
                    'total_events': sum(r['count'] for r in results),
                    'total_errors': sum(r['error_count'] for r in results),
                    'generated_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to generate audit summary: {e}")
            return {'error': str(e)}
    
    def cleanup_old_logs(self, days_to_keep: int = 90):
        """Clean up old audit logs"""
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.isoformat()
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM audit_log WHERE timestamp < ?",
                    (cutoff_str,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                logging.getLogger(__name__).info(f"Cleaned up {deleted_count} old audit log entries")
                return deleted_count
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to cleanup audit logs: {e}")
            return 0

# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None

def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger