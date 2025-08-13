"""
Automated login for Kite API (Zerodha)
"""
import logging
import re
import time
from typing import Optional, Tuple
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .base_login import BaseAutoLogin
from .credential_manager import CredentialManager

logger = logging.getLogger(__name__)

class KiteAutoLogin(BaseAutoLogin):
    """
    Automated login handler for Kite API
    """
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        super().__init__(headless, timeout)
        self.credential_manager = CredentialManager()
        self.api_key = self.credential_manager.get_kite_api_key()
        self.login_url = f"https://kite.zerodha.com/connect/login?api_key={self.api_key}&v=3"
        
    def login(self) -> Tuple[bool, Optional[str]]:
        """
        Perform automated login to Kite API
        
        Returns:
            Tuple of (success: bool, access_token or error_message: str)
        """
        try:
            # Get credentials
            credentials = self.credential_manager.get_kite_credentials()
            if not credentials:
                return False, "Kite credentials not found"
            
            # Setup driver
            if not self.setup_driver():
                return False, "Failed to setup WebDriver"
            
            logger.info("Starting Kite automated login...")
            
            # Navigate to login page
            self.driver.get(self.login_url)
            time.sleep(3)  # Wait for page load
            
            # Take screenshot for debugging
            self.take_screenshot("kite_login_page")
            
            # Enter User ID (Zerodha client ID)
            user_id_field = self.wait_for_element(By.ID, "userid")
            if not user_id_field:
                user_id_field = self.wait_for_element(By.XPATH, "//input[@type='text']")
            
            if user_id_field:
                user_id_field.clear()
                user_id_field.send_keys(credentials['user_id'])
                logger.info("Entered User ID")
            else:
                self.take_screenshot("kite_error_no_userid")
                return False, "User ID field not found"
            
            # Enter Password
            password_field = self.wait_for_element(By.ID, "password")
            if not password_field:
                password_field = self.wait_for_element(By.XPATH, "//input[@type='password']")
            
            if password_field:
                password_field.clear()
                password_field.send_keys(credentials['password'])
                logger.info("Entered Password")
            else:
                self.take_screenshot("kite_error_no_password")
                return False, "Password field not found"
            
            # Click Login button
            login_button = self.wait_for_element(By.XPATH, "//button[@type='submit']")
            if login_button:
                login_button.click()
                logger.info("Clicked login button")
            else:
                self.take_screenshot("kite_error_no_login_button")
                return False, "Login button not found"
            
            # Wait for 2FA page
            time.sleep(3)
            
            # Handle 2FA (PIN or TOTP)
            success = self.handle_2fa(credentials)
            if not success:
                return False, "2FA authentication failed"
            
            # Wait for redirect after successful login
            time.sleep(5)
            
            # Extract request token from URL
            current_url = self.driver.current_url
            request_token = self.extract_request_token(current_url)
            
            if request_token:
                logger.info(f"Successfully extracted request token: {request_token[:10]}...")
                
                # Generate access token from request token
                access_token = self.generate_access_token(request_token, credentials['api_secret'])
                
                if access_token:
                    logger.info(f"Successfully generated access token: {access_token[:10]}...")
                    self.take_screenshot("kite_login_success")
                    
                    # Update .env file
                    if self.update_env_file(access_token):
                        return True, access_token
                    else:
                        return False, "Failed to update .env file"
                else:
                    return False, "Failed to generate access token"
            else:
                self.take_screenshot("kite_error_no_token")
                return False, "Failed to extract request token"
                
        except Exception as e:
            logger.error(f"Kite login error: {e}")
            self.take_screenshot("kite_error_exception")
            return False, str(e)
        finally:
            self.cleanup_driver()
    
    def handle_2fa(self, credentials: dict) -> bool:
        """
        Handle Kite 2FA (PIN or TOTP)
        
        Args:
            credentials: User credentials dictionary
            
        Returns:
            True if 2FA successful
        """
        try:
            # Check if PIN field is present
            pin_field = self.wait_for_element(By.ID, "pin", timeout=5)
            if pin_field:
                if 'pin' in credentials:
                    pin_field.clear()
                    pin_field.send_keys(credentials['pin'])
                    logger.info("Entered PIN")
                    
                    # Submit PIN
                    submit_button = self.wait_for_element(By.XPATH, "//button[@type='submit']")
                    if submit_button:
                        submit_button.click()
                        time.sleep(3)
                        return True
                elif not self.headless:
                    input("Please enter PIN manually and submit, then press Enter to continue...")
                    return True
                else:
                    logger.error("PIN required but not available")
                    return False
            
            # Check if TOTP field is present
            totp_field = self.wait_for_element(By.ID, "totp", timeout=5)
            if totp_field:
                totp = self.get_totp()
                if totp:
                    totp_field.clear()
                    totp_field.send_keys(totp)
                    logger.info("Entered TOTP")
                    
                    # Submit TOTP
                    submit_button = self.wait_for_element(By.XPATH, "//button[@type='submit']")
                    if submit_button:
                        submit_button.click()
                        time.sleep(3)
                        return True
                elif not self.headless:
                    input("Please enter TOTP manually and submit, then press Enter to continue...")
                    return True
                else:
                    logger.error("TOTP required but not available")
                    return False
            
            # If no 2FA required
            logger.info("No 2FA required or already authenticated")
            return True
            
        except Exception as e:
            logger.error(f"2FA handling error: {e}")
            return False
    
    def get_totp(self) -> Optional[str]:
        """
        Get TOTP code for Kite 2FA
        
        Returns:
            TOTP code if available
        """
        totp_secret = self.credential_manager.get_kite_totp_secret()
        if totp_secret:
            try:
                import pyotp
                totp = pyotp.TOTP(totp_secret)
                otp_code = totp.now()
                logger.info(f"Generated TOTP: {otp_code}")
                return otp_code
            except Exception as e:
                logger.error(f"Failed to generate TOTP: {e}")
        
        return None
    
    def extract_request_token(self, url: str) -> Optional[str]:
        """
        Extract request token from URL after successful login
        
        Args:
            url: URL containing request token
            
        Returns:
            Request token if found
        """
        match = re.search(r'request_token=([^&]+)', url)
        if match:
            return match.group(1)
        return None
    
    def generate_access_token(self, request_token: str, api_secret: str) -> Optional[str]:
        """
        Generate access token from request token
        
        Args:
            request_token: Request token from login
            api_secret: Kite API secret
            
        Returns:
            Access token if successful
        """
        try:
            from kiteconnect import KiteConnect
            
            kite = KiteConnect(api_key=self.api_key)
            data = kite.generate_session(request_token, api_secret=api_secret)
            
            if data and 'access_token' in data:
                return data['access_token']
            
        except Exception as e:
            logger.error(f"Failed to generate access token: {e}")
        
        return None
    
    def validate_token(self, token: str) -> bool:
        """
        Validate if the Kite access token is working
        
        Args:
            token: Access token to validate
            
        Returns:
            True if token is valid
        """
        try:
            from kiteconnect import KiteConnect
            
            kite = KiteConnect(api_key=self.api_key)
            kite.set_access_token(token)
            
            # Try to fetch profile to validate token
            profile = kite.profile()
            
            if profile:
                logger.info(f"Kite token validation successful for user: {profile.get('user_id')}")
                return True
            else:
                logger.error("Kite token validation failed")
                return False
                
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False
    
    def update_env_file(self, token: str) -> bool:
        """
        Update .env file with new Kite access token
        
        Args:
            token: New access token
            
        Returns:
            True if update successful
        """
        try:
            env_path = Path(".env")
            
            if not env_path.exists():
                logger.error(".env file not found")
                return False
            
            # Read current content
            lines = env_path.read_text().splitlines()
            
            # Update KITE_ACCESS_TOKEN
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('KITE_ACCESS_TOKEN='):
                    lines[i] = f'KITE_ACCESS_TOKEN={token}'
                    updated = True
                    break
            
            if not updated:
                lines.append(f'KITE_ACCESS_TOKEN={token}')
            
            # Write back
            env_path.write_text('\n'.join(lines) + '\n')
            
            logger.info("Successfully updated .env with new Kite access token")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update .env file: {e}")
            return False