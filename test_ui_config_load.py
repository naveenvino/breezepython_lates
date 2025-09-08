import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import requests
import json

def test_config_loading():
    """Test if UI loads saved configuration values correctly"""
    
    print("Testing UI Configuration Loading")
    print("=" * 60)
    
    # First, save a test configuration via API
    BASE_URL = "http://localhost:8000"
    
    test_config = {
        "num_lots": 25,
        "entry_timing": "next_candle",
        "hedge_enabled": True,
        "hedge_method": "offset",
        "hedge_offset": 500,
        "profit_lock_enabled": True,
        "profit_target": 20.0,
        "profit_lock": 10.0,
        "selected_expiry": "2025-01-21",
        "exit_day_offset": 1,  # T+1
        "exit_time": "14:30",
        "auto_square_off_enabled": True,
        "weekday_config": {
            "monday": "next",
            "tuesday": "current",
            "wednesday": "month_end",
            "thursday": "next",
            "friday": "current"
        }
    }
    
    print("\n1. Saving test configuration via API...")
    response = requests.post(
        f"{BASE_URL}/api/trade-config/save",
        json={
            "config_name": "default",
            "user_id": "default",
            "config": test_config
        }
    )
    
    if not response.ok or not response.json().get('success'):
        print(f"   [FAIL] Could not save config: {response.text}")
        return False
    
    print("   [OK] Configuration saved to database")
    
    # Now test if UI loads the values
    print("\n2. Opening UI to check if values load...")
    
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        driver.get("http://localhost:8000/tradingview_pro.html")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "numLots"))
        )
        
        # Wait a bit for JavaScript to execute
        time.sleep(3)
        
        print("\n3. Checking loaded values in UI:")
        
        # Check basic settings
        num_lots = Select(driver.find_element(By.ID, "numLots"))
        actual_lots = num_lots.first_selected_option.get_attribute("value")
        expected_lots = str(test_config["num_lots"])
        if actual_lots == expected_lots:
            print(f"   [OK] Number of lots: {actual_lots}")
        else:
            print(f"   [FAIL] Number of lots: Expected {expected_lots}, got {actual_lots}")
        
        # Check entry timing
        entry_timing = Select(driver.find_element(By.ID, "entryTiming"))
        actual_timing = entry_timing.first_selected_option.get_attribute("value")
        expected_timing = test_config["entry_timing"]
        if actual_timing == expected_timing:
            print(f"   [OK] Entry timing: {actual_timing}")
        else:
            print(f"   [FAIL] Entry timing: Expected {expected_timing}, got {actual_timing}")
        
        # Check exit timing
        exit_day = Select(driver.find_element(By.ID, "exitDayOffset"))
        actual_exit_day = exit_day.first_selected_option.get_attribute("value")
        expected_exit_day = str(test_config["exit_day_offset"])
        if actual_exit_day == expected_exit_day:
            print(f"   [OK] Exit day offset: {actual_exit_day}")
        else:
            print(f"   [FAIL] Exit day offset: Expected {expected_exit_day}, got {actual_exit_day}")
        
        exit_time = driver.find_element(By.ID, "exitTime").get_attribute("value")
        if exit_time == test_config["exit_time"]:
            print(f"   [OK] Exit time: {exit_time}")
        else:
            print(f"   [FAIL] Exit time: Expected {test_config['exit_time']}, got {exit_time}")
        
        # Check weekday configuration
        print("\n4. Checking weekday configuration:")
        weekday_success = True
        
        for day, expected_value in test_config["weekday_config"].items():
            element_id = f"expiry{day.capitalize()}"
            try:
                select = Select(driver.find_element(By.ID, element_id))
                actual_value = select.first_selected_option.get_attribute("value")
                if actual_value == expected_value:
                    print(f"   [OK] {day.capitalize()}: {actual_value}")
                else:
                    print(f"   [FAIL] {day.capitalize()}: Expected {expected_value}, got {actual_value}")
                    weekday_success = False
            except Exception as e:
                print(f"   [FAIL] Could not find {element_id}: {e}")
                weekday_success = False
        
        # Check hedge settings
        hedge_method_offset = driver.find_element(By.ID, "hedgeMethodOffset")
        if hedge_method_offset.is_selected():
            print(f"   [OK] Hedge method: offset (radio selected)")
        else:
            print(f"   [FAIL] Hedge method: offset radio not selected")
        
        hedge_offset = driver.find_element(By.ID, "hedgeOffset").get_attribute("value")
        if hedge_offset == str(test_config["hedge_offset"]):
            print(f"   [OK] Hedge offset: {hedge_offset}")
        else:
            print(f"   [FAIL] Hedge offset: Expected {test_config['hedge_offset']}, got {hedge_offset}")
        
        # Check console for errors
        console_logs = driver.get_log('browser')
        errors = [log for log in console_logs if log['level'] == 'SEVERE']
        if errors:
            print("\n5. Console errors detected:")
            for error in errors[:5]:  # Show first 5 errors
                print(f"   [ERROR] {error['message']}")
        
        print("\n" + "=" * 60)
        
        if (actual_lots == expected_lots and 
            actual_timing == expected_timing and 
            actual_exit_day == expected_exit_day and 
            exit_time == test_config["exit_time"] and 
            weekday_success):
            print("SUCCESS: Configuration loads correctly in UI!")
            return True
        else:
            print("FAILURE: Some configuration values not loading correctly")
            
            # Try to debug by checking localStorage
            local_config = driver.execute_script("return localStorage.getItem('tradeConfig');")
            if local_config:
                stored = json.loads(local_config)
                print("\nLocalStorage contains:")
                print(f"  num_lots: {stored.get('num_lots')}")
                print(f"  exit_day_offset: {stored.get('exit_day_offset')}")
                print(f"  weekday_config: {stored.get('weekday_config')}")
            
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = test_config_loading()
    exit(0 if success else 1)