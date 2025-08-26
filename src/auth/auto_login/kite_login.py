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
from src.infrastructure.database.auth_repository import get_auth_repository
from src.auth.token_expiry_helper import get_kite_expiry

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
                logger.error("handle_2fa returned False")
                return False, "2FA authentication failed"
            else:
                logger.info("handle_2fa returned True - 2FA successful")
            
            # Wait for redirect after successful login with better error handling
            logger.info("Waiting for redirect to callback URL with request_token...")
            max_wait = 60  # Increased to 60 seconds to ensure we catch the redirect
            start_time = time.time()
            request_token = None
            last_url = ""
            
            while time.time() - start_time < max_wait:
                try:
                    current_url = self.driver.current_url
                    
                    # Only log if URL changed
                    if current_url != last_url:
                        logger.info(f"URL at {time.time() - start_time:.1f}s: {current_url}")
                        last_url = current_url
                    
                    # Multiple ways to check for request token
                    if 'request_token=' in current_url or 'request-token=' in current_url:
                        request_token = self.extract_request_token(current_url)
                        if request_token:
                            logger.info(f"✓ FOUND request token in URL after {time.time() - start_time:.1f}s")
                            logger.info(f"✓ Request token extracted: {request_token}")
                            break
                    
                    # Also check if we're on 127.0.0.1 or localhost which is the callback
                    if '127.0.0.1' in current_url or 'localhost' in current_url:
                        logger.info(f"✓ Reached callback URL: {current_url}")
                        request_token = self.extract_request_token(current_url)
                        if request_token:
                            logger.info(f"✓ Extracted token from callback: {request_token}")
                            break
                    
                    # Check JavaScript location in case browser location differs
                    try:
                        js_url = self.driver.execute_script("return window.location.href;")
                        if js_url != current_url and ("request_token=" in js_url or "localhost" in js_url):
                            logger.info(f"JS detected different URL: {js_url}")
                            request_token = self.extract_request_token(js_url)
                            if request_token:
                                logger.info(f"✓ Extracted token from JS URL: {request_token}")
                                break
                    except:
                        pass
                    
                    # Check for any error messages on the page
                    error_elements = self.driver.find_elements(By.CLASS_NAME, "error")
                    for error in error_elements:
                        if error.is_displayed() and error.text:
                            logger.error(f"Error on page: {error.text}")
                            self.take_screenshot("kite_error_on_page")
                            return False, f"Login error: {error.text}"
                    
                    time.sleep(1)  # Check every second
                except Exception as e:
                    logger.warning(f"Error while waiting for redirect: {e}")
                    time.sleep(1)
            
            # Final check for request token
            if not request_token:
                current_url = self.driver.current_url
                logger.warning(f"Token not found in loop, final URL: {current_url}")
                request_token = self.extract_request_token(current_url)
                
                # If still no token, take screenshot for debugging
                if not request_token:
                    self.take_screenshot("kite_no_token_found")
                    logger.error(f"Failed to find request_token in URL: {current_url}")
                    
                    # Try to get page source for debugging
                    try:
                        page_source = self.driver.page_source[:500]
                        logger.info(f"Page source snippet: {page_source}")
                    except:
                        pass
            
            if request_token:
                logger.info(f"✅ Successfully extracted request token: {request_token}")
                
                # Save request token to status file for debugging
                try:
                    import json
                    from datetime import datetime
                    status_file = Path("logs/kite_token_debug.json")
                    status_file.parent.mkdir(exist_ok=True)
                    with open(status_file, 'w') as f:
                        json.dump({
                            "timestamp": datetime.now().isoformat(),
                            "request_token": request_token,
                            "stage": "request_token_extracted"
                        }, f)
                except:
                    pass
                
                # Generate access token from request token
                logger.info("Generating access token from request token...")
                access_token = self.generate_access_token(request_token, credentials['api_secret'])
                
                if access_token:
                    logger.info(f"Successfully generated access token: {access_token[:20]}...")
                    
                    # CRITICAL: Update .env file FIRST (before validation to ensure it's saved)
                    env_updated = self.update_env_file(access_token)
                    if env_updated:
                        logger.info(f"✓ Successfully saved token to .env file: {access_token[:20]}...")
                        
                        # Verify it was actually saved
                        import os
                        from dotenv import load_dotenv
                        load_dotenv(override=True)
                        saved_token = os.getenv('KITE_ACCESS_TOKEN')
                        if saved_token == access_token:
                            logger.info("✓ Verified token is correctly saved in .env")
                        else:
                            logger.error(f"✗ Token mismatch! Saved: {saved_token[:20] if saved_token else 'None'}, Expected: {access_token[:20]}")
                    else:
                        logger.error("✗ Failed to update .env file with new token")
                    
                    # Clear any old cache before validation
                    cache_file = Path("logs/kite_auth_cache.json")
                    if cache_file.exists():
                        cache_file.unlink()
                        logger.info("✓ Cleared old cache before validation")
                    
                    # Validate the token
                    if self.validate_token(access_token):
                        logger.info("Token validation successful")
                        self.take_screenshot("kite_login_success")
                        
                        # Also save to credential manager
                        try:
                            self.credential_manager.save_kite_access_token(access_token)
                            logger.info("Token also saved to credential manager")
                        except Exception as e:
                            logger.warning(f"Could not save to credential manager: {e}")
                        
                        # Save to database with proper expiry
                        try:
                            auth_repo = get_auth_repository()
                            import os
                            from dotenv import load_dotenv
                            load_dotenv(override=True)
                            
                            expires_at = get_kite_expiry()
                            auth_repo.save_session(
                                service_type='kite',
                                access_token=access_token,
                                api_key=os.getenv('KITE_API_KEY'),
                                api_secret=os.getenv('KITE_API_SECRET'),
                                user_id=credentials.get('user_id'),
                                expires_at=expires_at
                            )
                            logger.info(f"Session saved to database with expiry: {expires_at}")
                        except Exception as e:
                            logger.warning(f"Could not save to database: {e}")
                        
                        return True, access_token
                    else:
                        logger.error("Generated token failed validation")
                        return False, "Generated token is invalid"
                else:
                    logger.error("Failed to generate access token from request token")
                    return False, "Failed to generate access token"
            else:
                self.take_screenshot("kite_error_no_token")
                return False, "Failed to extract request token"
                
        except Exception as e:
            logger.error(f"Kite login error: {e}")
            self.take_screenshot("kite_error_exception")
            return False, str(e)
        finally:
            # Add a delay before cleanup to ensure all operations complete
            time.sleep(2)
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
            # After login, Kite reuses the userid field for TOTP entry
            # Check if we're on the TOTP page by looking for the userid field with TOTP context
            time.sleep(2)  # Wait for page transition
            
            # Try to find the TOTP field - it might be userid or totp
            totp_field = None
            
            # First check if userid field exists and is for TOTP (after password submission)
            try:
                userid_field = self.driver.find_element(By.ID, "userid")
                # Check if it's for TOTP by checking placeholder or label
                placeholder = userid_field.get_attribute("placeholder")
                label = userid_field.get_attribute("label")
                field_type = userid_field.get_attribute("type")
                
                if (field_type == "number" or "totp" in label.lower() if label else False or 
                    "••••••" in placeholder if placeholder else False):
                    totp_field = userid_field
                    logger.info("Found TOTP field with id='userid'")
            except:
                pass
            
            # If not found, try other IDs
            if not totp_field:
                for field_id in ["totp", "pin", "totptoken", "token"]:
                    totp_field = self.wait_for_element(By.ID, field_id, timeout=2)
                    if totp_field:
                        logger.info(f"Found TOTP field with id='{field_id}'")
                        break
            
            if totp_field:
                totp = self.get_totp()
                if totp:
                    logger.info(f"Generated TOTP: {totp}")
                    
                    # Re-find the element to avoid stale reference
                    try:
                        totp_field = self.driver.find_element(By.ID, "userid")
                    except:
                        for field_id in ["totp", "pin", "totptoken", "token"]:
                            try:
                                totp_field = self.driver.find_element(By.ID, field_id)
                                break
                            except:
                                pass
                    
                    totp_field.clear()
                    time.sleep(0.5)
                    
                    # Enter TOTP all at once for numeric fields
                    totp_field.send_keys(str(totp))
                    time.sleep(0.5)
                    
                    # Verify it was entered
                    try:
                        entered_value = totp_field.get_attribute('value')
                        logger.info(f"Entered TOTP: {entered_value if entered_value else 'field appears empty'}")
                    except:
                        logger.info("Could not verify TOTP entry")
                    
                    # Submit TOTP - try multiple methods
                    time.sleep(1)
                    
                    # Method 1: Look for any visible submit button
                    buttons = self.driver.find_elements(By.TAG_NAME, "button")
                    submit_clicked = False
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            logger.info(f"Found button: '{btn.text}' - clicking...")
                            btn.click()
                            submit_clicked = True
                            break
                    
                    if not submit_clicked:
                        # Method 2: Try pressing Enter
                        logger.info("No button found, pressing Enter")
                        totp_field.send_keys(Keys.RETURN)
                    
                    # Wait longer for OTP submission to complete and check for redirect
                    logger.info("Waiting for OTP submission to complete...")
                    time.sleep(5)  # Initial wait
                    
                    # Check if we got redirected with request_token
                    current_url = self.driver.current_url
                    logger.info(f"URL after OTP submission: {current_url}")
                    
                    # Don't return yet - let the main function handle token extraction
                    return True
                elif not self.headless:
                    input("Please enter TOTP manually and submit, then press Enter to continue...")
                    return True
                else:
                    logger.error("TOTP required but not available")
                    return False
            
            # If no 2FA required
            logger.info("No 2FA field found - may not be required")
            return True
            
        except Exception as e:
            logger.error(f"2FA handling error: {e}")
            return False
    
    def get_totp(self) -> Optional[str]:
        """
        Get TOTP code for Kite 2FA with +60s offset
        Uses the NEXT interval's OTP to handle time sync issues
        
        Returns:
            TOTP code if available
        """
        totp_secret = self.credential_manager.get_kite_totp_secret()
        if totp_secret:
            try:
                import pyotp
                totp = pyotp.TOTP(totp_secret)
                
                # Generate OTP with +60 second offset (next interval)
                # This gives us the OTP that will be valid in the next time window
                future_time = time.time() + 60
                otp_code = totp.at(future_time)
                
                logger.info(f"Generated TOTP with +60s offset: {otp_code}")
                
                # Wait until we're in the 10-15 second window of the current 30-second period
                # This ensures we're using the OTP during its most stable period
                current_second = int(time.time()) % 30
                
                # Calculate wait time to reach the 10-15 second window
                if current_second < 10:
                    # We're before second 10, wait until second 10
                    wait_time = 10 - current_second
                    logger.info(f"Current second: {current_second}, waiting {wait_time}s to reach 10-15s window")
                    time.sleep(wait_time)
                elif current_second > 15:
                    # We're past second 15, wait for next cycle's 10-15 window
                    wait_time = (40 - current_second) % 30  # Wait until next cycle's second 10
                    logger.info(f"Current second: {current_second}, waiting {wait_time}s for next 10-15s window")
                    time.sleep(wait_time)
                else:
                    # We're already in the 10-15 second window
                    logger.info(f"Already in optimal window (second {current_second})")
                
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
        # Try multiple patterns
        patterns = [
            r'request_token=([^&]+)',
            r'request-token=([^&]+)',
            r'requestToken=([^&]+)',
            r'token=([^&]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                token = match.group(1)
                logger.info(f"✓ Token extracted with pattern '{pattern}': {token}")
                return token
        
        logger.warning(f"Could not extract token from URL: {url}")
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
            # Try multiple methods to generate access token
            
            # Method 1: Using kiteconnect library
            try:
                from kiteconnect import KiteConnect
                
                logger.info(f"Method 1: Using KiteConnect library")
                logger.info(f"API Key: {self.api_key}")
                logger.info(f"Request token: {request_token}")
                logger.info(f"API Secret length: {len(api_secret)}")
                
                kite = KiteConnect(api_key=self.api_key)
                
                # Generate session to get access token
                data = kite.generate_session(request_token, api_secret=api_secret)
                
                if data:
                    logger.info(f"✓ Session data received: {list(data.keys())}")
                    if 'access_token' in data:
                        access_token = data['access_token']
                        logger.info(f"✓✓ Access token generated: {access_token}")
                        
                        # IMMEDIATELY save it before anything else
                        logger.info("IMMEDIATELY saving token to .env...")
                        if self.update_env_file(access_token):
                            logger.info(f"✓✓✓ Token saved to .env: {access_token}")
                        
                        # Log user info
                        if 'user_name' in data:
                            logger.info(f"User: {data['user_name']}")
                        if 'user_id' in data:
                            logger.info(f"User ID: {data['user_id']}")
                        
                        return access_token
                    else:
                        logger.error(f"No access_token in response. Keys: {list(data.keys())}")
                        logger.error(f"Response: {data}")
                else:
                    logger.error("No data received from generate_session")
                    
            except Exception as e1:
                logger.error(f"Method 1 failed: {e1}")
                
                # Method 2: Direct API call
                logger.info("Method 2: Trying direct API call...")
                import hashlib
                import requests
                
                checksum = hashlib.sha256(
                    f"{self.api_key}{request_token}{api_secret}".encode()
                ).hexdigest()
                
                logger.info(f"Generated checksum: {checksum[:20]}...")
                
                response = requests.post(
                    "https://api.kite.trade/session/token",
                    data={
                        "api_key": self.api_key,
                        "request_token": request_token,
                        "checksum": checksum
                    },
                    headers={
                        "X-Kite-Version": "3",
                        "User-Agent": "Python/3.9"
                    },
                    timeout=10
                )
                
                logger.info(f"API Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and 'access_token' in data['data']:
                        access_token = data['data']['access_token']
                        logger.info(f"✓✓ Access token from API: {access_token}")
                        
                        # IMMEDIATELY save it
                        if self.update_env_file(access_token):
                            logger.info(f"✓✓✓ Token saved to .env: {access_token}")
                        
                        return access_token
                    else:
                        logger.error(f"Unexpected response format: {data}")
                else:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    
        except Exception as e:
            logger.error(f"Complete failure in generate_access_token: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
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
            
            # Reload environment variables
            from dotenv import load_dotenv
            load_dotenv(override=True)
            
            # Verify the token was saved
            import os
            saved_token = os.getenv('KITE_ACCESS_TOKEN')
            if saved_token == token:
                logger.info("Successfully updated and verified .env with new Kite access token")
                return True
            else:
                logger.error("Token was not properly saved to .env")
                return False
            
        except Exception as e:
            logger.error(f"Failed to update .env file: {e}")
            return False