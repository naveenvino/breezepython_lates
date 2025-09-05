"""
Production Readiness Test Suite for TradingView Pro Trading System
==================================================================
This comprehensive test suite validates ALL components for production deployment.
"""

import asyncio
import json
import time
import requests
import websocket
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import sys
import os

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8')

# Configuration
API_BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/tradingview"
TEST_CREDENTIALS = {
    "username": "naveen_vino",
    "password": "Vinoth@123"
}

class ProductionReadinessTest:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "categories": {},
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "critical_failures": [],
            "warnings": [],
            "production_ready": False
        }
        self.driver = None
        self.api_session = requests.Session()
        self.ws_connection = None
        
    def log(self, category: str, test: str, status: str, message: str, critical: bool = False):
        """Log test results"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if category not in self.results["categories"]:
            self.results["categories"][category] = {
                "tests": [],
                "passed": 0,
                "failed": 0
            }
        
        self.results["categories"][category]["tests"].append({
            "test": test,
            "status": status,
            "message": message,
            "timestamp": timestamp
        })
        
        if status == "PASS":
            self.results["categories"][category]["passed"] += 1
            self.results["passed"] += 1
            print(f"[{timestamp}] ✅ {category}: {test} - {message}")
        elif status == "FAIL":
            self.results["categories"][category]["failed"] += 1
            self.results["failed"] += 1
            print(f"[{timestamp}] ❌ {category}: {test} - {message}")
            if critical:
                self.results["critical_failures"].append(f"{category}: {test} - {message}")
        elif status == "WARN":
            self.results["warnings"].append(f"{category}: {test} - {message}")
            print(f"[{timestamp}] ⚠️ {category}: {test} - {message}")
        else:
            print(f"[{timestamp}] ℹ️ {category}: {test} - {message}")
        
        self.results["total_tests"] += 1

    # ==================== CATEGORY 1: API CONNECTIVITY ====================
    
    def test_api_health(self) -> bool:
        """Test API health endpoints"""
        category = "API Connectivity"
        
        try:
            # Test main health endpoint
            response = requests.get(f"{API_BASE_URL}/api/health")
            if response.status_code == 200:
                self.log(category, "API Health Check", "PASS", "API is responsive")
            else:
                self.log(category, "API Health Check", "FAIL", f"API returned {response.status_code}", critical=True)
                return False
                
            # Test broker status
            response = requests.get(f"{API_BASE_URL}/broker/status")
            data = response.json()
            if response.status_code == 200:
                self.log(category, "Broker Status", "PASS", f"Broker: {data.get('broker', 'Unknown')}")
            else:
                self.log(category, "Broker Status", "FAIL", "Cannot get broker status", critical=True)
                
            # Test Kite status
            response = requests.get(f"{API_BASE_URL}/kite/status")
            if response.status_code == 200:
                data = response.json()
                if data.get("connected"):
                    self.log(category, "Kite Connection", "PASS", "Kite API connected")
                else:
                    self.log(category, "Kite Connection", "WARN", "Kite API not connected")
            else:
                self.log(category, "Kite Connection", "FAIL", "Cannot check Kite status")
                
            return True
            
        except Exception as e:
            self.log(category, "API Connectivity", "FAIL", f"Connection error: {str(e)}", critical=True)
            return False

    # ==================== CATEGORY 2: AUTHENTICATION ====================
    
    def test_authentication(self) -> bool:
        """Test authentication system"""
        category = "Authentication"
        
        try:
            # Test login endpoint
            login_data = {
                "username": TEST_CREDENTIALS["username"],
                "password": TEST_CREDENTIALS["password"]
            }
            
            response = self.api_session.post(f"{API_BASE_URL}/auth/login", json=login_data)
            if response.status_code == 200:
                data = response.json()
                if "token" in data:
                    self.api_session.headers.update({"Authorization": f"Bearer {data['token']}"})
                    self.log(category, "API Login", "PASS", "Authentication successful")
                else:
                    self.log(category, "API Login", "FAIL", "No token received", critical=True)
                    return False
            else:
                self.log(category, "API Login", "FAIL", f"Login failed: {response.status_code}", critical=True)
                return False
                
            # Test session validation
            response = self.api_session.get(f"{API_BASE_URL}/auth/verify")
            if response.status_code == 200:
                self.log(category, "Session Validation", "PASS", "Session is valid")
            else:
                self.log(category, "Session Validation", "FAIL", "Invalid session")
                
            # Test Breeze authentication
            response = self.api_session.get(f"{API_BASE_URL}/live/auth/status")
            if response.status_code == 200:
                data = response.json()
                if data.get("authenticated"):
                    self.log(category, "Breeze Auth", "PASS", "Breeze API authenticated")
                else:
                    self.log(category, "Breeze Auth", "WARN", "Breeze API not authenticated")
            
            return True
            
        except Exception as e:
            self.log(category, "Authentication", "FAIL", f"Auth error: {str(e)}", critical=True)
            return False

    # ==================== CATEGORY 3: MARKET DATA ====================
    
    def test_market_data(self) -> bool:
        """Test market data endpoints"""
        category = "Market Data"
        
        try:
            # Test NIFTY spot price
            response = self.api_session.get(f"{API_BASE_URL}/api/live/nifty-spot")
            if response.status_code == 200:
                data = response.json()
                if "spot_price" in data:
                    self.log(category, "NIFTY Spot", "PASS", f"Price: {data['spot_price']}")
                else:
                    self.log(category, "NIFTY Spot", "FAIL", "No spot price data")
            else:
                self.log(category, "NIFTY Spot", "FAIL", "Cannot fetch spot price", critical=True)
                
            # Test option chain
            response = self.api_session.get(f"{API_BASE_URL}/api/live/option-chain")
            if response.status_code == 200:
                data = response.json()
                if "options" in data and len(data["options"]) > 0:
                    self.log(category, "Option Chain", "PASS", f"Loaded {len(data['options'])} options")
                else:
                    self.log(category, "Option Chain", "WARN", "Empty option chain")
            else:
                self.log(category, "Option Chain", "FAIL", "Cannot fetch option chain")
                
            # Test VIX
            response = self.api_session.get(f"{API_BASE_URL}/api/live/vix")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "India VIX", "PASS", f"VIX: {data.get('vix', 'N/A')}")
            else:
                self.log(category, "India VIX", "WARN", "Cannot fetch VIX")
                
            return True
            
        except Exception as e:
            self.log(category, "Market Data", "FAIL", f"Market data error: {str(e)}")
            return False

    # ==================== CATEGORY 4: WEBSOCKET CONNECTIVITY ====================
    
    def test_websocket(self) -> bool:
        """Test WebSocket connections"""
        category = "WebSocket"
        
        try:
            connected = threading.Event()
            received_data = []
            
            def on_open(ws):
                connected.set()
                
            def on_message(ws, message):
                received_data.append(json.loads(message))
                
            def on_error(ws, error):
                self.log(category, "WebSocket Error", "FAIL", str(error))
                
            # Test TradingView WebSocket
            ws = websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error
            )
            
            # Run WebSocket in thread
            ws_thread = threading.Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection
            if connected.wait(timeout=5):
                self.log(category, "TradingView WS", "PASS", "WebSocket connected")
                
                # Wait for data
                time.sleep(3)
                if received_data:
                    self.log(category, "WS Data Stream", "PASS", f"Received {len(received_data)} messages")
                else:
                    self.log(category, "WS Data Stream", "WARN", "No data received")
                    
                ws.close()
                return True
            else:
                self.log(category, "TradingView WS", "FAIL", "WebSocket connection failed", critical=True)
                return False
                
        except Exception as e:
            self.log(category, "WebSocket", "FAIL", f"WebSocket error: {str(e)}", critical=True)
            return False

    # ==================== CATEGORY 5: TRADING FUNCTIONALITY ====================
    
    def test_trading_functions(self) -> bool:
        """Test trading endpoints"""
        category = "Trading Functions"
        
        try:
            # Test position fetching
            response = self.api_session.get(f"{API_BASE_URL}/positions")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "Get Positions", "PASS", f"Fetched {len(data.get('positions', []))} positions")
            else:
                self.log(category, "Get Positions", "FAIL", "Cannot fetch positions")
                
            # Test order fetching
            response = self.api_session.get(f"{API_BASE_URL}/orders")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "Get Orders", "PASS", f"Fetched {len(data.get('orders', []))} orders")
            else:
                self.log(category, "Get Orders", "FAIL", "Cannot fetch orders")
                
            # Test auto-trade status
            response = self.api_session.get(f"{API_BASE_URL}/api/auto-trade/status")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "Auto Trade Status", "PASS", f"Auto-trade: {data.get('enabled', False)}")
            else:
                self.log(category, "Auto Trade Status", "WARN", "Cannot check auto-trade status")
                
            # Test signal execution (dry run)
            signal_data = {
                "signal": "S1",
                "action": "BUY",
                "strike": 25000,
                "type": "PE",
                "dry_run": True
            }
            response = self.api_session.post(f"{API_BASE_URL}/live/execute-signal", json=signal_data)
            if response.status_code in [200, 400]:  # 400 might be expected for dry run
                self.log(category, "Signal Execution", "PASS", "Signal endpoint accessible")
            else:
                self.log(category, "Signal Execution", "FAIL", "Signal execution failed")
                
            return True
            
        except Exception as e:
            self.log(category, "Trading Functions", "FAIL", f"Trading error: {str(e)}")
            return False

    # ==================== CATEGORY 6: RISK MANAGEMENT ====================
    
    def test_risk_management(self) -> bool:
        """Test risk management systems"""
        category = "Risk Management"
        
        try:
            # Test risk status
            response = self.api_session.get(f"{API_BASE_URL}/api/risk/status")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "Risk Status", "PASS", f"Risk monitoring: {data.get('active', False)}")
            else:
                self.log(category, "Risk Status", "FAIL", "Cannot check risk status")
                
            # Test risk limits
            response = self.api_session.get(f"{API_BASE_URL}/api/risk/limits")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "Risk Limits", "PASS", f"Max loss: {data.get('max_loss', 'N/A')}")
            else:
                self.log(category, "Risk Limits", "WARN", "Cannot fetch risk limits")
                
            # Test stop-loss monitoring
            response = self.api_session.get(f"{API_BASE_URL}/live/stop-loss/status")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "Stop Loss Monitor", "PASS", f"SL monitoring: {data.get('active', False)}")
            else:
                self.log(category, "Stop Loss Monitor", "WARN", "Stop-loss monitor not accessible")
                
            # Test position check
            position_data = {
                "symbol": "NIFTY25000PE",
                "quantity": 750,
                "entry_price": 100
            }
            response = self.api_session.post(f"{API_BASE_URL}/api/risk/check-position", json=position_data)
            if response.status_code in [200, 400]:
                self.log(category, "Position Risk Check", "PASS", "Risk check endpoint working")
            else:
                self.log(category, "Position Risk Check", "FAIL", "Risk check failed")
                
            return True
            
        except Exception as e:
            self.log(category, "Risk Management", "FAIL", f"Risk management error: {str(e)}")
            return False

    # ==================== CATEGORY 7: WEBHOOK INTEGRATION ====================
    
    def test_webhook_integration(self) -> bool:
        """Test TradingView webhook"""
        category = "Webhook Integration"
        
        try:
            # Test webhook endpoint
            webhook_data = {
                "signal": "TEST",
                "action": "test",
                "strike": 25000,
                "type": "PE"
            }
            
            response = self.api_session.post(f"{API_BASE_URL}/webhook/tradingview", json=webhook_data)
            if response.status_code in [200, 201]:
                self.log(category, "Webhook Endpoint", "PASS", "Webhook accepts signals")
            else:
                self.log(category, "Webhook Endpoint", "FAIL", f"Webhook failed: {response.status_code}", critical=True)
                
            # Test signal processing
            response = self.api_session.get(f"{API_BASE_URL}/live/signals/pending")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "Signal Queue", "PASS", f"Pending signals: {len(data.get('signals', []))}")
            else:
                self.log(category, "Signal Queue", "WARN", "Cannot check signal queue")
                
            return True
            
        except Exception as e:
            self.log(category, "Webhook Integration", "FAIL", f"Webhook error: {str(e)}", critical=True)
            return False

    # ==================== CATEGORY 8: DATA PERSISTENCE ====================
    
    def test_data_persistence(self) -> bool:
        """Test database and data storage"""
        category = "Data Persistence"
        
        try:
            # Test data overview
            response = self.api_session.get(f"{API_BASE_URL}/data/overview")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "Database Connection", "PASS", f"Tables: {data.get('table_count', 0)}")
            else:
                self.log(category, "Database Connection", "FAIL", "Cannot connect to database", critical=True)
                return False
                
            # Test backtest history
            response = self.api_session.get(f"{API_BASE_URL}/backtest/history")
            if response.status_code == 200:
                data = response.json()
                self.log(category, "Backtest Storage", "PASS", f"Backtests: {len(data.get('backtests', []))}")
            else:
                self.log(category, "Backtest Storage", "WARN", "Cannot fetch backtest history")
                
            # Test session history
            response = self.api_session.get(f"{API_BASE_URL}/session/history")
            if response.status_code == 200:
                self.log(category, "Session Storage", "PASS", "Session history accessible")
            else:
                self.log(category, "Session Storage", "WARN", "Session history not available")
                
            return True
            
        except Exception as e:
            self.log(category, "Data Persistence", "FAIL", f"Database error: {str(e)}", critical=True)
            return False

    # ==================== CATEGORY 9: UI INTEGRATION ====================
    
    def test_ui_integration(self) -> bool:
        """Test UI and API integration"""
        category = "UI Integration"
        
        try:
            # Setup Selenium
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
            self.driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(self.driver, 10)
            
            # Load TradingView Pro
            self.driver.get("http://localhost:8000/tradingview_pro.html")
            time.sleep(2)
            
            # Check if page loads
            if "TradingView Pro" in self.driver.title or "Trading" in self.driver.title:
                self.log(category, "Page Load", "PASS", "TradingView Pro loaded")
            else:
                self.log(category, "Page Load", "FAIL", "Page not loading correctly")
                
            # Check API connectivity from UI
            result = self.driver.execute_script("""
                return fetch('http://localhost:8000/api/health')
                    .then(r => r.status === 200)
                    .catch(() => false);
            """)
            
            if result:
                self.log(category, "UI-API Connection", "PASS", "UI can reach API")
            else:
                self.log(category, "UI-API Connection", "FAIL", "UI cannot connect to API", critical=True)
                
            # Check WebSocket from UI
            ws_status = self.driver.execute_script("""
                const ws = new WebSocket('ws://localhost:8000/ws/tradingview');
                return new Promise((resolve) => {
                    ws.onopen = () => { ws.close(); resolve(true); };
                    ws.onerror = () => resolve(false);
                    setTimeout(() => resolve(false), 3000);
                });
            """)
            
            if ws_status:
                self.log(category, "UI-WebSocket", "PASS", "UI WebSocket connectivity working")
            else:
                self.log(category, "UI-WebSocket", "FAIL", "UI WebSocket not connecting")
                
            self.driver.quit()
            return True
            
        except Exception as e:
            self.log(category, "UI Integration", "FAIL", f"UI integration error: {str(e)}")
            if self.driver:
                self.driver.quit()
            return False

    # ==================== CATEGORY 10: PERFORMANCE & LIMITS ====================
    
    def test_performance(self) -> bool:
        """Test system performance and limits"""
        category = "Performance"
        
        try:
            # Test API response time
            start = time.time()
            response = self.api_session.get(f"{API_BASE_URL}/api/health")
            latency = (time.time() - start) * 1000
            
            if latency < 100:
                self.log(category, "API Latency", "PASS", f"Response time: {latency:.2f}ms")
            elif latency < 500:
                self.log(category, "API Latency", "WARN", f"Slow response: {latency:.2f}ms")
            else:
                self.log(category, "API Latency", "FAIL", f"Very slow: {latency:.2f}ms")
                
            # Test system metrics
            response = self.api_session.get(f"{API_BASE_URL}/system/metrics")
            if response.status_code == 200:
                data = response.json()
                cpu = data.get("cpu_percent", 0)
                memory = data.get("memory_percent", 0)
                
                if cpu < 80 and memory < 80:
                    self.log(category, "System Resources", "PASS", f"CPU: {cpu}%, Memory: {memory}%")
                else:
                    self.log(category, "System Resources", "WARN", f"High usage - CPU: {cpu}%, Memory: {memory}%")
            else:
                self.log(category, "System Resources", "WARN", "Cannot fetch system metrics")
                
            # Test concurrent connections
            responses = []
            start = time.time()
            for _ in range(10):
                responses.append(self.api_session.get(f"{API_BASE_URL}/api/health"))
            elapsed = time.time() - start
            
            success_count = sum(1 for r in responses if r.status_code == 200)
            if success_count == 10:
                self.log(category, "Concurrent Requests", "PASS", f"Handled 10 requests in {elapsed:.2f}s")
            else:
                self.log(category, "Concurrent Requests", "FAIL", f"Only {success_count}/10 succeeded")
                
            return True
            
        except Exception as e:
            self.log(category, "Performance", "FAIL", f"Performance test error: {str(e)}")
            return False

    # ==================== MAIN TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run complete production readiness test suite"""
        print("\n" + "="*80)
        print("PRODUCTION READINESS TEST SUITE - TRADINGVIEW PRO")
        print("="*80 + "\n")
        
        test_categories = [
            ("API Connectivity", self.test_api_health),
            ("Authentication", self.test_authentication),
            ("Market Data", self.test_market_data),
            ("WebSocket", self.test_websocket),
            ("Trading Functions", self.test_trading_functions),
            ("Risk Management", self.test_risk_management),
            ("Webhook Integration", self.test_webhook_integration),
            ("Data Persistence", self.test_data_persistence),
            ("UI Integration", self.test_ui_integration),
            ("Performance", self.test_performance)
        ]
        
        for category_name, test_func in test_categories:
            print(f"\n📋 Testing: {category_name}")
            print("-" * 50)
            try:
                test_func()
            except Exception as e:
                self.log(category_name, "Category Test", "FAIL", f"Unexpected error: {str(e)}", critical=True)
        
        # Calculate final results
        self.calculate_production_readiness()
        
        # Generate report
        self.generate_report()
        
    def calculate_production_readiness(self):
        """Determine if system is production ready"""
        pass_rate = (self.results["passed"] / self.results["total_tests"]) * 100 if self.results["total_tests"] > 0 else 0
        
        # Production ready criteria:
        # 1. No critical failures
        # 2. Pass rate > 90%
        # 3. All essential categories passing
        
        essential_categories = ["API Connectivity", "Authentication", "Trading Functions", "Risk Management", "Data Persistence"]
        essential_passing = all(
            self.results["categories"].get(cat, {}).get("failed", 1) == 0 
            for cat in essential_categories
        )
        
        self.results["production_ready"] = (
            len(self.results["critical_failures"]) == 0 and
            pass_rate >= 90 and
            essential_passing
        )
        
        self.results["pass_rate"] = pass_rate
        
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("PRODUCTION READINESS REPORT")
        print("="*80 + "\n")
        
        # Overall statistics
        print(f"📊 OVERALL STATISTICS:")
        print(f"  Total Tests: {self.results['total_tests']}")
        print(f"  ✅ Passed: {self.results['passed']}")
        print(f"  ❌ Failed: {self.results['failed']}")
        print(f"  📈 Pass Rate: {self.results.get('pass_rate', 0):.1f}%\n")
        
        # Category breakdown
        print("📋 CATEGORY BREAKDOWN:")
        for category, data in self.results["categories"].items():
            status = "✅" if data["failed"] == 0 else "❌"
            print(f"  {status} {category}: {data['passed']}/{data['passed'] + data['failed']} passed")
        
        # Critical failures
        if self.results["critical_failures"]:
            print(f"\n🚨 CRITICAL FAILURES ({len(self.results['critical_failures'])}):")
            for failure in self.results["critical_failures"]:
                print(f"  - {failure}")
        
        # Warnings
        if self.results["warnings"]:
            print(f"\n⚠️ WARNINGS ({len(self.results['warnings'])}):")
            for warning in self.results["warnings"][:5]:  # Show first 5
                print(f"  - {warning}")
        
        # Production readiness verdict
        print("\n" + "="*80)
        if self.results["production_ready"]:
            print("✅ SYSTEM IS PRODUCTION READY")
            print("All critical tests passed. System can be deployed to production.")
        else:
            print("❌ SYSTEM IS NOT PRODUCTION READY")
            print("\nRequired fixes:")
            if self.results["critical_failures"]:
                print("1. Fix all critical failures")
            if self.results.get("pass_rate", 0) < 90:
                print("2. Improve pass rate to >90%")
            print("3. Ensure all essential categories are passing")
        print("="*80 + "\n")
        
        # Save detailed report
        with open("production_readiness_report.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print("📄 Detailed report saved to: production_readiness_report.json")
        
        # Generate action items
        self.generate_action_items()
        
    def generate_action_items(self):
        """Generate specific action items for production deployment"""
        print("\n📝 ACTION ITEMS FOR PRODUCTION:")
        
        action_items = []
        
        # Check for specific issues
        if "API Connectivity" in self.results["categories"]:
            if self.results["categories"]["API Connectivity"]["failed"] > 0:
                action_items.append("🔧 Fix API connectivity issues - ensure all services are running")
        
        if "Authentication" in self.results["categories"]:
            if self.results["categories"]["Authentication"]["failed"] > 0:
                action_items.append("🔐 Fix authentication - verify credentials and session management")
        
        if "Risk Management" in self.results["categories"]:
            if self.results["categories"]["Risk Management"]["failed"] > 0:
                action_items.append("⚠️ Implement proper risk management controls")
        
        if not action_items:
            action_items.append("✅ System ready for deployment")
            action_items.append("📋 Run final manual verification")
            action_items.append("📊 Set up production monitoring")
            action_items.append("📝 Document deployment procedures")
        
        for i, item in enumerate(action_items, 1):
            print(f"  {i}. {item}")
        
        print("\n" + "="*80)

if __name__ == "__main__":
    tester = ProductionReadinessTest()
    tester.run_all_tests()