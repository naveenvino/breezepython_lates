"""Test risk management limits and position size validation"""
import requests
import json

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "tradingview-webhook-secret-key-2025"

print("="*60)
print("RISK MANAGEMENT LIMIT TESTING")
print("="*60)

# Test 1: Position size limits
print("\n[TEST 1] Position Size Validation")
test_cases = [
    (0, False, "Below minimum"),
    (1, True, "Minimum allowed"),
    (50, True, "Mid-range"),
    (100, True, "Maximum allowed"),
    (101, False, "Above maximum"),
    (1000, False, "Way above maximum")
]

for lots, should_pass, description in test_cases:
    webhook_data = {
        "secret": WEBHOOK_SECRET,
        "signal": "S1",
        "strike": 25000,
        "option_type": "PE",
        "lots": lots,
        "timestamp": "2025-09-06T10:00:00"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/webhook/entry", json=webhook_data, timeout=3)
        
        if lots == 0 or lots > 100:
            # Should be rejected
            passed = response.status_code != 200 or "invalid" in response.text.lower()
        else:
            # Should be accepted (with correct secret)
            passed = response.status_code == 200
            
        status = "[PASS]" if passed == should_pass else "[FAIL]"
        print(f"  {status} {description}: {lots} lots - Status: {response.status_code}")
    except Exception as e:
        print(f"  [ERROR] {description}: {e}")

# Test 2: Stop loss configuration
print("\n[TEST 2] Stop Loss Settings")
try:
    response = requests.get(f"{BASE_URL}/api/settings")
    if response.status_code == 200:
        settings = response.json()
        stop_loss = settings.get("settings", {}).get("stop_loss_points", "200")
        print(f"  [OK] Stop loss configured: {stop_loss} points")
        
        # Verify it's a reasonable value
        try:
            sl_value = int(stop_loss)
            if 100 <= sl_value <= 500:
                print(f"  [OK] Stop loss value is reasonable: {sl_value}")
            else:
                print(f"  [WARN] Stop loss value unusual: {sl_value}")
        except:
            print("  [WARN] Stop loss not numeric")
except Exception as e:
    print(f"  [ERROR] Could not check stop loss: {e}")

# Test 3: Daily loss limit
print("\n[TEST 3] Daily Loss Limit")
try:
    response = requests.get(f"{BASE_URL}/api/settings")
    if response.status_code == 200:
        settings = response.json()
        daily_limit = settings.get("settings", {}).get("daily_loss_limit", "50000")
        print(f"  [OK] Daily loss limit configured: Rs.{daily_limit}")
        
        # Check if it matches production config
        try:
            limit_value = int(daily_limit)
            if limit_value == 50000:
                print(f"  [OK] Daily loss limit matches production config")
            else:
                print(f"  [WARN] Daily loss limit differs from production config")
        except:
            print("  [WARN] Daily loss limit not numeric")
except Exception as e:
    print(f"  [ERROR] Could not check daily loss limit: {e}")

# Test 4: Max positions limit
print("\n[TEST 4] Max Positions Limit")
try:
    response = requests.get(f"{BASE_URL}/api/settings")
    if response.status_code == 200:
        settings = response.json()
        max_pos = settings.get("settings", {}).get("max_positions", "3")
        print(f"  [OK] Max positions configured: {max_pos}")
        
        try:
            max_value = int(max_pos)
            if 1 <= max_value <= 10:
                print(f"  [OK] Max positions value is reasonable: {max_value}")
            else:
                print(f"  [WARN] Max positions value unusual: {max_value}")
        except:
            print("  [WARN] Max positions not numeric")
except Exception as e:
    print(f"  [ERROR] Could not check max positions: {e}")

# Test 5: Hedge configuration
print("\n[TEST 5] Hedge Configuration")
try:
    response = requests.get(f"{BASE_URL}/api/settings")
    if response.status_code == 200:
        settings = response.json()
        hedge_enabled = settings.get("settings", {}).get("enable_hedging", "false")
        hedge_offset = settings.get("settings", {}).get("hedge_offset", "200")
        hedge_percentage = settings.get("settings", {}).get("hedge_percentage", "0.4")
        
        print(f"  [OK] Hedging enabled: {hedge_enabled}")
        print(f"  [OK] Hedge offset: {hedge_offset} points")
        print(f"  [OK] Hedge percentage: {hedge_percentage}")
        
        if hedge_enabled.lower() == "true":
            print("  [OK] Hedge protection is active")
        else:
            print("  [WARN] Hedge protection is disabled")
except Exception as e:
    print(f"  [ERROR] Could not check hedge config: {e}")

print("\n" + "="*60)
print("Risk management testing complete")
print("="*60)