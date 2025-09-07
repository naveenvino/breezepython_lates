"""
Test with mixed values for Monday and Tuesday
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import time
import json

def test_mixed_values():
    """Test setting Monday to 'next' and Tuesday to 'monthend'"""
    
    chrome_options = Options()
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = None
    try:
        print("="*60)
        print("TESTING MIXED VALUES (Monday=next, Tuesday=monthend)")
        print("="*60)
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("file:///C:/Users/E1791/Kitepy/breezepython/tradingview_pro.html")
        time.sleep(3)
        
        # Clear localStorage first to start fresh
        driver.execute_script("localStorage.removeItem('weekdayExpiryConfig');")
        driver.refresh()
        time.sleep(2)
        
        print("\n1. STARTING FRESH (localStorage cleared):")
        print("-" * 40)
        
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        print(f"   Monday: {monday_select.first_selected_option.get_attribute('value')}")
        print(f"   Tuesday: {tuesday_select.first_selected_option.get_attribute('value')}")
        
        print("\n2. SETTING DIFFERENT VALUES:")
        print("-" * 40)
        
        # Set Monday to next
        print("   Setting Monday to 'next'...")
        monday_select.select_by_value("next")
        time.sleep(1)
        
        # Set Tuesday to monthend
        print("   Setting Tuesday to 'monthend'...")
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        tuesday_select.select_by_value("monthend")
        time.sleep(2)
        
        # Verify
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        print(f"   Monday after: {monday_select.first_selected_option.get_attribute('value')}")
        print(f"   Tuesday after: {tuesday_select.first_selected_option.get_attribute('value')}")
        
        # Check localStorage
        storage = driver.execute_script("return localStorage.getItem('weekdayExpiryConfig');")
        if storage:
            config = json.loads(storage)
            print(f"   LocalStorage: monday={config.get('monday')}, tuesday={config.get('tuesday')}")
        
        print("\n3. REFRESHING PAGE:")
        print("-" * 40)
        driver.refresh()
        time.sleep(3)
        
        print("\n4. AFTER REFRESH:")
        print("-" * 40)
        
        monday_refresh = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_refresh = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        monday_val = monday_refresh.first_selected_option.get_attribute('value')
        tuesday_val = tuesday_refresh.first_selected_option.get_attribute('value')
        
        print(f"   Monday: {monday_val} ({monday_refresh.first_selected_option.text})")
        print(f"   Tuesday: {tuesday_val} ({tuesday_refresh.first_selected_option.text})")
        
        # Check localStorage
        storage_after = driver.execute_script("return localStorage.getItem('weekdayExpiryConfig');")
        if storage_after:
            config_after = json.loads(storage_after)
            print(f"   LocalStorage: monday={config_after.get('monday')}, tuesday={config_after.get('tuesday')}")
        
        print("\n5. RESULTS:")
        print("-" * 40)
        
        if monday_val == "next" and tuesday_val == "monthend":
            print("   [SUCCESS] Mixed values persisted correctly!")
            return True
        else:
            print("   [FAILURE] Values did not persist correctly!")
            print(f"      Expected: Monday='next', Tuesday='monthend'")
            print(f"      Got: Monday='{monday_val}', Tuesday='{tuesday_val}'")
            
            # Debug - check what the immediate load script sees
            debug_info = driver.execute_script("""
                // Re-run the logic to see what happens
                const saved = localStorage.getItem('weekdayExpiryConfig');
                if (saved) {
                    const config = JSON.parse(saved);
                    const monday = document.getElementById('expiryMonday');
                    const tuesday = document.getElementById('expiryTuesday');
                    
                    return {
                        localStorage: config,
                        mondayElement: monday ? monday.value : 'not found',
                        tuesdayElement: tuesday ? tuesday.value : 'not found',
                        mondayOptions: monday ? Array.from(monday.options).map(o => o.value) : [],
                        tuesdayOptions: tuesday ? Array.from(tuesday.options).map(o => o.value) : []
                    };
                }
                return 'No localStorage';
            """)
            
            print("\n   Debug info:")
            print(f"      {debug_info}")
            return False
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            time.sleep(2)
            driver.quit()

if __name__ == "__main__":
    success = test_mixed_values()
    exit(0 if success else 1)