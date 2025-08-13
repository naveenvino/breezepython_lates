"""
Kite Auto-Login Service for API
"""
import os
import sys
import time
import pyotp
import hashlib
import requests
from pathlib import Path
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class KiteAutoLoginService:
    def __init__(self):
        load_dotenv(override=True)
        self.api_key = os.getenv('KITE_API_KEY', 'a3vacbrbn3fs98ie')
        self.api_secret = os.getenv('KITE_API_SECRET', 'zy2zaws481kifjmsv3v6pchu13ng2cbz')
        self.user_id = os.getenv('KITE_USER_ID', 'JR1507')
        self.password = os.getenv('KITE_PASSWORD', 'Vinoth@123')
        self.totp_secret = os.getenv('KITE_TOTP_SECRET', 'JGBTL6LWZHPCZK4NSWEDZNECWGC2SAVQ')
        
    def generate_totp(self):
        totp = pyotp.TOTP(self.totp_secret)
        adjusted_time = time.time() + 60
        return totp.at(adjusted_time)
    
    def is_connected(self):
        access_token = os.getenv('KITE_ACCESS_TOKEN', '')
        if not access_token:
            return False
            
        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{access_token}"
        }
        
        try:
            response = requests.get(
                "https://api.kite.trade/user/profile",
                headers=headers,
                timeout=5
            )
            # Check if we get a successful response
            if response.status_code == 200:
                data = response.json()
                # Verify it's actually successful
                return data.get('status') == 'success'
            return False
        except:
            return False
    
    def auto_login(self):
        if self.is_connected():
            return {"status": "already_connected", "message": "Kite is already connected"}
        
        driver = None
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            wait = WebDriverWait(driver, 10)
            
            # Step 1: Open login page
            login_url = f"https://kite.zerodha.com/connect/login?api_key={self.api_key}"
            driver.get(login_url)
            time.sleep(2)
            
            # Step 2: Enter credentials
            userid_field = wait.until(EC.presence_of_element_located((By.ID, "userid")))
            userid_field.send_keys(self.user_id)
            
            password_field = driver.find_element(By.ID, "password")
            password_field.send_keys(self.password)
            
            login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Step 3: Wait for TOTP page
            time.sleep(3)
            
            # Step 4: Enter TOTP
            current_otp = self.generate_totp()
            
            totp_selectors = [
                "//input[@type='number' and @placeholder='••••••']",
                "//input[@type='tel' and @placeholder='••••••']",
                "//input[@id='userid']",
                "//input[@type='number']",
                "//input[@type='tel']"
            ]
            
            totp_field = None
            for selector in totp_selectors:
                try:
                    elements = driver.find_elements(By.XPATH, selector)
                    if elements:
                        totp_field = elements[0]
                        break
                except:
                    continue
            
            if totp_field:
                driver.execute_script(f"arguments[0].value = '{current_otp}';", totp_field)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", totp_field)
                
                continue_button = driver.find_element(By.XPATH, "//button[contains(@class, 'button')]")
                continue_button.click()
                
                # Step 5: Wait for redirect
                time.sleep(3)
                
                current_url = driver.current_url
                if "request_token=" in current_url:
                    # Extract request token
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(current_url)
                    params = parse_qs(parsed.query)
                    request_token = params.get('request_token', [''])[0]
                    
                    if request_token:
                        # Exchange for access token
                        checksum = hashlib.sha256(
                            f"{self.api_key}{request_token}{self.api_secret}".encode()
                        ).hexdigest()
                        
                        data = {
                            "api_key": self.api_key,
                            "request_token": request_token,
                            "checksum": checksum
                        }
                        
                        response = requests.post(
                            "https://api.kite.trade/session/token",
                            data=data,
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            if result.get('status') == 'success':
                                access_token = result.get('data', {}).get('access_token')
                                user_name = result.get('data', {}).get('user_name')
                                
                                if access_token:
                                    # Update .env file
                                    env_path = Path(".env")
                                    if env_path.exists():
                                        with open(env_path, 'r') as f:
                                            lines = f.readlines()
                                        
                                        new_lines = []
                                        token_updated = False
                                        
                                        for line in lines:
                                            if line.startswith('KITE_ACCESS_TOKEN='):
                                                new_lines.append(f'KITE_ACCESS_TOKEN={access_token}\n')
                                                token_updated = True
                                            else:
                                                new_lines.append(line)
                                        
                                        if not token_updated:
                                            for i, line in enumerate(new_lines):
                                                if line.startswith('KITE_API_SECRET='):
                                                    new_lines.insert(i + 1, f'KITE_ACCESS_TOKEN={access_token}\n')
                                                    break
                                        
                                        with open(env_path, 'w') as f:
                                            f.writelines(new_lines)
                                        
                                        # Reload environment
                                        load_dotenv(override=True)
                                        
                                        return {
                                            "status": "success",
                                            "message": f"Successfully logged in as {user_name}",
                                            "access_token": access_token[:20] + "...",
                                            "user_name": user_name
                                        }
            
            return {"status": "error", "message": "Failed to complete login process"}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            if driver:
                driver.quit()