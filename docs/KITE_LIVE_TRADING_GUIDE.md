# Kite Connect Live Trading Integration Guide

## Overview
This guide explains how to use the Zerodha Kite Connect integration for live trading with the BreezeConnect Trading System. The system uses Breeze API for historical data and backtesting, while Kite Connect handles live order execution.

## Architecture
- **Breeze API**: Historical data, backtesting, signal generation
- **Kite Connect**: Live order placement, position monitoring, P&L tracking
- **Hybrid System**: Seamless integration between both APIs

## Prerequisites

### 1. Zerodha Account Setup
- Active Zerodha trading account
- 2FA (TOTP) enabled
- Sufficient capital for options trading

### 2. Kite Connect Developer Account
1. Visit https://developers.kite.trade/
2. Sign up for a developer account
3. Create a new app
4. Note your API Key and API Secret

### 3. Install Dependencies
```bash
pip install kiteconnect
# Or update all requirements
pip install -r requirements.txt
```

## Configuration

### 1. Environment Variables
Add to your `.env` file:
```env
# Kite Connect API Configuration
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_access_token_here  # Optional, generated daily
```

### 2. Database Setup
Run the SQL script to create live trading tables:
```bash
# Execute in SQL Server Management Studio or via sqlcmd
sqlcmd -S (localdb)\mssqllocaldb -d KiteConnectApi -i migrations/schema/create_live_trading_tables.sql
```

## Authentication Flow

### Step 1: Get Login URL
```bash
curl http://localhost:8000/live/auth/login-url
```
Response:
```json
{
  "login_url": "https://kite.trade/connect/login?api_key=your_api_key&v=3"
}
```

### Step 2: Complete Login
1. Visit the login URL in a browser
2. Log in with Zerodha credentials
3. You'll be redirected with a `request_token` parameter

### Step 3: Generate Access Token
```bash
curl -X POST "http://localhost:8000/live/auth/complete?request_token=YOUR_REQUEST_TOKEN"
```
Response:
```json
{
  "status": "success",
  "user_id": "AB1234",
  "user_name": "Your Name"
}
```

### Step 4: Check Authentication Status
```bash
curl http://localhost:8000/live/auth/status
```

## Live Trading Operations

### 1. Enable Live Trading
```bash
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

### 2. Manual Signal Execution
Execute a specific signal manually:
```bash
curl -X POST http://localhost:8000/live/execute-signal \
  -H "Content-Type: application/json" \
  -d '{
    "signal_type": "S1",
    "current_spot": 25000
  }'
```

### 3. Monitor Positions
```bash
# Get current positions
curl http://localhost:8000/live/positions

# Get real-time P&L
curl http://localhost:8000/live/pnl

# Get active trades
curl http://localhost:8000/live/trades/active
```

### 4. Risk Management
```bash
# Check stop loss status
curl http://localhost:8000/live/stop-loss/status

# Get stop loss summary
curl http://localhost:8000/live/stop-loss/summary
```

### 5. Emergency Controls
```bash
# Square off all positions
curl -X POST http://localhost:8000/live/square-off

# Disable live trading
curl -X POST http://localhost:8000/live/stop-trading
```

## Trading Rules & Configuration

### Position Sizing
- **Lot Size**: 75 (NIFTY standard)
- **Number of Lots**: 10 (configurable)
- **Total Quantity**: 750

### Entry/Exit Rules
- **Entry**: Market orders at signal generation
- **Stop Loss**: When option reaches main strike price
- **Expiry Exit**: Automatic square-off at 3:15 PM on Thursday
- **No New Positions**: After 3:00 PM on expiry day

### Risk Limits
```python
{
  "max_loss_per_day": 50000,
  "max_loss_per_trade": 25000,
  "max_positions": 1,
  "min_capital_required": 500000
}
```

## Signal Mapping

| Signal | Type | Direction | Action |
|--------|------|-----------|--------|
| S1 | Bear Trap | Bullish | Sell PUT |
| S2 | Support Hold | Bullish | Sell PUT |
| S3 | Resistance Hold | Bearish | Sell CALL |
| S4 | Bias Failure Bull | Bullish | Sell PUT |
| S5 | Bias Failure Bear | Bearish | Sell CALL |
| S6 | Weakness Confirmed | Bearish | Sell CALL |
| S7 | Breakout Confirmed | Bullish | Sell PUT |
| S8 | Breakdown Confirmed | Bearish | Sell CALL |

## Option Symbol Format
NIFTY options follow this format:
```
NIFTY{YY}{MON}{DD}{STRIKE}{CE/PE}
```
Examples:
- `NIFTY24DEC1925000CE` - December 19, 2024, 25000 CALL
- `NIFTY24DEC1925000PE` - December 19, 2024, 25000 PUT

Month codes:
- JAN, FEB, MAR, APR, MAY, JUN, JUL, AUG, SEP
- October: O, November: N, December: D

## Monitoring Dashboard

### Key Metrics to Track
1. **Current Positions**
   - Symbol, quantity, entry price
   - Current price and P&L
   - Time to expiry

2. **Daily Summary**
   - Total trades
   - Win/loss ratio
   - Total P&L
   - Stop losses hit

3. **Risk Metrics**
   - Current exposure
   - Margin utilization
   - Daily loss vs limit

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Ensure 2FA is enabled
   - Check API key and secret
   - Access token expires daily at 6 AM

2. **Order Rejection**
   - Check margin availability
   - Verify symbol format
   - Ensure market hours

3. **Position Not Squared Off**
   - Check if market is open
   - Verify position exists
   - Check for partial fills

### Error Codes
- `InputException`: Invalid parameters
- `TokenException`: Authentication issues
- `NetworkException`: Connection problems
- `OrderException`: Order placement issues

## Best Practices

1. **Testing**
   - Start with paper trading
   - Test with 1 lot before scaling
   - Verify all endpoints work

2. **Monitoring**
   - Set up alerts for stop losses
   - Monitor positions regularly
   - Check P&L limits

3. **Risk Management**
   - Never disable stop loss
   - Honor position limits
   - Keep sufficient margin

4. **Daily Routine**
   - Refresh access token before 9 AM
   - Check system health
   - Review previous day's trades

## API Endpoints Reference

### Authentication
- `GET /live/auth/status` - Check auth status
- `GET /live/auth/login-url` - Get login URL
- `POST /live/auth/complete` - Complete authentication

### Trading Control
- `POST /live/start-trading` - Enable trading
- `POST /live/stop-trading` - Disable trading
- `POST /live/square-off` - Emergency exit

### Monitoring
- `GET /live/positions` - Current positions
- `GET /live/pnl` - Real-time P&L
- `GET /live/trades/active` - Active trades

### Risk Management
- `GET /live/stop-loss/status` - Stop loss check
- `GET /live/stop-loss/summary` - Daily summary

### Execution
- `POST /live/execute-signal` - Manual signal execution

## Safety Checklist

Before going live:
- [ ] Test authentication flow
- [ ] Verify database tables created
- [ ] Test with small position
- [ ] Set up monitoring
- [ ] Configure risk limits
- [ ] Test emergency square-off
- [ ] Verify expiry day logic
- [ ] Check stop loss triggers
- [ ] Review error handling
- [ ] Document emergency contacts

## Support

For issues:
1. Check logs in `logs/` directory
2. Verify configuration in `.env`
3. Review trade records in database
4. Contact Zerodha support for API issues

Remember: Always start with small positions and gradually increase as you gain confidence in the system.