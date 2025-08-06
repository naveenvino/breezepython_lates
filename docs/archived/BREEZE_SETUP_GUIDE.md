# Breeze API Setup Guide

## Current Issue
The Breeze API is rejecting authentication with error: "Could not authenticate credentials. Please check api key."

## Steps to Fix

### 1. Get Your Correct API Credentials
1. Log in to ICICI Direct at https://secure.icicidirect.com/
2. Go to the API section
3. Find your API Key and API Secret
4. Copy them exactly as shown (including any special characters)

### 2. Generate Fresh Session Token
1. Go to: https://api.icicidirect.com/apiuser/login
2. Log in with your ICICI Direct credentials
3. You'll be redirected to a URL like: `https://localhost:56412/?apisession=XXXXXXXX`
4. Copy the `apisession` value (the XXXXXXXX part)

### 3. Update .env File
Edit the `.env` file with your correct credentials:
```
BREEZE_API_KEY=your_actual_api_key_here
BREEZE_API_SECRET=your_actual_api_secret_here
BREEZE_API_SESSION=your_new_session_token_here
```

### 4. Test Connection
Run the test script:
```bash
python test_breeze_simple.py
```

## Common Issues

### Issue 1: API Key Format
- The API key might look like: `I1234N567P89012Q3456R78`
- Make sure to copy it exactly, including any special characters
- Don't confuse O (letter) with 0 (zero)

### Issue 2: Session Expiry
- Session tokens expire after some time
- You need to regenerate them periodically
- The URL pattern after login should be: `https://localhost:56412/?apisession=XXXXXXXX`

### Issue 3: API Not Activated
- Make sure the API service is activated in your ICICI Direct account
- Check if you have the required permissions for historical data

## Current Configuration
Your current `.env` has:
- API Key: `23(326O4280m9516L8F4!1]R` (appears invalid)
- Session: `52469011` (from your provided URL)

## What You Need to Do
1. **Verify your API Key** - The current one is being rejected
2. **Confirm the API Secret** is correct
3. **The session token (52469011) seems correct** based on your URL

Most likely, the API key `23(326O4280m9516L8F4!1]R` is incorrect. Please check:
- Is 'O' actually the letter O or the number 0?
- Are the special characters `(`, `!`, `]` actually part of the key?
- Did you copy it correctly from the ICICI Direct portal?

## Testing After Fix
Once you update the credentials, the data collection should work:
```bash
# Test connection
python test_breeze_simple.py

# Then try data collection via API
curl -X POST "http://localhost:8000/collect/nifty-direct" \
  -H "Content-Type: application/json" \
  -d '{"from_date": "2025-01-20", "to_date": "2025-01-24", "symbol": "NIFTY", "force_refresh": true}'
```