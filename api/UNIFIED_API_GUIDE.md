# Unified Trading API Guide

## 🚀 Quick Start

```bash
# Start the unified API
python -m api.unified_trading_api

# Open browser
http://localhost:8000/docs
```

## 📋 What's Included

The Unified Trading API consolidates all functionality into a single service:

### 1. **Backtest System**
- Both GET and POST methods
- All 8 trading signals (S1-S8)
- Configurable parameters
- Detailed P&L reporting

### 2. **Data Collection**
- NIFTY index data (5-minute and hourly)
- Options historical data with Greeks
- Optimized bulk collection
- Data deletion endpoints

### 3. **Analysis Tools**
- Data availability checker
- Signal information
- Health monitoring

## 🎯 Common Use Cases

### 1. Run a Quick Backtest (Browser-Friendly GET)
```
http://localhost:8000/api/backtest?from_date=2025-07-14&to_date=2025-07-18&signals_to_test=S1
```

### 2. Run Full Backtest (POST with all parameters)
```json
POST http://localhost:8000/api/backtest
{
  "from_date": "2025-07-01",
  "to_date": "2025-07-31", 
  "signals_to_test": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
  "initial_capital": 500000,
  "lot_size": 75,
  "lots_to_trade": 10,
  "use_hedging": true,
  "hedge_offset": 200,
  "commission_per_lot": 40
}
```

### 3. Collect Data Before Backtesting
```json
# First, collect NIFTY data
POST http://localhost:8000/api/collect/nifty
{
  "from_date": "2025-07-01",
  "to_date": "2025-07-31",
  "symbol": "NIFTY"
}

# Then, collect options data
POST http://localhost:8000/api/collect/options
{
  "from_date": "2025-07-01",
  "to_date": "2025-07-31",
  "symbol": "NIFTY",
  "strike_range": 500
}
```

### 4. Check Data Before Running Backtest
```
GET http://localhost:8000/api/data/check?from_date=2025-07-01&to_date=2025-07-31
```

## 🔄 Typical Workflow

1. **Start API**: `python -m api.unified_trading_api`
2. **Check Health**: `GET /health`
3. **Check Data**: `GET /api/data/check`
4. **Collect Data** (if needed): `POST /api/collect/nifty` and `POST /api/collect/options`
5. **Run Backtest**: `POST /api/backtest` or `GET /api/backtest`
6. **Analyze Results**: Check the response JSON

## 📊 Response Format

### Successful Backtest Response:
```json
{
  "status": "success",
  "result": {
    "summary": {
      "from_date": "2025-07-01",
      "to_date": "2025-07-31",
      "initial_capital": 500000.0,
      "final_capital": 512345.50,
      "total_pnl": 12345.50,
      "total_trades": 15,
      "roi_percentage": 2.47
    },
    "signal_summary": {
      "S1": {
        "trades": 5,
        "total_pnl": 5000.0,
        "avg_pnl": 1000.0
      },
      // ... other signals
    },
    "trades": [
      {
        "signal": "S1",
        "entry_time": "2025-07-07 11:15:00",
        "exit_time": "2025-07-10 15:30:00",
        "main_strike": 25000,
        "hedge_strike": 25200,
        "entry_price": 150.5,
        "exit_price": 120.3,
        "pnl": 2265.0,
        "exit_reason": "expiry"
      },
      // ... more trades
    ]
  }
}
```

## 🛠️ Troubleshooting

### Port Already in Use
```bash
# Check what's using port 8000
netstat -ano | findstr :8000

# Kill all Python processes
powershell -Command "Get-Process python | Stop-Process -Force"
```

### Missing Data Error
1. Check data availability: `GET /api/data/check`
2. Collect missing data using the collect endpoints
3. Retry the backtest

### API Not Starting
1. Check `.env` file has correct database and Breeze credentials
2. Ensure SQL Server is running
3. Check Python dependencies: `pip install -r requirements.txt`

## 🔗 API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | API information |
| GET | /docs | Swagger UI |
| GET | /health | Health check |
| POST | /api/backtest | Run backtest (JSON body) |
| GET | /api/backtest | Run backtest (query params) |
| POST | /api/collect/nifty | Collect NIFTY data |
| POST | /api/collect/options | Collect options data |
| DELETE | /api/delete/nifty | Delete NIFTY data |
| DELETE | /api/delete/options | Delete options data |
| GET | /api/signals/available | List all signals |
| GET | /api/data/check | Check data availability |

## 💡 Tips

1. **Use Swagger UI** - It's the easiest way to test endpoints
2. **Start with GET backtest** - Easier to test in browser
3. **Check data first** - Always verify data exists before backtesting
4. **Test one signal first** - Before running all 8 signals
5. **Monitor logs** - Check console output for detailed information