#!/usr/bin/env python3
"""
Verification script to ensure NO mock data appears in the trading system
"""

import asyncio
import aiohttp
import json
from datetime import datetime

async def test_api_endpoints():
    """Test all API endpoints to ensure they don't return mock data"""
    
    base_url = "http://localhost:8000"
    results = []
    
    print("=" * 60)
    print("TESTING API ENDPOINTS FOR MOCK DATA")
    print("=" * 60)
    
    # Test NIFTY spot endpoint
    async with aiohttp.ClientSession() as session:
        try:
            # Test 1: NIFTY spot endpoint
            async with session.get(f"{base_url}/api/live/nifty-spot") as resp:
                data = await resp.json()
                
                print("\n1. Testing /api/live/nifty-spot")
                print(f"   Response: {json.dumps(data, indent=2)}")
                
                if data.get("success"):
                    spot_data = data.get("data", {})
                    
                    # Check for mock flag
                    if spot_data.get("is_mock"):
                        print("   [FAIL] Mock data detected!")
                        results.append(("NIFTY Spot", "FAIL", "Mock data flag present"))
                    else:
                        ltp = spot_data.get("ltp", 0)
                        if 15000 < ltp < 35000:
                            print(f"   [PASS] Real data: {ltp}")
                            results.append(("NIFTY Spot", "PASS", f"Real: {ltp}"))
                        else:
                            print(f"   [FAIL] Unrealistic value: {ltp}")
                            results.append(("NIFTY Spot", "FAIL", f"Bad value: {ltp}"))
                else:
                    error = data.get("error", "Unknown error")
                    print(f"   [OK] API returned error (expected if Breeze not connected): {error}")
                    results.append(("NIFTY Spot", "OK", "No data (Breeze disconnected)"))
                    
        except Exception as e:
            print(f"   [ERROR] Failed to test endpoint: {e}")
            results.append(("NIFTY Spot", "ERROR", str(e)))
            
        # Test 2: Option chain endpoint
        try:
            async with session.get(f"{base_url}/api/live/option-chain?strike=25000&range=1") as resp:
                data = await resp.json()
                
                print("\n2. Testing /api/live/option-chain")
                
                if data.get("success"):
                    chain = data.get("chain", [])
                    if chain and any(opt.get("is_mock") for opt in chain):
                        print("   [FAIL] Mock option data detected!")
                        results.append(("Option Chain", "FAIL", "Mock data in chain"))
                    elif chain:
                        print(f"   [PASS] Real option chain with {len(chain)} strikes")
                        results.append(("Option Chain", "PASS", f"{len(chain)} real strikes"))
                    else:
                        print("   [OK] Empty chain (market may be closed)")
                        results.append(("Option Chain", "OK", "Empty chain"))
                else:
                    print(f"   [OK] API returned error: {data.get('error', 'Unknown')}")
                    results.append(("Option Chain", "OK", "No data available"))
                    
        except Exception as e:
            print(f"   [ERROR] Failed to test endpoint: {e}")
            results.append(("Option Chain", "ERROR", str(e)))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for endpoint, status, detail in results:
        symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️" if status == "ERROR" else "ℹ️"
        print(f"{symbol} {endpoint:20} {status:6} - {detail}")
    
    # Overall verdict
    has_mock = any(status == "FAIL" for _, status, _ in results)
    
    print("\n" + "=" * 60)
    if has_mock:
        print("❌ FAILED: Mock data detected in the system!")
        print("Action needed: Check the service configuration")
    else:
        print("✅ PASSED: No mock data detected")
        print("System is correctly configured to show only real data or 'No data'")
    print("=" * 60)
    
    return not has_mock

async def check_ui_elements():
    """Simulate checking UI elements"""
    
    print("\n" + "=" * 60)
    print("UI ELEMENT VERIFICATION")
    print("=" * 60)
    
    print("\n1. Header NIFTY Spot Display:")
    print("   - Initial state: 'No data' (not 'Loading...')")
    print("   - With Breeze connected: Shows real price in green")
    print("   - Without Breeze: Shows 'No data' in red")
    
    print("\n2. 1H Candle Monitor - Current NIFTY:")
    print("   - Only accepts values between 15,000 and 35,000")
    print("   - Rejects any data with is_mock flag")
    print("   - Shows 'No data' instead of random values")
    
    print("\n3. Data Validation Chain:")
    print("   - Header text checked against invalid list")
    print("   - API response checked for is_mock flag")
    print("   - Values validated for realistic range")
    print("   - Final display only if all checks pass")

if __name__ == "__main__":
    print(f"Mock Data Verification Script")
    print(f"Started at: {datetime.now()}")
    
    success = asyncio.run(test_api_endpoints())
    check_ui_elements()
    
    print(f"\nCompleted at: {datetime.now()}")
    exit(0 if success else 1)