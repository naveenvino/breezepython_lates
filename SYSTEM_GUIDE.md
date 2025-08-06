# BreezeConnect + Kite Trading System Guide

## System Overview
A hybrid trading system using Breeze API for historical data/backtesting and Kite Connect for live trading execution.

## Quick Start

### 1. Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API credentials
```

### 2. Running the System

#### Main API (Port 8000)
```bash
python unified_api_correct.py
```

#### Alternative APIs
```bash
python -m src.api.main          # Clean architecture API
python -m api.data_collection_api  # Data collection (port 8002)
```

## API Endpoints

### Backtesting
- `POST /backtest` - Run backtest with signals
- `GET /backtest/{run_id}` - Get backtest results
- `POST /analyze-week` - Analyze weekly data

### Live Trading
- `POST /live/start-trading` - Enable live trading
- `POST /live/stop-trading` - Disable live trading
- `POST /live/place-signal-order` - Execute signal-based trade
- `GET /live/positions` - Get current positions
- `POST /live/square-off-all` - Close all positions
- `GET /live/pnl` - Get current P&L

### Data Collection
- `POST /collect-missing-strikes` - Collect missing options data
- `POST /collect-weekly-data` - Collect NIFTY weekly data
- `GET /check-data-availability` - Check data status

## Trading Signals (S1-S8)
- **S1**: Bear Trap (Bullish) - Sell PUT
- **S2**: Support Hold (Bullish) - Sell PUT
- **S3**: Resistance Hold (Bearish) - Sell CALL
- **S4**: Bias Failure Bull (Bullish) - Sell PUT
- **S5**: Bias Failure Bear (Bearish) - Sell CALL
- **S6**: Weakness Confirmed (Bearish) - Sell CALL
- **S7**: Breakout Confirmed (Bullish) - Sell PUT
- **S8**: Breakdown Confirmed (Bearish) - Sell CALL

## Trading Rules
- **Entry**: Second candle after signal (11:15 AM)
- **Stop Loss**: Main strike price
- **Position Size**: 10 lots × 75 quantity = 750 total
- **Hedging**: Optional, 200 points offset
- **Square Off**: 3:15 PM on expiry day (Thursday)

## Database Tables
- `BacktestRuns` - Backtest execution metadata
- `BacktestTrades` - Individual trade records
- `NIFTYData_5Min` - 5-minute candle data
- `OptionsData` - Historical options prices
- `LiveTrades` - Live trading records
- `LivePositions` - Current open positions

## Kite Integration

### Daily Authentication
```bash
python scripts/kite/kite_daily_auth.py
```

### Monitor Live Trading
```bash
python scripts/kite/live_trading_monitor.py
```

## Testing

### Quick Test
```bash
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{"from_date": "2025-07-14", "to_date": "2025-07-18", "signals_to_test": ["S1"]}'
```

### Run Tests
```bash
pytest
pytest --cov=src
```

## Environment Variables
```env
# Database
DB_SERVER=(localdb)\mssqllocaldb
DB_NAME=KiteConnectApi

# Breeze API
BREEZE_API_KEY=your_key
BREEZE_API_SECRET=your_secret
BREEZE_API_SESSION=your_session

# Kite API
KITE_API_KEY=your_key
KITE_API_SECRET=your_secret
```

## Support
- Report issues: https://github.com/anthropics/claude-code/issues
- API Documentation: See `/docs` endpoint when API is running