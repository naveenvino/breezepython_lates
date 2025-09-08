"""
Test the candle display issue using Selenium
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import json

def test_candle_display():
    print("\n" + "="*70)
    print("TESTING CANDLE DISPLAY WITH SELENIUM")
    print("="*70)
    
    # Setup Chrome in headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # 1. Load the main page
        print("\n[1] Loading tradingview_pro.html...")
        driver.get("http://localhost:8000/tradingview_pro.html")
        time.sleep(3)  # Wait for page to load
        
        # 2. Check current display values
        print("\n[2] Current Display Values:")
        print("-" * 40)
        
        try:
            current_nifty = driver.find_element(By.ID, "candleCurrentNifty").text
            print(f"Current NIFTY: '{current_nifty}'")
        except:
            print("Current NIFTY element not found!")
            
        try:
            last_close = driver.find_element(By.ID, "candleLastClose").text
            print(f"Last 1H Close: '{last_close}'")
        except:
            print("Last 1H Close element not found!")
        
        # 3. Execute JavaScript to check what's happening
        print("\n[3] Running JavaScript diagnostics...")
        print("-" * 40)
        
        # Check if update function exists
        result = driver.execute_script("return typeof update1HCandleMonitor;")
        print(f"update1HCandleMonitor exists: {result}")
        
        # Check if monitor is running
        result = driver.execute_script("return typeof hourCandleMonitor;")
        print(f"hourCandleMonitor interval exists: {result}")
        
        # 4. Manually trigger update and capture console logs
        print("\n[4] Manually triggering update1HCandleMonitor()...")
        print("-" * 40)
        
        # Enable console log capture
        driver.execute_script("""
            window.capturedLogs = [];
            const originalLog = console.log;
            const originalError = console.error;
            console.log = function() {
                window.capturedLogs.push({type: 'log', args: Array.from(arguments)});
                originalLog.apply(console, arguments);
            };
            console.error = function() {
                window.capturedLogs.push({type: 'error', args: Array.from(arguments)});
                originalError.apply(console, arguments);
            };
        """)
        
        # Run the update function
        driver.execute_script("update1HCandleMonitor();")
        time.sleep(3)  # Wait for async operations
        
        # Get captured logs
        logs = driver.execute_script("return window.capturedLogs;")
        
        print("Console output:")
        for log in logs:
            if '[CANDLE MONITOR]' in str(log['args']) or '[DEBUG]' in str(log['args']):
                print(f"  {log['type'].upper()}: {log['args']}")
        
        # 5. Check values after update
        print("\n[5] Display Values After Update:")
        print("-" * 40)
        
        current_nifty = driver.find_element(By.ID, "candleCurrentNifty").text
        print(f"Current NIFTY: '{current_nifty}'")
        
        last_close = driver.find_element(By.ID, "candleLastClose").text
        print(f"Last 1H Close: '{last_close}'")
        
        # 6. Test API calls directly from browser
        print("\n[6] Testing API calls from browser...")
        print("-" * 40)
        
        # Test spot API
        spot_result = driver.execute_script("""
            return fetch('http://localhost:8000/api/live/nifty-spot')
                .then(r => r.json())
                .then(data => data);
        """)
        time.sleep(1)
        spot_data = driver.execute_script("return arguments[0];", spot_result)
        print(f"Spot API response: {json.dumps(spot_data, indent=2) if spot_data else 'Failed'}")
        
        # Test candle API
        candle_result = driver.execute_script("""
            return fetch('http://localhost:8000/api/breeze/hourly-candle')
                .then(r => r.json())
                .then(data => data);
        """)
        time.sleep(1)
        candle_data = driver.execute_script("return arguments[0];", candle_result)
        print(f"Candle API response: {json.dumps(candle_data, indent=2) if candle_data else 'Failed'}")
        
        # 7. Try the debug page
        print("\n[7] Testing debug page...")
        print("-" * 40)
        driver.get("http://localhost:8000/debug_candle_monitor.html")
        time.sleep(2)
        
        # Click update button
        driver.find_element(By.XPATH, "//button[contains(text(), 'Update Now')]").click()
        time.sleep(2)
        
        debug_nifty = driver.find_element(By.ID, "testCurrentNifty").text
        debug_close = driver.find_element(By.ID, "testLastClose").text
        
        print(f"Debug page - Current NIFTY: '{debug_nifty}'")
        print(f"Debug page - Last 1H Close: '{debug_close}'")
        
        print("\n" + "="*70)
        print("ANALYSIS:")
        print("="*70)
        
        if current_nifty == "No data" and debug_nifty != "No data":
            print("❌ Main page is NOT working but debug page IS working")
            print("   -> Issue is in the main page JavaScript logic")
        elif current_nifty != "No data":
            print("✅ Main page is working correctly")
        else:
            print("❌ Both pages show 'No data'")
            print("   -> Issue might be with API or data availability")
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\nClosing browser in 5 seconds...")
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    test_candle_display()