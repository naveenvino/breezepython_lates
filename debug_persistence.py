from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import time

def debug_persistence():
    """Debug why settings aren't persisting"""
    
    driver = webdriver.Chrome()
    
    try:
        print("DEBUGGING SETTINGS PERSISTENCE")
        print("=" * 60)
        
        # Load page
        driver.get("http://localhost:8000/tradingview_pro.html")
        time.sleep(3)
        
        print("\n1. BEFORE SETTING VALUES:")
        print("-" * 40)
        
        # Check initial values
        exit_day = Select(driver.find_element(By.ID, "exitDayOffset"))
        print(f"Exit Day Initial: {exit_day.first_selected_option.text}")
        
        exit_time = Select(driver.find_element(By.ID, "exitTime"))
        print(f"Exit Time Initial: {exit_time.first_selected_option.text}")
        
        # Check localStorage before
        storage_before = driver.execute_script("return localStorage.getItem('exitTimingConfig');")
        print(f"LocalStorage Before: {storage_before}")
        
        print("\n2. SETTING VALUES:")
        print("-" * 40)
        
        # Set Expiry Day
        exit_day.select_by_value("0")
        print("Set Exit Day to: Expiry Day (value=0)")
        time.sleep(1)
        
        # Set time
        exit_time.select_by_value("14:15")
        print("Set Exit Time to: 14:15")
        time.sleep(1)
        
        # Check localStorage after setting
        storage_after = driver.execute_script("return localStorage.getItem('exitTimingConfig');")
        print(f"LocalStorage After: {storage_after}")
        
        print("\n3. EXECUTING loadExitTimingConfig():")
        print("-" * 40)
        
        # Clear the values first
        driver.execute_script("document.getElementById('exitDayOffset').value = '2';")
        driver.execute_script("document.getElementById('exitTime').value = '15:15';")
        print("Cleared values to defaults")
        
        # Now run the load function
        result = driver.execute_script("""
            loadExitTimingConfig();
            return {
                exitDay: document.getElementById('exitDayOffset').value,
                exitTime: document.getElementById('exitTime').value
            };
        """)
        
        print(f"After loadExitTimingConfig():")
        print(f"  Exit Day: {result['exitDay']}")
        print(f"  Exit Time: {result['exitTime']}")
        
        print("\n4. CHECKING WHAT'S IN LOCALSTORAGE:")
        print("-" * 40)
        
        # Get and parse localStorage
        storage_json = driver.execute_script("""
            const stored = localStorage.getItem('exitTimingConfig');
            if (stored) {
                const parsed = JSON.parse(stored);
                return {
                    raw: stored,
                    parsed: parsed,
                    exit_day_offset: parsed.exit_day_offset,
                    exit_day_type: typeof parsed.exit_day_offset
                };
            }
            return null;
        """)
        
        if storage_json:
            print(f"Raw JSON: {storage_json['raw']}")
            print(f"Parsed exit_day_offset: {storage_json['exit_day_offset']}")
            print(f"Type of exit_day_offset: {storage_json['exit_day_type']}")
        
        print("\n5. MANUAL TEST OF CONDITION:")
        print("-" * 40)
        
        # Test the condition directly
        condition_test = driver.execute_script("""
            const stored = localStorage.getItem('exitTimingConfig');
            const config = JSON.parse(stored);
            return {
                value: config.exit_day_offset,
                undefined_check: config.exit_day_offset !== undefined,
                result: config.exit_day_offset !== undefined ? config.exit_day_offset : 2
            };
        """)
        
        print(f"Value: {condition_test['value']}")
        print(f"!== undefined: {condition_test['undefined_check']}")
        print(f"Result: {condition_test['result']}")
        
        print("\n6. REFRESHING PAGE:")
        print("-" * 40)
        
        driver.refresh()
        time.sleep(3)
        
        # Check values after refresh
        exit_day_after = Select(driver.find_element(By.ID, "exitDayOffset"))
        exit_time_after = Select(driver.find_element(By.ID, "exitTime"))
        
        print(f"Exit Day After Refresh: {exit_day_after.first_selected_option.text}")
        print(f"Exit Time After Refresh: {exit_time_after.first_selected_option.text}")
        
        # Check if loadExitTimingConfig was called
        console_logs = driver.execute_script("""
            // Try to capture what happened
            const stored = localStorage.getItem('exitTimingConfig');
            return stored;
        """)
        
        print(f"LocalStorage still contains: {console_logs}")
        
        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nPress Enter to close...")
        input()
        driver.quit()

if __name__ == "__main__":
    debug_persistence()