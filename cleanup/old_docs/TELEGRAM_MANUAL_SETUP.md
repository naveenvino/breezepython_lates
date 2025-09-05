# 📱 TELEGRAM ALERTS - MANUAL SETUP

Since Telegram API is blocked on your network, follow these steps:

## ✅ Step 1: Get Your Chat ID (Choose ONE method)

### Method A: Use @userinfobot (EASIEST)
1. Open Telegram app on your phone
2. Search for: **@userinfobot**
3. Click Start
4. Bot will immediately show your Chat ID
5. Copy the number (e.g., 123456789)

### Method B: Use Mobile Data
1. Turn off WiFi, use mobile data
2. Open this link on your phone:
```
https://api.telegram.org/bot8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM/getUpdates
```
3. First message @Alphaone_alertbot
4. Refresh the link
5. Find `"chat":{"id":` and copy the number

### Method C: Use Web Telegram
1. Open https://web.telegram.org
2. Login and open any chat
3. Look at URL: `https://web.telegram.org/k/#123456789`
4. Numbers after # are your Chat ID

## ✅ Step 2: Configure Alerts

Once you have your Chat ID (e.g., 123456789), run:

```bash
python configure_alerts_offline.py
```

Enter your Chat ID when prompted.

## ✅ Step 3: Set Environment Variables

### Option A: Run the batch file
```bash
setup_telegram.bat
```

### Option B: Set manually
```cmd
setx TELEGRAM_BOT_TOKEN "8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM"
setx TELEGRAM_CHAT_ID "YOUR_CHAT_ID_HERE"
```

## ✅ Step 4: Test Your Setup

### Test from another network (mobile/VPN):
Replace YOUR_CHAT_ID with your actual ID:
```
https://api.telegram.org/bot8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM/sendMessage?chat_id=YOUR_CHAT_ID&text=Test%20Alert
```

## 📊 Your Bot Details

| Field | Value |
|-------|-------|
| Bot Name | @Alphaone_alertbot |
| Bot Token | 8268902303:AAFy8t0gARt0iWGech3mlIfrOZ9S4Jrt3WM |
| Your Chat ID | Get from Step 1 |

## 🔧 Network Bypass Options

If you want to use Telegram API from your current network:

1. **VPN Solutions**
   - Download Cloudflare WARP (free)
   - Or use any VPN service

2. **DNS Change**
   - Change DNS to: 8.8.8.8 or 1.1.1.1
   - Windows: Network Settings → Change adapter options → Properties → IPv4 → DNS

3. **Proxy Setup**
   - Use SOCKS5 proxy in Telegram settings
   - Many free proxies available online

## ✅ Configuration Files

After setup, you'll have:
- `telegram_config.json` - Your configuration
- `setup_telegram.bat` - Environment setup
- `alert_dashboard.html` - Testing interface

## 🎯 Testing Alerts

1. Open `alert_dashboard.html` in browser
2. Enter your Chat ID in configuration
3. Click test buttons
4. Check Telegram for messages (when network allows)

## 📝 Example Chat IDs

- Personal: `123456789` (9-10 digits, positive)
- Group: `-123456789` (negative)
- Channel: `-1001234567890` (with -100 prefix)

## ⚠️ Important Notes

- Alerts still work via console logs even without Telegram
- Dashboard shows all alerts locally
- Telegram is just one notification channel
- Your trading system is fully functional

## Need Help?

1. Get Chat ID from @userinfobot (easiest)
2. Configure offline using the script
3. Test when you have network access
4. Alerts work regardless of Telegram status