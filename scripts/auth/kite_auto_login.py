"""
Kite Login - Final Working Version
"""
import sys
import os
from pathlib import Path
import time

sys.path.append(str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import pyotp
from dotenv import load_dotenv

load_dotenv(override=True)

print("=" * 60)
print("KITE LOGIN - FINAL WORKING VERSION")
print("=" * 60)

# Get credentials
kite_user = os.getenv('KITE_USER_ID')
kite_pass = os.getenv('KITE_PASSWORD')
kite_totp_secret = os.getenv('KITE_TOTP_SECRET')
api_key = os.getenv('KITE_API_KEY', 'a3vacbrbn3fs98ie')
api_secret = os.getenv('KITE_API_SECRET', 'zy2zaws481kifjmsv3v6pchu13ng2cbz')

print(f"\n✓ User: {kite_user}")
print(f"✓ API Key: {api_key}")

# Setup TOTP with +60s offset (confirmed working)
totp = pyotp.TOTP(kite_totp_secret)
current_otp = totp.at(time.time() + 60)
print(f"✓ TOTP (with +60s offset): {current_otp}")

# Setup Chrome - Visible mode to debug
options = Options()
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
# Keep visible to see what's happening
# options.add_argument('--headless')

print("✓ Mode: Visible (for debugging)")
print("\n⚠️ Only 2 attempts left before account lock!")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

try:
    # Navigate to Kite Connect login
    login_url = f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
    print(f"\n1. Opening Kite Connect login page...")
    driver.get(login_url)
    time.sleep(3)
    
    print("2. Entering credentials on first page...")
    
    # Wait for login form to be ready
    wait.until(EC.presence_of_element_located((By.ID, "userid")))
    
    # User ID
    user_field = driver.find_element(By.ID, "userid")
    user_field.clear()
    user_field.send_keys(kite_user)
    print(f"   ✓ Entered User ID: {kite_user}")
    
    # Password
    pass_field = driver.find_element(By.ID, "password")
    pass_field.clear()
    pass_field.send_keys(kite_pass)
    print("   ✓ Entered Password")
    
    # Click login
    print("3. Clicking login button...")
    login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
    driver.execute_script("arguments[0].click();", login_button)  # Use JavaScript click
    
    # Wait for page transition
    print("\n4. Waiting for 2FA page...")
    time.sleep(5)
    
    # Wait for page to fully load
    wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
    
    print("5. Looking for TOTP field on 2FA page...")
    
    # The TOTP field appears as a different element on the 2FA page
    # It might still have id="userid" but on a different page context
    totp_field = None
    
    # Try to find the input field that's visible and enabled
    input_fields = driver.find_elements(By.TAG_NAME, "input")
    for field in input_fields:
        if field.is_displayed() and field.is_enabled():
            field_type = field.get_attribute("type")
            field_id = field.get_attribute("id")
            field_placeholder = field.get_attribute("placeholder")
            print(f"   Found input: type={field_type}, id={field_id}, placeholder={field_placeholder}")
            
            # The TOTP field is usually type="number" or type="text"
            if field_type in ["number", "text", "tel"]:
                totp_field = field
                print("   ✓ Using this as TOTP field")
                break
    
    if totp_field:
        # Generate fresh TOTP with +60s offset
        current_otp = totp.at(time.time() + 60)
        print(f"\n6. Entering TOTP: {current_otp}")
        
        # Method 1: JavaScript to set value directly
        driver.execute_script(f"arguments[0].value = '{current_otp}';", totp_field)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", totp_field)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", totp_field)
        
        # Verify it was set
        entered_value = totp_field.get_attribute("value")
        print(f"   Value after JS set: {entered_value}")
        
        # If JavaScript didn't work, try regular typing
        if entered_value != current_otp:
            print("   JS didn't work, trying regular typing...")
            totp_field.click()
            totp_field.clear()
            totp_field.send_keys(current_otp)
            
            # Double-check
            entered_value = totp_field.get_attribute("value")
            print(f"   Value after typing: {entered_value}")
        
        # Take screenshot to verify
        driver.save_screenshot("kite_totp_entered.png")
        print("   Screenshot saved: kite_totp_entered.png")
        
        # Wait a moment
        time.sleep(1)
        
        # Find and click Continue button
        print("\n7. Looking for Continue button...")
        
        # Try multiple ways to find the button
        continue_button = None
        button_selectors = [
            "//button[contains(text(), 'Continue')]",
            "//button[@type='submit']",
            "//button[contains(@class, 'button')]",
            "//input[@type='submit']"
        ]
        
        for selector in button_selectors:
            try:
                btn = driver.find_element(By.XPATH, selector)
                if btn.is_displayed() and btn.is_enabled():
                    continue_button = btn
                    print(f"   ✓ Found button with selector: {selector}")
                    break
            except:
                continue
        
        if continue_button:
            # Click using JavaScript to ensure it works
            driver.execute_script("arguments[0].click();", continue_button)
            print("   ✓ Clicked Continue button")
        else:
            print("   ⚠️ Continue button not found, trying Enter key...")
            totp_field.send_keys(Keys.RETURN)
        
        # Wait for response
        print("\n8. Waiting for response...")
        time.sleep(6)
        
        # Check current URL
        current_url = driver.current_url
        print(f"   Current URL: {current_url}")
        
        # Take screenshot
        driver.save_screenshot("kite_after_submit.png")
        print("   Screenshot saved: kite_after_submit.png")
        
        # Check for authorization page
        print("\n9. Checking for authorization page...")
        try:
            authorize_btn = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//button[contains(text(), 'Authorize')]")
            ), timeout=5)
            print("   ✅ Found Authorization page - TOTP worked!")
            driver.execute_script("arguments[0].click();", authorize_btn)
            print("   ✓ Clicked Authorize")
            time.sleep(5)
            
            # Get final URL
            final_url = driver.current_url
            print(f"\n10. Final URL: {final_url}")
            
            # Look for request token
            import re
            match = re.search(r'request_token=([^&]+)', final_url)
            if match:
                request_token = match.group(1)
                print(f"\n✅ SUCCESS! Got request token: {request_token}")
                
                # Exchange for access token
                print("\n11. Exchanging for access token...")
                
                import hashlib
                import requests
                
                checksum = hashlib.sha256(
                    f"{api_key}{request_token}{api_secret}".encode()
                ).hexdigest()
                
                data = {
                    "api_key": api_key,
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
                    access_token = result.get("data", {}).get("access_token")
                    if access_token:
                        print(f"✅ Got access token: {access_token}")
                        
                        # Save to .env
                        env_path = Path(".env")
                        with open(env_path, 'r') as f:
                            lines = f.readlines()
                        
                        new_lines = []
                        token_found = False
                        for line in lines:
                            if line.startswith('KITE_ACCESS_TOKEN='):
                                new_lines.append(f'KITE_ACCESS_TOKEN={access_token}\n')
                                token_found = True
                            else:
                                new_lines.append(line)
                        
                        if not token_found:
                            for i, line in enumerate(new_lines):
                                if line.startswith('KITE_PASSWORD='):
                                    new_lines.insert(i + 1, f'KITE_ACCESS_TOKEN={access_token}\n')
                                    break
                        
                        with open(env_path, 'w') as f:
                            f.writelines(new_lines)
                        
                        print("\n" + "=" * 60)
                        print("🎉 KITE LOGIN SUCCESSFUL!")
                        print("=" * 60)
                        print("✅ TOTP with +60s offset worked!")
                        print("✅ Access token saved to .env")
        except:
            print("   No Authorization page yet")
            
            # Check for error message
            try:
                error = driver.find_element(By.XPATH, "//*[contains(text(), 'Invalid')]")
                print(f"\n❌ Error on page: {error.text}")
            except:
                print("   No error message found")
    else:
        print("   ❌ Could not find TOTP field")
    
    print("\n" + "=" * 60)
    print("Browser is open - check what happened")
    print("=" * 60)
    input("\nPress Enter to close browser...")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    driver.save_screenshot("kite_error.png")
    input("\nPress Enter to close browser...")
    
finally:
    driver.quit()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)