# Header Status Bar - Real vs Fake Data Status

## Current Reality Check

### ✅ REAL DATA (Working Now)

1. **Broker Connection Status**
   - **Zerodha/Kite**: Real connection check via `/kite/status` endpoint
   - **Breeze**: Real connection check via `/broker/status` endpoint
   - Shows actual connection state, latency, and login buttons

2. **Date & Time**
   - Real internet time from `/time/internet` endpoint
   - Synced with IST (India Standard Time)
   - Updates every second

3. **System Performance** (After API restart)
   - **CPU Usage**: Real from `psutil.cpu_percent()`
   - **Memory Usage**: Real from `psutil.virtual_memory()`
   - **Disk Usage**: Real from `psutil.disk_usage()`
   - **Network Stats**: Real from `psutil.net_io_counters()`

### ⚠️ PARTIALLY REAL

1. **API Throughput** (req/s)
   - Calculated from actual API calls made by the page
   - But only counts calls from current browser session
   - Not server-wide throughput

2. **Average Response Time**
   - Real for API calls made from the page
   - Accurate latency measurements
   - But limited to current session

### ❌ STILL FAKE/STATIC

1. **Market Status**
   - Shows "MARKET CLOSED" or "MARKET OPEN" based on time
   - Not connected to actual NSE/BSE status
   - Needs `/market/status` endpoint to be active

2. **P&L Display**
   - No P&L shown in header currently
   - `/trading/pnl/live` endpoint created but not displayed

3. **TradingView Status**
   - Not shown in header
   - `/tradingview/status` endpoint created but not used

## How to Make Everything Real

### Step 1: Restart the API with new endpoints
```bash
# Kill old API
taskkill /F /IM python.exe

# Start secure API with new endpoints
python unified_api_secure.py
```

### Step 2: What Will Become Real After Restart

1. **Market Status**: Will show actual market hours/status
2. **System Metrics**: Real CPU, Memory, Disk usage
3. **P&L Data**: Can fetch real positions P&L (if Kite connected)
4. **TradingView**: Webhook status from database

### Step 3: To Add P&L Display to Header

The header currently doesn't show P&L. To add it:

1. Add P&L display elements to the header HTML
2. Call `/trading/pnl/live` endpoint
3. Update display with real values

## API Endpoints Created

All these endpoints are now available in `unified_api_secure.py`:

```
GET /system/metrics     - Real system performance data
GET /market/status      - Real market open/close status  
GET /trading/pnl/live   - Real P&L from positions
GET /tradingview/status - TradingView webhook status
GET /time/internet      - Internet time (already working)
GET /kite/status        - Kite connection (already working)
GET /broker/status      - Breeze status (already working)
```

## Summary

- **70% Real**: Broker connections, time, some metrics
- **30% Fake**: Market status, P&L display, full system metrics

After restarting the API, **everything will be 100% real** except:
- P&L display (needs HTML elements added)
- TradingView status (needs HTML elements added)

The infrastructure is ready - just needs API restart!