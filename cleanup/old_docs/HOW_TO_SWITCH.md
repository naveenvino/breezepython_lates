# How to Switch Between Original and Secure API

## Quick Start - 3 Easy Ways to Run

### Option 1: Run Original API Only (For Development)
```batch
run_original_api.bat
```
- **Port:** 8000
- **URL:** http://localhost:8000
- **Security:** None
- **Use When:** Developing features

### Option 2: Run Secure API Only (For Testing Security)
```batch
run_secure_api.bat
```
- **Port:** 8001
- **URL:** http://localhost:8001
- **Security:** Login required (test/test)
- **Use When:** Testing production security

### Option 3: Run Both Together (For Comparison)
```batch
run_both_apis.bat
```
- **Original:** http://localhost:8000
- **Secure:** http://localhost:8001
- **Use When:** Comparing both versions

## What Files Changed?

| File | Purpose | When to Use |
|------|---------|-------------|
| `unified_api_correct.py` | Original API (Port 8000) | Development |
| `unified_api_secure.py` | Secure API (Port 8001) | Production |
| No other files need changes! | | |

## How to Test Both?

### Method 1: Use the Test Script
```bash
python test_both_apis.py
```
This will:
- Test Original API endpoints
- Test Secure API with authentication
- Show comparison results

### Method 2: Manual Testing

**Test Original API (No Auth):**
```bash
# Health check
curl http://localhost:8000/health

# Auto login status
curl http://localhost:8000/auth/auto-login/status

# Backtest
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{"from_date": "2025-07-14", "to_date": "2025-07-18", "signals_to_test": ["S1"]}'
```

**Test Secure API (With Auth):**
```bash
# Step 1: Login
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test"}'

# Copy the token from response

# Step 2: Use token for requests
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8001/auth/verify
```

## UI Dashboard Access

### When Using Original API (Port 8000):
```
http://localhost:8000/auto_login_dashboard.html
http://localhost:8000/backtest.html
http://localhost:8000/option_chain.html
```

### When Using Secure API (Port 8001):
```
http://localhost:8001/auto_login_dashboard.html
http://localhost:8001/backtest.html
http://localhost:8001/option_chain.html
```

## Simple Decision Flow

```
What are you doing?
│
├── Writing new code/features?
│   └── Use: run_original_api.bat (Port 8000)
│
├── Testing security features?
│   └── Use: run_secure_api.bat (Port 8001)
│
└── Comparing both versions?
    └── Use: run_both_apis.bat (Both ports)
```

## Configuration Files

### Original API Configuration (.env)
```ini
# Your existing .env file works as-is
BREEZE_API_KEY=your_key
KITE_API_KEY=your_key
# No changes needed
```

### Secure API Additional Config (.env)
```ini
# Add these for secure version
JWT_SECRET_KEY=generate_random_key
APP_SECRET_KEY=generate_random_key
ENVIRONMENT=development  # or production
```

## Switching Checklist

- [ ] **To Use Original:** Just run `run_original_api.bat`
- [ ] **To Use Secure:** Just run `run_secure_api.bat`
- [ ] **To Use Both:** Just run `run_both_apis.bat`
- [ ] **No code changes needed**
- [ ] **No file modifications required**
- [ ] **All your features still work**

## Common Scenarios

### "I want to develop new features"
```batch
run_original_api.bat
```
Use http://localhost:8000 as before

### "I want to test if my app is secure"
```batch
run_secure_api.bat
```
Use http://localhost:8001 with login

### "I want to see the difference"
```batch
run_both_apis.bat
```
Compare both at once

## Troubleshooting

### Port Already in Use?
```bash
# Kill process on port 8000
taskkill /F /FI "WINDOWTITLE eq unified_api_correct.py*"

# Kill process on port 8001
taskkill /F /FI "WINDOWTITLE eq unified_api_secure.py*"
```

### Can't Connect?
1. Check if API is running in terminal
2. Check correct port (8000 or 8001)
3. For secure API, check if you're logged in

### Want Original Behavior Back?
Simply use `run_original_api.bat` - everything works exactly as before!

## Summary

**You don't need to change any code!** Just use the batch files:
- `run_original_api.bat` - Development (Port 8000)
- `run_secure_api.bat` - Security Testing (Port 8001)
- `run_both_apis.bat` - Run both together
- `test_both_apis.py` - Test both versions

That's it! Switch anytime by running different batch files.