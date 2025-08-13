"""
Automated login for Breeze API (ICICI Direct)
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

class BreezeAutoLogin(BaseAutoLogin):
    """
    Automated login handler for Breeze API
    """
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        super().__init__(headless, timeout)
        # Get API key from env
        import os
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv('BREEZE_API_KEY', 'w5905l77Q7Xb7138$7149Y9R40u0908I')
        self.login_url = f"https://api.icicidirect.com/apiuser/login?api_key={api_key}"
        self.credential_manager = CredentialManager()
        
    def login(self) -> Tuple[bool, Optional[str]]:
        """
        Perform automated login to Breeze API
        
        Returns:
            Tuple of (success: bool, session_token or error_message: str)
        """
        try:
            # Get credentials
            credentials = self.credential_manager.get_breeze_credentials()
            if not credentials:
                return False, "Breeze credentials not found"
            
            # Setup driver
            if not self.setup_driver():
                return False, "Failed to setup WebDriver"
            
            logger.info("Starting Breeze automated login...")
            
            # Navigate to login page
            self.driver.get(self.login_url)
            time.sleep(2)  # Wait for page load
            
            # Take screenshot for debugging
            self.take_screenshot("breeze_login_page")
            
            # Enter User ID
            user_id_field = self.wait_for_element(By.ID, "txtuid")
            
            if user_id_field:
                user_id_field.clear()
                user_id_field.send_keys(credentials['user_id'])
                logger.info("Entered User ID")
            else:
                self.take_screenshot("breeze_error_no_userid")
                return False, "User ID field not found"
            
            # Enter Password
            password_field = self.wait_for_element(By.ID, "txtPass")
            
            if password_field:
                password_field.clear()
                password_field.send_keys(credentials['password'])
                logger.info("Entered Password")
            else:
                self.take_screenshot("breeze_error_no_password")
                return False, "Password field not found"
            
            # Check Terms and Conditions checkbox
            tnc_checkbox = self.wait_for_element(By.ID, "chkssTnc", timeout=3)
            if tnc_checkbox:
                if not tnc_checkbox.is_selected():
                    tnc_checkbox.click()
                    logger.info("Checked Terms and Conditions")
            
            # Handle CAPTCHA if present (manual intervention may be needed)
            captcha_field = self.wait_for_element(By.ID, "txtcaptcha", timeout=3)
            if captcha_field:
                logger.warning("CAPTCHA detected - manual intervention may be required")
                self.take_screenshot("breeze_captcha_required")
                
                # If running in non-headless mode, wait for user to enter CAPTCHA
                if not self.headless:
                    input("Please enter CAPTCHA manually and press Enter to continue...")
            
            # Click Login button (it's an input with type='button')
            login_button = self.wait_for_element(By.ID, "btnSubmit")
            
            if login_button:
                login_button.click()
                logger.info("Clicked login button")
            else:
                self.take_screenshot("breeze_error_no_login_button")
                return False, "Login button not found"
            
            # Wait for login to complete
            time.sleep(5)
            
            # Check for 2FA/OTP
            otp_field = self.wait_for_element(By.ID, "txtotp", timeout=5)
            if otp_field:
                logger.info("OTP required")
                
                # Try to get OTP from email/SMS monitor (if configured)
                otp = self.get_otp()
                if otp:
                    otp_field.clear()
                    otp_field.send_keys(otp)
                    
                    # Submit OTP
                    otp_submit = self.wait_for_element(By.ID, "btnVerify")
                    if otp_submit:
                        otp_submit.click()
                        time.sleep(3)
                elif not self.headless:
                    # Manual OTP entry
                    input("Please enter OTP manually and submit, then press Enter to continue...")
                else:
                    return False, "OTP required but not available"
            
            # Extract session token from URL
            current_url = self.driver.current_url
            session_token = self.extract_session_token(current_url)
            
            if session_token:
                logger.info(f"Successfully extracted session token: {session_token[:10]}...")
                self.take_screenshot("breeze_login_success")
                
                # Update .env file
                if self.update_env_file(session_token):
                    return True, session_token
                else:
                    return False, "Failed to update .env file"
            else:
                # Try to extract from page content
                page_source = self.driver.page_source
                session_token = self.extract_session_from_page(page_source)
                
                if session_token:
                    logger.info(f"Extracted session token from page: {session_token[:10]}...")
                    if self.update_env_file(session_token):
                        return True, session_token
                
                self.take_screenshot("breeze_error_no_token")
                return False, "Failed to extract session token"
                
        except Exception as e:
            logger.error(f"Breeze login error: {e}")
            self.take_screenshot("breeze_error_exception")
            return False, str(e)
        finally:
            self.cleanup_driver()
    
    def extract_session_token(self, url: str) -> Optional[str]:
        """
        Extract session token from URL
        
        Args:
            url: URL containing session token
            
        Returns:
            Session token if found
        """
        match = re.search(r'apisession=(\d+)', url)
        if match:
            return match.group(1)
        return None
    
    def extract_session_from_page(self, page_source: str) -> Optional[str]:
        """
        Extract session token from page content
        
        Args:
            page_source: HTML page source
            
        Returns:
            Session token if found
        """
        # Look for session token in various places
        patterns = [
            r'session["\']?\s*[:=]\s*["\']?(\d+)',
            r'apisession["\']?\s*[:=]\s*["\']?(\d+)',
            r'token["\']?\s*[:=]\s*["\']?(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, page_source, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def get_otp(self) -> Optional[str]:
        """
        Get OTP from configured source (email/SMS/TOTP)
        
        Returns:
            OTP code if available
        """
        # Check if TOTP is configured
        totp_secret = self.credential_manager.get_breeze_totp_secret()
        if totp_secret:
            try:
                import pyotp
                import time
                # Remove any spaces and ensure uppercase
                totp_secret = totp_secret.replace(" ", "").upper()
                totp = pyotp.TOTP(totp_secret)
                # Apply +60 second offset (system is 60 seconds behind)
                adjusted_time = time.time() + 60
                otp_code = totp.at(adjusted_time)
                logger.info(f"Generated TOTP with +60s offset: {otp_code}")
                return otp_code
            except Exception as e:
                logger.error(f"Failed to generate TOTP: {e}")
        
        # Check .env directly as well
        import os
        from dotenv import load_dotenv
        load_dotenv(override=True)
        env_totp = os.getenv('BREEZE_TOTP_SECRET')
        if env_totp:
            try:
                import pyotp
                import time
                env_totp = env_totp.replace(" ", "").upper()
                totp = pyotp.TOTP(env_totp)
                # Apply +60 second offset (system is 60 seconds behind)
                adjusted_time = time.time() + 60
                otp_code = totp.at(adjusted_time)
                logger.info(f"Generated TOTP from .env with +60s offset: {otp_code}")
                return otp_code
            except Exception as e:
                logger.error(f"Failed to generate TOTP from .env: {e}")
        
        logger.warning("No TOTP secret configured, OTP will need manual entry")
        return None
    
    def validate_token(self, token: str) -> bool:
        """
        Validate if the Breeze session token is working
        
        Args:
            token: Session token to validate
            
        Returns:
            True if token is valid
        """
        try:
            import requests
            
            headers = {
                "X-SessionToken": token,
                "X-AppKey": self.credential_manager.get_breeze_api_key()
            }
            
            # Test API endpoint
            response = requests.get(
                "https://api.icicidirect.com/breezeapi/api/v1/customerdetails",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Breeze token validation successful")
                return True
            else:
                logger.error(f"Breeze token validation failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False
    
    def update_env_file(self, token: str) -> bool:
        """
        Update .env file with new Breeze session token
        
        Args:
            token: New session token
            
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
            
            # Update BREEZE_API_SESSION
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('BREEZE_API_SESSION='):
                    lines[i] = f'BREEZE_API_SESSION={token}'
                    updated = True
                    break
            
            if not updated:
                lines.append(f'BREEZE_API_SESSION={token}')
            
            # Write back
            env_path.write_text('\n'.join(lines) + '\n')
            
            logger.info("Successfully updated .env with new Breeze session token")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update .env file: {e}")
            return False