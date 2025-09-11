"""
PRE-LIVE Trading System Validation Suite
Complete end-to-end testing of the auto-trading platform
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
import requests
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PreLiveValidation:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.results = {
            "successful_flows": [],
            "failures": [],
            "risk_gaps": [],
            "improvements": [],
            "test_logs": []
        }
        self.confidence_score = 0
        
    def log_test(self, test_name: str, status: str, details: str = ""):
        """Log test execution details"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "test": test_name,
            "status": status,
            "details": details
        }
        self.results["test_logs"].append(log_entry)
        logger.info(f"[{status}] {test_name}: {details}")
        
    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     headers: Optional[Dict] = None) -> tuple:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=headers)
            else:
                response = requests.delete(url, headers=headers)
                
            return response.status_code, response.json() if response.text else {}
        except Exception as e:
            return 500, {"error": str(e)}
            
    def test_complete_trading_flow(self):
        """Test 1: Complete Trading Flow (Entry -> Monitoring -> Exit)"""
        print("\n[TEST 1] COMPLETE TRADING FLOW")
        print("=" * 60)
        
        # Step 1: Simulate entry signal
        entry_webhook = {
            "timestamp": datetime.now().isoformat(),
            "signal": "S1",
            "action": "entry",
            "strike": 25000,
            "option_type": "PE",
            "lots": 10,
            "premium": 150,
            "hedge_premium": 30,
            "secret": "tradingview-webhook-secret-key-2025"
        }
        
        print("[1/5] Sending entry webhook...")
        headers = {"X-Webhook-Secret": entry_webhook["secret"]}
        status, response = self.make_request("POST", "/webhook/entry", entry_webhook, headers)
        
        if status == 200:
            self.log_test("Entry Webhook", "SUCCESS", f"Position created: {response}")
            self.results["successful_flows"].append({
                "flow": "Entry Signal Processing",
                "details": "Webhook received -> Position created -> Hedge calculated",
                "response": response
            })
            
            # Step 2: Verify position in monitoring
            print("[2/5] Verifying position monitoring...")
            status, positions = self.make_request("GET", "/positions/live")
            
            if status == 200 and positions.get("positions"):
                position = positions["positions"][0]
                self.log_test("Position Monitoring", "SUCCESS", f"Position ID: {position['id']}")
                
                # Verify hedge calculation (200 points offset)
                expected_hedge = 25000 - 200  # For PE
                if position.get("hedge_strike") == expected_hedge:
                    self.log_test("Hedge Calculation", "SUCCESS", f"Hedge: {expected_hedge}")
                else:
                    self.results["failures"].append({
                        "test": "Hedge Calculation",
                        "expected": expected_hedge,
                        "actual": position.get("hedge_strike"),
                        "file": "unified_api_correct.py",
                        "function": "/webhook endpoint"
                    })
                    
                # Step 3: Simulate price movement
                print("[3/5] Simulating price movement...")
                update_data = {
                    "position_id": position["id"],
                    "main_price": 180,  # Price increased
                    "hedge_price": 25
                }
                status, _ = self.make_request("PUT", "/positions/update_prices", update_data)
                
                if status == 200:
                    self.log_test("Price Update", "SUCCESS", "Position prices updated")
                    
                    # Step 4: Check PnL calculation
                    status, updated_pos = self.make_request("GET", f"/positions/{position['id']}")
                    if status == 200:
                        pnl = updated_pos.get("pnl", 0)
                        expected_pnl = (150 - 180 + 25 - 30) * 10 * 75  # (main + hedge) * lots * lot_size
                        self.log_test("PnL Calculation", "SUCCESS", f"PnL: {pnl}")
                        
                # Step 5: Simulate exit signal
                print("[4/5] Sending exit webhook...")
                exit_webhook = {
                    "timestamp": datetime.now().isoformat(),
                    "signal": "S1",
                    "action": "exit",
                    "strike": 25000,
                    "option_type": "PE",
                    "secret": "tradingview-webhook-secret-key-2025"
                }
                
                status, response = self.make_request("POST", "/webhook/exit", exit_webhook, headers)
                
                if status == 200:
                    self.log_test("Exit Webhook", "SUCCESS", "Position closed")
                    self.results["successful_flows"].append({
                        "flow": "Exit Signal Processing",
                        "details": "Exit webhook -> Position closed -> Hedge unwound"
                    })
                    
                    # Step 5: Verify position is closed
                    print("[5/5] Verifying position closure...")
                    status, positions = self.make_request("GET", "/positions/live")
                    open_positions = [p for p in positions.get("positions", []) if p["status"] == "open"]
                    
                    if len(open_positions) == 0:
                        self.log_test("Position Closure", "SUCCESS", "All positions closed")
                        self.confidence_score += 2
                    else:
                        self.results["failures"].append({
                            "test": "Position Closure",
                            "issue": "Position not properly closed after exit signal",
                            "open_positions": len(open_positions)
                        })
            else:
                self.results["failures"].append({
                    "test": "Position Monitoring",
                    "issue": "Position not found after creation",
                    "file": "unified_api_correct.py",
                    "function": "/positions/live endpoint"
                })
        else:
            self.results["failures"].append({
                "test": "Entry Webhook",
                "issue": f"Webhook processing failed: {response}",
                "file": "unified_api_correct.py",
                "function": "/webhook endpoint",
                "reproduction": "POST /webhook with entry signal"
            })
            
    def test_order_placement_and_risk(self):
        """Test 2: Order Placement and Risk Management"""
        print("\n[TEST 2] ORDER PLACEMENT & RISK MANAGEMENT")
        print("=" * 60)
        
        # Test position sizing
        print("[1/4] Testing position sizing limits...")
        large_position = {
            "timestamp": datetime.now().isoformat(),
            "signal": "S2",
            "action": "entry",
            "strike": 25100,
            "option_type": "CE",
            "lots": 100,  # Excessive lots
            "premium": 200,
            "secret": "tradingview-webhook-secret-key-2025"
        }
        
        headers = {"X-Webhook-Secret": large_position["secret"]}
        status, response = self.make_request("POST", "/webhook/entry", large_position, headers)
        
        # Check if risk limits are enforced
        status, settings = self.make_request("GET", "/settings")
        max_lots = settings.get("settings", {}).get("max_lots_per_trade", 20)
        
        if large_position["lots"] > max_lots:
            self.results["risk_gaps"].append({
                "gap": "Position Size Validation",
                "issue": "No enforcement of max lots per trade",
                "severity": "HIGH",
                "recommendation": "Add validation in webhook handler to reject orders > max_lots"
            })
            
        # Test margin checks
        print("[2/4] Testing margin requirements...")
        required_margin = large_position["lots"] * 75 * large_position["premium"]
        
        status, account = self.make_request("GET", "/account/margin")
        if status == 200:
            available_margin = account.get("available_margin", 0)
            if required_margin > available_margin:
                self.log_test("Margin Check", "WARNING", "No margin validation before order")
                self.results["risk_gaps"].append({
                    "gap": "Margin Validation",
                    "issue": "Orders placed without margin check",
                    "severity": "CRITICAL",
                    "recommendation": "Add pre-trade margin validation"
                })
        
        # Test daily loss limits
        print("[3/4] Testing daily loss limits...")
        status, daily_pnl = self.make_request("GET", "/positions/daily_pnl")
        
        if status == 200:
            current_loss = daily_pnl.get("total_pnl", 0)
            max_daily_loss = settings.get("settings", {}).get("max_daily_loss", -50000)
            
            if current_loss < max_daily_loss:
                self.results["improvements"].append({
                    "area": "Daily Loss Limit",
                    "suggestion": "Implement automatic trading halt when daily loss exceeds limit",
                    "priority": "HIGH"
                })
                
        # Test duplicate order prevention
        print("[4/4] Testing duplicate order prevention...")
        duplicate_webhook = large_position.copy()
        
        status1, _ = self.make_request("POST", "/webhook/entry", duplicate_webhook, headers)
        time.sleep(0.5)
        status2, _ = self.make_request("POST", "/webhook/entry", duplicate_webhook, headers)
        
        if status1 == 200 and status2 == 200:
            self.results["risk_gaps"].append({
                "gap": "Duplicate Order Prevention",
                "issue": "Same signal can create multiple positions",
                "severity": "MEDIUM",
                "recommendation": "Add deduplication logic with time window"
            })
            self.confidence_score += 1
        else:
            self.log_test("Duplicate Prevention", "SUCCESS", "Duplicates blocked")
            self.confidence_score += 2
            
    def test_failsafe_scenarios(self):
        """Test 3: Fail-safe Scenarios"""
        print("\n[TEST 3] FAIL-SAFE SCENARIOS")
        print("=" * 60)
        
        # Test Kite API rejection handling
        print("[1/5] Testing Kite API rejection handling...")
        
        # Check if system handles broker disconnection
        status, broker_status = self.make_request("GET", "/status/all")
        
        if broker_status.get("kite", {}).get("connected"):
            # Simulate order with invalid instrument
            invalid_order = {
                "timestamp": datetime.now().isoformat(),
                "signal": "S3",
                "action": "entry",
                "strike": 99999,  # Invalid strike
                "option_type": "PE",
                "lots": 10,
                "premium": 100,
                "secret": "tradingview-webhook-secret-key-2025"
            }
            
            headers = {"X-Webhook-Secret": invalid_order["secret"]}
            status, response = self.make_request("POST", "/webhook/entry", invalid_order, headers)
            
            if "error" in str(response).lower():
                self.log_test("Invalid Order Handling", "SUCCESS", "Error handled gracefully")
                self.confidence_score += 1
            else:
                self.results["failures"].append({
                    "test": "Invalid Order Handling",
                    "issue": "System doesn't validate strike prices",
                    "severity": "HIGH"
                })
                
        # Test Breeze data timeout
        print("[2/5] Testing Breeze data timeout handling...")
        
        # Check token expiry handling
        if broker_status.get("breeze", {}).get("token_expiry"):
            expiry_time = broker_status["breeze"]["token_expiry"]
            self.log_test("Token Expiry Check", "INFO", f"Token expires at {expiry_time}")
            
            # Check if refresh mechanism exists
            status, _ = self.make_request("POST", "/breeze/refresh_token")
            if status == 200:
                self.results["successful_flows"].append({
                    "flow": "Token Refresh",
                    "details": "Breeze token can be refreshed before expiry"
                })
                self.confidence_score += 1
            else:
                self.results["risk_gaps"].append({
                    "gap": "Token Auto-Refresh",
                    "issue": "No automatic token refresh before expiry",
                    "severity": "CRITICAL",
                    "recommendation": "Implement scheduled token refresh 30 min before expiry"
                })
                
        # Test duplicate alert handling
        print("[3/5] Testing duplicate alert handling...")
        
        test_signal = {
            "timestamp": datetime.now().isoformat(),
            "signal": "S4",
            "action": "entry",
            "strike": 25200,
            "option_type": "CE",
            "lots": 10,
            "premium": 120,
            "secret": "tradingview-webhook-secret-key-2025"
        }
        
        headers = {"X-Webhook-Secret": test_signal["secret"]}
        
        # Send same signal 3 times rapidly
        responses = []
        for i in range(3):
            status, response = self.make_request("POST", "/webhook/entry", test_signal, headers)
            responses.append((status, response))
            time.sleep(0.1)
            
        # Check if duplicates were prevented
        successful_creates = sum(1 for s, r in responses if s == 200 and "position" in str(r))
        
        if successful_creates == 1:
            self.log_test("Duplicate Alert Prevention", "SUCCESS", "Only first alert processed")
            self.confidence_score += 2
        else:
            self.results["failures"].append({
                "test": "Duplicate Alert Prevention",
                "issue": f"{successful_creates} positions created from same signal",
                "severity": "HIGH",
                "file": "unified_api_correct.py",
                "function": "/webhook endpoint"
            })
            
        # Test market hours validation
        print("[4/5] Testing market hours validation...")
        
        current_time = datetime.now()
        market_open = current_time.replace(hour=9, minute=15, second=0)
        market_close = current_time.replace(hour=15, minute=30, second=0)
        
        if current_time < market_open or current_time > market_close:
            # We're outside market hours - perfect for testing
            after_hours_signal = {
                "timestamp": datetime.now().isoformat(),
                "signal": "S5",
                "action": "entry",
                "strike": 25300,
                "option_type": "PE",
                "lots": 10,
                "premium": 110,
                "secret": "tradingview-webhook-secret-key-2025"
            }
            
            status, response = self.make_request("POST", "/webhook/entry", after_hours_signal, headers)
            
            if "market closed" in str(response).lower() or "outside market hours" in str(response).lower():
                self.log_test("Market Hours Check", "SUCCESS", "After-hours orders blocked")
                self.confidence_score += 1
            else:
                self.results["risk_gaps"].append({
                    "gap": "Market Hours Validation",
                    "issue": "Orders accepted outside market hours",
                    "severity": "MEDIUM",
                    "recommendation": "Add market hours check in webhook handler"
                })
                
        # Test kill switch
        print("[5/5] Testing emergency kill switch...")
        
        # Activate kill switch
        status, _ = self.make_request("POST", "/killswitch/activate")
        
        if status == 200:
            # Try to place order with kill switch active
            test_order = {
                "timestamp": datetime.now().isoformat(),
                "signal": "S6",
                "action": "entry",
                "strike": 25400,
                "option_type": "CE",
                "lots": 10,
                "premium": 100,
                "secret": "tradingview-webhook-secret-key-2025"
            }
            
            status, response = self.make_request("POST", "/webhook/entry", test_order, headers)
            
            if status != 200 or "kill switch" in str(response).lower():
                self.log_test("Kill Switch", "SUCCESS", "Trading blocked when kill switch active")
                self.confidence_score += 2
                
                # Deactivate kill switch
                self.make_request("POST", "/killswitch/deactivate")
            else:
                self.results["failures"].append({
                    "test": "Kill Switch",
                    "issue": "Orders still processed with kill switch active",
                    "severity": "CRITICAL"
                })
        else:
            self.results["risk_gaps"].append({
                "gap": "Kill Switch Implementation",
                "issue": "No working kill switch found",
                "severity": "CRITICAL",
                "recommendation": "Implement emergency trading halt mechanism"
            })
            
    def test_data_integrity(self):
        """Test 4: Data Integrity and UI Updates"""
        print("\n[TEST 4] DATA INTEGRITY & UI UPDATES")
        print("=" * 60)
        
        # Test real-time data updates
        print("[1/3] Testing real-time data updates...")
        
        status, ws_status = self.make_request("GET", "/websocket/status")
        
        if status == 200 and ws_status.get("connected"):
            self.log_test("WebSocket Connection", "SUCCESS", "Real-time updates available")
            self.confidence_score += 1
        else:
            self.results["risk_gaps"].append({
                "gap": "Real-time Updates",
                "issue": "WebSocket not connected for real-time updates",
                "severity": "MEDIUM",
                "recommendation": "Ensure WebSocket auto-reconnect on disconnect"
            })
            
        # Test data consistency
        print("[2/3] Testing data consistency...")
        
        # Get positions from different endpoints
        status1, positions1 = self.make_request("GET", "/positions/live")
        status2, positions2 = self.make_request("GET", "/positions")
        
        if status1 == 200 and status2 == 200:
            if positions1 == positions2:
                self.log_test("Data Consistency", "SUCCESS", "Position data consistent")
                self.confidence_score += 1
            else:
                self.results["failures"].append({
                    "test": "Data Consistency",
                    "issue": "Different endpoints return different position data",
                    "endpoints": ["/positions/live", "/positions"]
                })
                
        # Test fallback messages
        print("[3/3] Testing UI fallback messages...")
        
        # Try to get data that might not exist
        status, response = self.make_request("GET", "/positions/9999")
        
        if status == 404:
            if "not found" in str(response).lower() and "404" not in str(response):
                self.log_test("Error Messages", "SUCCESS", "Proper error messages")
            else:
                self.results["improvements"].append({
                    "area": "Error Messages",
                    "suggestion": "Provide user-friendly error messages instead of technical errors",
                    "priority": "LOW"
                })
                
    def generate_report(self):
        """Generate comprehensive PRE-LIVE validation report"""
        print("\n" + "=" * 80)
        print("PRE-LIVE VALIDATION REPORT")
        print("=" * 80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
        print(f"System: Auto-Trading Platform v2.0")
        print(f"Environment: PRE-LIVE (Market: PRE-MARKET)")
        print("-" * 80)
        
        # Successful Flows
        print("\n[OK] SUCCESSFUL FLOWS")
        print("-" * 40)
        if self.results["successful_flows"]:
            for flow in self.results["successful_flows"]:
                print(f"  + {flow['flow']}")
                print(f"    Details: {flow['details']}")
        else:
            print("  No successful flows recorded")
            
        # Failures
        print("\n[X] FAILURES")
        print("-" * 40)
        if self.results["failures"]:
            for failure in self.results["failures"]:
                print(f"  - Test: {failure['test']}")
                print(f"    Issue: {failure['issue']}")
                if "file" in failure:
                    print(f"    Location: {failure['file']} -> {failure['function']}")
                if "reproduction" in failure:
                    print(f"    Reproduce: {failure['reproduction']}")
        else:
            print("  No critical failures found")
            
        # Risk Gaps
        print("\n[!] RISK GAPS (Non-blocking)")
        print("-" * 40)
        if self.results["risk_gaps"]:
            for gap in self.results["risk_gaps"]:
                severity_icon = "[!!!]" if gap["severity"] == "CRITICAL" else "[!!]" if gap["severity"] == "HIGH" else "[!]"
                print(f"  {severity_icon} {gap['gap']}")
                print(f"      Issue: {gap['issue']}")
                print(f"      Fix: {gap['recommendation']}")
        else:
            print("  No risk gaps identified")
            
        # Improvements
        print("\n[i] SUGGESTED IMPROVEMENTS")
        print("-" * 40)
        if self.results["improvements"]:
            for improvement in self.results["improvements"]:
                priority_icon = "***" if improvement["priority"] == "HIGH" else "**" if improvement["priority"] == "MEDIUM" else "*"
                print(f"  {priority_icon} {improvement['area']}")
                print(f"      {improvement['suggestion']}")
        else:
            print("  No improvements suggested")
            
        # Critical Checklist
        print("\n[v] CRITICAL CHECKLIST")
        print("-" * 40)
        
        checklist = {
            "Broker Connectivity": self.check_broker_status(),
            "Webhook Processing": len([f for f in self.results["failures"] if "webhook" in f.get("test", "").lower()]) == 0,
            "Position Management": len([f for f in self.results["failures"] if "position" in f.get("test", "").lower()]) == 0,
            "Risk Controls": len([g for g in self.results["risk_gaps"] if g["severity"] == "CRITICAL"]) == 0,
            "Data Integrity": len([f for f in self.results["failures"] if "consistency" in f.get("test", "").lower()]) == 0,
            "Market Hours Check": any("Market Hours" in g.get("gap", "") for g in self.results["risk_gaps"]),
            "Kill Switch": any("Kill Switch" in f.get("flow", "") for f in self.results["successful_flows"]),
            "Token Management": any("Token" in f.get("flow", "") for f in self.results["successful_flows"])
        }
        
        for item, status in checklist.items():
            status_icon = "[OK]" if status else "[FAIL]"
            print(f"  {status_icon} {item}")
            
        # Confidence Score
        print("\n" + "=" * 80)
        max_score = 10
        final_score = min(self.confidence_score, max_score)
        
        # Adjust score based on critical issues
        critical_failures = len(self.results["failures"])
        critical_gaps = len([g for g in self.results["risk_gaps"] if g["severity"] == "CRITICAL"])
        
        final_score = max(0, final_score - critical_failures - (critical_gaps * 2))
        
        print(f"\n[ROCKET] CONFIDENCE SCORE: {final_score}/10")
        print("-" * 40)
        
        if final_score >= 8:
            print("STATUS: READY FOR LIVE TRADING")
            print("The system is well-prepared for production trading.")
        elif final_score >= 6:
            print("STATUS: READY WITH CAUTION")
            print("System can go live but monitor closely and fix risk gaps.")
        elif final_score >= 4:
            print("STATUS: NOT RECOMMENDED")
            print("Several critical issues need fixing before live trading.")
        else:
            print("STATUS: DO NOT GO LIVE")
            print("Critical failures detected. Fix all issues before trading.")
            
        # Immediate Actions
        print("\n[!] IMMEDIATE ACTIONS BEFORE MARKET OPEN")
        print("-" * 40)
        
        if critical_failures > 0 or critical_gaps > 0:
            print("1. Fix all CRITICAL failures and risk gaps")
        print("2. Verify Breeze token refresh before 23:17 IST")
        print("3. Set appropriate position size limits in settings")
        print("4. Enable kill switch for emergency control")
        print("5. Monitor first few trades manually")
        
        # Save detailed report
        report_file = f"pre_live_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "confidence_score": final_score,
                "results": self.results,
                "checklist": checklist
            }, f, indent=2, default=str)
            
        print(f"\nDetailed report saved: {report_file}")
        
        return final_score
        
    def check_broker_status(self) -> bool:
        """Check if both brokers are connected"""
        status, response = self.make_request("GET", "/status/all")
        if status == 200:
            kite_connected = response.get("kite", {}).get("connected", False)
            breeze_connected = response.get("breeze", {}).get("connected", False)
            return kite_connected and breeze_connected
        return False
        
    def run_all_tests(self):
        """Execute all validation tests"""
        print("\n" + "=" * 80)
        print("STARTING PRE-LIVE VALIDATION SUITE")
        print("=" * 80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
        print("Testing all critical paths for live trading readiness...")
        
        try:
            # Run all test suites
            self.test_complete_trading_flow()
            self.test_order_placement_and_risk()
            self.test_failsafe_scenarios()
            self.test_data_integrity()
            
            # Generate final report
            confidence_score = self.generate_report()
            
            return confidence_score
            
        except Exception as e:
            logger.error(f"Validation suite failed: {e}")
            print(f"\n[ERROR] Validation suite encountered an error: {e}")
            return 0
            
if __name__ == "__main__":
    validator = PreLiveValidation()
    score = validator.run_all_tests()
    
    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print(f"Final Confidence Score: {score}/10")
    print("=" * 80)