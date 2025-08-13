"""
Kite authentication service with database storage
"""
import os
import hashlib
from typing import Dict, Optional, Tuple
from kiteconnect import KiteConnect
from dotenv import load_dotenv, set_key
from src.infrastructure.database.auth_repository import get_auth_repository

load_dotenv()

class KiteDBService:
    def __init__(self):
        self.auth_repo = get_auth_repository()
        self.kite = None
        self._load_from_db()
    
    def _load_from_db(self):
        """Load credentials from database if available"""
        session = self.auth_repo.get_active_session('kite')
        if session:
            # Update environment variables from DB
            if session.api_key:
                os.environ['KITE_API_KEY'] = session.api_key
            if session.api_secret:
                os.environ['KITE_API_SECRET'] = session.api_secret
            if session.access_token:
                os.environ['KITE_ACCESS_TOKEN'] = session.access_token
    
    def is_connected(self) -> bool:
        """Check if Kite is connected"""
        try:
            session = self.auth_repo.get_active_session('kite')
            if not session or not session.access_token:
                return False
            
            # Try to initialize Kite with stored token
            if not self.kite:
                api_key = session.api_key or os.getenv('KITE_API_KEY')
                
                if not api_key:
                    return False
                
                self.kite = KiteConnect(api_key=api_key)
                self.kite.set_access_token(session.access_token)
            
            # Test connection
            profile = self.kite.profile()
            return profile is not None
            
        except Exception:
            return False
    
    def save_session(
        self, 
        access_token: str, 
        user_id: Optional[str] = None,
        request_token: Optional[str] = None
    ) -> bool:
        """Save Kite session to database"""
        try:
            api_key = os.getenv('KITE_API_KEY')
            api_secret = os.getenv('KITE_API_SECRET')
            
            # Save to database
            session_id = self.auth_repo.save_session(
                service_type='kite',
                access_token=access_token,
                session_token=request_token,  # Store request_token as session_token
                api_key=api_key,
                api_secret=api_secret,
                user_id=user_id,
                expires_in_hours=24,
                metadata={'source': 'auto_login'}
            )
            
            # Also update .env for backward compatibility
            env_path = '.env'
            set_key(env_path, 'KITE_ACCESS_TOKEN', access_token)
            if request_token:
                set_key(env_path, 'KITE_REQUEST_TOKEN', request_token)
            
            return True
            
        except Exception as e:
            print(f"Error saving Kite session: {e}")
            return False
    
    def exchange_token(self, request_token: str) -> Tuple[bool, str]:
        """Exchange request token for access token"""
        try:
            api_key = os.getenv('KITE_API_KEY')
            api_secret = os.getenv('KITE_API_SECRET')
            
            if not api_key or not api_secret:
                return False, "API credentials not configured"
            
            kite = KiteConnect(api_key=api_key)
            
            # Generate checksum
            checksum = hashlib.sha256(
                f"{api_key}{request_token}{api_secret}".encode()
            ).hexdigest()
            
            # Exchange token
            data = kite.generate_session(request_token, api_secret=api_secret)
            access_token = data.get("access_token")
            
            if access_token:
                # Save to database
                self.save_session(
                    access_token=access_token,
                    user_id=data.get("user_id"),
                    request_token=request_token
                )
                return True, access_token
            else:
                return False, "No access token received"
                
        except Exception as e:
            return False, str(e)
    
    def get_status(self) -> Dict:
        """Get Kite connection status"""
        session = self.auth_repo.get_active_session('kite')
        
        if session:
            return {
                'connected': self.is_connected(),
                'service': 'kite',
                'user_id': session.user_id,
                'expires_at': session.expires_at.isoformat() if session.expires_at else None,
                'last_updated': session.updated_at.isoformat()
            }
        
        return {
            'connected': False,
            'service': 'kite',
            'user_id': None,
            'expires_at': None,
            'last_updated': None
        }
    
    def auto_login(self) -> Tuple[bool, str]:
        """Perform auto-login and save to database"""
        try:
            from src.auth.kite_auto_login_service import KiteAutoLoginService
            
            kite_login = KiteAutoLoginService()
            result = kite_login.auto_login()
            
            if result['success']:
                # Token already saved by KiteAutoLoginService
                # Just ensure it's in database
                access_token = os.getenv('KITE_ACCESS_TOKEN')
                if access_token:
                    self.save_session(access_token)
                return True, result['message']
            else:
                return False, result['message']
                
        except Exception as e:
            return False, f"Error during Kite auto-login: {str(e)}"
    
    def disconnect(self) -> bool:
        """Disconnect and deactivate session"""
        try:
            # Deactivate in database
            self.auth_repo.deactivate_session('kite')
            
            # Clear from environment
            if 'KITE_ACCESS_TOKEN' in os.environ:
                del os.environ['KITE_ACCESS_TOKEN']
            if 'KITE_REQUEST_TOKEN' in os.environ:
                del os.environ['KITE_REQUEST_TOKEN']
            
            # Clear from .env
            env_path = '.env'
            set_key(env_path, 'KITE_ACCESS_TOKEN', '')
            set_key(env_path, 'KITE_REQUEST_TOKEN', '')
            
            self.kite = None
            return True
            
        except Exception:
            return False

# Singleton instance
_kite_service = None

def get_kite_service() -> KiteDBService:
    global _kite_service
    if _kite_service is None:
        _kite_service = KiteDBService()
    return _kite_service