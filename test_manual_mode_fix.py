"""
Test that MANUAL MODE is not duplicated
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

def test_manual_mode_fix():
    print("\n" + "="*70)
    print("TESTING MANUAL MODE DUPLICATION FIX")
    print("="*70)
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print("\n[1] Loading tradingview_pro.html directly...")
        driver.get("http://localhost:8000/tradingview_pro.html")
        time.sleep(3)
        
        # Find all elements containing "MANUAL MODE"
        all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'MANUAL MODE')]")
        print(f"Elements with 'MANUAL MODE' text: {len(all_elements)}")
        
        for i, elem in enumerate(all_elements):
            print(f"  Element {i+1}: tag={elem.tag_name}, id={elem.get_attribute('id')}, visible={elem.is_displayed()}")
        
        # Check specific known elements
        print("\n[2] Checking specific elements:")
        print("-" * 40)
        
        # Check tradingModeText
        try:
            mode_text = driver.find_element(By.ID, "tradingModeText")
            print(f"tradingModeText found: '{mode_text.text}', visible: {mode_text.is_displayed()}")
        except:
            print("tradingModeText not found")
        
        # Check for autoTradeStatusIndicator (should not exist anymore)
        try:
            auto_indicator = driver.find_element(By.ID, "autoTradeStatusIndicator")
            print(f"autoTradeStatusIndicator found: '{auto_indicator.text}', visible: {auto_indicator.is_displayed()}")
        except:
            print("autoTradeStatusIndicator not found (GOOD - no duplicate)")
        
        # Check overall visible text
        print("\n[3] Checking visible text in master controls area:")
        print("-" * 40)
        
        master_controls = driver.find_element(By.CLASS_NAME, "master-controls")
        visible_text = master_controls.text
        manual_count = visible_text.count("MANUAL MODE")
        print(f"'MANUAL MODE' appears {manual_count} time(s) in master controls")
        print(f"Master controls text:\n{visible_text}")
        
        print("\n" + "="*70)
        print("RESULTS:")
        print("="*70)
        
        if manual_count == 1 and len(all_elements) == 1:
            print("[OK] FIX SUCCESSFUL!")
            print("  - 'MANUAL MODE' appears only once")
            print("  - No duplicate status indicators")
        else:
            print("[ERROR] Duplication still exists")
            print(f"  - 'MANUAL MODE' appears {manual_count} time(s)")
            print(f"  - Total elements with text: {len(all_elements)}")
            
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_manual_mode_fix()