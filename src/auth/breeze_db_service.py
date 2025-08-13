"""
Breeze authentication service with database storage
"""
import os
from typing import Dict, Optional, Tuple
from breeze_connect import BreezeConnect
from dotenv import load_dotenv, set_key
from src.infrastructure.database.auth_repository import get_auth_repository

load_dotenv()

class BreezeDBService:
    def __init__(self):
        self.auth_repo = get_auth_repository()
        self.breeze = None
        self._load_from_db()
    
    def _load_from_db(self):
        """Load credentials from database if available"""
        session = self.auth_repo.get_active_session('breeze')
        if session:
            # Update environment variables from DB
            if session.api_key:
                os.environ['BREEZE_API_KEY'] = session.api_key
            if session.api_secret:
                os.environ['BREEZE_API_SECRET'] = session.api_secret
            if session.session_token:
                os.environ['BREEZE_API_SESSION'] = session.session_token
    
    def is_connected(self) -> bool:
        """Check if Breeze is connected"""
        try:
            session = self.auth_repo.get_active_session('breeze')
            if not session or not session.session_token:
                return False
            
            # Try to initialize Breeze with stored token
            if not self.breeze:
                api_key = session.api_key or os.getenv('BREEZE_API_KEY')
                api_secret = session.api_secret or os.getenv('BREEZE_API_SECRET')
                
                if not api_key or not api_secret:
                    return False
                
                self.breeze = BreezeConnect(api_key=api_key)
                self.breeze.generate_session(
                    api_secret=api_secret,
                    session_token=session.session_token
                )
            
            # Test connection
            customer = self.breeze.get_customer_details()
            return customer is not None
            
        except Exception:
            return False
    
    def save_session(self, session_token: str, user_id: Optional[str] = None) -> bool:
        """Save Breeze session to database"""
        try:
            api_key = os.getenv('BREEZE_API_KEY')
            api_secret = os.getenv('BREEZE_API_SECRET')
            
            # Save to database
            session_id = self.auth_repo.save_session(
                service_type='breeze',
                session_token=session_token,
                api_key=api_key,
                api_secret=api_secret,
                user_id=user_id,
                expires_in_hours=24,
                metadata={'source': 'auto_login'}
            )
            
            # Also update .env for backward compatibility
            env_path = '.env'
            set_key(env_path, 'BREEZE_API_SESSION', session_token)
            
            return True
            
        except Exception as e:
            print(f"Error saving Breeze session: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get Breeze connection status"""
        session = self.auth_repo.get_active_session('breeze')
        
        if session:
            return {
                'connected': self.is_connected(),
                'service': 'breeze',
                'user_id': session.user_id,
                'expires_at': session.expires_at.isoformat() if session.expires_at else None,
                'last_updated': session.updated_at.isoformat()
            }
        
        return {
            'connected': False,
            'service': 'breeze',
            'user_id': None,
            'expires_at': None,
            'last_updated': None
        }
    
    def auto_login(self) -> Tuple[bool, str]:
        """Perform auto-login and save to database"""
        try:
            from src.auth.auto_login import BreezeAutoLogin
            
            breeze_login = BreezeAutoLogin(headless=True)
            success, result = breeze_login.login()
            
            if success:
                # Save to database
                self.save_session(result)
                return True, "Breeze login successful"
            else:
                return False, f"Breeze login failed: {result}"
                
        except Exception as e:
            return False, f"Error during Breeze auto-login: {str(e)}"
    
    def disconnect(self) -> bool:
        """Disconnect and deactivate session"""
        try:
            # Deactivate in database
            self.auth_repo.deactivate_session('breeze')
            
            # Clear from environment
            if 'BREEZE_API_SESSION' in os.environ:
                del os.environ['BREEZE_API_SESSION']
            
            # Clear from .env
            env_path = '.env'
            set_key(env_path, 'BREEZE_API_SESSION', '')
            
            self.breeze = None
            return True
            
        except Exception:
            return False

# Singleton instance
_breeze_service = None

def get_breeze_service() -> BreezeDBService:
    global _breeze_service
    if _breeze_service is None:
        _breeze_service = BreezeDBService()
    return _breeze_service