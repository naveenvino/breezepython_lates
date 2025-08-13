# Auto-Login Permanent Setup Guide

## Current Status ✅
- **Breeze**: Session active, TOTP configured
- **Kite**: Connected, TOTP configured  
- **Scheduler**: RUNNING with jobs scheduled at:
  - Breeze: 5:30 AM, 8:30 AM
  - Kite: 5:45 AM, 8:45 AM

## What's Working Now
1. ✅ Auto-login credentials saved in `.env`
2. ✅ TOTP secrets configured for automatic OTP generation
3. ✅ Scheduler is running and will trigger logins at scheduled times
4. ✅ Auto-login dashboard available in UI

## To Ensure It Works Tomorrow

### Option 1: Keep API Running (Recommended)
The scheduler is currently running in the background. As long as the API stays running, it will automatically login at the scheduled times.

**To keep API running:**
- Don't close the terminal running `python unified_api_correct.py`
- Or run it as: `start /min python unified_api_correct.py`

### Option 2: Manual Startup Each Day
If the API is stopped, you need to:
1. Start the API: `python unified_api_correct.py`
2. The scheduler will automatically start with the API

### Option 3: Windows Startup (Manual Setup Required)
1. Press `Win + R`, type `shell:startup`
2. Copy `start_api_on_boot.bat` to the startup folder
3. This will start the API when Windows starts

## Manual Login Commands (If Needed)
```bash
# Breeze login with TOTP (automatic OTP)
python scripts/auth/breeze_auto_login.py

# Kite login with TOTP (automatic OTP)  
python scripts/auth/kite_auto_login.py

# Check status
curl http://localhost:8000/auth/auto-login/status
```

## Verify Tomorrow Morning
1. Check the auto-login dashboard in UI
2. Or run: `curl http://localhost:8000/auth/auto-login/status`
3. Both should show as "Active/Connected"

## Important Notes
- The system clock offset (+60 seconds) is compensated automatically
- Sessions expire daily and need fresh login
- The scheduler handles this automatically at the configured times
- Logs are saved in `logs/` folder

## If Auto-Login Fails Tomorrow
1. Check if API is running
2. Check scheduler status: `/auth/auto-login/schedule/status`
3. If scheduler not running: POST to `/auth/auto-login/schedule/start`
4. Manual fallback: Run the scripts mentioned above

## Configuration Files
- Credentials: `.env` file
- Scheduler config: `config/scheduler_config.json`
- Login status: `logs/login_status.json`