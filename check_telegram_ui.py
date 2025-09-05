"""
Check if Telegram configuration is visible in the UI using Selenium
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

try:
    # Create driver
    print("Starting Chrome driver...")
    driver = webdriver.Chrome(options=chrome_options)
    
    # Load the page
    print("Loading tradingview_pro.html...")
    driver.get("file:///C:/Users/E1791/Kitepy/breezepython/tradingview_pro.html")
    
    # Wait for page to load
    time.sleep(3)
    
    # Check if Telegram checkbox exists
    try:
        telegram_checkbox = driver.find_element(By.ID, "telegramEnabled")
        print(f"[OK] Telegram checkbox found - Checked: {telegram_checkbox.is_selected()}")
    except:
        print("[FAIL] Telegram checkbox NOT found")
    
    # Check if Telegram config div exists and is visible
    try:
        telegram_config = driver.find_element(By.ID, "telegramConfig")
        is_displayed = telegram_config.is_displayed()
        style = telegram_config.get_attribute("style")
        print(f"[OK] Telegram config div found - Visible: {is_displayed}")
        print(f"  Style attribute: {style}")
    except:
        print("[FAIL] Telegram config div NOT found")
    
    # Check if Bot Token field exists
    try:
        bot_token = driver.find_element(By.ID, "telegramBotToken")
        token_value = bot_token.get_attribute("value")
        print(f"[OK] Bot Token field found - Value: {token_value[:20]}..." if token_value else "[FAIL] Bot Token field empty")
    except:
        print("[FAIL] Bot Token field NOT found")
    
    # Check if Chat ID field exists
    try:
        chat_id = driver.find_element(By.ID, "telegramChatId")
        chat_value = chat_id.get_attribute("value")
        print(f"[OK] Chat ID field found - Value: {chat_value}")
    except:
        print("[FAIL] Chat ID field NOT found")
    
    # Check if Test button exists
    try:
        test_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Test Telegram')]")
        if test_buttons:
            print(f"[OK] Test Telegram button found")
        else:
            print("[FAIL] Test Telegram button NOT found")
    except:
        print("[FAIL] Error finding Test Telegram button")
    
    # Execute JavaScript to check what's happening
    print("\n--- JavaScript Console Check ---")
    
    # Check if loadAlertConfig function exists
    has_function = driver.execute_script("return typeof loadAlertConfig === 'function';")
    print(f"loadAlertConfig function exists: {has_function}")
    
    # Try to manually trigger the function
    if has_function:
        print("Manually triggering loadAlertConfig()...")
        driver.execute_script("loadAlertConfig();")
        time.sleep(2)
        
        # Check again if config is visible
        telegram_config = driver.find_element(By.ID, "telegramConfig")
        is_displayed_after = telegram_config.is_displayed()
        style_after = telegram_config.get_attribute("style")
        print(f"After manual trigger - Visible: {is_displayed_after}")
        print(f"Style after trigger: {style_after}")
    
    # Get any console errors
    logs = driver.get_log('browser')
    if logs:
        print("\n--- Browser Console Logs ---")
        for log in logs:
            if 'ALERT' in log['message'] or 'error' in log['message'].lower():
                print(f"{log['level']}: {log['message']}")
    
    # Try alternative approach - directly set visibility
    print("\n--- Forcing visibility via JavaScript ---")
    driver.execute_script("""
        var checkbox = document.getElementById('telegramEnabled');
        var config = document.getElementById('telegramConfig');
        if (checkbox) {
            checkbox.checked = true;
            console.log('Checkbox checked');
        }
        if (config) {
            config.style.display = 'block';
            config.style.visibility = 'visible';
            console.log('Config made visible');
        }
        if (document.getElementById('telegramBotToken')) {
            document.getElementById('telegramBotToken').value = '8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM';
        }
        if (document.getElementById('telegramChatId')) {
            document.getElementById('telegramChatId').value = '992005734';
        }
    """)
    
    time.sleep(1)
    
    # Final check
    telegram_config = driver.find_element(By.ID, "telegramConfig")
    print(f"\nFinal check - Config visible: {telegram_config.is_displayed()}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    
finally:
    if 'driver' in locals():
        driver.quit()
        print("\nDriver closed")