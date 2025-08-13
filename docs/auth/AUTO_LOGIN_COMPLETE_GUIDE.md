# Complete Auto-Login Guide for Breeze & Kite

## Overview
This guide covers the complete setup and usage of automated login for both Breeze (ICICI Direct) and Kite (Zerodha) trading platforms.

## System Requirements
- Python 3.8+
- Chrome browser installed
- ChromeDriver (automatically downloaded)
- System time should be synchronized (or use offset)

## Quick Start

### Daily Auto-Login
```bash
# Login to Breeze
python scripts/auth/breeze_auto_login.py

# Login to Kite  
python scripts/auth/kite_auto_login.py
```

## Platform-Specific Setup

### Breeze (ICICI Direct)

#### Prerequisites
1. Breeze API credentials (API Key, Secret)
2. TOTP enabled on your account
3. TOTP secret key

#### Configuration
Add to `.env`:
```
BREEZE_API_KEY=your_api_key
BREEZE_API_SECRET=your_api_secret
BREEZE_USER_ID=your_email@domain.com
BREEZE_PASSWORD=your_password
BREEZE_TOTP_SECRET=your_totp_secret
```

#### Time Offset
- **Required**: +60 seconds offset
- Already configured in the script
- This compensates for system time being 60 seconds behind

### Kite (Zerodha)

#### Prerequisites
1. Kite Connect API credentials (API Key, Secret)
2. **External TOTP** enabled (NOT App Code)
3. TOTP secret key from Kite

#### Enable External TOTP
1. Login to https://kite.zerodha.com
2. Go to Settings → Password & Security
3. Enable "External TOTP" (not App Code)
4. Click "Can't scan? Copy the key"
5. Save the secret key

#### Configuration
Add to `.env`:
```
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
KITE_USER_ID=your_user_id
KITE_PASSWORD=your_password
KITE_TOTP_SECRET=your_totp_secret
```

#### Time Offset
- **Required**: +60 seconds offset
- Already configured in the script
- Same offset as Breeze

## Common Issues & Solutions

### Issue: Invalid TOTP
**Solution**: Check system time synchronization
```bash
# Check current TOTP
python -c "import pyotp; print(pyotp.TOTP('YOUR_SECRET').now())"
```

### Issue: TOTP field not found
**Solution**: Ensure you're using External TOTP for Kite, not App Code

### Issue: Session expired
**Solution**: Run the auto-login script again to get fresh tokens

## Architecture

### Directory Structure
```
scripts/auth/
├── breeze_auto_login.py   # Breeze automated login
├── kite_auto_login.py      # Kite automated login
└── daily_login.py          # Run both logins

src/auth/auto_login/
├── base_login.py           # Base automation class
├── breeze_login.py         # Breeze-specific logic
├── kite_login.py           # Kite-specific logic
└── credential_manager.py   # Secure credential handling
```

### Key Features
1. **Headless Operation**: Runs without displaying browser
2. **TOTP Generation**: Automatic OTP generation with time offset
3. **Token Persistence**: Saves tokens to .env file
4. **Error Handling**: Screenshots on failure for debugging
5. **Credential Security**: Uses environment variables

## Advanced Usage

### Run Both Logins
Create `scripts/auth/daily_login.py`:
```python
import subprocess
import sys

print("Starting daily auto-login...")

# Login to Breeze
print("\n1. Logging into Breeze...")
subprocess.run([sys.executable, "scripts/auth/breeze_auto_login.py"])

# Login to Kite
print("\n2. Logging into Kite...")
subprocess.run([sys.executable, "scripts/auth/kite_auto_login.py"])

print("\nDaily login complete!")
```

### Verify Login Status
```python
import os
from dotenv import load_dotenv

load_dotenv()

breeze_session = os.getenv('BREEZE_API_SESSION')
kite_token = os.getenv('KITE_ACCESS_TOKEN')

print(f"Breeze Session: {'✓' if breeze_session else '✗'}")
print(f"Kite Token: {'✓' if kite_token else '✗'}")
```

## Security Best Practices

1. **Never commit `.env` file** to version control
2. **Use strong passwords** for trading accounts
3. **Keep TOTP secrets secure** - treat like passwords
4. **Rotate API keys** periodically
5. **Monitor login attempts** for unauthorized access

## Troubleshooting

### Debug Mode
Run with visible browser:
```python
# Edit the script and comment out:
# options.add_argument('--headless')
```

### Check Logs
Screenshots saved in `logs/screenshots/` on failure

### Time Sync Issues
If TOTP consistently fails:
1. Sync Windows time: Settings → Time & Date → Sync now
2. Or adjust offset in script (currently +60s)

## Support

For issues or questions:
1. Check error screenshots in `logs/screenshots/`
2. Verify TOTP matches Google Authenticator
3. Ensure External TOTP is enabled (for Kite)
4. Check system time synchronization

## Version History
- v1.0: Initial implementation with +60s offset for both platforms
- Successfully tested with Breeze and Kite on 2025-08-11