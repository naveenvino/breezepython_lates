# API Cleanup Analysis for unified_api_correct.py

## Summary
- **Total Endpoints**: 281
- **Duplicate Endpoints**: ~40-50
- **Actually Used by UI**: ~60-70

## APIs Actually Used by Frontend

### From tradingview_pro.html:
```
✅ /api/trade-config/save
✅ /api/trade-config/load/default
✅ /webhook/tradingview (webhook URL display)
✅ /webhook/entry
✅ /api/health
✅ /api/webhook/metrics
✅ /api/trading/positions
✅ /api/live/nifty-spot
✅ /api/v1/execute-trade
✅ /api/alerts/config
✅ /api/alerts/test/telegram
✅ /api/alerts/test/email
✅ /api/alerts/stoploss
✅ /api/alerts/history
✅ /api/auto-trade/enable
✅ /api/auto-trade/disable
✅ /api/auto-trade/status
✅ /api/kill-switch/status
✅ /api/kill-switch/trigger
✅ /api/kill-switch/reset
✅ /positions/square-off-all
✅ /api/expiry/available
✅ /api/expiry/weekday-config (GET & POST)
✅ /api/expiry/select
✅ /api/exit-timing/configure
✅ /api/exit-timing/options
✅ /live/execute-signal
✅ /live/positions
✅ /live/auth/status
✅ /live/candles/latest
✅ /option-chain/fast
✅ /signals/statistics
✅ /settings (GET & POST)
✅ /kite/status
✅ /api/order-status/{order_id}
✅ /api/positions/breakeven
✅ /api/breeze/hourly-candle
✅ /api/nifty-1h-close
✅ /api/paper/* (paper trading endpoints)
✅ /server-time
```

### From index_hybrid.html (COMPLETE SCAN):
```
✅ /time/internet (line 2380)
✅ /status/all (line 2501)
✅ /auth/auto-login/status (lines 2580, 2703)
✅ /auth/auto-login/kite (lines 2830, 2871)
✅ /auth/auto-login/breeze (lines 2850, 2872)
✅ /session/validate (lines 2605, 2727)
✅ /system/metrics (line 2992)
✅ /health (line 3048)
✅ /signals/detect (line 3172)
✅ /positions (line 3222)
✅ /orders (line 3268)
✅ /live/pnl (line 3307)
```

## Duplicate Endpoints to Archive

### 1. Trade Configuration (DUPLICATES)
```
KEEP:
✅ /api/trade-config/save (line 9229)
✅ /api/trade-config/load/{config_name} (line 9276)
✅ /api/trade-config/validate (line 9298)
✅ /api/trade-config/list (line 9324)
✅ /api/trade-config/duplicate (line 9342)
✅ /api/trade-config/{config_name} DELETE (line 9361)

ARCHIVE:
❌ /save-trade-config (line 4127) - OLD VERSION
❌ /trade-config GET (line 4178) - OLD VERSION
❌ /save-trade-config (line 9997) - DUPLICATE
❌ /trade-config GET (line 10033) - DUPLICATE
```

### 2. Health/Status (DUPLICATES)
```
KEEP:
✅ /api/health (line 118)

ARCHIVE:
❌ /health (line 1575) - DUPLICATE
```

### 3. Positions (DUPLICATES)
```
KEEP:
✅ /api/positions (line 2415)
✅ /api/trading/positions (line 2431) - Used by UI
✅ /live/positions (line 2403) - Used by UI

ARCHIVE:
❌ /positions (line 2420) - DUPLICATE
```

### 4. Settings (DUPLICATES)
```
KEEP:
✅ /api/settings (line 3872)
✅ /settings (line 3877) - Used by UI

ARCHIVE:
None - Both are used
```

### 5. Root Endpoint (DUPLICATES)
```
KEEP:
✅ / (line 114) - Serves main page

ARCHIVE:
❌ / (line 1560) - DUPLICATE
```

### 6. Signal States
```
ARCHIVE:
❌ /save-signal-states (line 4223) - NOT USED
```

## Endpoints NOT Used by UI (Candidates for Archive)

### Data Collection Endpoints (NOT USED IN UI)
```
❌ /collect/nifty-direct
❌ /collect/nifty-bulk
❌ /collect/options-direct
❌ /collect/options-bulk
❌ /collect/options-specific
❌ /api/v1/collect/options-by-signals
❌ /api/v1/collect/options-by-signals-fast
❌ /api/v1/collect/options-by-signals-optimized
❌ /collect/missing-from-insights
❌ /collect/tradingview
❌ /collect/tradingview-bulk
❌ /api/v1/collect/weekly-data
```

### Data Deletion Endpoints (NOT USED IN UI)
```
❌ /delete/nifty-direct
❌ /delete/options-direct
❌ /delete/all
```

### Holiday Management (NOT USED IN UI)
```
❌ /api/v1/holidays/{year}
❌ /api/v1/holidays/load-defaults
❌ /api/v1/holidays/check/{date}
❌ /api/v1/holidays/trading-days
❌ /api/v1/holidays/load-all-defaults
❌ /api/v1/holidays/fetch-from-nse
```

### ML Endpoints (NOT USED IN UI)
```
❌ /ml/validate
❌ /ml/validate/{validation_id}
❌ /ml/validate/{validation_id}/detailed
❌ /ml/analyze-with-gemini/{validation_id}
❌ /ml/current-metrics
```

### Backtest Endpoints (MAY BE USED)
```
⚠️ /backtest (GET & POST)
⚠️ /backtest/history
⚠️ /backtest/{backtest_id}/details
⚠️ /backtest/progressive-sl
⚠️ /backtest/progressive-sl/{backtest_id}/summary
```

## Recommended Actions

1. **Create Archive Folder**: `archived_endpoints/`
2. **Move duplicates to separate file**: `archived_endpoints/duplicates.py`
3. **Move unused endpoints to**: `archived_endpoints/unused_endpoints.py`
4. **Keep main file clean with only used endpoints**
5. **Add deprecation warnings before archiving**
6. **Test each endpoint removal carefully**

## Statistics After Cleanup
- **Before**: 281 endpoints
- **After**: ~120-150 endpoints (estimated)
- **Archived**: ~130-160 endpoints
- **Improvement**: 45-55% reduction in file size