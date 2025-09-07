"""
Comprehensive UI-API Integration Test
Tests all critical endpoints that the UI uses
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import time

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "tradingview-webhook-secret-key-2025"

class UIAPIIntegrationTest:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    async def test_endpoint(self, name, method, endpoint, data=None, headers=None):
        """Test a single endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{BASE_URL}{endpoint}"
                default_headers = {"Content-Type": "application/json"}
                if headers:
                    default_headers.update(headers)
                
                async with session.request(
                    method, 
                    url, 
                    json=data,
                    headers=default_headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    status = response.status
                    text = await response.text()
                    
                    if status in [200, 201]:
                        self.passed += 1
                        print(f"[PASS] {name}: {status}")
                        return True
                    else:
                        self.failed += 1
                        print(f"[FAIL] {name}: {status} - {text[:100]}")
                        return False
                        
        except Exception as e:
            self.failed += 1
            print(f"[ERROR] {name}: {str(e)}")
            return False
    
    async def run_tests(self):
        """Run all integration tests"""
        print("\n" + "="*60)
        print("UI-API INTEGRATION TEST")
        print("="*60)
        
        # 1. Test webhook endpoint (fixed)
        await self.test_endpoint(
            "Webhook Entry",
            "POST",
            "/webhook/entry",
            {
                "secret": WEBHOOK_SECRET,
                "signal": "S1",
                "strike": 25000,
                "option_type": "PE",
                "lots": 10,
                "timestamp": datetime.now().isoformat(),
                "test_mode": True
            }
        )
        
        # 2. Test settings endpoints
        await self.test_endpoint(
            "Get Settings",
            "GET",
            "/settings"
        )
        
        await self.test_endpoint(
            "Update Settings",
            "POST",
            "/settings",
            {
                "key": "test_setting",
                "value": "test_value",
                "category": "general"
            }
        )
        
        # 3. Test positions endpoints
        await self.test_endpoint(
            "Get Positions",
            "GET",
            "/positions"
        )
        
        await self.test_endpoint(
            "Square Off All",
            "POST",
            "/positions/square-off-all"
        )
        
        # 4. Test kill switch endpoints
        await self.test_endpoint(
            "Kill Switch Status",
            "GET",
            "/kill-switch/status"
        )
        
        await self.test_endpoint(
            "Kill Switch Trigger",
            "POST",
            "/kill-switch/trigger",
            {
                "reason": "Test trigger",
                "source": "test"
            }
        )
        
        await self.test_endpoint(
            "Kill Switch Reset",
            "POST",
            "/kill-switch/reset"
        )
        
        # 5. Test auto trade toggle
        await self.test_endpoint(
            "Auto Trade Status",
            "GET",
            "/auto-trade/status"
        )
        
        await self.test_endpoint(
            "Auto Trade Toggle",
            "POST",
            "/auto-trade/toggle",
            {"enabled": False}
        )
        
        # 6. Test broker status
        await self.test_endpoint(
            "Breeze Status",
            "GET",
            "/breeze/status"
        )
        
        await self.test_endpoint(
            "Kite Status",
            "GET",
            "/kite/status"
        )
        
        # 7. Test NIFTY data
        await self.test_endpoint(
            "NIFTY Spot",
            "GET",
            "/nifty/spot"
        )
        
        # 8. Test expiry configuration
        await self.test_endpoint(
            "Get Expiry Config",
            "GET",
            "/expiry/config"
        )
        
        await self.test_endpoint(
            "Update Expiry Config",
            "POST",
            "/expiry/config",
            {
                "Monday": "current",
                "Tuesday": "current",
                "Wednesday": "current",
                "Thursday": "current",
                "Friday": "current"
            }
        )
        
        # 9. Test risk management
        await self.test_endpoint(
            "Risk Limits",
            "GET",
            "/risk/limits"
        )
        
        await self.test_endpoint(
            "Update Risk Limits",
            "POST",
            "/risk/limits",
            {
                "max_loss_per_day": 50000,
                "max_positions": 5,
                "stop_loss_percent": 30
            }
        )
        
        # 10. Test trade configuration
        await self.test_endpoint(
            "Get Trade Config",
            "GET",
            "/config/trade"
        )
        
        await self.test_endpoint(
            "Save Trade Config",
            "POST",
            "/config/trade",
            {
                "default_lots": 10,
                "strike_offset": 200,
                "hedge_enabled": True
            }
        )
        
        # Print summary
        print("\n" + "="*60)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("="*60)
        
        if self.failed == 0:
            print("[SUCCESS] ALL UI-API CONNECTIONS WORKING!")
        else:
            print(f"[WARNING] {self.failed} ENDPOINTS NEED ATTENTION")
        
        return self.failed == 0

async def main():
    tester = UIAPIIntegrationTest()
    success = await tester.run_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)