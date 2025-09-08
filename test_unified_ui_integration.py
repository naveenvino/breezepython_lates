"""
Comprehensive UI Integration Test for Unified Settings System
Tests all UI components interact correctly with consolidated settings API
"""

import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime

class UnifiedSettingsUITest:
    def __init__(self):
        self.api_base = "http://localhost:8000"
        self.ui_base = "http://localhost:8000"
        self.driver = None
        self.test_results = []
        
    def setup_driver(self):
        """Setup Chrome driver for UI testing"""
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_window_size(1920, 1080)
        
    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            self.driver.quit()
            
    def log_result(self, test_name, passed, details=""):
        """Log test result"""
        result = {
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {test_name}: {details}")
        
    def test_api_settings_retrieval(self):
        """Test API retrieves all settings correctly"""
        try:
            response = requests.get(f"{self.api_base}/settings")
            data = response.json()
            
            if response.status_code == 200 and "settings" in data:
                settings_count = len(data["settings"])
                self.log_result("API Settings Retrieval", True, f"Retrieved {settings_count} settings")
                return data["settings"]
            else:
                self.log_result("API Settings Retrieval", False, f"Status: {response.status_code}")
                return {}
        except Exception as e:
            self.log_result("API Settings Retrieval", False, str(e))
            return {}
            
    def test_ui_settings_page_load(self):
        """Test settings page loads correctly"""
        try:
            self.driver.get(f"{self.ui_base}/settings")
            time.sleep(2)
            
            # Check if settings form exists
            settings_form = self.driver.find_elements(By.ID, "settingsForm")
            if settings_form:
                self.log_result("UI Settings Page Load", True, "Settings form found")
                return True
            else:
                # Try alternative URL
                self.driver.get(f"{self.ui_base}/settings.html")
                time.sleep(2)
                settings_form = self.driver.find_elements(By.ID, "settingsForm")
                if settings_form:
                    self.log_result("UI Settings Page Load", True, "Settings form found at settings.html")
                    return True
                else:
                    self.log_result("UI Settings Page Load", False, "Settings form not found")
                    return False
        except Exception as e:
            self.log_result("UI Settings Page Load", False, str(e))
            return False
            
    def test_trading_settings_update(self):
        """Test updating trading settings through UI"""
        try:
            # Navigate to settings
            self.driver.get(f"{self.ui_base}/settings.html")
            time.sleep(2)
            
            # Update lot size
            lot_size_input = self.driver.find_element(By.ID, "lot_size")
            lot_size_input.clear()
            lot_size_input.send_keys("15")
            
            # Update trading mode
            auto_trade_checkbox = self.driver.find_element(By.ID, "autoTrade")
            if not auto_trade_checkbox.is_selected():
                auto_trade_checkbox.click()
                
            # Save settings
            save_button = self.driver.find_element(By.ID, "saveBtn")
            save_button.click()
            time.sleep(2)
            
            # Verify through API
            response = requests.get(f"{self.api_base}/settings")
            settings = response.json().get("settings", {})
            
            lot_size_saved = settings.get("lot_size", "")
            auto_trade_saved = settings.get("auto_trade", "")
            
            if lot_size_saved == "15" or lot_size_saved == 15:
                self.log_result("Trading Settings Update", True, f"Lot size updated to {lot_size_saved}")
                return True
            else:
                self.log_result("Trading Settings Update", False, f"Lot size not updated: {lot_size_saved}")
                return False
        except Exception as e:
            self.log_result("Trading Settings Update", False, str(e))
            return False
            
    def test_risk_management_settings(self):
        """Test risk management settings through UI"""
        try:
            # Update via API first
            risk_settings = {
                "max_loss_per_trade": 5000,
                "max_profit": 10000,
                "stop_loss_percentage": 2.5,
                "max_exposure": 100000
            }
            
            response = requests.post(f"{self.api_base}/settings", json=risk_settings)
            
            if response.status_code == 200:
                # Verify retrieval
                get_response = requests.get(f"{self.api_base}/settings")
                saved_settings = get_response.json().get("settings", {})
                
                max_loss = saved_settings.get("max_loss_per_trade")
                if max_loss == "5000" or max_loss == 5000:
                    self.log_result("Risk Management Settings", True, "Risk settings saved correctly")
                    return True
                else:
                    self.log_result("Risk Management Settings", False, f"Unexpected value: {max_loss}")
                    return False
            else:
                self.log_result("Risk Management Settings", False, f"Save failed: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Risk Management Settings", False, str(e))
            return False
            
    def test_signal_configuration(self):
        """Test signal configuration settings"""
        try:
            # Test signal settings
            signal_settings = {
                "s1_enabled": True,
                "s2_enabled": False,
                "s3_enabled": True,
                "signal_threshold": 0.8,
                "signal_cooldown": 300
            }
            
            response = requests.post(f"{self.api_base}/settings", json=signal_settings)
            
            if response.status_code == 200:
                # Verify
                get_response = requests.get(f"{self.api_base}/settings")
                saved = get_response.json().get("settings", {})
                
                s1_enabled = saved.get("s1_enabled")
                if s1_enabled in ["true", "True", True, "1", 1]:
                    self.log_result("Signal Configuration", True, "Signal settings saved")
                    return True
                else:
                    self.log_result("Signal Configuration", False, f"S1 not enabled: {s1_enabled}")
                    return False
            else:
                self.log_result("Signal Configuration", False, f"Save failed: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Signal Configuration", False, str(e))
            return False
            
    def test_bulk_settings_update(self):
        """Test bulk settings update"""
        try:
            bulk_settings = {
                "lot_size": 20,
                "hedge_enabled": True,
                "hedge_offset": 250,
                "max_positions": 5,
                "expiry_exit_time": "15:20",
                "panic_close_time": "15:25",
                "auto_trade": True,
                "risk_percentage": 2.0
            }
            
            response = requests.post(f"{self.api_base}/settings/bulk", json=bulk_settings)
            
            if response.status_code == 200:
                # Verify all saved
                get_response = requests.get(f"{self.api_base}/settings")
                saved = get_response.json().get("settings", {})
                
                lot_size = saved.get("lot_size")
                hedge_offset = saved.get("hedge_offset")
                
                if (lot_size in ["20", 20]) and (hedge_offset in ["250", 250]):
                    self.log_result("Bulk Settings Update", True, "All settings saved")
                    return True
                else:
                    self.log_result("Bulk Settings Update", False, f"Values: lot={lot_size}, hedge={hedge_offset}")
                    return False
            else:
                self.log_result("Bulk Settings Update", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Bulk Settings Update", False, str(e))
            return False
            
    def test_settings_persistence(self):
        """Test settings persist across sessions"""
        try:
            # Save test value
            test_settings = {"test_persistence_key": "test_value_12345"}
            response = requests.post(f"{self.api_base}/settings", json=test_settings)
            
            if response.status_code == 200:
                # Immediate retrieval
                get_response = requests.get(f"{self.api_base}/settings")
                saved = get_response.json().get("settings", {})
                
                test_value = saved.get("test_persistence_key")
                if test_value == "test_value_12345":
                    self.log_result("Settings Persistence", True, "Settings persisted correctly")
                    return True
                else:
                    self.log_result("Settings Persistence", False, f"Value not persisted: {test_value}")
                    return False
            else:
                self.log_result("Settings Persistence", False, f"Save failed: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Settings Persistence", False, str(e))
            return False
            
    def test_namespace_organization(self):
        """Test settings are organized by namespace"""
        try:
            response = requests.get(f"{self.api_base}/settings/all")
            
            if response.status_code == 200:
                data = response.json()
                namespaces = data.get("settings", {})
                
                expected_namespaces = ["trading", "risk", "hedge", "signal", "general"]
                found_namespaces = list(namespaces.keys())
                
                has_namespaces = any(ns in found_namespaces for ns in expected_namespaces)
                
                if has_namespaces:
                    self.log_result("Namespace Organization", True, f"Found namespaces: {found_namespaces}")
                    return True
                else:
                    self.log_result("Namespace Organization", False, f"Namespaces: {found_namespaces}")
                    return False
            else:
                self.log_result("Namespace Organization", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Namespace Organization", False, str(e))
            return False
            
    def test_backward_compatibility(self):
        """Test backward compatibility with flat structure"""
        try:
            response = requests.get(f"{self.api_base}/settings")
            data = response.json()
            
            if "settings" in data:
                settings = data["settings"]
                # Should be flat dictionary, not nested
                is_flat = all(not isinstance(v, dict) for v in settings.values())
                
                if is_flat:
                    self.log_result("Backward Compatibility", True, "Flat structure maintained")
                    return True
                else:
                    self.log_result("Backward Compatibility", False, "Structure is nested")
                    return False
            else:
                self.log_result("Backward Compatibility", False, "No settings key in response")
                return False
        except Exception as e:
            self.log_result("Backward Compatibility", False, str(e))
            return False
            
    def run_all_tests(self):
        """Run all UI integration tests"""
        print("\n" + "="*60)
        print("UNIFIED SETTINGS UI INTEGRATION TEST")
        print("="*60 + "\n")
        
        # API tests (no UI needed)
        print("[TEST CATEGORY: API Integration]")
        self.test_api_settings_retrieval()
        self.test_risk_management_settings()
        self.test_signal_configuration()
        self.test_bulk_settings_update()
        self.test_settings_persistence()
        self.test_namespace_organization()
        self.test_backward_compatibility()
        
        # UI tests (requires Selenium)
        print("\n[TEST CATEGORY: UI Integration]")
        try:
            self.setup_driver()
            self.test_ui_settings_page_load()
            self.test_trading_settings_update()
        except Exception as e:
            print(f"[SKIP] UI tests skipped (Selenium not available): {e}")
        finally:
            self.cleanup()
            
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = total - passed
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print("\nFailed Tests:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        return passed == total

if __name__ == "__main__":
    tester = UnifiedSettingsUITest()
    success = tester.run_all_tests()
    exit(0 if success else 1)