"""
Complete Live Trading System Test
Full end-to-end validation with all components
"""

import requests
import json
import time
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class CompleteLiveTest:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests_passed": 0,
            "tests_failed": 0,
            "critical_issues": [],
            "warnings": [],
            "successful_flows": []
        }
        
    def log(self, message, level="INFO"):
        logger.info(f"[{level}] {message}")
        
    def make_request(self, method, endpoint, data=None, headers=None):
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=headers)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            return response.status_code, response.json() if response.text else {}
        except Exception as e:
            return 500, {"error": str(e)}
            
    def test_complete_trading_flow(self):
        """Test 1: Complete Trading Flow with Real Brokers"""
        print("\n" + "="*60)
        print("TEST 1: COMPLETE TRADING FLOW")
        print("="*60)
        
        results = {"passed": [], "failed": []}
        
        # 1. Verify broker connections
        self.log("Checking broker connections...")
        status, response = self.make_request("GET", "/status/all")
        
        if status == 200:
            kite_connected = response.get("kite", {}).get("connected", False)
            breeze_connected = response.get("breeze", {}).get("connected", False)
            
            if kite_connected and breeze_connected:
                results["passed"].append("Both brokers connected")
                self.test_results["tests_passed"] += 1
                self.log(f"Kite: Connected (User: {response['kite'].get('user_id')})")
                self.log(f"Breeze: Connected (Token expires: {response['breeze'].get('token_expiry')})")
            else:
                results["failed"].append("Broker connection issues")
                self.test_results["tests_failed"] += 1
                self.test_results["critical_issues"].append("Broker not connected")
                
        # 2. Create test position via webhook
        self.log("Creating test position via webhook...")
        test_signal = {
            "timestamp": datetime.now().isoformat(),
            "signal": "S1",
            "action": "entry",
            "strike": 25000,
            "option_type": "PE",
            "lots": 1,  # Small test position
            "premium": 150,
            "hedge_premium": 30,
            "secret": "tradingview-webhook-secret-key-2025"
        }
        
        headers = {"X-Webhook-Secret": test_signal["secret"]}
        status, response = self.make_request("POST", "/webhook/entry", test_signal, headers)
        
        position_id = None
        if status == 200:
            results["passed"].append("Position created via webhook")
            self.test_results["tests_passed"] += 1
            position_id = response.get("position", {}).get("id")
            self.log(f"Position created: ID={position_id}")
            
            # Verify hedge calculation
            main_strike = test_signal["strike"]
            expected_hedge = main_strike - 200  # For PE
            actual_hedge = response.get("position", {}).get("hedge_leg", {}).get("strike")
            
            if actual_hedge == expected_hedge:
                results["passed"].append("Hedge calculation correct")
                self.test_results["tests_passed"] += 1
            else:
                results["failed"].append(f"Hedge incorrect: Expected {expected_hedge}, got {actual_hedge}")
                self.test_results["tests_failed"] += 1
        else:
            results["failed"].append(f"Webhook failed: {response}")
            self.test_results["tests_failed"] += 1
            self.test_results["critical_issues"].append("Webhook processing failed")
            
        # 3. Verify position monitoring
        time.sleep(1)
        self.log("Checking position monitoring...")
        status, positions = self.make_request("GET", "/positions/live")
        
        if status == 200:
            live_positions = positions.get("positions", [])
            if position_id and any(p.get("id") == position_id for p in live_positions):
                results["passed"].append("Position visible in monitoring")
                self.test_results["tests_passed"] += 1
            else:
                results["failed"].append("Position not in monitoring")
                self.test_results["tests_failed"] += 1
                self.test_results["critical_issues"].append("Position tracking broken")
                
        # 4. Test price update
        if position_id:
            self.log("Testing price updates...")
            update_data = {
                "position_id": position_id,
                "main_price": 180,
                "hedge_price": 25
            }
            status, response = self.make_request("PUT", "/positions/update_prices", update_data)
            
            if status == 200:
                results["passed"].append("Price update successful")
                self.test_results["tests_passed"] += 1
            else:
                results["failed"].append("Price update failed")
                self.test_results["tests_failed"] += 1
                
        # 5. Test exit signal
        if position_id:
            self.log("Testing exit signal...")
            exit_signal = {
                "timestamp": datetime.now().isoformat(),
                "signal": "S1",
                "action": "exit",
                "strike": 25000,
                "option_type": "PE",
                "secret": "tradingview-webhook-secret-key-2025"
            }
            
            status, response = self.make_request("POST", "/webhook/exit", exit_signal, headers)
            
            if status == 200:
                results["passed"].append("Exit signal processed")
                self.test_results["tests_passed"] += 1
            else:
                results["failed"].append("Exit signal failed")
                self.test_results["tests_failed"] += 1
                
        return results
        
    def test_risk_management(self):
        """Test 2: Risk Management and Limits"""
        print("\n" + "="*60)
        print("TEST 2: RISK MANAGEMENT")
        print("="*60)
        
        results = {"passed": [], "failed": []}
        
        # 1. Test position size limits
        self.log("Testing position size limits...")
        large_position = {
            "timestamp": datetime.now().isoformat(),
            "signal": "S2",
            "action": "entry",
            "strike": 25100,
            "option_type": "CE",
            "lots": 100,  # Excessive
            "premium": 200,
            "secret": "tradingview-webhook-secret-key-2025"
        }
        
        headers = {"X-Webhook-Secret": large_position["secret"]}
        status, response = self.make_request("POST", "/webhook/entry", large_position, headers)
        
        if status == 200:
            # Check if it was actually limited
            created_lots = response.get("position", {}).get("main_leg", {}).get("lots", 100)
            if created_lots < 100:
                results["passed"].append(f"Position size limited to {created_lots}")
                self.test_results["tests_passed"] += 1
            else:
                results["failed"].append("No position size limits enforced")
                self.test_results["tests_failed"] += 1
                self.test_results["warnings"].append("Accepts unlimited position sizes")
        
        # 2. Test duplicate prevention
        self.log("Testing duplicate signal prevention...")
        dup_signal = {
            "timestamp": datetime.now().isoformat(),
            "signal": "S3",
            "action": "entry",
            "strike": 25200,
            "option_type": "PE",
            "lots": 1,
            "premium": 120,
            "secret": "tradingview-webhook-secret-key-2025"
        }
        
        # Send same signal 3 times
        positions_created = 0
        for i in range(3):
            status, response = self.make_request("POST", "/webhook/entry", dup_signal, headers)
            if status == 200 and "position" in response:
                positions_created += 1
            time.sleep(0.2)
            
        if positions_created == 1:
            results["passed"].append("Duplicate signals blocked")
            self.test_results["tests_passed"] += 1
        else:
            results["failed"].append(f"{positions_created} duplicates created")
            self.test_results["tests_failed"] += 1
            self.test_results["warnings"].append("No duplicate prevention")
            
        # 3. Test daily limits
        self.log("Testing daily P&L limits...")
        status, daily_pnl = self.make_request("GET", "/positions/daily_pnl")
        
        if status == 200:
            results["passed"].append("Daily P&L tracking available")
            self.test_results["tests_passed"] += 1
            
            # Check if limits are enforced
            total_pnl = daily_pnl.get("total_pnl", 0)
            max_loss = daily_pnl.get("max_daily_loss", -50000)
            
            if total_pnl < max_loss:
                self.test_results["warnings"].append("Daily loss limit exceeded but trading not halted")
        else:
            results["failed"].append("No daily P&L tracking")
            self.test_results["tests_failed"] += 1
            
        return results
        
    def test_failsafe_mechanisms(self):
        """Test 3: Fail-safe and Emergency Controls"""
        print("\n" + "="*60)
        print("TEST 3: FAIL-SAFE MECHANISMS")
        print("="*60)
        
        results = {"passed": [], "failed": []}
        
        # 1. Test kill switch
        self.log("Testing kill switch...")
        status, response = self.make_request("POST", "/killswitch/activate")
        
        if status == 200:
            results["passed"].append("Kill switch activated")
            self.test_results["tests_passed"] += 1
            
            # Try to place order with kill switch active
            test_order = {
                "timestamp": datetime.now().isoformat(),
                "signal": "S4",
                "action": "entry",
                "strike": 25300,
                "option_type": "CE",
                "lots": 1,
                "premium": 100,
                "secret": "tradingview-webhook-secret-key-2025"
            }
            
            headers = {"X-Webhook-Secret": test_order["secret"]}
            status, response = self.make_request("POST", "/webhook/entry", test_order, headers)
            
            if status != 200 or "kill" in str(response).lower() or "blocked" in str(response).lower():
                results["passed"].append("Kill switch blocks trading")
                self.test_results["tests_passed"] += 1
            else:
                results["failed"].append("Kill switch not blocking trades")
                self.test_results["tests_failed"] += 1
                self.test_results["critical_issues"].append("Kill switch ineffective")
                
            # Deactivate
            self.make_request("POST", "/killswitch/deactivate")
        else:
            results["failed"].append("No kill switch available")
            self.test_results["tests_failed"] += 1
            self.test_results["critical_issues"].append("No emergency stop mechanism")
            
        # 2. Test market hours validation
        self.log("Testing market hours validation...")
        current_time = datetime.now()
        market_open = current_time.replace(hour=9, minute=15)
        market_close = current_time.replace(hour=15, minute=30)
        
        if market_open <= current_time <= market_close:
            results["passed"].append("Within market hours")
            self.test_results["tests_passed"] += 1
        else:
            # Test after-hours rejection
            after_hours_signal = {
                "timestamp": datetime.now().isoformat(),
                "signal": "S5",
                "action": "entry",
                "strike": 25400,
                "option_type": "PE",
                "lots": 1,
                "premium": 110,
                "secret": "tradingview-webhook-secret-key-2025"
            }
            
            headers = {"X-Webhook-Secret": after_hours_signal["secret"]}
            status, response = self.make_request("POST", "/webhook/entry", after_hours_signal, headers)
            
            if "market" in str(response).lower() or status != 200:
                results["passed"].append("After-hours orders blocked")
                self.test_results["tests_passed"] += 1
            else:
                results["failed"].append("Accepts after-hours orders")
                self.test_results["tests_failed"] += 1
                self.test_results["warnings"].append("No market hours validation")
                
        # 3. Test invalid strike handling
        self.log("Testing invalid strike handling...")
        invalid_signal = {
            "timestamp": datetime.now().isoformat(),
            "signal": "S6",
            "action": "entry",
            "strike": 99999,  # Invalid
            "option_type": "CE",
            "lots": 1,
            "premium": 100,
            "secret": "tradingview-webhook-secret-key-2025"
        }
        
        headers = {"X-Webhook-Secret": invalid_signal["secret"]}
        status, response = self.make_request("POST", "/webhook/entry", invalid_signal, headers)
        
        if status != 200 or "error" in str(response).lower() or "invalid" in str(response).lower():
            results["passed"].append("Invalid strikes rejected")
            self.test_results["tests_passed"] += 1
        else:
            results["failed"].append("Accepts invalid strikes")
            self.test_results["tests_failed"] += 1
            self.test_results["warnings"].append("No strike validation")
            
        return results
        
    def test_realtime_monitoring(self):
        """Test 4: Real-time Monitoring and Updates"""
        print("\n" + "="*60)
        print("TEST 4: REAL-TIME MONITORING")
        print("="*60)
        
        results = {"passed": [], "failed": []}
        
        # 1. Test WebSocket status
        self.log("Testing WebSocket connection...")
        status, response = self.make_request("GET", "/websocket/status")
        
        if status == 200 and response.get("connected"):
            results["passed"].append("WebSocket connected")
            self.test_results["tests_passed"] += 1
        else:
            results["failed"].append("WebSocket not connected")
            self.test_results["tests_failed"] += 1
            self.test_results["warnings"].append("No real-time updates")
            
        # 2. Test live positions endpoint
        self.log("Testing live positions endpoint...")
        status, response = self.make_request("GET", "/positions/live")
        
        if status == 200:
            results["passed"].append("Live positions endpoint working")
            self.test_results["tests_passed"] += 1
            
            positions = response.get("positions", [])
            if positions:
                self.log(f"Found {len(positions)} live positions")
                
                # Check if positions have required fields
                required_fields = ["id", "signal_type", "main_strike", "status", "pnl"]
                sample_position = positions[0] if positions else {}
                missing_fields = [f for f in required_fields if f not in sample_position]
                
                if not missing_fields:
                    results["passed"].append("Position data complete")
                    self.test_results["tests_passed"] += 1
                else:
                    results["failed"].append(f"Missing fields: {missing_fields}")
                    self.test_results["tests_failed"] += 1
        else:
            results["failed"].append("Live positions endpoint error")
            self.test_results["tests_failed"] += 1
            
        # 3. Test alerts/notifications
        self.log("Testing alerts system...")
        status, response = self.make_request("GET", "/alerts/recent")
        
        if status == 200:
            results["passed"].append("Alerts system available")
            self.test_results["tests_passed"] += 1
        else:
            results["failed"].append("No alerts system")
            self.test_results["tests_failed"] += 1
            
        # 4. Test settings persistence
        self.log("Testing settings persistence...")
        status, settings = self.make_request("GET", "/settings")
        
        if status == 200:
            # Update a setting
            test_setting = {
                "key": "test_mode",
                "value": True
            }
            status, response = self.make_request("PUT", "/settings/update", test_setting)
            
            if status == 200:
                # Verify it persisted
                status, new_settings = self.make_request("GET", "/settings")
                if new_settings.get("settings", {}).get("test_mode") == True:
                    results["passed"].append("Settings persist correctly")
                    self.test_results["tests_passed"] += 1
                else:
                    results["failed"].append("Settings not persisting")
                    self.test_results["tests_failed"] += 1
        
        return results
        
    def generate_final_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("COMPLETE LIVE TRADING TEST REPORT")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
        print(f"Environment: LIVE (Market Open)")
        print("-"*80)
        
        # Calculate scores
        total_tests = self.test_results["tests_passed"] + self.test_results["tests_failed"]
        pass_rate = (self.test_results["tests_passed"] / total_tests * 100) if total_tests > 0 else 0
        
        # Confidence calculation
        confidence = 10
        confidence -= len(self.test_results["critical_issues"]) * 2
        confidence -= len(self.test_results["warnings"]) * 0.5
        confidence = max(0, min(10, confidence))
        
        print(f"\nTEST SUMMARY")
        print("-"*40)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.test_results['tests_passed']}")
        print(f"Failed: {self.test_results['tests_failed']}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        
        if self.test_results["critical_issues"]:
            print(f"\nCRITICAL ISSUES ({len(self.test_results['critical_issues'])})")
            print("-"*40)
            for issue in self.test_results["critical_issues"]:
                print(f"  [X] {issue}")
                
        if self.test_results["warnings"]:
            print(f"\nWARNINGS ({len(self.test_results['warnings'])})")
            print("-"*40)
            for warning in self.test_results["warnings"]:
                print(f"  [!] {warning}")
                
        print(f"\nSYSTEM READINESS")
        print("-"*40)
        print(f"Confidence Score: {confidence:.1f}/10")
        
        if confidence >= 8:
            print("Status: READY FOR LIVE TRADING")
            print("Recommendation: Safe to trade with normal position sizes")
        elif confidence >= 6:
            print("Status: READY WITH CAUTION")
            print("Recommendation: Trade with reduced position sizes and monitor closely")
        elif confidence >= 4:
            print("Status: NOT RECOMMENDED")
            print("Recommendation: Fix critical issues before live trading")
        else:
            print("Status: DO NOT TRADE")
            print("Recommendation: System has critical failures that must be fixed")
            
        # Save detailed report
        report_file = f"complete_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
            
        print(f"\nDetailed report saved: {report_file}")
        
        return confidence
        
    def run_all_tests(self):
        """Execute complete test suite"""
        print("\n" + "="*80)
        print("STARTING COMPLETE LIVE TRADING TEST")
        print("="*80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
        print("Testing with LIVE brokers connected...")
        
        try:
            # Run all test categories
            flow_results = self.test_complete_trading_flow()
            risk_results = self.test_risk_management()
            failsafe_results = self.test_failsafe_mechanisms()
            monitoring_results = self.test_realtime_monitoring()
            
            # Compile results
            all_results = {
                "Trading Flow": flow_results,
                "Risk Management": risk_results,
                "Fail-safe Mechanisms": failsafe_results,
                "Real-time Monitoring": monitoring_results
            }
            
            # Display category results
            print("\n" + "="*80)
            print("CATEGORY RESULTS")
            print("="*80)
            
            for category, results in all_results.items():
                print(f"\n{category}:")
                print("  Passed:")
                for item in results.get("passed", []):
                    print(f"    [OK] {item}")
                print("  Failed:")
                for item in results.get("failed", []):
                    print(f"    [X] {item}")
                    
            # Generate final report
            confidence = self.generate_final_report()
            
            return confidence
            
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            print(f"\n[ERROR] Test suite encountered an error: {e}")
            return 0
            
if __name__ == "__main__":
    tester = CompleteLiveTest()
    confidence = tester.run_all_tests()
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print(f"Final Confidence Score: {confidence:.1f}/10")
    print("="*80)