# TradingView Setup Guide

## Setting Up Credentials

To access more historical data from TradingView, you need to provide your TradingView credentials.

### Method 1: Using .env file (Recommended)

1. Create a `.env` file in the project root directory
2. Add your TradingView credentials:

```
TRADINGVIEW_USERNAME=your_username
TRADINGVIEW_PASSWORD=your_password
```

### Method 2: Direct Configuration

Edit `config/tradingview_config.py` and add your credentials:

```python
TRADINGVIEW_USERNAME = 'your_username'
TRADINGVIEW_PASSWORD = 'your_password'
```

## Benefits of Using Credentials

- **More Historical Data**: Access up to 5000 bars of historical data
- **All Symbols**: Access to more symbols without limitations
- **Better Performance**: Fewer rate limiting issues

## Without Credentials

Without credentials, you'll see:
- "you are using nologin method, data you access may be limited"
- Limited historical data access
- Some symbols may not be available

## Testing Your Setup

Run this test to verify credentials are working:

```python
from tvDatafeed import TvDatafeed
from config.tradingview_config import get_tv_credentials

username, password = get_tv_credentials()
if username and password:
    tv = TvDatafeed(username, password)
    print("Logged in successfully!")
else:
    print("No credentials found")
```

## Important Notes

1. **Keep credentials secure** - Never commit .env file to version control
2. **Rate Limits** - Even with login, respect TradingView's rate limits
3. **Terms of Service** - Ensure you comply with TradingView's ToS