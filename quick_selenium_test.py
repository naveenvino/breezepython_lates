"""
Quick Selenium test to find the issue
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

# Setup Chrome in headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

driver = webdriver.Chrome(options=chrome_options)

try:
    print("Loading page...")
    driver.get("http://localhost:8000/tradingview_pro.html")
    time.sleep(3)
    
    # Check display values
    current_nifty = driver.find_element(By.ID, "candleCurrentNifty").text
    last_close = driver.find_element(By.ID, "candleLastClose").text
    
    print(f"Current NIFTY: '{current_nifty}'")
    print(f"Last 1H Close: '{last_close}'")
    
    # Execute update function
    print("\nRunning update1HCandleMonitor()...")
    driver.execute_script("update1HCandleMonitor();")
    time.sleep(3)
    
    # Check values after update
    current_nifty_after = driver.find_element(By.ID, "candleCurrentNifty").text
    last_close_after = driver.find_element(By.ID, "candleLastClose").text
    
    print(f"After update - Current NIFTY: '{current_nifty_after}'")
    print(f"After update - Last 1H Close: '{last_close_after}'")
    
    # Get any errors from console
    logs = driver.get_log('browser')
    errors = [log for log in logs if log['level'] == 'SEVERE']
    if errors:
        print("\nErrors found:")
        for error in errors:
            print(f"  {error['message']}")
    
finally:
    driver.quit()
    print("\nTest complete")