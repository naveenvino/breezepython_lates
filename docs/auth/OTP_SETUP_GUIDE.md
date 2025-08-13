# Auto-Login OTP/2FA Setup Guide

## Important: OTP/2FA is Required!

Both Breeze (ICICI Direct) and Kite (Zerodha) require two-factor authentication for login. The auto-login system cannot work without handling OTP/2FA.

## Option 1: Breeze (ICICI Direct) - Email OTP

Breeze sends OTP to your registered email/mobile. To automate this:

### Method A: Manual OTP Entry (Current Implementation)
1. Run auto-login in non-headless mode
2. When OTP is requested, enter it manually
3. The system will wait for your input

### Method B: Email Integration (Advanced - Not Implemented)
Would require:
- IMAP access to your email
- Email parsing to extract OTP
- Security risks of storing email credentials

### Method C: TOTP Setup (If Available)
Some Breeze accounts support TOTP (Google Authenticator):
1. Enable TOTP in your Breeze account settings
2. Save the TOTP secret in credentials
3. System will auto-generate OTP codes

## Option 2: Kite (Zerodha) - PIN or TOTP

Kite supports two methods:

### Method A: PIN Entry
- Use your 6-digit PIN (simpler but less secure)
- PIN is stored encrypted with credentials

### Method B: TOTP (Google Authenticator)
1. Enable 2FA in Kite account settings
2. Save the TOTP secret when setting up Google Authenticator
3. System will auto-generate TOTP codes

## Current Status

The system is currently configured for:
- Manual OTP entry when running in non-headless mode
- Automatic TOTP generation if TOTP secret is configured

## Quick Test Commands

### Test Breeze Login (Manual OTP):
```bash
python test_breeze_manual.py
```

### Test Kite Login (with PIN):
```bash
python test_kite_pin.py
```

## Security Notes

1. **Never share your TOTP secrets**
2. **Store credentials securely** (encrypted)
3. **Use dedicated API accounts** if possible
4. **Monitor login activity** regularly

## Troubleshooting

### "OTP required but not available"
- System is running in headless mode without TOTP configured
- Solution: Run in non-headless mode OR configure TOTP

### "Login failed after OTP"
- OTP might have expired (usually valid for 30-60 seconds)
- Solution: Ensure quick OTP entry or use TOTP for instant generation

### "Session token not found"
- Login succeeded but session extraction failed
- Check browser screenshots in logs/screenshots/

## Alternative: API Keys (Recommended)

Instead of auto-login, consider using:
1. **Breeze API Session**: Generate once daily, valid for 24 hours
2. **Kite Connect API**: Use API key + secret (no login needed)

These are more reliable than browser automation!