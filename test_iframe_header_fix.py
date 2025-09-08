"""
Test that duplicate headers are hidden when tradingview_pro.html is loaded in iframe
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

def test_iframe_header_fix():
    print("\n" + "="*70)
    print("TESTING IFRAME HEADER FIX")
    print("="*70)
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Test 1: Load tradingview_pro.html directly
        print("\n[1] Testing direct load of tradingview_pro.html:")
        print("-" * 40)
        driver.get("http://localhost:8000/tradingview_pro.html")
        time.sleep(2)
        
        # Check if header is visible
        header = driver.find_element(By.CLASS_NAME, "header")
        is_visible_direct = header.is_displayed()
        print(f"Header visible when loaded directly: {is_visible_direct}")
        
        # Check for in-iframe class
        has_iframe_class_direct = "in-iframe" in driver.find_element(By.TAG_NAME, "html").get_attribute("class") or ""
        print(f"Has 'in-iframe' class: {has_iframe_class_direct}")
        
        # Test 2: Load index_hybrid.html and navigate to tradingview_pro
        print("\n[2] Testing when loaded in iframe via index_hybrid.html:")
        print("-" * 40)
        driver.get("http://localhost:8000/index_hybrid.html")
        time.sleep(2)
        
        # Click on TradingView Pro menu item or card
        try:
            # Try to find and click the menu item
            menu_item = driver.find_element(By.XPATH, "//a[@data-page='tradingview_pro.html']")
            menu_item.click()
            print("Clicked TradingView Pro menu item")
        except:
            try:
                # Try to find and click the dashboard card
                card = driver.find_element(By.XPATH, "//div[@onclick=\"loadPageDirect('tradingview_pro.html', 'TradingView Pro')\"]")
                card.click()
                print("Clicked TradingView Pro dashboard card")
            except:
                print("Could not find TradingView Pro link")
                return
        
        time.sleep(3)
        
        # Switch to iframe
        iframe = driver.find_element(By.ID, "contentFrame")
        driver.switch_to.frame(iframe)
        
        # Check if header is hidden in iframe
        try:
            header_in_iframe = driver.find_element(By.CLASS_NAME, "header")
            is_visible_iframe = header_in_iframe.is_displayed()
            print(f"Header visible when in iframe: {is_visible_iframe}")
        except:
            print("Header element not found (good - it's hidden)")
            is_visible_iframe = False
        
        # Check for in-iframe class
        has_iframe_class = "in-iframe" in driver.find_element(By.TAG_NAME, "html").get_attribute("class") or ""
        print(f"Has 'in-iframe' class: {has_iframe_class}")
        
        # Check if master controls are still visible
        try:
            master_controls = driver.find_element(By.CLASS_NAME, "master-controls")
            controls_visible = master_controls.is_displayed()
            print(f"Master controls visible: {controls_visible}")
        except:
            print("Master controls not found")
            controls_visible = False
        
        # Switch back to main frame
        driver.switch_to.default_content()
        
        # Check parent page header
        parent_header = driver.find_element(By.CLASS_NAME, "top-nav")
        parent_visible = parent_header.is_displayed()
        print(f"Parent page header visible: {parent_visible}")
        
        print("\n" + "="*70)
        print("RESULTS:")
        print("="*70)
        
        if is_visible_direct and not is_visible_iframe and controls_visible and parent_visible:
            print("[OK] FIX IS WORKING CORRECTLY!")
            print("  - Header shows when page loaded directly")
            print("  - Header hidden when loaded in iframe")
            print("  - Master controls remain visible")
            print("  - Parent header shows properly")
            print("\nNo more duplicate headers!")
        else:
            print("[ERROR] Fix not working as expected")
            print(f"  Direct load header: {is_visible_direct} (should be True)")
            print(f"  Iframe header: {is_visible_iframe} (should be False)")
            print(f"  Master controls: {controls_visible} (should be True)")
            print(f"  Parent header: {parent_visible} (should be True)")
            
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_iframe_header_fix()