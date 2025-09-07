"""
Test settings persistence using Selenium
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import sys

def test_settings_persistence():
    """Test that exit timing and weekday config persist across page refreshes"""
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = None
    try:
        print("="*60)
        print("TESTING SETTINGS PERSISTENCE WITH SELENIUM")
        print("="*60)
        
        print("\n1. Starting Chrome browser...")
        driver = webdriver.Chrome(options=chrome_options)
        
        # Load the trading page
        print("2. Loading TradingView Pro page...")
        driver.get("http://localhost:8000/tradingview_pro.html")
        
        # Wait for page to fully load
        time.sleep(3)
        
        print("\n3. SETTING TEST VALUES...")
        print("-" * 40)
        
        # Set Exit Timing to Expiry Day
        try:
            exit_day_select = Select(driver.find_element(By.ID, "exitDayOffset"))
            print("   Current exit day value:", exit_day_select.first_selected_option.text)
            exit_day_select.select_by_value("0")  # Expiry Day
            print("   [SET] Exit Day = Expiry Day")
            time.sleep(1)
        except Exception as e:
            print(f"   [ERROR] Could not set exit day: {e}")
        
        # Set Exit Time to 14:15
        try:
            exit_time_select = Select(driver.find_element(By.ID, "exitTime"))
            print("   Current exit time value:", exit_time_select.first_selected_option.text)
            exit_time_select.select_by_value("14:15")
            print("   [SET] Exit Time = 14:15 (2:15 PM)")
            time.sleep(1)
        except Exception as e:
            print(f"   [ERROR] Could not set exit time: {e}")
        
        # Set Weekday Configurations
        print("\n4. SETTING WEEKDAY CONFIGURATIONS...")
        print("-" * 40)
        
        weekday_configs = {
            'monday': 'current',
            'tuesday': 'current',
            'wednesday': 'next',
            'thursday': 'next',
            'friday': 'monthend'
        }
        
        for day, value in weekday_configs.items():
            try:
                # Find the weekday element
                day_element = driver.find_element(By.CSS_SELECTOR, f'[data-day="{day}"]')
                if day_element:
                    select = Select(day_element.find_element(By.TAG_NAME, 'select'))
                    select.select_by_value(value)
                    print(f"   [SET] {day.capitalize()} = {value}")
                    time.sleep(0.5)
            except Exception as e:
                print(f"   [ERROR] Could not set {day}: {e}")
        
        # Check localStorage to confirm save
        print("\n5. CHECKING LOCALSTORAGE...")
        print("-" * 40)
        
        exit_config = driver.execute_script("return localStorage.getItem('exitTimingConfig');")
        weekday_config = driver.execute_script("return localStorage.getItem('weekdayExpiryConfig');")
        
        if exit_config:
            print("   [OK] Exit timing saved to localStorage")
            print(f"       Data: {exit_config}")
        else:
            print("   [FAIL] Exit timing NOT in localStorage")
            
        if weekday_config:
            print("   [OK] Weekday config saved to localStorage")
            print(f"       Data: {weekday_config}")
        else:
            print("   [FAIL] Weekday config NOT in localStorage")
        
        # Wait a bit to ensure save
        time.sleep(2)
        
        print("\n6. REFRESHING PAGE...")
        print("-" * 40)
        driver.refresh()
        time.sleep(3)  # Wait for page to reload
        
        print("\n7. VERIFYING SETTINGS AFTER REFRESH...")
        print("-" * 40)
        
        # Check Exit Timing
        success_count = 0
        fail_count = 0
        
        try:
            exit_day_select = Select(driver.find_element(By.ID, "exitDayOffset"))
            current_value = exit_day_select.first_selected_option.get_attribute('value')
            current_text = exit_day_select.first_selected_option.text
            
            if current_value == "0":
                print(f"   [OK] Exit Day = {current_text} (Expiry Day) - PERSISTED!")
                success_count += 1
            else:
                print(f"   [FAIL] Exit Day = {current_text} (Expected: Expiry Day)")
                fail_count += 1
        except Exception as e:
            print(f"   [ERROR] Could not check exit day: {e}")
            fail_count += 1
        
        try:
            exit_time_select = Select(driver.find_element(By.ID, "exitTime"))
            current_value = exit_time_select.first_selected_option.get_attribute('value')
            current_text = exit_time_select.first_selected_option.text
            
            if current_value == "14:15":
                print(f"   [OK] Exit Time = {current_text} - PERSISTED!")
                success_count += 1
            else:
                print(f"   [FAIL] Exit Time = {current_text} (Expected: 2:15 PM)")
                fail_count += 1
        except Exception as e:
            print(f"   [ERROR] Could not check exit time: {e}")
            fail_count += 1
        
        # Check Weekday Configurations
        print("\n8. VERIFYING WEEKDAY CONFIGURATIONS...")
        print("-" * 40)
        
        for day, expected_value in weekday_configs.items():
            try:
                day_element = driver.find_element(By.CSS_SELECTOR, f'[data-day="{day}"]')
                if day_element:
                    select = Select(day_element.find_element(By.TAG_NAME, 'select'))
                    current_value = select.first_selected_option.get_attribute('value')
                    
                    if current_value == expected_value:
                        print(f"   [OK] {day.capitalize()} = {current_value} - PERSISTED!")
                        success_count += 1
                    else:
                        print(f"   [FAIL] {day.capitalize()} = {current_value} (Expected: {expected_value})")
                        fail_count += 1
            except Exception as e:
                print(f"   [ERROR] Could not check {day}: {e}")
                fail_count += 1
        
        # Final Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Successful: {success_count}")
        print(f"Failed: {fail_count}")
        
        if fail_count == 0:
            print("\n[SUCCESS] ALL SETTINGS PERSISTED CORRECTLY!")
            print("Exit timing and weekday configurations are being saved and restored properly.")
        else:
            print(f"\n[FAILURE] {fail_count} settings did not persist")
            print("Some settings are not being saved or restored correctly.")
            
            # Additional debugging
            print("\n9. DEBUGGING INFO...")
            print("-" * 40)
            
            # Check console logs
            logs = driver.get_log('browser')
            relevant_logs = [log for log in logs if 'CONFIG' in log.get('message', '') or 'EXIT' in log.get('message', '')]
            if relevant_logs:
                print("Console logs related to config:")
                for log in relevant_logs[-5:]:  # Last 5 relevant logs
                    print(f"   {log['level']}: {log['message'][:100]}")
        
        # Take screenshot for verification
        driver.save_screenshot("settings_persistence_test.png")
        print("\nScreenshot saved as 'settings_persistence_test.png'")
        
        return fail_count == 0
        
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            print("\nClosing browser...")
            time.sleep(2)
            driver.quit()

if __name__ == "__main__":
    success = test_settings_persistence()
    sys.exit(0 if success else 1)