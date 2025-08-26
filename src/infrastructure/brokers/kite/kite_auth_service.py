"""
Kite Authentication Service
Handles authentication flow and token management
"""
import logging
import json
import os
from datetime import datetime, time
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class KiteAuthService:
    """
    Manages Kite Connect authentication and token persistence
    """
    
    def __init__(self, kite_client):
        self.kite_client = kite_client
        # Use the auto login token file in logs directory
        self.token_file = Path("logs/kite_auth_cache.json")
        self.load_saved_token()
    
    def load_saved_token(self) -> bool:
        """Load saved access token if available and valid"""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                
                # Handle both formats - auto login uses 'cached_at', manual uses 'timestamp'
                timestamp_key = 'cached_at' if 'cached_at' in data else 'timestamp'
                
                # Check if token is from today (tokens expire daily)
                token_date = datetime.fromisoformat(data[timestamp_key]).date()
                if token_date == datetime.now().date():
                    self.kite_client.set_access_token(data['access_token'])
                    logger.info("Loaded saved access token from auto login")
                    return True
                else:
                    logger.info("Saved token expired, need new authentication")
            except Exception as e:
                logger.error(f"Error loading saved token: {e}")
        
        return False
    
    def save_token(self, access_token: str):
        """Save access token to file"""
        try:
            data = {
                'access_token': access_token,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.token_file, 'w') as f:
                json.dump(data, f)
            logger.info("Access token saved successfully")
        except Exception as e:
            logger.error(f"Error saving token: {e}")
    
    def get_login_url(self) -> str:
        """Get Kite login URL for user authentication"""
        return self.kite_client.get_login_url()
    
    def complete_authentication(self, request_token: str) -> Dict[str, Any]:
        """
        Complete authentication process with request token
        Returns user data including access token
        """
        try:
            data = self.kite_client.generate_session(request_token)
            self.save_token(data['access_token'])
            
            # Also update environment variable for current session
            os.environ['KITE_ACCESS_TOKEN'] = data['access_token']
            
            logger.info(f"Authentication successful for user: {data.get('user_id')}")
            return data
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    def is_authenticated(self) -> bool:
        """Check if client is authenticated"""
        try:
            # Try to fetch profile to verify authentication
            self.kite_client.kite.profile()
            return True
        except:
            return False
    
    def needs_reauthentication(self) -> bool:
        """
        Check if reauthentication is needed
        Kite tokens expire at 6 AM daily
        """
        current_time = datetime.now().time()
        market_start = time(6, 0)  # 6 AM
        
        # If it's after 6 AM and we haven't authenticated today
        if current_time >= market_start:
            if not self.token_file.exists():
                return True
            
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                token_date = datetime.fromisoformat(data['timestamp']).date()
                return token_date != datetime.now().date()
            except:
                return True
        
        return False
    
    def get_auth_status(self) -> Dict[str, Any]:
        """Get current authentication status"""
        status = {
            'authenticated': self.is_authenticated(),
            'needs_reauthentication': self.needs_reauthentication(),
            'token_file_exists': self.token_file.exists()
        }
        
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                status['token_timestamp'] = data.get('timestamp')
            except:
                pass
        
        return status