"""
Session Validator Service
Validates external API sessions before making API calls
"""
import logging
import os
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import aiohttp

# Handle breeze_connect import error (network issues during import)
try:
    from breeze_connect import BreezeConnect
    BREEZE_AVAILABLE = True
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"BreezeConnect import failed (likely network issue): {e}")
    BREEZE_AVAILABLE = False
    BreezeConnect = None

logger = logging.getLogger(__name__)

class SessionValidator:
    """Validates and manages external API sessions"""
    
    def __init__(self):
        self.last_check_time = None
        self.check_interval = timedelta(minutes=5)  # Check every 5 minutes
        self.session_valid = False
        self.last_error = None
        
    async def validate_breeze_session(self) -> Tuple[bool, Optional[str]]:
        """
        Validates Breeze API session
        Returns: (is_valid, error_message)
        """
        try:
            # Check if BreezeConnect is available
            if not BREEZE_AVAILABLE:
                return False, "BreezeConnect library not available (network issue during import)"
            
            # Check if we recently validated
            if self.last_check_time and self.session_valid:
                if datetime.now() - self.last_check_time < self.check_interval:
                    return True, None
            
            # Get credentials from environment - reload to get latest
            from dotenv import load_dotenv
            load_dotenv(override=True)
            
            api_key = os.getenv('BREEZE_API_KEY')
            api_secret = os.getenv('BREEZE_API_SECRET')
            session_token = os.getenv('BREEZE_API_SESSION')
            
            # Log what we found for debugging
            logger.info(f"Validating Breeze - API Key: {api_key[:10] if api_key else 'None'}..., Secret: {api_secret[:10] if api_secret else 'None'}..., Session: {session_token if session_token else 'None'}")
            
            if not api_key:
                return False, "Missing Breeze API key in .env file"
            if not api_secret:
                return False, "Missing Breeze API secret in .env file"
            if not session_token:
                return False, "Missing Breeze API session token in .env file. Please run auto-login or update BREEZE_API_SESSION in .env"
            
            # Test connection with a simple API call
            breeze = BreezeConnect(api_key=api_key)
            breeze.generate_session(
                api_secret=api_secret,
                session_token=str(session_token)  # Ensure it's a string
            )
            
            # Try to get funds as a test (more reliable than customer_details)
            response = breeze.get_funds()
            
            # Check various success patterns
            if response:
                # Check for Success field
                if response.get('Success'):
                    self.session_valid = True
                    self.last_check_time = datetime.now()
                    self.last_error = None
                    logger.info(f"Breeze session validated successfully with token: {session_token[:10]}...")
                    return True, None
                # Check for Status field
                elif response.get('Status') == 200:
                    self.session_valid = True
                    self.last_check_time = datetime.now()
                    self.last_error = None
                    logger.info(f"Breeze session validated successfully with token: {session_token[:10]}...")
                    return True, None
                # Check if we got data back (some endpoints return data directly)
                elif 'trade_name' in response or 'pan' in response:
                    self.session_valid = True
                    self.last_check_time = datetime.now()
                    self.last_error = None
                    logger.info(f"Breeze session validated successfully with token: {session_token[:10]}...")
                    return True, None
                    
                error_msg = response.get('Error', 'Unknown error') if response else 'No response'
                self.session_valid = False
                self.last_error = error_msg
                
                # Check for specific token expiry error
                if 'session' in str(error_msg).lower() or 'token' in str(error_msg).lower():
                    return False, f"Session token expired or invalid. Please update your Breeze session token in .env file. Error: {error_msg}"
                else:
                    return False, f"Breeze API error: {error_msg}"
                    
        except Exception as e:
            self.session_valid = False
            self.last_error = str(e)
            
            # Parse error for common issues
            error_str = str(e).lower()
            if 'session' in error_str or 'token' in error_str or 'expired' in error_str:
                return False, f"Session token expired or invalid. Please update your Breeze session token. Error: {e}"
            elif 'connection' in error_str or 'timeout' in error_str:
                return False, f"Cannot connect to Breeze API. Please check your internet connection. Error: {e}"
            elif 'unauthorized' in error_str or 'forbidden' in error_str:
                return False, f"Authentication failed. Please check your API credentials. Error: {e}"
            else:
                return False, f"Failed to validate Breeze session: {e}"
    
    async def validate_kite_session(self) -> Tuple[bool, Optional[str]]:
        """
        Validates Kite Connect API session
        Returns: (is_valid, error_message)
        """
        try:
            # Reload environment to get latest
            from dotenv import load_dotenv
            load_dotenv(override=True)
            
            api_key = os.getenv('KITE_API_KEY')
            access_token = os.getenv('KITE_ACCESS_TOKEN')
            
            # Log what we found for debugging
            logger.info(f"Validating Kite - API Key: {api_key[:10] if api_key else 'None'}..., Access Token: {access_token[:10] if access_token else 'None'}...")
            
            if not api_key:
                return False, "Missing Kite API key in .env file"
            
            if not access_token:
                return False, "Missing Kite access token. Please run auto-login or generate a new token from https://kite.trade/connect/login"
            
            # Test with a simple API call
            url = f"https://api.kite.trade/user/profile"
            headers = {
                'X-Kite-Version': '3',
                'Authorization': f'token {api_key}:{access_token}'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        logger.info("Kite session validated successfully")
                        return True, None
                    elif response.status == 403:
                        return False, "Kite access token expired. Please generate a new token from https://kite.trade/connect/login"
                    else:
                        text = await response.text()
                        return False, f"Kite API error (status {response.status}): {text}"
                        
        except asyncio.TimeoutError:
            return False, "Kite API connection timeout. Please check your internet connection."
        except Exception as e:
            return False, f"Failed to validate Kite session: {e}"
    
    def get_session_update_instructions(self, api_type: str = "breeze") -> str:
        """Returns instructions for updating session token"""
        if api_type.lower() == "breeze":
            return """
To update your Breeze session token:
1. Login to Breeze at: https://api.icicidirect.com/apiuser/login
2. After login, copy the session token from the URL (apisession=XXXXXXXX)
3. Update the token using one of these methods:
   
   Method 1 - Using the update script:
   python update_breeze_session.py "https://api.icicidirect.com/apiuser/login?apisession=XXXXXXXX"
   
   Method 2 - Manual update in .env file:
   Open .env file and update: BREEZE_API_SESSION=XXXXXXXX
   
4. Restart the API server after updating
"""
        elif api_type.lower() == "kite":
            api_key = os.getenv('KITE_API_KEY', 'your_api_key')
            return f"""
To update your Kite access token:
1. Visit: https://kite.trade/connect/login?api_key={api_key}
2. Login with your Kite credentials
3. Copy the access token from the response
4. Update in .env file: KITE_ACCESS_TOKEN=your_new_token
5. Restart the API server after updating
"""
        else:
            return "Unknown API type"
    
    async def ensure_session_valid(self, api_type: str = "breeze") -> None:
        """
        Ensures session is valid, raises exception with instructions if not
        """
        if api_type.lower() == "breeze":
            is_valid, error = await self.validate_breeze_session()
        elif api_type.lower() == "kite":
            is_valid, error = await self.validate_kite_session()
        else:
            raise ValueError(f"Unknown API type: {api_type}")
        
        if not is_valid:
            instructions = self.get_session_update_instructions(api_type)
            raise ConnectionError(f"{error}\n\n{instructions}")
    
    def clear_cache(self):
        """Clears validation cache to force re-check"""
        self.last_check_time = None
        self.session_valid = False
        self.last_error = None

# Global session validator instance
_session_validator = None

def get_session_validator() -> SessionValidator:
    """Get or create global session validator instance"""
    global _session_validator
    if _session_validator is None:
        _session_validator = SessionValidator()
    return _session_validator

async def validate_before_api_call(api_type: str = "breeze") -> None:
    """
    Decorator/helper to validate session before API calls
    Usage: await validate_before_api_call() before any external API call
    """
    validator = get_session_validator()
    await validator.ensure_session_valid(api_type)