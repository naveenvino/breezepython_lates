"""
Test to verify what happens with immediate load script
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import json

chrome_options = Options()
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

driver = webdriver.Chrome(options=chrome_options)

# First set some values and save them
driver.get("file:///C:/Users/E1791/Kitepy/breezepython/tradingview_pro.html")
time.sleep(2)

# Set Monday to next, Tuesday to monthend
driver.execute_script("""
    document.getElementById('expiryMonday').value = 'next';
    document.getElementById('expiryTuesday').value = 'monthend';
    
    // Save to localStorage
    const config = {
        monday: 'next',
        tuesday: 'monthend',
        wednesday: 'next',
        thursday: 'next',
        friday: 'next'
    };
    localStorage.setItem('weekdayExpiryConfig', JSON.stringify(config));
    console.log('Saved config:', config);
""")

print("Config saved to localStorage")
time.sleep(1)

# Now refresh and check console logs
driver.refresh()
time.sleep(2)

# Get all console logs and dropdown values
logs = driver.get_log('browser')
monday_val = driver.execute_script("return document.getElementById('expiryMonday').value;")
tuesday_val = driver.execute_script("return document.getElementById('expiryTuesday').value;")
storage_val = driver.execute_script("return localStorage.getItem('weekdayExpiryConfig');")

print("\n=== CONSOLE LOGS ===")
for log in logs:
    if 'IMMEDIATE' in log.get('message', '') or 'WEEKDAY' in log.get('message', ''):
        print(log['message'])

print(f"\n=== ACTUAL VALUES ===")
print(f"Monday dropdown: {monday_val}")
print(f"Tuesday dropdown: {tuesday_val}")
print(f"LocalStorage: {storage_val}")

driver.quit()
