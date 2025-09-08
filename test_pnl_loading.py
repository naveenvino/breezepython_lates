import requests
import time
import json

def test_pnl_display():
    """Test if P&L is displaying correctly instead of Loading..."""
    
    print("\n" + "="*60)
    print("TESTING P&L DISPLAY")
    print("="*60)
    
    base_url = "http://localhost:8000"
    
    # Test the API endpoints
    print("\n1. Testing /live/positions endpoint:")
    try:
        response = requests.get(f"{base_url}/live/positions")
        data = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Total P&L: ₹{data.get('total_pnl', 0)}")
        print(f"   Positions: {len(data.get('positions', []))}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test trading positions endpoint
    print("\n2. Testing /api/trading/positions endpoint:")
    try:
        response = requests.get(f"{base_url}/api/trading/positions")
        data = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Success: {data.get('success', False)}")
        print(f"   Count: {data.get('count', 0)}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Check HTML for Loading...
    print("\n3. Checking HTML content:")
    try:
        response = requests.get(f"{base_url}/tradingview_pro.html")
        html = response.text
        
        # Find the P&L display
        if 'id="todayPnL">Loading...' in html:
            print("   [WARNING] P&L still shows 'Loading...' in HTML")
            print("   This should be updated by JavaScript on page load")
        elif 'id="todayPnL">₹0' in html:
            print("   [OK] P&L shows ₹0 (no positions)")
        else:
            # Try to find what it shows
            import re
            match = re.search(r'id="todayPnL">([^<]+)<', html)
            if match:
                print(f"   [OK] P&L shows: {match.group(1)}")
            else:
                print("   [INFO] P&L value will be set by JavaScript")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*60)
    print("EXPECTED BEHAVIOR:")
    print("  • P&L should show '₹0' when no positions")
    print("  • Updates every 10 seconds automatically")
    print("  • Never stays on 'Loading...' for more than a few seconds")
    print("\nIf still showing 'Loading...':")
    print("  1. Check browser console for JavaScript errors")
    print("  2. Hard refresh the page (Ctrl+F5)")
    print("  3. Clear browser cache")
    print("="*60)

if __name__ == "__main__":
    test_pnl_display()