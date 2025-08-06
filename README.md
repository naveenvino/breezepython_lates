# BreezeConnect + Kite Hybrid Trading System

A comprehensive trading platform using Breeze API for historical data/backtesting and Kite Connect for live trading execution, built with Clean Architecture principles.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```env
# Database
DB_SERVER=(localdb)\mssqllocaldb
DB_NAME=KiteConnectApi

# Breeze API (Historical Data & Backtesting)
BREEZE_API_KEY=your_api_key
BREEZE_API_SECRET=your_api_secret
BREEZE_SESSION_TOKEN=your_session_token

# Kite API (Live Trading)
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
```

### 3. Available APIs

#### Unified Trading API (Recommended) - Port 8000
```bash
# Start the unified API with all features
python unified_api_correct.py

# Access at http://localhost:8000/docs
```

This consolidated API includes:
- ✅ Backtest (both GET and POST methods)
- ✅ Data Collection (NIFTY and Options)
- ✅ Live Trading (Kite Integration)
- ✅ Signal Analysis
- ✅ Position Management
- ✅ Health Checks

#### Alternative APIs (in api/ folder)
If you prefer to use individual APIs:
```bash
# Main Clean Architecture API
python -m src.api.main

# Data Collection API
python -m api.data_collection_api

# Backtest POST API
python -m api.backtest_api_post

# Backtest GET API  
python -m api.backtest_api_get
```

## 📁 Project Structure

```
breezepython/
├── src/                          # Clean architecture source code
│   ├── domain/                   # Core business logic
│   ├── application/              # Use cases and DTOs
│   ├── infrastructure/           # External services, database
│   └── api/                      # FastAPI routes
├── api/                          # All API modules
│   ├── unified_trading_api.py    # 🆕 Complete unified API (recommended)
│   ├── data_collection_api.py    # NIFTY & options data collection
│   ├── backtest_api_post.py      # POST endpoint backtest
│   ├── backtest_api_get.py       # GET endpoint backtest
│   └── optimizations/            # Performance optimization modules
├── api_backup_20250728/          # Backup of original APIs
├── scripts/                      # Utility scripts
├── docs/                         # Documentation
└── tests/                        # Test suite
```

## 🛠️ Key Features

### 1. Hybrid Trading System
- **Breeze API**: Historical data download and backtesting
- **Kite Connect**: Live trading execution and order management
- **Automatic Square-off**: 3:15 PM on expiry day (Thursday)
- **Position Sizing**: 10 lots × 75 quantity = 750 total

### 2. Data Collection & Backtest
- **NIFTY Index Data**: 5-minute and hourly candles
- **Options Data**: Historical options prices with Greeks
- **8 Trading Signals**: S1-S8 with customizable parameters
- **Performance Metrics**: Detailed P&L analysis

### 3. Live Trading Features
- **Signal-based Orders**: Automatic order placement on signals
- **Stop Loss Management**: Dynamic stop loss tracking
- **Position Monitoring**: Real-time P&L tracking
- **WebSocket Streaming**: Live market data updates

### 4. Clean Architecture
- **Domain Layer**: Pure business logic
- **Application Layer**: Use cases orchestration
- **Infrastructure Layer**: External integrations
- **Dependency Injection**: Loose coupling

## 📚 API Documentation - Unified API

All endpoints are available at `http://localhost:8000` when running the unified API.

### Backtest Endpoints

#### Run Backtest (POST) - Recommended
```bash
POST http://localhost:8000/api/backtest
{
  "from_date": "2025-07-01",
  "to_date": "2025-07-31",
  "signals_to_test": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
  "lot_size": 75,
  "lots_to_trade": 10,
  "initial_capital": 500000,
  "use_hedging": true,
  "hedge_offset": 200,
  "commission_per_lot": 40
}
```

#### Run Backtest (GET) - Quick Testing
```bash
GET http://localhost:8000/api/backtest?from_date=2025-07-01&to_date=2025-07-31&signals_to_test=S1,S2,S3
```

### Data Collection Endpoints

#### Collect NIFTY Data
```bash
POST http://localhost:8000/api/collect/nifty
{
  "from_date": "2025-01-01",
  "to_date": "2025-01-31",
  "symbol": "NIFTY",
  "force_refresh": false
}
```

#### Collect Options Data
```bash
POST http://localhost:8000/api/collect/options
{
  "from_date": "2025-01-01", 
  "to_date": "2025-01-31",
  "symbol": "NIFTY",
  "strike_range": 500,
  "use_optimization": true
}
```

### Analysis Endpoints

#### Check Data Availability
```bash
GET http://localhost:8000/api/data/check?from_date=2025-07-01&to_date=2025-07-31&symbol=NIFTY
```

#### Get Available Signals
```bash
GET http://localhost:8000/api/signals/available
```

## 🧪 Testing

### Test Backtest System
```python
# Test all 8 signals for a specific period
python backtest_api_post.py
# Navigate to http://localhost:8002/docs
# Use the /backtest endpoint with desired parameters
```

### Test Data Collection
```python
# Start the data collection API
python -m api.data_collection_api
# Navigate to http://localhost:8002/docs
# Use /collect/nifty or /collect/options endpoints
```

## 📊 Trading Signals

- **S1** - Bear Trap (Bullish) - Sell PUT
- **S2** - Support Hold (Bullish) - Sell PUT
- **S3** - Resistance Hold (Bearish) - Sell CALL
- **S4** - Bias Failure Bull (Bullish) - Sell PUT
- **S5** - Bias Failure Bear (Bearish) - Sell CALL
- **S6** - Weakness Confirmed (Bearish) - Sell CALL
- **S7** - Breakout Confirmed (Bullish) - Sell PUT
- **S8** - Breakdown Confirmed (Bearish) - Sell CALL

## 🔧 Configuration

### Database Settings
Configure in `src/config/settings.py` or via environment variables:
```python
DB_SERVER = os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')
DB_NAME = os.getenv('DB_NAME', 'KiteConnectApi')
```

### API Settings
```python
# Port configuration
MAIN_API_PORT = 8000
DATA_COLLECTION_PORT = 8002
BACKTEST_GET_PORT = 8001
```

## 📈 Performance Optimizations

- **Parallel Processing**: Multi-threaded data collection
- **Smart Caching**: Reduces redundant API calls
- **Bulk Operations**: Efficient database inserts
- **Connection Pooling**: Optimized database connections

## 🐛 Troubleshooting

1. **API Key Issues**: Ensure Breeze API credentials are correct in `.env`
2. **Database Connection**: Check SQL Server is running and accessible
3. **Port Conflicts**: Ensure ports 8000, 8001, 8002 are available
4. **Missing Data**: Run data collection before backtesting

## 🚀 Live Trading Setup

### Daily Kite Authentication
```bash
python scripts/kite/kite_daily_auth.py
```

### Monitor Live Trading
```bash
python scripts/kite/live_trading_monitor.py
```

### API Manager
```bash
# Interactive menu
api_manager.bat

# Direct commands
api_manager.bat start
api_manager.bat stop
api_manager.bat restart
api_manager.bat test
api_manager.bat status
```

## 📞 Support

For detailed information:
- See `SYSTEM_GUIDE.md` for complete system documentation
- Check `docs/` folder for additional documentation
- Review API documentation at `/docs` endpoints
- Report issues at https://github.com/anthropics/claude-code/issues