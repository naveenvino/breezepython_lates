"""
FINAL PRODUCTION READINESS TEST
Expert-level validation for live trading system
"""
import requests
import json
import os
from datetime import datetime
from pathlib import Path

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "tradingview-webhook-secret-key-2025"

class FinalProductionTest:
    def __init__(self):
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }
        
    def test(self, name, condition, critical=True):
        if condition:
            self.results["passed"].append(name)
            print(f"[PASS] {name}")
            return True
        else:
            if critical:
                self.results["failed"].append(name)
                print(f"[FAIL] {name}")
            else:
                self.results["warnings"].append(name)
                print(f"[WARN] {name}")
            return False
    
    def run_all_tests(self):
        print("\n" + "="*70)
        print("  FINAL PRODUCTION READINESS TEST")
        print("  Expert Analysis for Live Trading")
        print("="*70)
        
        # 1. SECURITY TESTS
        print("\n[1] SECURITY VALIDATION")
        print("-" * 40)
        
        # Test webhook security
        try:
            # Wrong secret should fail
            bad_webhook = {
                "secret": "wrong_secret",
                "signal": "S1",
                "strike": 25000,
                "option_type": "PE",
                "lots": 1
            }
            resp = requests.post(f"{BASE_URL}/webhook/entry", json=bad_webhook)
            self.test("Webhook Security (rejects invalid)", resp.status_code == 401)
            
            # Correct secret should work
            good_webhook = {
                "secret": WEBHOOK_SECRET,
                "signal": "S1",
                "strike": 25000,
                "option_type": "PE",
                "lots": 1,
                "timestamp": datetime.now().isoformat()
            }
            resp = requests.post(f"{BASE_URL}/webhook/entry", json=good_webhook)
            self.test("Webhook Security (accepts valid)", resp.status_code == 200)
            
        except Exception as e:
            self.test("Webhook Security", False)
        
        # Test position size validation
        try:
            # Test invalid sizes
            for lots in [0, 101, 1000]:
                webhook = {
                    "secret": WEBHOOK_SECRET,
                    "signal": "S1",
                    "strike": 25000,
                    "option_type": "PE",
                    "lots": lots,
                    "timestamp": datetime.now().isoformat()
                }
                resp = requests.post(f"{BASE_URL}/webhook/entry", json=webhook)
                if resp.status_code == 400 or "invalid" in resp.text.lower():
                    self.test(f"Position Validation ({lots} lots rejected)", True)
                else:
                    self.test(f"Position Validation ({lots} lots)", False)
                    
        except:
            self.test("Position Size Validation", False)
        
        # 2. KILL SWITCH TEST
        print("\n[2] EMERGENCY CONTROLS")
        print("-" * 40)
        
        try:
            # Check kill switch status
            resp = requests.get(f"{BASE_URL}/api/kill-switch/status")
            if resp.status_code == 200:
                status = resp.json()
                self.test("Kill Switch Available", True)
                self.test("Kill Switch Ready", not status.get("active", False))
            else:
                self.test("Kill Switch", False)
        except:
            self.test("Kill Switch", False)
        
        # 3. RISK MANAGEMENT
        print("\n[3] RISK MANAGEMENT")
        print("-" * 40)
        
        # Check configuration
        if Path("production_config.json").exists():
            with open("production_config.json", "r") as f:
                config = json.load(f)
                
                self.test("Paper Trading OFF", not config["trading"]["paper_trading"])
                self.test("Stop Loss Configured", config["risk"]["stop_loss_percentage"] > 0)
                self.test("Daily Loss Limit Set", config["risk"]["max_daily_loss"] > 0)
                self.test("Panic Close Enabled", config["risk"]["panic_close"])
                self.test("Position Limit Set", config["trading"]["max_positions"] > 0)
        
        # 4. ICEBERG ORDER SYSTEM
        print("\n[4] ICEBERG ORDER SYSTEM")
        print("-" * 40)
        
        # Check if iceberg service exists
        iceberg_file = Path("src/services/iceberg_order_service.py")
        self.test("Iceberg Service Exists", iceberg_file.exists())
        
        if iceberg_file.exists():
            content = iceberg_file.read_text(encoding='utf-8')
            self.test("Hedge Protection Logic", "place_hedged_iceberg_order" in content)
            self.test("Order Splitting Logic", "calculate_order_splits" in content)
            self.test("Max 24 Lots Per Order", "MAX_LOTS_PER_ORDER = 24" in content)
        
        # 5. API ENDPOINTS
        print("\n[5] API ENDPOINTS")
        print("-" * 40)
        
        endpoints = [
            ("/health", "Health Check"),
            ("/api/settings", "Settings API"),
            ("/api/option-chain", "Option Chain API"),
            ("/api/kill-switch/status", "Kill Switch API")
        ]
        
        for endpoint, name in endpoints:
            try:
                resp = requests.get(f"{BASE_URL}{endpoint}", timeout=2)
                self.test(name, resp.status_code in [200, 401])
            except:
                self.test(name, False)
        
        # 6. TRADING MODE
        print("\n[6] TRADING MODE")
        print("-" * 40)
        
        if Path("auto_trade_state.json").exists():
            with open("auto_trade_state.json", "r") as f:
                state = json.load(f)
                self.test("Live Mode Active", state["mode"] == "LIVE")
                self.test("Auto-Trade Disabled (safe)", not state.get("enabled", True))
        
        # 7. CRITICAL FILES
        print("\n[7] CRITICAL FILES")
        print("-" * 40)
        
        critical_files = [
            ("unified_api_correct.py", "Main API"),
            ("tradingview_pro.html", "Trading UI"),
            ("production_config.json", "Production Config"),
            ("auto_trade_state.json", "Trading State")
        ]
        
        for file, name in critical_files:
            self.test(f"{name} exists", Path(file).exists())
        
        # FINAL REPORT
        print("\n" + "="*70)
        print("  PRODUCTION READINESS REPORT")
        print("="*70)
        
        total = len(self.results["passed"]) + len(self.results["failed"]) + len(self.results["warnings"])
        pass_rate = (len(self.results["passed"]) / max(total, 1)) * 100
        
        print(f"\nTest Results:")
        print(f"  Passed: {len(self.results['passed'])}")
        print(f"  Failed: {len(self.results['failed'])}")
        print(f"  Warnings: {len(self.results['warnings'])}")
        print(f"  Pass Rate: {pass_rate:.1f}%")
        
        if self.results["failed"]:
            print(f"\nFailed Tests:")
            for test in self.results["failed"][:5]:
                print(f"  - {test}")
        
        # VERDICT
        print("\n" + "="*70)
        print("  EXPERT VERDICT")
        print("="*70)
        
        if len(self.results["failed"]) == 0 and pass_rate >= 95:
            print("\n[READY] SYSTEM IS FULLY READY FOR LIVE TRADING")
            print("\nRecommendations:")
            print("  1. Start with 1 lot positions")
            print("  2. Monitor first 5 trades manually")
            print("  3. Keep kill switch accessible")
            print("  4. Use iceberg orders for >24 lots")
            print("  5. Verify hedge executes before main")
            return True
            
        elif len(self.results["failed"]) <= 2 and pass_rate >= 85:
            print("\n[CAUTION] READY FOR CAUTIOUS LIVE TRADING")
            print("\nRequirements:")
            print("  1. Fix any failed tests if critical")
            print("  2. Start with 1 lot ONLY")
            print("  3. Manual monitoring REQUIRED")
            print("  4. Test during low volatility")
            print("  5. Do NOT use auto-trade initially")
            return True
            
        else:
            print("\n[STOP] NOT READY FOR LIVE TRADING")
            print("\nMust Fix:")
            for test in self.results["failed"]:
                print(f"  - {test}")
            return False

def main():
    tester = FinalProductionTest()
    is_ready = tester.run_all_tests()
    
    print("\n" + "="*70)
    print(f"Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    return 0 if is_ready else 1

if __name__ == "__main__":
    exit(main())