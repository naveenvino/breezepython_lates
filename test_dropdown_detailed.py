"""
Detailed test to debug Monday/Tuesday dropdown issue
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import time

def test_dropdown_detailed():
    """Detailed test of dropdown behavior"""
    
    chrome_options = Options()
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = None
    try:
        print("="*60)
        print("DETAILED DROPDOWN TEST")
        print("="*60)
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("file:///C:/Users/E1791/Kitepy/breezepython/tradingview_pro.html")
        time.sleep(3)
        
        # Get both dropdowns
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        print("\n1. INITIAL STATE:")
        print(f"   Monday ID: {driver.find_element(By.ID, 'expiryMonday').get_attribute('id')}")
        print(f"   Tuesday ID: {driver.find_element(By.ID, 'expiryTuesday').get_attribute('id')}")
        print(f"   Monday value: {monday_select.first_selected_option.get_attribute('value')}")
        print(f"   Tuesday value: {tuesday_select.first_selected_option.get_attribute('value')}")
        
        print("\n2. TRYING TO CHANGE MONDAY TO 'next':")
        print("   Before click - Monday value:", monday_select.first_selected_option.get_attribute('value'))
        
        # Try different methods to change Monday
        monday_element = driver.find_element(By.ID, "expiryMonday")
        print(f"   Monday element found: {monday_element is not None}")
        print(f"   Monday options: {[opt.get_attribute('value') for opt in monday_select.options]}")
        
        # Method 1: Direct select
        monday_select.select_by_value("next")
        time.sleep(1)
        
        # Re-get the select to ensure fresh reference
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        print(f"   After select - Monday value: {monday_select.first_selected_option.get_attribute('value')}")
        print(f"   After select - Tuesday value: {tuesday_select.first_selected_option.get_attribute('value')}")
        
        # Check if JavaScript is interfering
        print("\n3. CHECKING FOR JAVASCRIPT INTERFERENCE:")
        
        # Check event listeners
        has_onchange = driver.execute_script("""
            const monday = document.getElementById('expiryMonday');
            return monday ? monday.onchange !== null : false;
        """)
        print(f"   Monday has inline onchange: {has_onchange}")
        
        # Check if there are any event listeners
        listeners = driver.execute_script("""
            const monday = document.getElementById('expiryMonday');
            if (!monday) return 'Element not found';
            
            // Try to get event listeners (this is limited in what it can detect)
            const listeners = [];
            if (monday.onchange) listeners.push('inline onchange');
            
            // Check jQuery if available
            if (typeof $ !== 'undefined' && $(monday).data('events')) {
                const events = $(monday).data('events');
                for (let evt in events) {
                    listeners.push('jQuery ' + evt);
                }
            }
            
            return listeners.length > 0 ? listeners : 'No detectable listeners';
        """)
        print(f"   Detected listeners: {listeners}")
        
        print("\n4. TRYING JAVASCRIPT DIRECT SET:")
        
        # Try setting via JavaScript
        driver.execute_script("""
            document.getElementById('expiryMonday').value = 'monthend';
        """)
        time.sleep(1)
        
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        print(f"   After JS set - Monday value: {monday_select.first_selected_option.get_attribute('value')}")
        
        print("\n5. CHECKING DATA-DAY ATTRIBUTES:")
        
        # Check if data-day selectors are interfering
        monday_parent = driver.execute_script("""
            const monday = document.getElementById('expiryMonday');
            const parent = monday ? monday.closest('[data-day]') : null;
            return parent ? parent.getAttribute('data-day') : 'No data-day parent';
        """)
        print(f"   Monday parent data-day: {monday_parent}")
        
        tuesday_parent = driver.execute_script("""
            const tuesday = document.getElementById('expiryTuesday');
            const parent = tuesday ? tuesday.closest('[data-day]') : null;
            return parent ? parent.getAttribute('data-day') : 'No data-day parent';
        """)
        print(f"   Tuesday parent data-day: {tuesday_parent}")
        
        print("\n6. CHECKING FOR DUPLICATE IDS:")
        
        # Check for duplicate IDs
        monday_count = driver.execute_script("""
            return document.querySelectorAll('#expiryMonday').length;
        """)
        tuesday_count = driver.execute_script("""
            return document.querySelectorAll('#expiryTuesday').length;
        """)
        
        print(f"   Elements with ID 'expiryMonday': {monday_count}")
        print(f"   Elements with ID 'expiryTuesday': {tuesday_count}")
        
        if monday_count > 1 or tuesday_count > 1:
            print("   [ERROR] DUPLICATE IDS FOUND!")
        
        print("\n7. TRYING TO CHANGE TUESDAY:")
        
        tuesday_select.select_by_value("monthend")
        time.sleep(1)
        
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        print(f"   After changing Tuesday - Monday value: {monday_select.first_selected_option.get_attribute('value')}")
        print(f"   After changing Tuesday - Tuesday value: {tuesday_select.first_selected_option.get_attribute('value')}")
        
        print("\n8. CHECKING LOCALSTORAGE:")
        
        storage = driver.execute_script("""
            return localStorage.getItem('weekdayExpiryConfig');
        """)
        print(f"   LocalStorage: {storage}")
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            time.sleep(2)
            driver.quit()

if __name__ == "__main__":
    test_dropdown_detailed()