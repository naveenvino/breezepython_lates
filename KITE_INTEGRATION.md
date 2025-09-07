# Zerodha Kite Integration - Production Ready

## Overview
Complete integration of Zerodha Kite for real-time NIFTY weekly options trading with automatic expiry selection and iron condor strategy execution.

## Key Features
✅ **Automatic Expiry Selection** - Configurable per weekday (current/next/month-end)
✅ **NIFTY Weekly Options** - Correct symbol formatting for Tuesday expiries
✅ **Iron Condor Strategy** - Main + hedge leg execution
✅ **Paper/Real Trading Modes** - Seamless switching via environment variable
✅ **TradingView Webhook Integration** - Direct signal to order placement
✅ **Auto Square-off** - Scheduled exit at configured time

## System Architecture

```
TradingView Alert
        ↓
Webhook Handler (unified_api_correct.py)
        ↓
Expiry Management Service (determines correct expiry)
        ↓
Kite Weekly Options Executor (formats symbols & places orders)
        ↓
Zerodha Kite API (executes on exchange)
```

## Configuration

### 1. Environment Variables (.env)
```bash
# Trading Mode
PAPER_TRADING_MODE=true  # Set to false for real trading

# Kite Credentials
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_daily_access_token

# Webhook Secret
WEBHOOK_SECRET=tradingview-webhook-secret-key-2025
```

### 2. Weekday Expiry Configuration
Configure which expiry to use for each weekday:

```javascript
// Via API
POST http://localhost:8000/api/expiry/weekday-config
{
    "monday": "current",     // Current week (Tuesday)
    "tuesday": "current",     // Current week (Tuesday)
    "wednesday": "next",      // Next week
    "thursday": "next",       // Next week
    "friday": "next"          // Next week
}
```

### 3. Exit Timing Configuration
```javascript
POST http://localhost:8000/api/exit-timing/configure
{
    "exit_day_offset": 2,        // T+2 days
    "exit_time": "14:15",        // 2:15 PM
    "auto_square_off_enabled": true
}
```

## Symbol Generation

### Weekly Options (Tuesday Expiry)
- Format: `NIFTY{YY}{M}{DD}{STRIKE}{TYPE}`
- Example: `NIFTY2511425000PE` (14-Jan-2025, 25000 strike, PUT)
- Month codes: 1-9 (numeric), O (Oct), N (Nov), D (Dec)

### Monthly Options (Last Thursday)
- Format: `NIFTY{YY}{MMM}{STRIKE}{TYPE}`
- Example: `NIFTY25JAN25000CE` (30-Jan-2025, 25000 strike, CALL)

## Order Execution Flow

### 1. Entry Signal from TradingView
```json
{
    "secret": "your-webhook-secret",
    "signal": "S1",
    "action": "ENTRY",
    "strike": 25000,
    "option_type": "PE",
    "premium": 120,
    "hedge_premium": 30,
    "lots": 10,
    "timestamp": "2025-01-14T10:15:00"
}
```

### 2. System Processing
1. Verify webhook secret
2. Determine expiry based on current day config
3. Generate Kite symbols with correct expiry
4. If real trading mode:
   - Place hedge order first (BUY) for margin benefit
   - Place main order (SELL)
   - Store order IDs
5. Schedule auto square-off
6. Return position details with order IDs

### 3. Exit Signal or Auto Square-off
```json
{
    "secret": "your-webhook-secret",
    "signal": "S1",
    "action": "EXIT",
    "reason": "stop_loss",
    "timestamp": "2025-01-14T14:15:00"
}
```

## Testing

### Run Integration Test
```bash
python test_kite_integration.py
```

### Test Output (Paper Mode)
```
CHECKING TRADING MODE
[INFO] Trading Mode: PAPER
[INFO] Position created successfully!
[INFO] Paper trading mode - no real orders placed
```

### Test Output (Real Mode)
```
CHECKING TRADING MODE
[INFO] Trading Mode: REAL
[INFO] Position created successfully!
KITE ORDER IDs (REAL TRADING):
  Main Order: 250114000123456
  Hedge Order: 250114000123457
```

## Production Checklist

### Pre-Production
- [ ] Test in paper trading mode
- [ ] Verify symbol generation for current week
- [ ] Verify webhook authentication
- [ ] Test with small lot size (1 lot)
- [ ] Verify margin requirements

### Go-Live Steps
1. **Set Credentials**
   ```bash
   PAPER_TRADING_MODE=false
   KITE_API_KEY=your_actual_api_key
   KITE_ACCESS_TOKEN=fresh_daily_token
   ```

2. **Configure TradingView**
   - Webhook URL: `https://your-domain.com/webhook/entry`
   - Include secret in JSON payload

3. **Start API Server**
   ```bash
   python unified_api_correct.py
   ```

4. **Monitor Logs**
   ```bash
   tail -f logs/trading.log
   ```

### Daily Tasks
- [ ] Generate fresh Kite access token (before 9:15 AM)
- [ ] Update KITE_ACCESS_TOKEN in .env
- [ ] Restart API server to load new token
- [ ] Verify webhook connectivity
- [ ] Check margin availability

## Error Handling

### Paper Trading Fallback
If real order placement fails, the system continues with paper trading to track positions.

### Order Rejection Handling
Common reasons and solutions:
- **Insufficient Margin**: Reduce lot size or add funds
- **Invalid Symbol**: Check expiry date and holiday calendar
- **Market Closed**: Orders only during market hours (9:15 AM - 3:30 PM)
- **Token Expired**: Generate fresh access token

## API Endpoints

### Trading Endpoints
- `POST /webhook/entry` - Entry signal from TradingView
- `POST /webhook/exit` - Exit signal from TradingView
- `GET /api/positions` - Current positions
- `POST /api/square-off/manual` - Manual square-off

### Configuration Endpoints
- `POST /api/expiry/weekday-config` - Set weekday expiry preferences
- `GET /api/expiry/available` - Get available expiries
- `POST /api/exit-timing/configure` - Set exit timing
- `GET /api/square-off/pending` - View pending square-offs

## Security Considerations

1. **Webhook Authentication**: Always verify webhook secret
2. **Access Token Security**: Never commit tokens to git
3. **IP Whitelisting**: Restrict webhook to TradingView IPs
4. **Rate Limiting**: Implement to prevent abuse
5. **Audit Logging**: Log all order placements

## Troubleshooting

### Symbol Not Found
- Verify expiry date is correct trading day
- Check for NSE holidays
- Ensure symbol format matches Kite requirements

### Order Rejected
- Check Kite order rejection reason in response
- Verify margin requirements
- Ensure market is open

### Webhook Not Working
- Verify webhook secret matches
- Check API server is accessible publicly
- Ensure JSON payload format is correct

## Support Files

- `src/services/kite_weekly_options_executor.py` - Kite order execution
- `src/services/expiry_management_service.py` - Expiry calculations
- `unified_api_correct.py` - Main API with webhook handlers
- `test_kite_integration.py` - Integration tests
- `expiry_weekday_config.json` - Weekday configuration storage

## Next Steps

1. **Add Position Monitoring**
   - Real-time P&L tracking
   - Stop-loss monitoring
   - Alert notifications

2. **Enhanced Risk Management**
   - Position size limits
   - Daily loss limits
   - Exposure limits

3. **Order Management**
   - Modify orders
   - Partial fills handling
   - Order status tracking

## Contact & Support

For issues or questions about the Kite integration:
1. Check logs in `logs/trading.log`
2. Run test script: `python test_kite_integration.py`
3. Verify environment variables are set correctly
4. Ensure Kite access token is fresh (regenerate daily)