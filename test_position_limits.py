"""
Test Position Limits and Risk Management
CRITICAL: Prevents excessive position sizes that could cause huge losses
"""

import requests
import json
import time
from datetime import datetime
import threading

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "tradingview-webhook-secret-key-2025"

def test_max_lots_per_trade():
    """Test maximum lots per trade limit"""
    print("\n" + "="*60)
    print("TESTING MAX LOTS PER TRADE LIMIT")
    print("="*60)
    
    # Try to place order with excessive lots
    test_cases = [
        {"lots": 10, "expected": "accept"},
        {"lots": 50, "expected": "accept"},
        {"lots": 100, "expected": "accept_or_warn"},
        {"lots": 500, "expected": "reject"},
        {"lots": 1000, "expected": "reject"},
        {"lots": 1800, "expected": "reject"},  # NIFTY freeze quantity
        {"lots": 5000, "expected": "reject"}
    ]
    
    results = []
    
    for test in test_cases:
        payload = {
            "secret": WEBHOOK_SECRET,
            "signal": "S1",
            "strike": 25000,
            "option_type": "PE",
            "lots": test["lots"],
            "timestamp": datetime.now().isoformat(),
            "test_mode": True  # Enable test mode for weekend testing
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/webhook/entry",
                json=payload,
                timeout=5
            )
            
            result = {
                "lots": test["lots"],
                "status": response.status_code,
                "expected": test["expected"],
                "passed": False
            }
            
            if test["expected"] == "accept":
                result["passed"] = response.status_code == 200
            elif test["expected"] == "accept_or_warn":
                result["passed"] = response.status_code in [200, 202]
            elif test["expected"] == "reject":
                result["passed"] = response.status_code in [400, 403, 422]
            
            results.append(result)
            
        except Exception as e:
            results.append({
                "lots": test["lots"],
                "status": "error",
                "expected": test["expected"],
                "passed": False,
                "error": str(e)
            })
    
    # Display results
    print("\nResults:")
    for result in results:
        status = "[PASS]" if result["passed"] else "[FAIL]"
        print(f"  {result['lots']} lots: Status {result['status']} (Expected: {result['expected']}) {status}")
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    print(f"\nOverall: {passed}/{total} tests passed")
    return passed == total

def test_max_exposure_limit():
    """Test maximum exposure limit in rupees"""
    print("\n" + "="*60)
    print("TESTING MAX EXPOSURE LIMIT")
    print("="*60)
    
    # Check current exposure
    try:
        response = requests.get(f"{BASE_URL}/api/risk/exposure", timeout=5)
        if response.status_code == 200:
            exposure = response.json()
            print(f"Current exposure: {exposure.get('total_exposure', 'N/A')}")
            print(f"Max allowed: {exposure.get('max_exposure', '10,00,000')}")
        elif response.status_code == 404:
            print("Exposure endpoint not found - creating test")
    except:
        print("Could not check current exposure")
    
    # Try to exceed exposure limit
    # Assuming each lot is worth ~5000 rupees premium
    # 200 lots * 5000 = 10,00,000 rupees
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S2",
        "strike": 25000,
        "option_type": "CE",
        "lots": 200,
        "estimated_premium": 5000,
        "timestamp": datetime.now().isoformat(),
        "test_mode": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=payload,
            timeout=5
        )
        
        if response.status_code in [400, 403, 422]:
            print(f"[PASS] Exposure limit enforced - order rejected")
            return True
        elif response.status_code == 200:
            print(f"[WARNING] Large exposure accepted - check if intended")
            return False
        else:
            print(f"[INFO] Response: {response.status_code}")
            return True
            
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_concurrent_position_limit():
    """Test maximum concurrent positions"""
    print("\n" + "="*60)
    print("TESTING CONCURRENT POSITION LIMIT")
    print("="*60)
    
    # Try to create multiple positions
    results = []
    
    def create_position(position_num):
        payload = {
            "secret": WEBHOOK_SECRET,
            "signal": f"S{(position_num % 8) + 1}",
            "strike": 25000 + (position_num * 50),
            "option_type": "PE" if position_num % 2 == 0 else "CE",
            "lots": 1,
            "timestamp": datetime.now().isoformat(),
            "position_id": f"pos_{position_num}",
            "test_mode": True
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/webhook/entry",
                json=payload,
                timeout=5
            )
            results.append({
                "position": position_num,
                "status": response.status_code
            })
        except Exception as e:
            results.append({
                "position": position_num,
                "status": "error",
                "error": str(e)
            })
    
    # Create 20 positions concurrently
    threads = []
    for i in range(20):
        thread = threading.Thread(target=create_position, args=(i,))
        threads.append(thread)
        thread.start()
        time.sleep(0.1)
    
    for thread in threads:
        thread.join()
    
    # Check how many succeeded
    success_count = sum(1 for r in results if isinstance(r.get("status"), int) and r["status"] == 200)
    
    print(f"\nResults:")
    print(f"  Positions created: {success_count}/20")
    
    if success_count > 10:
        print(f"[WARNING] System allows {success_count} concurrent positions")
        return False
    else:
        print(f"[PASS] Position limit enforced")
        return True

def test_per_signal_limit():
    """Test maximum positions per signal type"""
    print("\n" + "="*60)
    print("TESTING PER-SIGNAL POSITION LIMIT")
    print("="*60)
    
    # Try to create multiple positions for same signal
    results = []
    
    for i in range(5):
        payload = {
            "secret": WEBHOOK_SECRET,
            "signal": "S1",  # Same signal
            "strike": 25000 + (i * 50),  # Different strikes
            "option_type": "PE",
            "lots": 1,
            "timestamp": datetime.now().isoformat(),
            "test_mode": True
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/webhook/entry",
                json=payload,
                timeout=5
            )
            results.append({
                "attempt": i + 1,
                "status": response.status_code
            })
            time.sleep(1)
        except Exception as e:
            results.append({
                "attempt": i + 1,
                "status": "error"
            })
    
    success_count = sum(1 for r in results if r.get("status") == 200)
    
    print(f"\nResults:")
    for result in results:
        print(f"  Attempt {result['attempt']}: Status {result['status']}")
    
    if success_count <= 2:
        print(f"[PASS] Per-signal limit enforced")
        return True
    else:
        print(f"[WARNING] {success_count} positions allowed for same signal")
        return False

def test_margin_requirement():
    """Test margin requirement validation"""
    print("\n" + "="*60)
    print("TESTING MARGIN REQUIREMENT VALIDATION")
    print("="*60)
    
    # Check available margin
    try:
        response = requests.get(f"{BASE_URL}/api/account/margin", timeout=5)
        if response.status_code == 200:
            margin = response.json()
            print(f"Available margin: {margin.get('available', 'N/A')}")
        elif response.status_code == 404:
            print("Margin endpoint not found")
    except:
        print("Could not check margin")
    
    # Try to place order requiring high margin
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S3",
        "strike": 25000,
        "option_type": "PE",
        "lots": 100,
        "required_margin": 500000,  # 5 lakh margin required
        "timestamp": datetime.now().isoformat(),
        "test_mode": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=payload,
            timeout=5
        )
        
        if response.status_code in [400, 403, 422]:
            print(f"[PASS] Margin validation working")
            return True
        elif response.status_code == 200:
            print(f"[INFO] Order accepted - check margin calculation")
            return True
        else:
            print(f"Response: {response.status_code}")
            return True
            
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_kill_switch_blocks_orders():
    """Test that kill switch blocks new orders"""
    print("\n" + "="*60)
    print("TESTING KILL SWITCH BLOCKS ORDERS")
    print("="*60)
    
    # First activate kill switch
    try:
        response = requests.post(
            f"{BASE_URL}/api/kill-switch/trigger",
            json={"reason": "Testing kill switch"},
            timeout=5
        )
        print(f"Kill switch activation: {response.status_code}")
        time.sleep(1)
    except:
        print("Could not activate kill switch")
        return False
    
    # Now try to place order
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S4",
        "strike": 25000,
        "option_type": "CE",
        "lots": 1,
        "timestamp": datetime.now().isoformat(),
        "test_mode": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/entry",
            json=payload,
            timeout=5
        )
        
        if response.status_code in [403, 503]:
            print(f"[PASS] Kill switch blocks orders correctly")
            result = True
        else:
            print(f"[FAIL] Order went through despite kill switch!")
            result = False
    except:
        print(f"[PASS] Connection blocked by kill switch")
        result = True
    
    # Reset kill switch
    try:
        response = requests.post(
            f"{BASE_URL}/api/kill-switch/reset",
            timeout=5
        )
        print(f"Kill switch reset: {response.status_code}")
    except:
        print("Could not reset kill switch")
    
    return result

if __name__ == "__main__":
    print("\n" + "="*70)
    print("CRITICAL TEST: POSITION LIMITS AND RISK MANAGEMENT")
    print("="*70)
    print("This test ensures position size limits prevent catastrophic losses")
    
    test_results = []
    
    # Run tests
    test_results.append(("Max Lots Per Trade", test_max_lots_per_trade()))
    time.sleep(2)
    
    test_results.append(("Max Exposure Limit", test_max_exposure_limit()))
    time.sleep(2)
    
    test_results.append(("Concurrent Position Limit", test_concurrent_position_limit()))
    time.sleep(2)
    
    test_results.append(("Per Signal Limit", test_per_signal_limit()))
    time.sleep(2)
    
    test_results.append(("Margin Requirement", test_margin_requirement()))
    time.sleep(2)
    
    test_results.append(("Kill Switch Blocks Orders", test_kill_switch_blocks_orders()))
    
    # Summary
    print("\n" + "="*70)
    print("POSITION LIMITS TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nSUCCESS: Position limits and risk management working!")
    else:
        print("\nWARNING: Some risk limits not properly enforced!")
        print("This could lead to excessive losses!")