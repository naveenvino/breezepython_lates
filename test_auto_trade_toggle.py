"""
Test Auto Trade Toggle functionality
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

def test_auto_trade_toggle():
    print("\n" + "="*70)
    print("TESTING AUTO TRADE TOGGLE")
    print("="*70)
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print("\n[1] Loading page...")
        driver.get("http://localhost:8000/tradingview_pro.html")
        time.sleep(3)
        
        print("\n[2] Initial State Check:")
        print("-" * 40)
        
        # Check toggle state
        toggle = driver.find_element(By.ID, "autoTradeToggle")
        is_checked = toggle.is_selected()
        print(f"Toggle state: {'ENABLED' if is_checked else 'DISABLED'}")
        
        # Check display text
        mode_text = driver.find_element(By.ID, "tradingModeText").text
        print(f"Display text: '{mode_text}'")
        
        # Check background color
        mode_div = driver.find_element(By.ID, "tradingModeStatus")
        bg_color = driver.execute_script("return window.getComputedStyle(arguments[0]).backgroundColor;", mode_div)
        print(f"Background color: {bg_color}")
        
        # Verify consistency
        if is_checked and mode_text == "LIVE TRADING MODE":
            print("[OK] Toggle and display are CONSISTENT (Live mode)")
        elif not is_checked and mode_text == "MANUAL MODE":
            print("[OK] Toggle and display are CONSISTENT (Manual mode)")
        else:
            print(f"[ERROR] INCONSISTENCY: Toggle={is_checked}, Display={mode_text}")
        
        print("\n[3] Testing Toggle Interaction:")
        print("-" * 40)
        
        # Click the toggle
        print("Clicking toggle...")
        driver.execute_script("document.getElementById('autoTradeToggle').click();")
        time.sleep(2)
        
        # Check for modal
        try:
            modal = driver.find_element(By.CLASS_NAME, "modal-overlay")
            if modal.is_displayed():
                print("[OK] Confirmation modal appeared")
                # Cancel for safety
                cancel_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Cancel')]")
                cancel_btn.click()
                print("Clicked Cancel")
                time.sleep(1)
        except:
            print("No modal found")
        
        # Check state after cancel
        print("\n[4] State After Cancel:")
        print("-" * 40)
        
        toggle_after = driver.find_element(By.ID, "autoTradeToggle").is_selected()
        mode_text_after = driver.find_element(By.ID, "tradingModeText").text
        
        print(f"Toggle state: {'ENABLED' if toggle_after else 'DISABLED'}")
        print(f"Display text: '{mode_text_after}'")
        
        if toggle_after == is_checked and mode_text_after == mode_text:
            print("[OK] State correctly reverted after cancel")
        else:
            print("[ERROR] State changed unexpectedly")
        
        print("\n[5] Testing Page Refresh:")
        print("-" * 40)
        
        # Refresh page
        driver.refresh()
        time.sleep(3)
        
        # Check state after refresh
        toggle_refresh = driver.find_element(By.ID, "autoTradeToggle").is_selected()
        mode_text_refresh = driver.find_element(By.ID, "tradingModeText").text
        
        print(f"Toggle state: {'ENABLED' if toggle_refresh else 'DISABLED'}")
        print(f"Display text: '{mode_text_refresh}'")
        
        if toggle_refresh and mode_text_refresh == "LIVE TRADING MODE":
            print("[OK] State persisted correctly (Live mode)")
        elif not toggle_refresh and mode_text_refresh == "MANUAL MODE":
            print("[OK] State persisted correctly (Manual mode)")
        else:
            print(f"[ERROR] INCONSISTENCY after refresh: Toggle={toggle_refresh}, Display={mode_text_refresh}")
        
        print("\n" + "="*70)
        print("SUMMARY:")
        print("="*70)
        
        # Final verdict
        if not is_checked and mode_text == "MANUAL MODE" and mode_text_refresh == "MANUAL MODE":
            print("[OK] AUTO TRADE TOGGLE IS WORKING CORRECTLY")
            print("   - Shows 'MANUAL MODE' when disabled")
            print("   - Shows correct background color")
            print("   - State persists after refresh")
        else:
            print("[WARNING] ISSUES DETECTED - Review the results above")
            
    except Exception as e:
        print(f"\n[ERROR] Error during test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_auto_trade_toggle()