"""
Test that Monday and Tuesday dropdowns work independently
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import time

def test_dropdown_independence():
    """Test that Monday and Tuesday dropdowns change independently"""
    
    chrome_options = Options()
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = None
    try:
        print("="*60)
        print("TESTING DROPDOWN INDEPENDENCE")
        print("="*60)
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("file:///C:/Users/E1791/Kitepy/breezepython/tradingview_pro.html")
        time.sleep(3)
        
        print("\n1. INITIAL STATE:")
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        print(f"   Monday: {monday_select.first_selected_option.text}")
        print(f"   Tuesday: {tuesday_select.first_selected_option.text}")
        
        print("\n2. CHANGING MONDAY TO 'next':")
        monday_select.select_by_value("next")
        time.sleep(1)
        
        # Check values
        monday_value = monday_select.first_selected_option.get_attribute('value')
        tuesday_value = tuesday_select.first_selected_option.get_attribute('value')
        
        print(f"   Monday: {monday_value} ({monday_select.first_selected_option.text})")
        print(f"   Tuesday: {tuesday_value} ({tuesday_select.first_selected_option.text})")
        
        if monday_value != "next":
            print("   [FAIL] Monday didn't change to 'next'!")
            return False
        
        print("\n3. CHANGING TUESDAY TO 'monthend':")
        tuesday_select.select_by_value("monthend")
        time.sleep(1)
        
        # Check values again
        monday_value = monday_select.first_selected_option.get_attribute('value')
        tuesday_value = tuesday_select.first_selected_option.get_attribute('value')
        
        print(f"   Monday: {monday_value} ({monday_select.first_selected_option.text})")
        print(f"   Tuesday: {tuesday_value} ({tuesday_select.first_selected_option.text})")
        
        if tuesday_value != "monthend":
            print("   [FAIL] Tuesday didn't change to 'monthend'!")
            return False
            
        if monday_value != "next":
            print("   [FAIL] Monday value changed when Tuesday was modified!")
            return False
        
        print("\n4. CHANGING MONDAY TO 'current':")
        monday_select.select_by_value("current")
        time.sleep(1)
        
        # Final check
        monday_value = monday_select.first_selected_option.get_attribute('value')
        tuesday_value = tuesday_select.first_selected_option.get_attribute('value')
        
        print(f"   Monday: {monday_value} ({monday_select.first_selected_option.text})")
        print(f"   Tuesday: {tuesday_value} ({tuesday_select.first_selected_option.text})")
        
        if monday_value != "current":
            print("   [FAIL] Monday didn't change to 'current'!")
            return False
            
        if tuesday_value != "monthend":
            print("   [FAIL] Tuesday value changed when Monday was modified!")
            return False
        
        print("\n" + "="*60)
        print("[SUCCESS] Dropdowns work independently!")
        print("="*60)
        return True
        
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
    success = test_dropdown_independence()
    exit(0 if success else 1)