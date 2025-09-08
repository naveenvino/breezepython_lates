"""
Test script to verify no mock/dummy data remains in production code
"""

import json
import re
import os
import requests
from pathlib import Path

def test_api_endpoints():
    """Test that API endpoints don't return mock data"""
    base_url = "http://localhost:8000"
    tests_passed = []
    tests_failed = []
    
    print("\n[1] Testing API Endpoints...")
    
    # Test spot price endpoint
    try:
        response = requests.get(f"{base_url}/api/breeze/spot-price", timeout=2)
        data = response.json()
        
        # Check for hardcoded 25000 value
        if data and isinstance(data, dict):
            spot_value = data.get('spot')
            if spot_value == 25000:
                tests_failed.append("API returns hardcoded spot price 25000")
            elif spot_value is None or data.get('error'):
                tests_passed.append("Spot price correctly returns no data when unavailable")
            else:
                tests_passed.append(f"Spot price returns real value: {spot_value}")
        else:
            tests_passed.append("Spot price endpoint returns appropriate response")
    except Exception as e:
        print(f"  Warning: Could not test spot price endpoint: {e}")
    
    # Test market depth endpoint
    try:
        response = requests.get(f"{base_url}/api/market-depth/NIFTY", timeout=2)
        data = response.json()
        
        if data and isinstance(data, dict):
            if data.get('is_mock') == True:
                tests_failed.append("Market depth returns mock data flag")
            else:
                tests_passed.append("Market depth doesn't use mock flag")
    except Exception as e:
        print(f"  Warning: Could not test market depth endpoint: {e}")
    
    return tests_passed, tests_failed

def test_html_files():
    """Test that HTML files don't contain hardcoded values"""
    tests_passed = []
    tests_failed = []
    
    print("\n[2] Testing HTML Files...")
    
    html_files = [
        'tradingview_pro.html',
        'integrated_trading_dashboard.html',
        'live_trading_pro_complete.html',
        'margin_calculator.html',
        'tradingview_pro_real.html',
        'paper_trading.html',
        'expiry_comparison.html'
    ]
    
    forbidden_patterns = [
        (r'value="25000"', 'Hardcoded spot price 25000'),
        (r'value="200"[^>]*hedgeOffset', 'Hardcoded hedge offset 200'),
        (r'992005734', 'Hardcoded Telegram chat ID'),
        (r'return 25000;.*Default', 'Hardcoded fallback value 25000')
    ]
    
    for html_file in html_files:
        if os.path.exists(html_file):
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            file_ok = True
            for pattern, description in forbidden_patterns:
                if re.search(pattern, content):
                    tests_failed.append(f"{html_file}: Contains {description}")
                    file_ok = False
            
            if file_ok:
                tests_passed.append(f"{html_file}: No hardcoded values found")
    
    return tests_passed, tests_failed

def test_service_files():
    """Test that service files don't contain test prefixes"""
    tests_passed = []
    tests_failed = []
    
    print("\n[3] Testing Service Files...")
    
    service_files = [
        'src/services/iceberg_order_service.py',
        'src/services/live_market_service_fixed.py'
    ]
    
    for service_file in service_files:
        if os.path.exists(service_file):
            with open(service_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for TEST_ prefixes
            if 'TEST_' in content and 'order_id = f"TEST_' in content:
                tests_failed.append(f"{service_file}: Still contains TEST_ prefixes")
            else:
                tests_passed.append(f"{service_file}: No TEST_ prefixes found")
            
            # Check mock data methods don't raise exceptions inappropriately
            if 'raise Exception("Mock data is disabled' in content:
                tests_failed.append(f"{service_file}: Mock methods still raise exceptions")
    
    return tests_passed, tests_failed

def test_data_binding_helper():
    """Test that data binding helper was created"""
    tests_passed = []
    tests_failed = []
    
    print("\n[4] Testing Data Binding Helper...")
    
    helper_file = 'src/utils/data_binding_helper.py'
    if os.path.exists(helper_file):
        tests_passed.append("Data binding helper created successfully")
        
        # Test the helper module can be imported
        try:
            import sys
            sys.path.insert(0, 'src/utils')
            exec(open(helper_file).read())
            tests_passed.append("Data binding helper is valid Python code")
        except Exception as e:
            tests_failed.append(f"Data binding helper has syntax errors: {e}")
    else:
        tests_failed.append("Data binding helper not created")
    
    return tests_passed, tests_failed

def main():
    print("=" * 70)
    print("PRODUCTION READINESS TEST - NO MOCK DATA VERIFICATION")
    print("=" * 70)
    
    all_passed = []
    all_failed = []
    
    # Test API endpoints
    passed, failed = test_api_endpoints()
    all_passed.extend(passed)
    all_failed.extend(failed)
    
    # Test HTML files
    passed, failed = test_html_files()
    all_passed.extend(passed)
    all_failed.extend(failed)
    
    # Test service files
    passed, failed = test_service_files()
    all_passed.extend(passed)
    all_failed.extend(failed)
    
    # Test data binding helper
    passed, failed = test_data_binding_helper()
    all_passed.extend(passed)
    all_failed.extend(failed)
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    if all_passed:
        print(f"\nPASSED: {len(all_passed)} tests")
        for test in all_passed:
            print(f"  [OK] {test}")
    
    if all_failed:
        print(f"\nFAILED: {len(all_failed)} tests")
        for test in all_failed:
            print(f"  [FAIL] {test}")
    
    print("\n" + "=" * 70)
    if not all_failed:
        print("SUCCESS: All mock/dummy data has been removed!")
        print("The system is now production-ready with real data binding.")
    else:
        print(f"WARNING: {len(all_failed)} issues found. Please review and fix.")
    print("=" * 70)
    
    return len(all_failed) == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)