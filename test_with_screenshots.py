"""
Test configuration persistence with screenshots
"""
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import os

def test_configuration_with_screenshots():
    print("\n" + "="*70)
    print("TESTING CONFIGURATION WITH SCREENSHOTS")
    print("="*70)
    
    # Create screenshots directory
    screenshot_dir = "test_screenshots"
    if not os.path.exists(screenshot_dir):
        os.makedirs(screenshot_dir)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        # 1. Load the page
        print("\n[1] Loading page...")
        driver.get("http://localhost:8000/tradingview_pro.html")
        time.sleep(5)  # Wait for page to fully load
        
        # 2. Set test values
        print("\n[2] Setting test values:")
        print("    - Number of Lots: 30")
        print("    - Exit Day: Expiry Day (0)")
        print("    - Exit Time: 09:30")
        print("    - Monday: Current Week")
        
        # Set values
        Select(driver.find_element(By.ID, "numLots")).select_by_value("30")
        Select(driver.find_element(By.ID, "exitDayOffset")).select_by_value("0")
        Select(driver.find_element(By.ID, "exitTime")).select_by_value("09:30")
        Select(driver.find_element(By.ID, "expiryMonday")).select_by_value("current")
        
        # Scroll to config section
        config_section = driver.find_element(By.ID, "exitDayOffset")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", config_section)
        time.sleep(1)
        
        # Take BEFORE SAVE screenshot
        timestamp = datetime.now().strftime("%H%M%S")
        before_path = f"{screenshot_dir}/before_save_{timestamp}.png"
        driver.save_screenshot(before_path)
        print(f"\n📸 Screenshot 1 (BEFORE SAVE): {before_path}")
        
        # 3. Click Save
        print("\n[3] Clicking Save Config...")
        save_btn = driver.find_element(By.XPATH, "//button[contains(., 'Save Config')]")
        driver.execute_script("arguments[0].click();", save_btn)
        time.sleep(3)
        
        # Take AFTER SAVE screenshot
        after_save_path = f"{screenshot_dir}/after_save_{timestamp}.png"
        driver.save_screenshot(after_save_path)
        print(f"📸 Screenshot 2 (AFTER SAVE): {after_save_path}")
        
        # 4. Refresh the page
        print("\n[4] Refreshing page...")
        driver.refresh()
        time.sleep(5)  # Wait for reload and config to load
        
        # Scroll to config section again
        config_section = driver.find_element(By.ID, "exitDayOffset")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", config_section)
        time.sleep(1)
        
        # Take AFTER REFRESH screenshot
        after_refresh_path = f"{screenshot_dir}/after_refresh_{timestamp}.png"
        driver.save_screenshot(after_refresh_path)
        print(f"📸 Screenshot 3 (AFTER REFRESH): {after_refresh_path}")
        
        # 5. Check the values
        print("\n[5] Checking loaded values:")
        
        num_lots = Select(driver.find_element(By.ID, "numLots"))
        exit_day = Select(driver.find_element(By.ID, "exitDayOffset"))
        exit_time = Select(driver.find_element(By.ID, "exitTime"))
        monday = Select(driver.find_element(By.ID, "expiryMonday"))
        
        lots_value = num_lots.first_selected_option.get_attribute("value")
        exit_day_value = exit_day.first_selected_option.get_attribute("value")
        exit_time_value = exit_time.first_selected_option.get_attribute("value")
        monday_value = monday.first_selected_option.get_attribute("value")
        
        print(f"    Number of Lots: {lots_value} {'✓' if lots_value == '30' else '✗ (Expected 30)'}")
        print(f"    Exit Day: {exit_day_value} {'✓' if exit_day_value == '0' else '✗ (Expected 0)'}")
        print(f"    Exit Time: {exit_time_value} {'✓' if exit_time_value == '09:30' else '✗ (Expected 09:30)'}")
        print(f"    Monday: {monday_value} {'✓' if monday_value == 'current' else '✗ (Expected current)'}")
        
        # 6. Check API
        print("\n[6] Checking API values:")
        response = requests.get("http://localhost:8000/api/trade-config/load/default?user_id=default")
        if response.ok:
            config = response.json().get('config', {})
            print(f"    API num_lots: {config.get('num_lots')}")
            print(f"    API exit_day_offset: {config.get('exit_day_offset')}")
            print(f"    API exit_time: {config.get('exit_time')}")
        
        print("\n" + "="*70)
        print("SCREENSHOTS SAVED IN: test_screenshots folder")
        print("="*70)
        print("\nPlease check the screenshots:")
        print(f"1. {before_path} - Shows values BEFORE saving")
        print(f"2. {after_save_path} - Shows values AFTER saving")
        print(f"3. {after_refresh_path} - Shows values AFTER page refresh")
        print("\n✅ Screenshots 2 and 3 should show the SAME values if persistence works")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        # Take error screenshot
        error_path = f"{screenshot_dir}/error_{datetime.now().strftime('%H%M%S')}.png"
        driver.save_screenshot(error_path)
        print(f"📸 Error screenshot: {error_path}")
        return False
        
    finally:
        print("\nClosing browser in 5 seconds...")
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    test_configuration_with_screenshots()