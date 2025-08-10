# Breeze Session Token - Complete Guide

## ⚠️ IMPORTANT: Current Issue
The tokens you're providing (52547680, 52547699) are NOT valid session tokens. These appear to be login page identifiers, not actual authentication tokens.

## How to Get a VALID Session Token

### Step 1: Open Breeze Login Page
Go to: https://api.icicidirect.com/apiuser/login

### Step 2: Login with Your Credentials
- Enter your username/client ID
- Enter your password
- Complete any 2FA if required
- Click Login/Submit

### Step 3: After Successful Login
You will be redirected to a URL that looks like:
```
https://api.icicidirect.com/apiuser/?apisession=ACTUAL_TOKEN_HERE
```

### Step 4: Copy the ACTUAL Token
The `ACTUAL_TOKEN_HERE` part is your real session token. It will be:
- Much longer than just 8 digits
- Usually 20-40 characters
- Mix of letters and numbers
- Example: `AbC123XyZ456DefGhi789jKlMnO`

## What You're Currently Providing vs What's Needed

### ❌ INCORRECT (What you're providing):
- URL: `https://localhost:56412/?apisession=52547699`
- Token: `52547699`
- This is the LOGIN PAGE URL, not the post-login URL
- This short number is NOT a valid session token

### ✅ CORRECT (What you need):
- Complete the login on Breeze website
- Get redirected to: `https://api.icicidirect.com/apiuser/?apisession=RealLongTokenHere123ABC`
- Token: `RealLongTokenHere123ABC` (example)

## How to Update Once You Have the Real Token

```bash
# Method 1: Direct token
python update_session.py RealLongTokenHere123ABC

# Method 2: Full URL after login
python update_session.py "https://api.icicidirect.com/apiuser/?apisession=RealLongTokenHere123ABC"
```

## Current System Status

- ✅ API Server: Running fine
- ✅ Database: Connected
- ✅ Backtesting: Works with existing data
- ❌ Breeze Session: Invalid token (needs real post-login token)
- ✅ UI: All modules functional

## What Works Without Valid Token

You can still:
1. Run backtests with existing data
2. View ML validation results
3. Use all UI features
4. Check historical data

## What Needs Valid Token

You need a valid token to:
1. Fetch new market data
2. Get live prices
3. Update options data
4. Access Breeze API features

## Next Steps

1. **Login to Breeze**: Actually complete the login process
2. **Get Real Token**: Copy the token from the URL AFTER successful login
3. **Update Token**: Use `python update_session.py YOUR_REAL_TOKEN`
4. **Restart API**: The API will automatically use the new token
5. **Verify**: Check the dashboard to see "Session Valid"

## Remember

The URL `https://localhost:56412/?apisession=52547699` is showing you the LOGIN page, not the authenticated page. You need to:
1. Complete the login
2. Get the token from the URL you're redirected to AFTER login
3. That post-login token is what we need!