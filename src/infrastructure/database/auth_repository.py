"""
Database repository for authentication sessions
"""
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pyodbc
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AuthSession:
    id: str
    service_type: str
    session_token: Optional[str]
    access_token: Optional[str]
    refresh_token: Optional[str]
    api_key: Optional[str]
    api_secret: Optional[str]
    user_id: Optional[str]
    user_name: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    metadata: Optional[Dict[str, Any]]

class AuthRepository:
    def __init__(self):
        self.connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')};"
            f"DATABASE={os.getenv('DB_NAME', 'KiteConnectApi')};"
            f"Trusted_Connection=yes;"
        )
    
    def _get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def get_active_session(self, service_type: str) -> Optional[AuthSession]:
        """Get active session for a service"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT TOP 1 
                    id, service_type, session_token, access_token, 
                    refresh_token, api_key, api_secret, user_id, 
                    user_name, expires_at, created_at, updated_at, 
                    is_active, metadata
                FROM AuthSessions
                WHERE service_type = ? 
                    AND is_active = 1
                    AND (expires_at IS NULL OR expires_at > GETDATE())
                ORDER BY updated_at DESC
            """, service_type)
            
            row = cursor.fetchone()
            if row:
                return AuthSession(
                    id=str(row[0]),
                    service_type=row[1],
                    session_token=row[2],
                    access_token=row[3],
                    refresh_token=row[4],
                    api_key=row[5],
                    api_secret=row[6],
                    user_id=row[7],
                    user_name=row[8],
                    expires_at=row[9],
                    created_at=row[10],
                    updated_at=row[11],
                    is_active=bool(row[12]),
                    metadata=json.loads(row[13]) if row[13] else None
                )
            return None
            
        finally:
            cursor.close()
            conn.close()
    
    def save_session(
        self,
        service_type: str,
        session_token: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        expires_in_hours: int = 24,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save or update authentication session"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Deactivate existing sessions
            cursor.execute("""
                UPDATE AuthSessions 
                SET is_active = 0, updated_at = GETDATE()
                WHERE service_type = ? AND is_active = 1
            """, service_type)
            
            # Insert new session
            expires_at = datetime.now() + timedelta(hours=expires_in_hours)
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute("""
                INSERT INTO AuthSessions (
                    service_type, session_token, access_token, 
                    refresh_token, api_key, api_secret, 
                    user_id, user_name, expires_at, metadata, 
                    is_active, created_at, updated_at
                ) 
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE(), GETDATE())
            """, (
                service_type, session_token, access_token,
                refresh_token, api_key, api_secret,
                user_id, user_name, expires_at, metadata_json
            ))
            
            session_id = cursor.fetchone()[0]
            conn.commit()
            
            return str(session_id)
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def update_session_token(
        self, 
        service_type: str, 
        access_token: str,
        session_token: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Update just the tokens for a service"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE AuthSessions 
                SET access_token = ?, 
                    session_token = COALESCE(?, session_token),
                    user_id = COALESCE(?, user_id),
                    updated_at = GETDATE(),
                    expires_at = DATEADD(hour, 24, GETDATE())
                WHERE service_type = ? AND is_active = 1
            """, (access_token, session_token, user_id, service_type))
            
            if cursor.rowcount == 0:
                # No active session, create new one
                self.save_session(
                    service_type=service_type,
                    access_token=access_token,
                    session_token=session_token,
                    user_id=user_id
                )
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def deactivate_session(self, service_type: str) -> bool:
        """Deactivate all sessions for a service"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE AuthSessions 
                SET is_active = 0, updated_at = GETDATE()
                WHERE service_type = ? AND is_active = 1
            """, service_type)
            
            conn.commit()
            return cursor.rowcount > 0
            
        finally:
            cursor.close()
            conn.close()
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE AuthSessions 
                SET is_active = 0 
                WHERE expires_at < GETDATE() AND is_active = 1
            """)
            
            count = cursor.rowcount
            conn.commit()
            return count
            
        finally:
            cursor.close()
            conn.close()

# Singleton instance
_auth_repository = None

def get_auth_repository() -> AuthRepository:
    global _auth_repository
    if _auth_repository is None:
        _auth_repository = AuthRepository()
    return _auth_repository