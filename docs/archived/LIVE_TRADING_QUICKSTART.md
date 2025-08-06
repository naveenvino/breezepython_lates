# Live Trading Quick Start Guide

## Prerequisites Checklist
- ✅ Zerodha trading account with F&O enabled
- ✅ Kite Connect developer account
- ✅ Python 3.8+ installed
- ✅ SQL Server database running

## Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

## Step 2: Database Setup
Run the SQL script to create live trading tables:
```bash
# Using SQL Server Management Studio or sqlcmd:
sqlcmd -S (localdb)\mssqllocaldb -d KiteConnectApi -i migrations/schema/create_live_trading_tables.sql
```

## Step 3: Configure API Keys
Your Kite API credentials have been added to `.env`:
- API Key: `a3vacbrbn3fs98ie`
- API Secret: `zy2zaws481kifjmsv3v6pchu13ng2cbz`

## Step 4: Daily Authentication (REQUIRED EVERY DAY)
Run the authentication script each trading day before 9 AM:
```bash
python scripts/kite_daily_auth.py
```

This will:
1. Open Kite login page in your browser
2. After login, copy the redirect URL
3. Paste it in the script to generate access token
4. Token will be saved automatically

## Step 5: Start the API Server
```bash
python unified_api_correct.py
```
The API will start on http://localhost:8000

## Step 6: Start Live Trading Monitor (Optional)
In a new terminal:
```bash
python scripts/live_trading_monitor.py
```
This provides a real-time dashboard of your positions and P&L.

## Step 7: Enable Live Trading
```bash
# Enable trading with default settings
curl -X POST http://localhost:8000/live/start-trading \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "lot_size": 75,
    "num_lots": 10,
    "use_hedging": true,
    "max_positions": 1
  }'
```

## Testing the System

### 1. Check Authentication Status
```bash
curl http://localhost:8000/live/auth/status
```

### 2. Test with Manual Signal (Paper Trade First!)
```bash
# Execute a test signal with current NIFTY spot price
curl -X POST http://localhost:8000/live/execute-signal \
  -H "Content-Type: application/json" \
  -d '{
    "signal_type": "S1",
    "current_spot": 25000
  }'
```

### 3. Monitor Positions
```bash
# View current positions
curl http://localhost:8000/live/positions

# View P&L
curl http://localhost:8000/live/pnl
```

## Important URLs

### API Documentation
http://localhost:8000/docs

### Key Endpoints
- **Auth**: `/live/auth/status`, `/live/auth/login-url`
- **Trading**: `/live/start-trading`, `/live/stop-trading`
- **Monitoring**: `/live/positions`, `/live/pnl`
- **Risk**: `/live/stop-loss/status`
- **Emergency**: `/live/square-off`

## Daily Routine

### Before Market (8:30 AM)
1. Run authentication script
2. Start API server
3. Check system health
4. Enable live trading

### During Market
1. Monitor positions dashboard
2. Check stop loss alerts
3. Watch for signals

### End of Day
1. Review trades
2. Check P&L summary
3. Disable trading (optional)

## Safety Features
- ✅ Automatic stop loss monitoring
- ✅ Expiry day square-off at 3:15 PM
- ✅ Position limits enforced
- ✅ Daily loss limits
- ✅ Emergency square-off button

## Troubleshooting

### Authentication Issues
- Ensure 2FA is enabled on Zerodha
- Check if access token expired (6 AM daily)
- Verify API key and secret

### Order Failures
- Check margin availability
- Verify market hours
- Check symbol format

### Connection Issues
- Ensure API server is running
- Check network connectivity
- Verify firewall settings

## Emergency Contacts
- Zerodha Support: 080-40402020
- Kite Connect Forum: kite.trade/forum

## Important Notes
1. **Start Small**: Test with 1 lot before scaling to 10
2. **Monitor Closely**: Keep dashboard open during trading
3. **Risk Management**: Never disable stop loss
4. **Daily Auth**: Must authenticate every day before 9 AM
5. **Expiry Day**: System auto-squares off at 3:15 PM on Thursday

## Your Login URL
```
https://kite.trade/connect/login?api_key=a3vacbrbn3fs98ie&v=3
```

Save this URL for daily authentication!

---
Ready to start? Run `python scripts/kite_daily_auth.py` to authenticate!