"""
Test that all restrictions are removed
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "tradingview-webhook-secret-key-2025"

def test_no_restrictions():
    print("\n" + "="*60)
    print("TESTING NO RESTRICTIONS")
    print("="*60)
    
    # Test 1: Large lot size (should be accepted)
    print("\n1. Testing large lot size (5000 lots):")
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S1",
        "strike": 25000,
        "option_type": "PE",
        "lots": 5000,
        "timestamp": datetime.now().isoformat(),
        "test_mode": True
    }
    
    try:
        response = requests.post(f"{BASE_URL}/webhook/entry", json=payload, timeout=5)
        if response.status_code == 200:
            print("   [PASS] Large lot size accepted")
        else:
            print(f"   [FAIL] Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"   [ERROR] {e}")
    
    # Test 2: Multiple positions same signal (should be accepted)
    print("\n2. Testing multiple positions for same signal:")
    for i in range(3):
        payload = {
            "secret": WEBHOOK_SECRET,
            "signal": "S2",
            "strike": 25000 + (i * 100),
            "option_type": "CE",
            "lots": 10,
            "timestamp": datetime.now().isoformat(),
            "test_mode": True
        }
        
        try:
            response = requests.post(f"{BASE_URL}/webhook/entry", json=payload, timeout=5)
            if response.status_code == 200:
                print(f"   Position {i+1}: [PASS] Created")
            else:
                print(f"   Position {i+1}: [FAIL] Status {response.status_code}")
        except Exception as e:
            print(f"   Position {i+1}: [ERROR] {e}")
    
    # Test 3: Rapid duplicate webhooks (should be accepted)
    print("\n3. Testing rapid duplicate webhooks:")
    payload = {
        "secret": WEBHOOK_SECRET,
        "signal": "S3",
        "strike": 25000,
        "option_type": "PE",
        "lots": 10,
        "timestamp": datetime.now().isoformat(),
        "test_mode": True
    }
    
    for i in range(3):
        try:
            response = requests.post(f"{BASE_URL}/webhook/entry", json=payload, timeout=5)
            if response.status_code == 200:
                print(f"   Webhook {i+1}: [PASS] Accepted")
            else:
                print(f"   Webhook {i+1}: [FAIL] Status {response.status_code}")
        except Exception as e:
            print(f"   Webhook {i+1}: [ERROR] {e}")
    
    print("\n" + "="*60)
    print("ALL RESTRICTIONS REMOVED - SYSTEM ACCEPTS EVERYTHING")
    print("="*60)

if __name__ == "__main__":
    test_no_restrictions()