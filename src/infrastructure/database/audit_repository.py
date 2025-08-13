"""
Database repository for audit logging
"""
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import pyodbc
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

class AuditAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXECUTE = "execute"
    VIEW = "view"

class EntityType(Enum):
    AUTH = "auth"
    CONFIG = "config"
    TRADE = "trade"
    JOB = "job"
    BACKTEST = "backtest"
    DATA = "data"

@dataclass
class AuditLog:
    id: str
    entity_type: str
    entity_id: Optional[str]
    action: str
    old_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]
    user_id: Optional[str]
    ip_address: Optional[str]
    timestamp: datetime
    details: Optional[str]

class AuditRepository:
    def __init__(self):
        self.connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')};"
            f"DATABASE={os.getenv('DB_NAME', 'KiteConnectApi')};"
            f"Trusted_Connection=yes;"
        )
    
    def _get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def log(
        self,
        entity_type: str,
        action: str,
        entity_id: Optional[str] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[str] = None
    ) -> bool:
        """Create an audit log entry"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Convert values to JSON if they're complex types
            old_json = None
            new_json = None
            
            if old_value is not None:
                if isinstance(old_value, (dict, list)):
                    old_json = json.dumps(old_value)
                else:
                    old_json = str(old_value)
            
            if new_value is not None:
                if isinstance(new_value, (dict, list)):
                    new_json = json.dumps(new_value)
                else:
                    new_json = str(new_value)
            
            cursor.execute("""
                INSERT INTO AuditLogs (
                    entity_type, entity_id, action,
                    old_value, new_value, user_id,
                    ip_address, timestamp, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE(), ?)
            """, (
                entity_type, entity_id, action,
                old_json, new_json, user_id,
                ip_address, details
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"Error creating audit log: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    def log_auth_action(
        self,
        action: str,
        service: str,
        success: bool,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[str] = None
    ) -> bool:
        """Log authentication-related actions"""
        return self.log(
            entity_type=EntityType.AUTH.value,
            action=action,
            entity_id=service,
            new_value={"success": success, "service": service},
            user_id=user_id,
            ip_address=ip_address,
            details=details
        )
    
    def log_config_change(
        self,
        config_type: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        user_id: Optional[str] = None
    ) -> bool:
        """Log configuration changes"""
        return self.log(
            entity_type=EntityType.CONFIG.value,
            action=AuditAction.UPDATE.value,
            entity_id=f"{config_type}.{config_key}",
            old_value=old_value,
            new_value=new_value,
            user_id=user_id
        )
    
    def log_job_action(
        self,
        job_id: str,
        job_type: str,
        action: str,
        status: str,
        user_id: Optional[str] = None,
        details: Optional[str] = None
    ) -> bool:
        """Log job-related actions"""
        return self.log(
            entity_type=EntityType.JOB.value,
            action=action,
            entity_id=job_id,
            new_value={"job_type": job_type, "status": status},
            user_id=user_id,
            details=details
        )
    
    def log_backtest(
        self,
        backtest_id: str,
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
        results: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Log backtest-related actions"""
        return self.log(
            entity_type=EntityType.BACKTEST.value,
            action=action,
            entity_id=backtest_id,
            old_value=parameters,
            new_value=results,
            user_id=user_id
        )
    
    def get_logs_by_entity(
        self,
        entity_type: str,
        entity_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs for a specific entity"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if entity_id:
                cursor.execute("""
                    SELECT TOP(?)
                        id, entity_type, entity_id, action,
                        old_value, new_value, user_id,
                        ip_address, timestamp, details
                    FROM AuditLogs
                    WHERE entity_type = ? AND entity_id = ?
                    ORDER BY timestamp DESC
                """, (limit, entity_type, entity_id))
            else:
                cursor.execute("""
                    SELECT TOP(?)
                        id, entity_type, entity_id, action,
                        old_value, new_value, user_id,
                        ip_address, timestamp, details
                    FROM AuditLogs
                    WHERE entity_type = ?
                    ORDER BY timestamp DESC
                """, (limit, entity_type))
            
            logs = []
            for row in cursor.fetchall():
                logs.append(AuditLog(
                    id=str(row[0]),
                    entity_type=row[1],
                    entity_id=row[2],
                    action=row[3],
                    old_value=json.loads(row[4]) if row[4] else None,
                    new_value=json.loads(row[5]) if row[5] else None,
                    user_id=row[6],
                    ip_address=row[7],
                    timestamp=row[8],
                    details=row[9]
                ))
            
            return logs
            
        finally:
            cursor.close()
            conn.close()
    
    def get_logs_by_user(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs for a specific user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT TOP(?)
                    id, entity_type, entity_id, action,
                    old_value, new_value, user_id,
                    ip_address, timestamp, details
                FROM AuditLogs
                WHERE user_id = ?
                ORDER BY timestamp DESC
            """, (limit, user_id))
            
            logs = []
            for row in cursor.fetchall():
                logs.append(AuditLog(
                    id=str(row[0]),
                    entity_type=row[1],
                    entity_id=row[2],
                    action=row[3],
                    old_value=json.loads(row[4]) if row[4] else None,
                    new_value=json.loads(row[5]) if row[5] else None,
                    user_id=row[6],
                    ip_address=row[7],
                    timestamp=row[8],
                    details=row[9]
                ))
            
            return logs
            
        finally:
            cursor.close()
            conn.close()
    
    def get_recent_logs(
        self,
        hours: int = 24,
        entity_type: Optional[str] = None
    ) -> List[AuditLog]:
        """Get recent audit logs"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if entity_type:
                cursor.execute("""
                    SELECT 
                        id, entity_type, entity_id, action,
                        old_value, new_value, user_id,
                        ip_address, timestamp, details
                    FROM AuditLogs
                    WHERE timestamp > DATEADD(hour, -?, GETDATE())
                        AND entity_type = ?
                    ORDER BY timestamp DESC
                """, (hours, entity_type))
            else:
                cursor.execute("""
                    SELECT 
                        id, entity_type, entity_id, action,
                        old_value, new_value, user_id,
                        ip_address, timestamp, details
                    FROM AuditLogs
                    WHERE timestamp > DATEADD(hour, -?, GETDATE())
                    ORDER BY timestamp DESC
                """, hours)
            
            logs = []
            for row in cursor.fetchall():
                logs.append(AuditLog(
                    id=str(row[0]),
                    entity_type=row[1],
                    entity_id=row[2],
                    action=row[3],
                    old_value=json.loads(row[4]) if row[4] else None,
                    new_value=json.loads(row[5]) if row[5] else None,
                    user_id=row[6],
                    ip_address=row[7],
                    timestamp=row[8],
                    details=row[9]
                ))
            
            return logs
            
        finally:
            cursor.close()
            conn.close()
    
    def cleanup_old_logs(self, days: int = 90) -> int:
        """Clean up audit logs older than specified days"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM AuditLogs
                WHERE timestamp < DATEADD(day, -?, GETDATE())
            """, days)
            
            count = cursor.rowcount
            conn.commit()
            return count
            
        finally:
            cursor.close()
            conn.close()

# Singleton instance
_audit_repository = None

def get_audit_repository() -> AuditRepository:
    global _audit_repository
    if _audit_repository is None:
        _audit_repository = AuditRepository()
    return _audit_repository