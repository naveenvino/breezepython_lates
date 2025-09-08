import requests
import json
import time

def test_endpoint(url, method="GET", data=None):
    """Test an endpoint and return status"""
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        else:
            response = requests.post(url, json=data, timeout=5)
        
        if response.status_code == 200:
            return True, "OK"
        else:
            return False, f"Status {response.status_code}"
    except Exception as e:
        return False, str(e)

def main():
    base_url = "http://localhost:8000"
    
    print("\n" + "="*60)
    print("HTML PAGES API INTEGRATION TEST")
    print("="*60)
    
    # Test endpoints used by index_hybrid.html
    print("\n[TEST] Endpoints for index_hybrid.html:")
    hybrid_endpoints = [
        ("/time/internet", "GET"),
        ("/status/all", "GET"),
        ("/auth/auto-login/status", "GET"),
        ("/session/validate?api_type=kite", "GET"),
        ("/session/validate?api_type=breeze", "GET"),
        ("/auth/auto-login/kite", "POST"),
        ("/auth/auto-login/breeze", "POST"),
        ("/system/metrics", "GET"),
        ("/health", "GET"),
        ("/signals/detect", "GET"),
        ("/positions", "GET"),
        ("/orders", "GET"),
        ("/live/pnl", "GET")
    ]
    
    hybrid_pass = 0
    hybrid_fail = 0
    
    for endpoint, method in hybrid_endpoints:
        success, msg = test_endpoint(base_url + endpoint, method)
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {endpoint}: {msg}")
        if success:
            hybrid_pass += 1
        else:
            hybrid_fail += 1
    
    # Test endpoints used by tradingview_pro.html
    print("\n[TEST] Endpoints for tradingview_pro.html:")
    tradingview_endpoints = [
        ("/api/trade-config/save", "POST", {"config_name": "test", "parameters": {"num_lots": 10}}),
        ("/api/trade-config/load/default?user_id=default", "GET", None),
        ("/api/live/nifty-spot", "GET", None),
        ("/live/auth/status", "GET", None),
        ("/kite/status", "GET", None),
        ("/live/positions", "GET", None),
        ("/api/trading/positions", "GET", None),
        ("/signals/statistics", "GET", None),
        ("/api/health", "GET", None),
        ("/api/webhook/metrics", "GET", None),
        ("/live/candles/latest?count=1", "GET", None),
        ("/api/execute-trade", "POST", {"signal": "S1", "strike": 25000, "option_type": "CALL", "quantity": 75}),
        ("/api/option-chain?strike=25000&type=CALL", "GET", None)
    ]
    
    tv_pass = 0
    tv_fail = 0
    
    for item in tradingview_endpoints:
        if len(item) == 3:
            endpoint, method, data = item
        else:
            endpoint, method = item
            data = None
        success, msg = test_endpoint(base_url + endpoint, method, data)
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {endpoint}: {msg}")
        if success:
            tv_pass += 1
        else:
            tv_fail += 1
    
    # Test HTML pages themselves
    print("\n[TEST] HTML Page Loading:")
    html_pages = [
        "/index_hybrid.html",
        "/tradingview_pro.html"
    ]
    
    for page in html_pages:
        response = requests.get(base_url + page)
        if response.status_code == 200 and "TradingView" in response.text:
            print(f"  [OK] {page}: Loads successfully")
        else:
            print(f"  [FAIL] {page}: Failed to load")
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"\nindex_hybrid.html endpoints:")
    print(f"  Passed: {hybrid_pass}/{len(hybrid_endpoints)}")
    print(f"  Failed: {hybrid_fail}/{len(hybrid_endpoints)}")
    
    print(f"\ntradingview_pro.html endpoints:")
    print(f"  Passed: {tv_pass}/{len(tradingview_endpoints)}")
    print(f"  Failed: {tv_fail}/{len(tradingview_endpoints)}")
    
    total_pass = hybrid_pass + tv_pass
    total_endpoints = len(hybrid_endpoints) + len(tradingview_endpoints)
    success_rate = (total_pass / total_endpoints) * 100
    
    print(f"\nOverall Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("\n[SUCCESS] HTML pages are working properly!")
    elif success_rate >= 70:
        print("\n[WARNING] HTML pages are partially working")
    else:
        print("\n[ERROR] HTML pages have significant issues")

if __name__ == "__main__":
    main()