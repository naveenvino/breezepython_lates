"""
Visual test to check what user sees when changing dropdowns
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import time

def test_visual_check():
    """Test what the user actually sees"""
    
    chrome_options = Options()
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = None
    try:
        print("="*60)
        print("VISUAL DROPDOWN TEST - Check the browser window!")
        print("="*60)
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("file:///C:/Users/E1791/Kitepy/breezepython/tradingview_pro.html")
        driver.maximize_window()
        time.sleep(3)
        
        print("\nTesting dropdown behavior...")
        time.sleep(2)
        
        # Get initial state
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        print(f"\nBEFORE: Monday = {monday_select.first_selected_option.text}")
        print(f"BEFORE: Tuesday = {tuesday_select.first_selected_option.text}")
        
        print("\nChanging Monday to 'Next Week Tuesday'...")
        monday_select.select_by_value("next")
        
        time.sleep(2)  # Wait for any updates
        
        # Re-get selects
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        print(f"\nAFTER: Monday = {monday_select.first_selected_option.text}")
        print(f"AFTER: Tuesday = {tuesday_select.first_selected_option.text}")
        
        print("\n" + "-"*40)
        print("Now changing Tuesday to 'Month End Tuesday'...")
        tuesday_select.select_by_value("monthend")
        
        time.sleep(2)
        
        # Re-get selects again
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        print(f"\nFINAL: Monday = {monday_select.first_selected_option.text}")
        print(f"FINAL: Tuesday = {tuesday_select.first_selected_option.text}")
        
        # Check what saveExpiryConfig is actually saving
        print("\n" + "-"*40)
        print("Checking what's being saved...")
        
        saved_config = driver.execute_script("""
            // Manually collect the config like saveExpiryConfig does
            const config = {};
            const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Tuesday', 'Friday'];
            
            weekdays.forEach(day => {
                const select = document.getElementById(`expiry${day}`);
                if (select) {
                    config[day.toLowerCase()] = select.value;
                }
            });
            
            return config;
        """)
        
        print(f"Config that would be saved: {saved_config}")
        
        localStorage = driver.execute_script("return localStorage.getItem('weekdayExpiryConfig');")
        print(f"Current localStorage: {localStorage}")
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
        
        time.sleep(3)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    test_visual_check()