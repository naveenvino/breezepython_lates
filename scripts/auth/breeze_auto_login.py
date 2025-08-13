"""
Login with CORRECT time offset (+60 seconds)
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
import pyotp
from dotenv import load_dotenv

load_dotenv(override=True)

print("=" * 60)
print("BREEZE LOGIN WITH CORRECT TIME OFFSET")
print("=" * 60)

# Get credentials
breeze_user = os.getenv('BREEZE_USER_ID')
breeze_pass = os.getenv('BREEZE_PASSWORD')
totp_secret = os.getenv('BREEZE_TOTP_SECRET')
api_key = os.getenv('BREEZE_API_KEY', 'w5905l77Q7Xb7138$7149Y9R40u0908I')

print(f"\n✓ User: {breeze_user}")

# CORRECT time offset - your system is 60 seconds behind
time_offset = +60  # 60 seconds ahead (what Google Auth shows)
print(f"✓ Using time offset: +{time_offset} seconds")
print("  (Your system time is 60 seconds behind)")

# Generate OTP with offset
totp = pyotp.TOTP(totp_secret)
adjusted_time = time.time() + time_offset
current_otp = totp.at(adjusted_time)
print(f"✓ Generated OTP: {current_otp}")
print("  (This should match your Google Authenticator)")

# Setup Chrome (headless)
options = Options()
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--headless')

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 10)

try:
    # Navigate to login
    login_url = f"https://api.icicidirect.com/apiuser/login?api_key={api_key}"
    print(f"\n1. Navigating to login page...")
    driver.get(login_url)
    time.sleep(2)
    
    # Fill credentials
    print("2. Entering credentials...")
    user_field = wait.until(EC.presence_of_element_located((By.ID, "txtuid")))
    user_field.clear()
    user_field.send_keys(breeze_user)
    
    pass_field = driver.find_element(By.ID, "txtPass")
    pass_field.clear()
    pass_field.send_keys(breeze_pass)
    
    # Check T&C
    tnc_checkbox = driver.find_element(By.ID, "chkssTnc")
    if not tnc_checkbox.is_selected():
        tnc_checkbox.click()
    
    # Click login
    print("3. Clicking login...")
    login_button = driver.find_element(By.ID, "btnSubmit")
    login_button.click()
    
    # Wait for OTP field
    time.sleep(3)
    
    print("4. Looking for OTP field...")
    inputs = driver.find_elements(By.XPATH, "//input[@type='text']")
    otp_field = None
    for inp in inputs:
        if inp.is_displayed() and inp.is_enabled():
            otp_field = inp
            break
    
    if otp_field:
        # Re-generate OTP with correct offset
        adjusted_time = time.time() + time_offset
        current_otp = totp.at(adjusted_time)
        
        print(f"5. Entering OTP: {current_otp}")
        otp_field.clear()
        otp_field.send_keys(current_otp)
        
        # Find submit button
        submit_buttons = driver.find_elements(By.XPATH, "//input[@type='submit' or @type='button']")
        for btn in submit_buttons:
            if btn.is_displayed() and btn.is_enabled():
                value = btn.get_attribute("value")
                if value and ("submit" in value.lower() or "verify" in value.lower()):
                    print("6. Clicking submit...")
                    btn.click()
                    break
        
        # Wait for response
        time.sleep(5)
        
        # Handle alert
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"\n⚠️ Alert: {alert_text}")
            alert.accept()
            
            if "incorrect" in alert_text.lower():
                print("\n❌ Login failed - check error")
        except:
            # No alert - check for success
            final_url = driver.current_url
            print(f"\n7. Final URL: {final_url}")
            
            if "apisession=" in final_url:
                import re
                match = re.search(r'apisession=(\d+)', final_url)
                if match:
                    session = match.group(1)
                    print(f"\n✅ SUCCESS! Session token: {session}")
                    
                    # Save to .env
                    env_path = Path(".env")
                    if env_path.exists():
                        with open(env_path, 'r') as f:
                            lines = f.readlines()
                    else:
                        lines = []
                    
                    new_lines = []
                    for line in lines:
                        if not line.startswith('BREEZE_API_SESSION='):
                            new_lines.append(line)
                    new_lines.append(f'BREEZE_API_SESSION={session}\n')
                    
                    with open(env_path, 'w') as f:
                        f.writelines(new_lines)
                    
                    print("✅ Session saved to .env!")
                    print("\n🎉 AUTO-LOGIN SUCCESSFUL!")
                    print("\nThe system will now use +60 second offset for all future logins")
            elif "home" in final_url:
                print("\n✅ Successfully logged in to home page!")
                print("Check page for session details")
            else:
                print("\n⚠️ Login completed but session not in URL")
                print(f"Current page: {final_url}")
    else:
        print("❌ Could not find OTP field")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    screenshot_dir = Path("logs/screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(screenshot_dir / "login_final.png"))
    driver.quit()

print("\n" + "=" * 60)
print("COMPLETE!")
print("=" * 60)
print("\nIMPORTANT: Your system time is 60 seconds behind actual time")
print("To fix permanently: Windows Settings → Time & Date → Sync now")
print("=" * 60)