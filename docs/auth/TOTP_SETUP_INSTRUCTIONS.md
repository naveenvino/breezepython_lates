# TOTP Setup Instructions for Breeze Auto-Login

Since you have TOTP already enabled on your Breeze account, follow these steps:

## Step 1: Get Your TOTP Secret

Your TOTP secret is the key that was shown when you first set up Google Authenticator with Breeze.

### If you still have the secret:
- It looks like: `ABCDEFGHIJKLMNOP` or `ABCD EFGH IJKL MNOP`
- It's usually 16-32 characters long

### If you don't have the secret saved:
Unfortunately, you'll need to:
1. Login to Breeze website
2. Go to Security Settings
3. Disable 2FA/TOTP
4. Re-enable it
5. When the QR code appears, look for "Can't scan?" or "Manual entry"
6. Copy the secret key shown

## Step 2: Save Your TOTP Secret

Run this command:
```bash
python save_totp_secret.py
```

When prompted, enter your TOTP secret (the input will be hidden).

## Step 3: Test Automatic Login

Run this command to test:
```bash
python test_breeze_totp.py
```

This will:
- Automatically generate the current OTP using your secret
- Login to Breeze without manual intervention
- Save the session token to .env

## Step 4: Use Dashboard

Now when you click "Manual Login" in the dashboard:
- It will automatically login using TOTP
- No manual OTP entry needed
- Session token will be saved

## Alternative: Quick Save

If you want to save the secret directly to .env:

1. Open `.env` file
2. Add this line:
```
BREEZE_TOTP_SECRET=YOUR_SECRET_HERE
```
3. Replace `YOUR_SECRET_HERE` with your actual secret (no spaces)

## Verify Setup

Run:
```bash
curl http://localhost:8000/auth/auto-login/status
```

If TOTP is configured, you'll see it can do automatic login.

## Troubleshooting

### "Invalid TOTP" error
- Make sure your system time is synchronized
- Windows: Run `w32tm /resync` as administrator
- The secret should be uppercase with no spaces

### "OTP expired" error
- OTP codes are only valid for 30 seconds
- The automatic system generates them instantly, so this shouldn't happen
- Check system time synchronization

## Security Notes

- Your TOTP secret is stored locally in `.env`
- Never share this secret with anyone
- It gives full access to generate OTPs for your account
- Consider using a dedicated API account if available