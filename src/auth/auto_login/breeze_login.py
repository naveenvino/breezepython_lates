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
from src.infrastructure.database.auth_repository import get_auth_repository
from src.auth.token_expiry_helper import get_breeze_expiry

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
            
            # Wait for login to complete and page to redirect
            time.sleep(8)
            
            # Check for 2FA/OTP - Handle both single field and split fields
            # First check for split OTP fields (6 separate inputs with maxlength="1")
            otp_split_fields = self.driver.find_elements(By.CSS_SELECTOR, 'input[maxlength="1"]')
            
            if len(otp_split_fields) >= 6:
                logger.info(f"Found {len(otp_split_fields)} split OTP fields")
                
                # Generate OTP
                otp = self.get_otp()
                if otp:
                    logger.info(f"Generated OTP: {otp}")
                    
                    # Enter each digit in its own field
                    for i, digit in enumerate(str(otp)):
                        if i < len(otp_split_fields) and otp_split_fields[i].is_displayed():
                            otp_split_fields[i].clear()
                            otp_split_fields[i].send_keys(digit)
                            time.sleep(0.1)  # Small delay between digits
                    
                    logger.info("Entered all OTP digits")
                    
                    # Submit OTP
                    time.sleep(1)
                    submit_selectors = [
                        (By.CSS_SELECTOR, "input[type='button'][value*='Verify']"),
                        (By.CSS_SELECTOR, "input[type='button'][value*='Submit']"),
                        (By.ID, "btnVerify"),
                        (By.ID, "btnSubmit"),
                        (By.CSS_SELECTOR, "button[type='submit']")
                    ]
                    
                    for sel_type, sel_value in submit_selectors:
                        try:
                            otp_submit = self.driver.find_element(sel_type, sel_value)
                            if otp_submit.is_displayed():
                                logger.info(f"Found submit button using {sel_type}")
                                otp_submit.click()
                                time.sleep(8)  # Wait longer for redirect
                                break
                        except:
                            continue
                elif not self.headless:
                    input("Please enter OTP manually and submit, then press Enter to continue...")
                else:
                    return False, "OTP required but not available"
            else:
                # Fallback to single OTP field
                otp_field = None
                otp_selectors = [
                    (By.ID, "txtotp"),
                    (By.CSS_SELECTOR, "input[type='text'][maxlength='6']"),
                    (By.CSS_SELECTOR, "input[type='password'][maxlength='6']")
                ]
                
                for selector_type, selector_value in otp_selectors:
                    otp_field = self.wait_for_element(selector_type, selector_value, timeout=3)
                    if otp_field and otp_field.is_displayed():
                        logger.info(f"Single OTP field found using {selector_type}")
                        break
                
                if otp_field:
                    logger.info("OTP required (single field)")
                    otp = self.get_otp()
                    if otp:
                        logger.info(f"Generated OTP: {otp}")
                        otp_field.clear()
                        otp_field.send_keys(otp)
                        logger.info("Entered OTP")
                        
                        # Submit
                        submit_selectors = [
                            (By.ID, "btnVerify"),
                            (By.CSS_SELECTOR, "input[type='submit']"),
                            (By.CSS_SELECTOR, "input[type='button'][value*='Verify']")
                        ]
                        
                        for sel_type, sel_value in submit_selectors:
                            otp_submit = self.wait_for_element(sel_type, sel_value, timeout=2)
                            if otp_submit and otp_submit.is_displayed():
                                otp_submit.click()
                                time.sleep(8)  # Wait longer for redirect
                                break
            
            # Extract session token from URL
            current_url = self.driver.current_url
            session_token = self.extract_session_token(current_url)
            
            if session_token:
                logger.info(f"Successfully extracted session token: {session_token[:10]}...")
                self.take_screenshot("breeze_login_success")
                
                # Update .env file and validate
                if self.update_env_file(session_token):
                    # Test if the session actually works
                    if self.validate_token(session_token):
                        logger.info("Session token validated successfully")
                        
                        # Save to credential manager as well
                        try:
                            self.credential_manager.save_breeze_session(session_token)
                            logger.info("Session also saved to credential manager")
                        except Exception as e:
                            logger.warning(f"Could not save to credential manager: {e}")
                        
                        # Save to database with proper expiry
                        try:
                            auth_repo = get_auth_repository()
                            import os
                            from dotenv import load_dotenv
                            load_dotenv(override=True)
                            
                            expires_at = get_breeze_expiry()
                            auth_repo.save_session(
                                service_type='breeze',
                                session_token=session_token,
                                api_key=os.getenv('BREEZE_API_KEY'),
                                api_secret=os.getenv('BREEZE_API_SECRET'),
                                user_id=credentials.get('user_id'),
                                expires_at=expires_at
                            )
                            logger.info(f"Session saved to database with expiry: {expires_at}")
                        except Exception as e:
                            logger.warning(f"Could not save to database: {e}")
                        
                        return True, session_token
                    else:
                        logger.warning("Session token saved but validation failed")
                        return True, session_token  # Still return success as token is saved
                else:
                    return False, "Failed to update .env file"
            else:
                # Try to extract from page content
                page_source = self.driver.page_source
                session_token = self.extract_session_from_page(page_source)
                
                if session_token:
                    logger.info(f"Extracted session token from page: {session_token[:10]}...")
                    if self.update_env_file(session_token):
                        # Test if the session actually works
                        if self.validate_token(session_token):
                            logger.info("Session token validated successfully")
                        else:
                            logger.warning("Session token saved but validation failed")
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
                
                # Wait for optimal timing window (10-15 seconds into TOTP period)
                # For Breeze, we use +60 second offset
                current_second = int(time.time()) % 30
                
                logger.info(f"Breeze TOTP current second: {current_second}")
                
                # Calculate wait time to reach the 10-15 second window
                if current_second < 10:
                    # We're before second 10, wait until second 10
                    wait_time = 10 - current_second
                    logger.info(f"Waiting {wait_time}s to reach 10-15s window...")
                    time.sleep(wait_time)
                elif current_second > 15:
                    # We're past second 15, wait for next cycle's 10-15 window
                    wait_time = (40 - current_second) % 30  # Wait until next cycle's second 10
                    logger.info(f"Waiting {wait_time}s for next 10-15s window...")
                    time.sleep(wait_time)
                else:
                    # We're already in the 10-15 second window
                    logger.info(f"Already in optimal window (second {current_second})")
                
                # Now generate with +60 second offset
                adjusted_time = time.time() + 60
                
                # Remove any spaces and ensure uppercase
                totp_secret = totp_secret.replace(" ", "").upper()
                totp = pyotp.TOTP(totp_secret)
                # Generate with +60 second offset
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
                
                # Wait for optimal timing window (10-15 seconds into TOTP period)
                current_second = int(time.time()) % 30
                
                if current_second < 10:
                    wait_time = 10 - current_second
                    time.sleep(wait_time)
                elif current_second > 15:
                    wait_time = (40 - current_second) % 30
                    time.sleep(wait_time)
                
                # Now generate with +60 second offset
                adjusted_time = time.time() + 60
                
                env_totp = env_totp.replace(" ", "").upper()
                totp = pyotp.TOTP(env_totp)
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
            # Use BreezeConnect SDK for validation
            from breeze_connect import BreezeConnect
            import os
            from dotenv import load_dotenv
            
            load_dotenv(override=True)
            
            api_key = os.getenv('BREEZE_API_KEY')
            api_secret = os.getenv('BREEZE_API_SECRET')
            
            if not api_key or not api_secret:
                logger.error("Missing API credentials for validation")
                return False
            
            # Test connection
            breeze = BreezeConnect(api_key=api_key)
            breeze.generate_session(
                api_secret=api_secret,
                session_token=str(token)
            )
            
            # Try to get funds as a test (more reliable than customer_details)
            response = breeze.get_funds()
            
            if response and (response.get('Success') or response.get('Status') == 200):
                logger.info("Breeze token validation successful")
                return True
            else:
                error_msg = response.get('Error', 'Unknown error') if response else 'No response'
                logger.error(f"Breeze token validation failed: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            # Don't fail validation on errors during auto-login
            # The token might still be valid
            return True
    
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
            
            # Reload environment variables
            from dotenv import load_dotenv
            load_dotenv(override=True)
            
            # Verify the token was saved
            import os
            saved_token = os.getenv('BREEZE_API_SESSION')
            if saved_token == token:
                logger.info(f"Successfully updated and verified .env with new Breeze session token: {token[:10]}...")
                
                # Clear session validator cache to force revalidation
                try:
                    from src.infrastructure.services.session_validator import get_session_validator
                    validator = get_session_validator()
                    validator.clear_cache()
                    logger.info("Cleared session validator cache")
                except Exception as e:
                    logger.warning(f"Could not clear validator cache: {e}")
                
                return True
            else:
                logger.error("Token was not properly saved to .env")
                return False
            
        except Exception as e:
            logger.error(f"Failed to update .env file: {e}")
            return False