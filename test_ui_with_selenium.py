"""
Test TradingView Pro UI with Selenium to verify actual display
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
from datetime import datetime

def test_tradingview_ui():
    print("=" * 60)
    print("SELENIUM UI VERIFICATION TEST")
    print("=" * 60)
    print(f"Time: {datetime.now()}")
    print()
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = None
    try:
        # Initialize Chrome driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_window_size(1920, 1080)
        
        # Load the TradingView Pro page
        url = "http://localhost:8000/ui/modules/trading/tradingview_pro.html"
        print(f"Loading URL: {url}")
        driver.get(url)
        
        # Wait for page to load and API calls to complete
        print("Waiting for page to fully load...")
        time.sleep(5)
        
        # Try to trigger loadLiveSpotPrice function manually
        try:
            driver.execute_script("if (typeof window.loadLiveSpotPrice === 'function') { window.loadLiveSpotPrice(); }")
            print("Triggered loadLiveSpotPrice function")
            time.sleep(3)  # Wait for API response
        except Exception as e:
            print(f"Could not trigger loadLiveSpotPrice: {e}")
        
        print("\n1. CHECKING NIFTY SPOT PRICE")
        print("-" * 40)
        
        # Check multiple possible spot price elements
        spot_elements = [
            ("spotPrice", "Main spot price element"),
            ("niftySpot", "NIFTY spot element"),
            ("candleCurrentNifty", "Current NIFTY in candle monitor")
        ]
        
        spot_found = False
        for elem_id, description in spot_elements:
            try:
                element = driver.find_element(By.ID, elem_id)
                if element:
                    text = element.text.strip()
                    print(f"   {description} (#{elem_id}): '{text}'")
                    if text and text != "No data" and text != "--:--:--" and text != "0.00" and text != "Connecting...":
                        spot_found = True
                        print(f"   [VALID] Data found: {text}")
            except:
                print(f"   {description} (#{elem_id}): Not found")
        
        if not spot_found:
            print("   [X] No valid NIFTY spot price displayed")
        
        print("\n2. CHECKING ACTIVE ORDERS")
        print("-" * 40)
        try:
            orders_container = driver.find_element(By.ID, "activeOrdersContainer")
            orders = orders_container.find_elements(By.CLASS_NAME, "order-card")
            print(f"   Active orders displayed: {len(orders)}")
            if len(orders) > 0:
                first_order = orders[0]
                print(f"   First order text: {first_order.text[:100]}...")
        except:
            print("   Active orders container not found")
        
        print("\n3. CHECKING OPTION CHAIN")
        print("-" * 40)
        try:
            chain_container = driver.find_element(By.ID, "optionChainContainer")
            rows = chain_container.find_elements(By.TAG_NAME, "tr")
            print(f"   Option chain rows: {len(rows)}")
            if len(rows) > 1:  # More than header
                print("   [OK] Option chain is populated")
        except:
            print("   Option chain container not found")
        
        print("\n4. CHECKING WEBSOCKET STATUS")
        print("-" * 40)
        try:
            ws_element = driver.find_element(By.ID, "wsStatus")
            ws_text = ws_element.text.strip()
            print(f"   WebSocket status: '{ws_text}'")
            # Check color/class for connection status
            classes = ws_element.get_attribute("class")
            if "connected" in classes or "text-success" in classes:
                print("   [OK] WebSocket appears connected")
            else:
                print("   [X] WebSocket not connected")
        except:
            print("   WebSocket status element not found")
        
        print("\n5. CHECKING POSITIONS")
        print("-" * 40)
        try:
            positions_container = driver.find_element(By.ID, "positionsContainer")
            positions = positions_container.find_elements(By.CLASS_NAME, "position-card")
            print(f"   Positions displayed: {len(positions)}")
        except:
            print("   Positions container not found")
        
        print("\n6. CHECKING DATA SOURCE INDICATOR")
        print("-" * 40)
        try:
            # Look for any element showing data source
            source_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'KITE') or contains(text(), 'BREEZE')]")
            if source_elements:
                for elem in source_elements[:3]:  # Show first 3
                    print(f"   Found data source text: '{elem.text}'")
        except:
            print("   No data source indicators found")
        
        # Take a screenshot for manual review
        screenshot_path = "tradingview_ui_screenshot.png"
        driver.save_screenshot(screenshot_path)
        print(f"\n[SUCCESS] Screenshot saved: {screenshot_path}")
        
        # Check console errors
        print("\n7. CHECKING BROWSER CONSOLE")
        print("-" * 40)
        logs = driver.get_log('browser')
        errors = [log for log in logs if log['level'] == 'SEVERE']
        if errors:
            print(f"   Found {len(errors)} console errors:")
            for error in errors[:5]:  # Show first 5
                print(f"   - {error['message'][:100]}...")
        else:
            print("   No console errors found")
        
        # Final check - Try to fetch data via JavaScript
        print("\n8. JAVASCRIPT DATA CHECK")
        print("-" * 40)
        try:
            # Execute JavaScript to check if data is being fetched
            result = driver.execute_script("""
                return fetch('http://localhost:8000/api/live/nifty-spot')
                    .then(r => r.json())
                    .then(data => {
                        return {
                            success: data.success,
                            price: data.data ? data.data.price : null,
                            source: data.data ? data.data.source : null
                        };
                    })
                    .catch(e => ({error: e.message}));
            """)
            time.sleep(2)  # Wait for async execution
            result = driver.execute_async_script("""
                var callback = arguments[arguments.length - 1];
                fetch('http://localhost:8000/api/live/nifty-spot')
                    .then(r => r.json())
                    .then(data => callback(data))
                    .catch(e => callback({error: e.message}));
            """)
            print(f"   API Response: {result}")
            if result and result.get('success'):
                print(f"   [OK] API is returning data: {result.get('data', {}).get('price')} from {result.get('data', {}).get('source')}")
        except Exception as e:
            print(f"   Could not fetch via JavaScript: {e}")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if driver:
            print("\nClosing browser...")
            driver.quit()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_tradingview_ui()