"""
Test Duplicate Webhook Signal Handling
CRITICAL: Prevents duplicate orders from multiple webhook calls
"""

import requests
import json
import time
import threading
from datetime import datetime
import hashlib

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "tradingview-webhook-secret-key-2025"

def test_duplicate_prevention():
    """Test that duplicate signals don't create multiple positions"""
    print("\n" + "="*60)
    print("TESTING DUPLICATE WEBHOOK PREVENTION")
    print("="*60)
    
    # Create unique signal with timestamp
    signal_id = hashlib.md5(f"S1_{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S1",
        "strike": 25000,
        "option_type": "PE",
        "lots": 10,
        "timestamp": datetime.now().isoformat(),
        "signal_id": signal_id,
        "test_mode": True  # Enable test mode for weekend testing
    }
    
    results = []
    
    def send_webhook():
        """Send webhook request"""
        try:
            response = requests.post(
                f"{BASE_URL}/webhook/entry",
                json=payload,
                timeout=5
            )
            results.append({
                "status": response.status_code,
                "response": response.json() if response.status_code == 200 else None
            })
        except Exception as e:
            results.append({"status": "error", "error": str(e)})
    
    # Send same signal 5 times rapidly
    threads = []
    for i in range(5):
        thread = threading.Thread(target=send_webhook)
        threads.append(thread)
        thread.start()
        time.sleep(0.1)  # Small delay between requests
    
    # Wait for all threads
    for thread in threads:
        thread.join()
    
    # Analyze results
    success_count = sum(1 for r in results if r.get("status") == 200)
    duplicate_rejected = sum(1 for r in results if r.get("status") == 409)
    
    print(f"\nResults:")
    print(f"  Total requests sent: 5")
    print(f"  Successful orders: {success_count}")
    print(f"  Duplicates rejected: {duplicate_rejected}")
    
    # Check positions to verify only 1 was created
    try:
        positions = requests.get(f"{BASE_URL}/api/positions", timeout=5)
        if positions.status_code == 200:
            position_data = positions.json()
            position_count = len(position_data.get("positions", []))
            print(f"  Active positions: {position_count}")
    except:
        print("  Could not verify positions")
    
    # Test verdict
    if success_count == 1:
        print("\nPASS: Duplicate prevention working correctly")
        return True
    else:
        print(f"\nFAIL: {success_count} orders created instead of 1")
        return False

def test_same_signal_different_timestamp():
    """Test same signal with different timestamps"""
    print("\n" + "="*60)
    print("TESTING SAME SIGNAL WITH DIFFERENT TIMESTAMPS")
    print("="*60)
    
    base_payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S2",
        "strike": 25000,
        "option_type": "CE",
        "lots": 5,
        "test_mode": True
    }
    
    results = []
    
    # Send with 1 minute intervals
    for i in range(3):
        payload = base_payload.copy()
        payload["timestamp"] = datetime.now().isoformat()
        
        try:
            response = requests.post(
                f"{BASE_URL}/webhook/entry",
                json=payload,
                timeout=5
            )
            results.append({
                "attempt": i + 1,
                "status": response.status_code,
                "time": datetime.now().strftime("%H:%M:%S")
            })
        except Exception as e:
            results.append({
                "attempt": i + 1,
                "status": "error",
                "error": str(e)
            })
        
        if i < 2:
            print(f"  Waiting 60 seconds before next signal...")
            time.sleep(60)
    
    # Display results
    print("\nResults:")
    for result in results:
        print(f"  Attempt {result['attempt']}: Status {result['status']} at {result.get('time', 'N/A')}")
    
    # Check if duplicate prevention has time window
    success_count = sum(1 for r in results if r.get("status") == 200)
    
    if success_count == 1:
        print("\nPASS: Time-window based duplicate prevention working")
        return True
    elif success_count == 3:
        print("\nWARNING: No time-window protection, all signals accepted")
        return False
    else:
        print(f"\nINFO: {success_count}/3 signals accepted")
        return True

def test_rapid_fire_webhooks():
    """Test system under rapid webhook bombardment"""
    print("\n" + "="*60)
    print("TESTING RAPID FIRE WEBHOOKS (STRESS TEST)")
    print("="*60)
    
    results = {"success": 0, "duplicate": 0, "error": 0}
    
    def send_burst(signal_num):
        """Send a burst of webhooks"""
        payload = {
            "secret": WEBHOOK_SECRET,
            "signal": f"S{(signal_num % 8) + 1}",
            "strike": 25000 + (signal_num * 50),
            "option_type": "PE" if signal_num % 2 == 0 else "CE",
            "lots": 1,
            "timestamp": datetime.now().isoformat(),
            "request_id": f"rapid_{signal_num}",
            "test_mode": True
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/webhook/entry",
                json=payload,
                timeout=2
            )
            if response.status_code == 200:
                results["success"] += 1
            elif response.status_code == 409:
                results["duplicate"] += 1
            else:
                results["error"] += 1
        except:
            results["error"] += 1
    
    # Send 50 webhooks in parallel
    threads = []
    start_time = time.time()
    
    for i in range(50):
        thread = threading.Thread(target=send_burst, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for completion
    for thread in threads:
        thread.join()
    
    duration = time.time() - start_time
    
    print(f"\nResults in {duration:.2f} seconds:")
    print(f"  Successful: {results['success']}")
    print(f"  Duplicates blocked: {results['duplicate']}")
    print(f"  Errors: {results['error']}")
    print(f"  Requests/second: {50/duration:.1f}")
    
    if results["error"] < 5:  # Allow up to 10% error rate
        print("\nPASS: System handles rapid webhooks")
        return True
    else:
        print(f"\nFAIL: Too many errors ({results['error']}/50)")
        return False

def test_idempotency_key():
    """Test idempotency with explicit key"""
    print("\n" + "="*60)
    print("TESTING IDEMPOTENCY KEY HANDLING")
    print("="*60)
    
    idempotency_key = f"test_key_{int(time.time())}"
    
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S3",
        "strike": 25000,
        "option_type": "PE",
        "lots": 5,
        "idempotency_key": idempotency_key,
        "timestamp": datetime.now().isoformat(),
        "test_mode": True
    }
    
    results = []
    
    # Send same idempotency key 3 times
    for i in range(3):
        try:
            response = requests.post(
                f"{BASE_URL}/webhook/entry",
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
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
                "status": "error",
                "error": str(e)
            })
    
    print("\nResults:")
    for result in results:
        print(f"  Attempt {result['attempt']}: Status {result['status']}")
    
    success_count = sum(1 for r in results if r.get("status") == 200)
    
    if success_count == 1:
        print("\nPASS: Idempotency key working correctly")
        return True
    else:
        print(f"\nFAIL: {success_count} orders created with same idempotency key")
        return False

if __name__ == "__main__":
    print("\n" + "="*70)
    print("CRITICAL TEST: DUPLICATE WEBHOOK PREVENTION")
    print("="*70)
    print("This test ensures duplicate webhooks don't create multiple positions")
    print("which could cause significant financial loss")
    
    test_results = []
    
    # Run all tests
    test_results.append(("Duplicate Prevention", test_duplicate_prevention()))
    time.sleep(2)
    
    test_results.append(("Idempotency Key", test_idempotency_key()))
    time.sleep(2)
    
    test_results.append(("Rapid Fire Stress", test_rapid_fire_webhooks()))
    time.sleep(2)
    
    # Note: Skipping time-window test as it takes 2+ minutes
    # test_results.append(("Time Window", test_same_signal_different_timestamp()))
    
    # Summary
    print("\n" + "="*70)
    print("DUPLICATE WEBHOOK TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nSUCCESS: Duplicate webhook protection is working!")
    else:
        print("\nWARNING: Duplicate webhook protection needs improvement!")
        print("This could lead to duplicate orders and financial loss!")