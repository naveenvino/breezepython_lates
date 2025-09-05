# 📱 TELEGRAM ALERTS SETUP GUIDE

## Your Bot Details
- **Bot Name**: @Alphaone_alertbot  
- **Bot Token**: `8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM`

## Step 1: Start Your Bot
1. Open Telegram app
2. Search for: **@Alphaone_alertbot**
3. Click "Start" or send `/start`
4. Send a test message like "Hello"

## Step 2: Get Your Chat ID

### Option A: Via Browser
1. Open your browser
2. Go to: 
```
https://api.telegram.org/bot8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM/getUpdates
```
3. Look for `"chat":{"id":` in the response
4. Copy the number after `"id":` (that's your chat ID)

### Option B: Use Bot Commands
1. Send `/myid` to @Alphaone_alertbot
2. Or send `/start` and check the browser link above

## Step 3: Configure Alerts

### Method 1: Environment Variables (Permanent)
Run these commands in Command Prompt:
```cmd
setx TELEGRAM_BOT_TOKEN "8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM"
setx TELEGRAM_CHAT_ID "YOUR_CHAT_ID_HERE"
```

### Method 2: Create Config File
Create `telegram_config.json`:
```json
{
  "telegram_enabled": true,
  "telegram_bot_token": "8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM",
  "telegram_chat_id": "YOUR_CHAT_ID_HERE"
}
```

### Method 3: Use Alert Dashboard
1. Open `alert_dashboard.html` in browser
2. Enter bot token and chat ID
3. Click "Save Configuration"

## Step 4: Test Alerts

### Quick Test with cURL
```bash
curl -X POST https://api.telegram.org/bot8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM/sendMessage \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"YOUR_CHAT_ID","text":"🎉 Alerts Working!"}'
```

### Test via API
```python
import requests

BOT_TOKEN = "8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM"
CHAT_ID = "YOUR_CHAT_ID_HERE"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
data = {
    "chat_id": CHAT_ID,
    "text": "✅ Trading alerts configured!",
    "parse_mode": "Markdown"
}
requests.post(url, json=data)
```

## Step 5: Restart Trading System
```bash
python unified_api_correct.py
```

## Alert Types You'll Receive
- 📈 **Trade Entry**: When new positions open
- 📉 **Trade Exit**: When positions close
- 🛑 **Stop Loss**: When stop loss triggers
- ⚠️ **Risk Warning**: At 80% of daily loss limit
- 📊 **Daily Summary**: End of day report

## Troubleshooting

### Can't get chat ID?
1. Make sure you sent a message to the bot
2. Try this direct link in browser:
   `https://api.telegram.org/bot8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM/getUpdates`

### Alerts not working?
1. Check environment variables are set
2. Restart the API server
3. Check logs for errors

### Network issues?
- Use a VPN if Telegram is blocked
- Check firewall settings
- Try from a different network

## Example Chat ID Format
Your chat ID will look like one of these:
- Personal: `123456789` (positive number)
- Group: `-123456789` (negative number)

## Support
Bot: @Alphaone_alertbot
Created for: AlphaOne Trading System