"""
Test to reproduce the Monday/Tuesday refresh issue
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import time
import json

def test_monday_tuesday_refresh():
    """Test that specifically changes Monday and Tuesday to 'next' and refreshes"""
    
    chrome_options = Options()
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = None
    try:
        print("="*60)
        print("TESTING MONDAY/TUESDAY REFRESH ISSUE")
        print("="*60)
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("file:///C:/Users/E1791/Kitepy/breezepython/tradingview_pro.html")
        time.sleep(3)
        
        print("\n1. INITIAL STATE:")
        print("-" * 40)
        
        # Get initial values
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        monday_initial = monday_select.first_selected_option.get_attribute('value')
        tuesday_initial = tuesday_select.first_selected_option.get_attribute('value')
        
        print(f"   Monday: {monday_initial} ({monday_select.first_selected_option.text})")
        print(f"   Tuesday: {tuesday_initial} ({tuesday_select.first_selected_option.text})")
        
        # Check localStorage before changes
        storage_before = driver.execute_script("return localStorage.getItem('weekdayExpiryConfig');")
        if storage_before:
            config_before = json.loads(storage_before)
            print(f"   LocalStorage before: monday={config_before.get('monday')}, tuesday={config_before.get('tuesday')}")
        else:
            print("   LocalStorage before: Empty")
        
        print("\n2. CHANGING BOTH TO 'NEXT WEEK':")
        print("-" * 40)
        
        # Change Monday to next
        print("   Setting Monday to 'next'...")
        monday_select.select_by_value("next")
        time.sleep(1)
        
        # Change Tuesday to next
        print("   Setting Tuesday to 'next'...")
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        tuesday_select.select_by_value("next")
        time.sleep(2)  # Wait for save
        
        # Verify changes took effect
        monday_select = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        monday_after = monday_select.first_selected_option.get_attribute('value')
        tuesday_after = tuesday_select.first_selected_option.get_attribute('value')
        
        print(f"   Monday after change: {monday_after} ({monday_select.first_selected_option.text})")
        print(f"   Tuesday after change: {tuesday_after} ({tuesday_select.first_selected_option.text})")
        
        # Check localStorage after changes
        storage_after = driver.execute_script("return localStorage.getItem('weekdayExpiryConfig');")
        if storage_after:
            config_after = json.loads(storage_after)
            print(f"   LocalStorage after: monday={config_after.get('monday')}, tuesday={config_after.get('tuesday')}")
        else:
            print("   LocalStorage after: Empty (ERROR!)")
        
        # Check console logs
        console_logs = driver.execute_script("""
            // Get console logs if available
            return window.console.logs || 'No logs captured';
        """)
        
        print("\n3. REFRESHING PAGE:")
        print("-" * 40)
        print("   Refreshing browser...")
        driver.refresh()
        time.sleep(3)
        
        print("\n4. CHECKING VALUES AFTER REFRESH:")
        print("-" * 40)
        
        # Get values after refresh
        monday_select_refresh = Select(driver.find_element(By.ID, "expiryMonday"))
        tuesday_select_refresh = Select(driver.find_element(By.ID, "expiryTuesday"))
        
        monday_refresh = monday_select_refresh.first_selected_option.get_attribute('value')
        tuesday_refresh = tuesday_select_refresh.first_selected_option.get_attribute('value')
        
        print(f"   Monday after refresh: {monday_refresh} ({monday_select_refresh.first_selected_option.text})")
        print(f"   Tuesday after refresh: {tuesday_refresh} ({tuesday_select_refresh.first_selected_option.text})")
        
        # Check localStorage after refresh
        storage_refresh = driver.execute_script("return localStorage.getItem('weekdayExpiryConfig');")
        if storage_refresh:
            config_refresh = json.loads(storage_refresh)
            print(f"   LocalStorage after refresh: monday={config_refresh.get('monday')}, tuesday={config_refresh.get('tuesday')}")
        else:
            print("   LocalStorage after refresh: Empty")
        
        # Check if immediate load script ran
        console_after = driver.execute_script("""
            // Check if our immediate load script ran
            const logs = [];
            const originalLog = console.log;
            
            // Check page source for immediate load script
            const scripts = document.getElementsByTagName('script');
            for (let script of scripts) {
                if (script.innerHTML.includes('IMMEDIATE LOAD')) {
                    logs.push('Immediate load script found in page');
                    break;
                }
            }
            
            return logs.length > 0 ? logs : 'Immediate load script not found';
        """)
        print(f"   Script check: {console_after}")
        
        print("\n5. TEST RESULTS:")
        print("-" * 40)
        
        # Determine if test passed or failed
        if monday_refresh == "next" and tuesday_refresh == "next":
            print("   [SUCCESS] Monday and Tuesday persisted as 'next' after refresh!")
        else:
            print("   [FAILURE] Settings did not persist!")
            print(f"      Expected: Monday='next', Tuesday='next'")
            print(f"      Got: Monday='{monday_refresh}', Tuesday='{tuesday_refresh}'")
            
            # Additional debugging
            print("\n6. DEBUGGING INFO:")
            print("-" * 40)
            
            # Check if dropdowns have the right options
            monday_options = driver.execute_script("""
                const select = document.getElementById('expiryMonday');
                return Array.from(select.options).map(opt => ({
                    value: opt.value,
                    text: opt.text,
                    selected: opt.selected
                }));
            """)
            print("   Monday dropdown options:")
            for opt in monday_options:
                print(f"      - {opt['value']}: {opt['text']} {'(SELECTED)' if opt['selected'] else ''}")
            
            # Check browser console for errors
            browser_logs = driver.get_log('browser')
            if browser_logs:
                print("\n   Browser console logs:")
                for log in browser_logs[-10:]:  # Last 10 logs
                    if 'IMMEDIATE' in log.get('message', '') or 'expiry' in log.get('message', '').lower():
                        print(f"      {log['level']}: {log['message'][:200]}")
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
        
        return monday_refresh == "next" and tuesday_refresh == "next"
        
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
    success = test_monday_tuesday_refresh()
    exit(0 if success else 1)