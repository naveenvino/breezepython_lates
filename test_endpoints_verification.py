"""
Quick verification that all missing endpoints have been added to unified_api_correct.py
This doesn't run the API but verifies the code exists
"""
import re

def verify_endpoints():
    print("=" * 60)
    print("ENDPOINT CODE VERIFICATION")
    print("=" * 60)
    
    try:
        with open('unified_api_correct.py', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ unified_api_correct.py not found!")
        return
    
    # List of endpoints that were missing and should now be present
    required_endpoints = [
        # Settings CRUD
        ('GET', '/settings/{key}', 'get_setting'),
        ('PUT', '/settings/{key}', 'update_setting'),
        ('DELETE', '/settings/{key}', 'delete_setting'),
        
        # Trade Config
        ('POST', '/save-trade-config', 'save_trade_config'),
        ('GET', '/trade-config', 'get_trade_config'),
        
        # Signal States
        ('POST', '/save-signal-states', 'save_signal_states'),
        ('GET', '/signal-states', 'get_signal_states'),
        
        # Expiry Config
        ('POST', '/save-weekday-expiry-config', 'save_weekday_expiry_config'),
        ('GET', '/weekday-expiry-config', 'get_weekday_expiry_config'),
        ('POST', '/save-exit-timing-config', 'save_exit_timing_config'),
        
        # Market Data
        ('GET', '/nifty-spot', 'get_nifty_spot'),
        ('GET', '/positions', 'get_positions'),
    ]
    
    results = []
    
    for method, endpoint, func_name in required_endpoints:
        # Check for endpoint decorator
        escaped_endpoint = re.escape(endpoint.replace("{key}", ""))
        endpoint_pattern = f'@app\\.{method.lower()}\\(["\'].*{escaped_endpoint}.*["\']'
        endpoint_found = bool(re.search(endpoint_pattern, content, re.IGNORECASE))
        
        # Check for function definition
        func_pattern = rf'async def {func_name}\('
        func_found = bool(re.search(func_pattern, content))
        
        success = endpoint_found and func_found
        results.append((method, endpoint, func_name, success, endpoint_found, func_found))
        
        status = "[OK] FOUND" if success else "[X] MISSING"
        print(f"{method:6} {endpoint:30} {func_name:25} {status}")
        
        if not success:
            if not endpoint_found:
                print(f"       └── Missing decorator: @app.{method.lower()}(...)")
            if not func_found:
                print(f"       └── Missing function: async def {func_name}(...)")
    
    print("=" * 60)
    
    # Check for the section header
    if "# MISSING UI INTEGRATION ENDPOINTS" in content:
        print("[OK] Found integration endpoints section")
    else:
        print("[X] Missing integration endpoints section")
    
    # Summary
    total = len(required_endpoints)
    found = sum(1 for _, _, _, success, _, _ in results if success)
    missing = total - found
    
    print(f"\nSUMMARY:")
    print(f"Total endpoints required: {total}")
    print(f"Found in code: {found}")
    print(f"Missing: {missing}")
    print(f"Success rate: {found/total*100:.1f}%")
    
    if missing == 0:
        print("\n[SUCCESS] ALL REQUIRED ENDPOINTS HAVE BEEN ADDED!")
        print("The unified_api_correct.py now includes all missing endpoints.")
        print("Ready for testing once the API server is running.")
    else:
        print(f"\n[WARNING] {missing} endpoints still need to be added.")
        
    # Check database setup
    if "sqlite3.connect" in content and "trading_settings.db" in content:
        print("[OK] SQLite database setup found")
    else:
        print("[X] Database setup missing")
        
    # Check error handling
    error_handling_count = len(re.findall(r'try:\s*.*?except.*?Exception', content, re.DOTALL))
    print(f"[OK] Found {error_handling_count} error handling blocks")
    
    print("=" * 60)

if __name__ == "__main__":
    verify_endpoints()