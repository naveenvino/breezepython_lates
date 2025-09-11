"""
Test if immediate load script executes
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

chrome_options = Options()
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
chrome_options.add_experimental_option('prefs', {'profile.default_content_setting_values.notifications': 2})

driver = webdriver.Chrome(options=chrome_options)
driver.get("file:///C:/Users/E1791/Kitepy/breezepython/tradingview_pro.html")
time.sleep(2)

# Check if script executed by looking for console logs
result = driver.execute_script("""
    // Check if our immediate load script ran
    const scripts = document.getElementsByTagName('script');
    let foundScript = false;
    for (let script of scripts) {
        if (script.innerHTML.includes('[IMMEDIATE LOAD]')) {
            foundScript = true;
            break;
        }
    }
    
    // Also check current dropdown values
    return {
        scriptFound: foundScript,
        mondayValue: document.getElementById('expiryMonday').value,
        tuesdayValue: document.getElementById('expiryTuesday').value,
        localStorage: localStorage.getItem('weekdayExpiryConfig')
    };
""")

print("Script found in HTML:", result['scriptFound'])
print("Monday value:", result['mondayValue'])
print("Tuesday value:", result['tuesdayValue'])
print("LocalStorage:", result['localStorage'])

# Now manually run the immediate load code to see if it works
driver.execute_script("""
    console.log('[TEST] Manually running immediate load logic...');
    const saved = localStorage.getItem('weekdayExpiryConfig');
    if (saved) {
        const config = JSON.parse(saved);
        console.log('[TEST] Config found:', config);
        
        const weekdays = ['monday', 'tuesday', 'wednesday', 'tuesday', 'friday'];
        weekdays.forEach(day => {
            const select = document.getElementById('expiry' + day.charAt(0).toUpperCase() + day.slice(1));
            if (select && config[day]) {
                console.log(`[TEST] Setting ${day} from ${select.value} to ${config[day]}`);
                select.value = config[day];
            }
        });
    }
""")

time.sleep(1)

# Check values after manual execution
result2 = driver.execute_script("""
    return {
        mondayValue: document.getElementById('expiryMonday').value,
        tuesdayValue: document.getElementById('expiryTuesday').value
    };
""")

print("\nAfter manual execution:")
print("Monday value:", result2['mondayValue'])
print("Tuesday value:", result2['tuesdayValue'])

driver.quit()
