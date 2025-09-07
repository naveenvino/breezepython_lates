"""
Test with pre-saved config
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import json

chrome_options = Options()
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

driver = webdriver.Chrome(options=chrome_options)
driver.get("file:///C:/Users/E1791/Kitepy/breezepython/tradingview_pro.html")
time.sleep(2)

# Save config to localStorage
driver.execute_script("""
    const config = {
        monday: 'next',
        tuesday: 'monthend',
        wednesday: 'next', 
        thursday: 'next',
        friday: 'next'
    };
    localStorage.setItem('weekdayExpiryConfig', JSON.stringify(config));
    console.log('Config saved:', config);
""")

print("Config saved, now refreshing...")

# Refresh the page
driver.refresh()
time.sleep(3)

# Check what happened
result = driver.execute_script("""
    // Get console output by intercepting console.log
    const logs = [];
    const originalLog = console.log;
    console.log = function(...args) {
        logs.push(args.join(' '));
        originalLog.apply(console, args);
    };
    
    // Re-run the immediate load logic to capture logs
    (function() {
        console.log('[RE-RUN TEST] Loading weekday expiry settings...');
        const saved = localStorage.getItem('weekdayExpiryConfig');
        if (saved) {
            try {
                const config = JSON.parse(saved);
                console.log('[RE-RUN TEST] Found saved config:', JSON.stringify(config));
                
                const weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'];
                weekdays.forEach(day => {
                    const select = document.getElementById('expiry' + day.charAt(0).toUpperCase() + day.slice(1));
                    if (select && config[day]) {
                        console.log(`[RE-RUN TEST] Setting ${day} to ${config[day]}`);
                        select.value = config[day];
                    }
                });
            } catch (e) {
                console.log('[RE-RUN TEST] Error:', e.message);
            }
        } else {
            console.log('[RE-RUN TEST] No saved config found');
        }
    })();
    
    return {
        mondayBefore: document.getElementById('expiryMonday').value,
        tuesdayBefore: document.getElementById('expiryTuesday').value,
        logs: logs,
        localStorage: localStorage.getItem('weekdayExpiryConfig')
    };
""")

print("\n=== RESULTS ===")
print(f"Monday value: {result['mondayBefore']}")
print(f"Tuesday value: {result['tuesdayBefore']}")
print(f"LocalStorage: {result['localStorage']}")
print("\n=== CONSOLE LOGS FROM RE-RUN ===")
for log in result['logs']:
    print(log)

# Final check after re-run
final = driver.execute_script("""
    return {
        monday: document.getElementById('expiryMonday').value,
        tuesday: document.getElementById('expiryTuesday').value
    };
""")

print("\n=== AFTER RE-RUN ===")
print(f"Monday: {final['monday']}")
print(f"Tuesday: {final['tuesday']}")

driver.quit()
