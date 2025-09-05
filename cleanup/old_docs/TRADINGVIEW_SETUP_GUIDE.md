# TradingView Setup Guide for S1-S8 Signals

## Step 1: Add Pine Script to TradingView

1. **Open TradingView** and go to NIFTY chart
2. Click on **"Pine Editor"** at the bottom
3. Copy the entire content from `tradingview_signals_s1_s8.pine`
4. Paste it in the Pine Editor
5. Click **"Add to Chart"**
6. You should see:
   - Support/Resistance lines
   - Signal labels (S1-S8) when triggered
   - Status table in top-right corner

## Step 2: Configure Webhook URL

### For Local Testing:
```
http://localhost:8000/api/v2/webhook/tradingview
```

### For Production (using ngrok):
1. Install ngrok: `choco install ngrok` (or download from ngrok.com)
2. Run: `ngrok http 8000`
3. Use the HTTPS URL provided: `https://xxxxx.ngrok.io/api/v2/webhook/tradingview`

### For Cloud Deployment:
```
https://yourdomain.com/api/v2/webhook/tradingview
```

## Step 3: Create Alerts for Each Signal

For each signal (S1-S8), create an alert:

1. **Right-click on chart** → **"Add Alert"**
2. Configure alert settings:

### Alert Configuration:

**Condition Tab:**
- Condition: `S1-S8 Option Selling Signals`
- Select specific signal (e.g., "S1 Signal")
- Trigger: `Once Per Bar Close`

**Actions Tab:**
- ✅ Webhook URL
- URL: `http://localhost:8000/api/v2/webhook/tradingview`

**Message Tab:**
Use this exact format:
```json
{
  "signal": "S1",
  "action": "SELL_PUT",
  "symbol": "NIFTY",
  "price": "{{close}}",
  "volume": "{{volume}}",
  "time": "{{time}}",
  "quantity": 10
}
```

### Alert Messages for Each Signal:

**S1 - Bear Trap (Sell PUT):**
```json
{"signal":"S1","action":"SELL_PUT","symbol":"NIFTY","price":"{{close}}","quantity":10}
```

**S2 - Support Hold (Sell PUT):**
```json
{"signal":"S2","action":"SELL_PUT","symbol":"NIFTY","price":"{{close}}","quantity":10}
```

**S3 - Resistance Hold (Sell CALL):**
```json
{"signal":"S3","action":"SELL_CALL","symbol":"NIFTY","price":"{{close}}","quantity":10}
```

**S4 - Bias Failure Bull (Sell PUT):**
```json
{"signal":"S4","action":"SELL_PUT","symbol":"NIFTY","price":"{{close}}","quantity":10}
```

**S5 - Bias Failure Bear (Sell CALL):**
```json
{"signal":"S5","action":"SELL_CALL","symbol":"NIFTY","price":"{{close}}","quantity":10}
```

**S6 - Weakness Confirmed (Sell CALL):**
```json
{"signal":"S6","action":"SELL_CALL","symbol":"NIFTY","price":"{{close}}","quantity":10}
```

**S7 - Breakout Confirmed (Sell PUT):**
```json
{"signal":"S7","action":"SELL_PUT","symbol":"NIFTY","price":"{{close}}","quantity":10}
```

**S8 - Breakdown Confirmed (Sell CALL):**
```json
{"signal":"S8","action":"SELL_CALL","symbol":"NIFTY","price":"{{close}}","quantity":10}
```

## Step 4: Test Your Setup

### 1. Start Your Trading System:
```bash
# Terminal 1: Start API
python unified_api_correct.py

# Terminal 2: Monitor logs
tail -f logs/trading.log
```

### 2. Test Webhook Manually:
```bash
curl -X POST http://localhost:8000/api/v2/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{"signal":"S1","action":"SELL_PUT","symbol":"NIFTY","price":"25000","quantity":10}'
```

### 3. Check System Response:
```bash
# Check active signals
curl http://localhost:8000/api/v2/webhook/signals/active

# Check positions
curl http://localhost:8000/api/v2/trading/positions
```

## Step 5: Monitor Signals

### Real-time Monitoring Dashboard:
Open `http://localhost:8000/monitoring_dashboard.html`

### Check Signal Performance:
```bash
# Get signal history
curl http://localhost:8000/api/v2/webhook/signals/history

# Get performance metrics
curl http://localhost:8000/api/v2/performance/analytics
```

## Step 6: Go Live Checklist

Before enabling live trading:

- [ ] Run backtest and identify profitable signals
- [ ] Test all signals in paper mode for 1 week
- [ ] Verify webhook receives alerts correctly
- [ ] Check safety features (kill switch, circuit breaker)
- [ ] Set appropriate position sizes based on capital
- [ ] Configure max daily loss limits
- [ ] Have emergency contact configured
- [ ] Test with 1 lot first

## Troubleshooting

### Alert Not Triggering:
1. Check if market is open (9:15 AM - 3:30 PM)
2. Verify Pine Script is added to chart
3. Check alert is active in TradingView
4. Ensure webhook URL is correct

### Webhook Not Received:
1. Check API is running: `curl http://localhost:8000/api/v2/health`
2. Check firewall settings
3. Use ngrok for external access
4. Check webhook logs: `tail -f logs/webhook.log`

### Order Not Placed:
1. Check paper mode vs live mode
2. Verify broker connection: `curl http://localhost:8000/api/v2/broker/status`
3. Check safety limits not exceeded
4. Review risk management settings

## Signal Optimization Tips

Based on backtest results:

1. **High Win Rate Signals**: Focus on S1, S2, S7 (bullish)
2. **Best Risk-Reward**: S3, S6 (bearish) in down trends
3. **Avoid During**: High volatility (VIX > 20)
4. **Best Times**: 10:00 AM - 2:00 PM
5. **Position Sizing**: Start with 5 lots, scale to 10-15

## Safety Reminders

⚠️ **IMPORTANT**:
- Always start with paper trading
- Never disable safety features
- Keep max daily loss at 2-3% of capital
- Monitor positions actively
- Have broker support number ready
- Test kill switch regularly

## Support

For issues or questions:
1. Check logs: `logs/` directory
2. System health: `http://localhost:8000/api/v2/health`
3. Review this guide
4. Check backtest results before trading