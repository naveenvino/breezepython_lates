"""
Test Security Fixes - Verifies all critical security improvements
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

def test_no_sensitive_data_in_logs() -> Tuple[bool, List[str]]:
    """Check that no sensitive data appears in log messages"""
    issues = []
    sensitive_patterns = [
        r'logger\.\w+\([^)]*access_token[^)]*\)',  # Direct token logging
        r'logger\.\w+\([^)]*api_key[^)]*\)',       # API key logging
        r'logger\.\w+\([^)]*api_secret[^)]*\)',    # API secret logging
        r'logger\.\w+\([^)]*password[^)]*\)',      # Password logging
        r'logger\.\w+\(f["\'][^"\']*\{[^}]*token[^}]*\}',  # f-string with token
        r'logger\.\w+\(f["\'][^"\']*\{[^}]*key[^}]*\}',    # f-string with key
    ]
    
    files_to_check = [
        'src/services/kite_order_manager.py',
        'src/services/zerodha_order_executor.py',
        'src/infrastructure/brokers/kite/kite_auth_service.py',
        'src/infrastructure/services/session_validator.py',
        'src/services/auto_trade_executor.py'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
                for pattern in sensitive_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Check if it's properly redacted
                        if '[REDACTED]' not in match and 'credentials' not in match.lower():
                            issues.append(f"{file_path}: Found sensitive data in logging: {match[:100]}")
    
    return len(issues) == 0, issues

def test_no_fake_data_returns() -> Tuple[bool, List[str]]:
    """Check that no functions return fake/dummy data"""
    issues = []
    fake_patterns = [
        r'return\s+\[\s*\]',  # Empty list returns
        r'return\s+\{\s*\}',  # Empty dict returns  
        r'return\s+0',        # Zero returns (could be legitimate)
        r'return\s+None',     # None returns (could be legitimate)
    ]
    
    files_to_check = [
        'src/brokers/breeze_broker.py',
        'src/live_feed/data_feed.py',
        'src/services/breeze_option_service.py',
        'src/services/live_market_service.py'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    # Check for error handling
                    if 'return' in line and 'except' in ''.join(lines[max(0, i-5):i]):
                        # This is in exception handling - check if it raises
                        if not any(kw in ''.join(lines[i-5:i+2]) for kw in ['raise', 'RuntimeError', 'ValueError', 'Exception']):
                            if 'return []' in line or 'return {}' in line:
                                issues.append(f"{file_path}:{i} Returns empty value in exception handler without raising")
    
    return len(issues) == 0, issues

def test_structured_logging() -> Tuple[bool, List[str]]:
    """Check that trade execution uses structured logging"""
    issues = []
    
    file_path = 'src/services/auto_trade_executor.py'
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            content = f.read()
            
            # Check for structured logging with extra parameter
            if 'logger.info("Paper trade executed", extra=' not in content:
                issues.append(f"{file_path}: Missing structured logging for paper trades")
            if 'logger.info("Live trade executed", extra=' not in content:
                issues.append(f"{file_path}: Missing structured logging for live trades")
            if 'logger.warning("STOP LOSS TRIGGERED", extra=' not in content:
                issues.append(f"{file_path}: Missing structured logging for stop loss triggers")
    
    return len(issues) == 0, issues

def test_error_handler_exists() -> Tuple[bool, List[str]]:
    """Check that universal error handler is properly implemented"""
    issues = []
    
    file_path = 'src/api/utils/error_handler.py'
    if not os.path.exists(file_path):
        issues.append(f"{file_path}: Universal error handler file not found")
    else:
        with open(file_path, 'r') as f:
            content = f.read()
            
            required_components = [
                'class ErrorCode(Enum)',
                'class TradingException(Exception)',
                'def create_error_response',
                'async def global_exception_handler',
                'BREEZE_SESSION_EXPIRED',
                'ORDER_PLACEMENT_FAILED',
                'KILL_SWITCH_TRIGGERED'
            ]
            
            for component in required_components:
                if component not in content:
                    issues.append(f"{file_path}: Missing required component: {component}")
    
    return len(issues) == 0, issues

def test_expiry_is_tuesday() -> Tuple[bool, List[str]]:
    """Check that all expiry calculations use Tuesday"""
    issues = []
    
    files_to_check = Path('.').rglob('*.py')
    thursday_patterns = [
        r'days_ahead = 3 - today\.weekday\(\)',  # Thursday calculation
        r'weekday\(\) == 3',                      # Thursday check
        r'Thursday',                              # Thursday text
    ]
    
    for file_path in files_to_check:
        if 'test' not in str(file_path) and '.venv' not in str(file_path):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    for pattern in thursday_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            # Check if it's been fixed to Tuesday
                            if 'Tuesday' not in content and 'weekday() == 1' not in content:
                                issues.append(f"{file_path}: Still references Thursday expiry")
            except:
                pass
    
    return len(issues) == 0, issues

def run_all_tests():
    """Run all security tests"""
    print("="*60)
    print("SECURITY FIXES VERIFICATION")
    print("="*60)
    print(f"Testing at: {datetime.now().isoformat()}\n")
    
    tests = [
        ("No Sensitive Data in Logs", test_no_sensitive_data_in_logs),
        ("No Fake Data Returns", test_no_fake_data_returns),
        ("Structured Logging", test_structured_logging),
        ("Universal Error Handler", test_error_handler_exists),
        ("Expiry is Tuesday", test_expiry_is_tuesday)
    ]
    
    all_passed = True
    total_issues = 0
    
    for test_name, test_func in tests:
        print(f"\nTesting: {test_name}")
        print("-" * 40)
        
        try:
            passed, issues = test_func()
            
            if passed:
                print(f"[PASS] PASSED")
            else:
                print(f"[FAIL] FAILED - {len(issues)} issues found:")
                for issue in issues[:5]:  # Show first 5 issues
                    print(f"  - {issue}")
                if len(issues) > 5:
                    print(f"  ... and {len(issues) - 5} more")
                all_passed = False
                total_issues += len(issues)
        except Exception as e:
            print(f"[ERROR] ERROR: {str(e)}")
            all_passed = False
            total_issues += 1
    
    print("\n" + "="*60)
    if all_passed:
        print("[SUCCESS] ALL SECURITY TESTS PASSED!")
    else:
        print(f"[FAILED] FAILED: {total_issues} total issues found")
        print("Please review and fix the remaining issues.")
    print("="*60)
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)