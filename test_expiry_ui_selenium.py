"""
Test expiry selection UI with Selenium
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import sys

def test_expiry_ui():
    """Test the expiry selection UI functionality"""
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = None
    try:
        print("Starting Chrome browser...")
        driver = webdriver.Chrome(options=chrome_options)
        
        # Load the trading page
        print("Loading tradingview_pro.html...")
        driver.get("http://localhost:8000/tradingview_pro.html")
        
        # Wait for page to load
        time.sleep(3)
        
        print("\n" + "="*60)
        print("TESTING EXPIRY SELECTION UI")
        print("="*60)
        
        # Test 1: Check if expiry section exists
        print("\n[TEST 1] Checking if expiry section exists...")
        try:
            expiry_section = driver.find_element(By.ID, "expirySelectionContainer")
            if expiry_section.is_displayed():
                print("[OK] Expiry selection container found and visible")
            else:
                print("[FAIL] Expiry selection container not visible")
        except Exception as e:
            print(f"[FAIL] Expiry selection container not found: {e}")
        
        # Test 2: Check weeks list
        print("\n[TEST 2] Checking weeks list...")
        try:
            weeks_list = driver.find_element(By.ID, "weeksList")
            week_items = weeks_list.find_elements(By.TAG_NAME, "div")
            print(f"[OK] Found {len(week_items)} week items")
            
            # Try clicking first week
            if week_items:
                week_items[0].click()
                print("[OK] Clicked first week")
        except Exception as e:
            print(f"[FAIL] Weeks list error: {e}")
        
        # Test 3: Check expiry dropdown
        print("\n[TEST 3] Checking expiry dropdown...")
        try:
            expiry_dropdown = driver.find_element(By.ID, "expiryDate")
            
            # Check if dropdown has options
            select = Select(expiry_dropdown)
            options = select.options
            print(f"[OK] Expiry dropdown has {len(options)} options")
            
            if options:
                for i, option in enumerate(options[:3]):  # Show first 3
                    print(f"     Option {i+1}: {option.text}")
                
                # Try selecting an option
                if len(options) > 0:
                    select.select_by_index(0)
                    print(f"[OK] Selected first option: {options[0].text}")
            else:
                print("[FAIL] No options in expiry dropdown")
                
        except Exception as e:
            print(f"[FAIL] Expiry dropdown error: {e}")
        
        # Test 4: Check exit timing section
        print("\n[TEST 4] Checking exit timing configuration...")
        try:
            exit_day = driver.find_element(By.ID, "exitDayOffset")
            exit_time = driver.find_element(By.ID, "exitTime")
            auto_square = driver.find_element(By.ID, "autoSquareOffEnabled")
            
            print("[OK] Exit day dropdown found")
            print("[OK] Exit time dropdown found")
            print(f"[OK] Auto square-off checkbox found (checked: {auto_square.is_selected()})")
            
            # Test Expiry Day option
            select_day = Select(exit_day)
            print("\n   Testing Expiry Day Selection:")
            select_day.select_by_value("0")
            time.sleep(1)
            print("[OK] Selected Expiry Day (T+0)")
            
            # Check preview for Expiry Day
            exit_preview = driver.find_element(By.ID, "exitPreview")
            preview_text = exit_preview.text
            if "Expiry Day" in preview_text and "Tuesday" in preview_text:
                print("[OK] Preview shows Expiry Day and Tuesday correctly")
            else:
                print(f"[WARN] Preview text: {preview_text[:100]}")
            
            # Try T+3 for comparison
            select_day.select_by_value("3")
            time.sleep(1)
            print("[OK] Changed exit day to T+3")
            
            # Switch back to Expiry Day
            select_day.select_by_value("0")
            time.sleep(1)
            print("[OK] Switched back to Expiry Day")
            
            # Try changing exit time
            select_time = Select(exit_time)
            select_time.select_by_value("14:15")
            print("[OK] Changed exit time to 14:15")
            
        except Exception as e:
            print(f"[FAIL] Exit timing error: {e}")
        
        # Test 5: Check exit preview
        print("\n[TEST 5] Checking exit preview...")
        try:
            exit_preview = driver.find_element(By.ID, "exitPreview")
            preview_text = exit_preview.text
            if preview_text:
                print(f"[OK] Exit preview showing: {preview_text[:100]}...")
            else:
                print("[FAIL] Exit preview is empty")
        except Exception as e:
            print(f"[FAIL] Exit preview error: {e}")
        
        # Test 6: Check alignment and styling
        print("\n[TEST 6] Checking UI alignment...")
        try:
            container = driver.find_element(By.ID, "expirySelectionContainer")
            
            # Get computed styles
            display = driver.execute_script("return window.getComputedStyle(arguments[0]).display", container)
            gap = driver.execute_script("return window.getComputedStyle(arguments[0]).gap", container)
            
            print(f"[INFO] Container display: {display}")
            print(f"[INFO] Container gap: {gap}")
            
            # Check if flex layout is working
            if display == "flex":
                print("[OK] Flex layout is applied")
            else:
                print(f"[WARN] Display is '{display}', expected 'flex'")
                
        except Exception as e:
            print(f"[FAIL] Style check error: {e}")
        
        # Test 7: Take screenshot for visual inspection
        print("\n[TEST 7] Taking screenshot...")
        try:
            # Scroll to expiry section
            expiry_section = driver.find_element(By.ID, "expirySelectionContainer")
            driver.execute_script("arguments[0].scrollIntoView(true);", expiry_section)
            time.sleep(1)
            
            # Take screenshot
            driver.save_screenshot("expiry_ui_test.png")
            print("[OK] Screenshot saved as 'expiry_ui_test.png'")
        except Exception as e:
            print(f"[FAIL] Screenshot error: {e}")
        
        # Test 8: Check JavaScript errors
        print("\n[TEST 8] Checking for JavaScript errors...")
        logs = driver.get_log('browser')
        js_errors = [log for log in logs if log['level'] == 'SEVERE']
        if js_errors:
            print(f"[WARN] Found {len(js_errors)} JavaScript errors:")
            for error in js_errors[:3]:  # Show first 3
                print(f"     {error['message'][:100]}...")
        else:
            print("[OK] No JavaScript errors found")
        
        print("\n" + "="*60)
        print("UI TEST SUMMARY")
        print("="*60)
        print("\nIssues Found:")
        print("1. Check if expiry dropdown is populating")
        print("2. Verify week selection highlighting")
        print("3. Confirm exit preview updates dynamically")
        print("\nReview screenshot 'expiry_ui_test.png' for visual issues")
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            print("\nPress Enter to close browser...")
            input()
            driver.quit()

if __name__ == "__main__":
    test_expiry_ui()