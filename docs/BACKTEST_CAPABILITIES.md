# Backtest API Capabilities

## Full Feature List

### 1. **Signal Selection**
The API can test any combination of the 8 signals:

- **S1** - Bear Trap (Bullish) - Sell PUT
- **S2** - Support Hold (Bullish) - Sell PUT  
- **S3** - Resistance Hold (Bearish) - Sell CALL
- **S4** - Bias Failure Bull (Bullish) - Sell PUT
- **S5** - Bias Failure Bear (Bearish) - Sell CALL
- **S6** - Weakness Confirmed (Bearish) - Sell CALL
- **S7** - Breakout Confirmed (Bullish) - Sell PUT
- **S8** - Breakdown Confirmed (Bearish) - Sell CALL

### 2. **Flexible Parameters**

#### In Swagger UI (http://localhost:8002/docs):

```
- from_date: Any date (e.g., "2025-01-01")
- to_date: Any date (e.g., "2025-12-31")
- initial_capital: Starting capital (default: 500000)
- lot_size: NIFTY lot size (default: 75)
- lots_to_trade: Number of lots per trade (default: 10)
- use_hedging: Enable/disable hedging (default: true)
- hedge_offset: Points for hedge strike (default: 200)
- commission_per_lot: Brokerage per lot (default: 40)
- signals_to_test: Array of signals (e.g., ["S1", "S2", "S3"])
```

### 3. **Testing Scenarios**

#### Test All Signals:
```json
{
  "from_date": "2025-01-01",
  "to_date": "2025-12-31",
  "signals_to_test": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
}
```

#### Test Only Bullish Signals:
```json
{
  "from_date": "2025-07-01",
  "to_date": "2025-07-31",
  "signals_to_test": ["S1", "S2", "S4", "S7"]
}
```

#### Test Only Bearish Signals:
```json
{
  "from_date": "2025-07-01",
  "to_date": "2025-07-31",
  "signals_to_test": ["S3", "S5", "S6", "S8"]
}
```

#### Test Single Signal:
```json
{
  "from_date": "2025-07-14",
  "to_date": "2025-07-18",
  "signals_to_test": ["S1"]
}
```

### 4. **Key Features Implemented**

1. **Entry Logic**:
   - Signal triggers at candle close
   - Entry at next candle (second candle after signal)

2. **Exit Logic**:
   - Stop Loss = Main Strike Price
   - Exit on stop loss (hourly close below/above strike)
   - Exit on weekly expiry (Thursday 15:30)

3. **Position Sizing**:
   - Configurable lots (default 10)
   - Automatic hedge calculation

4. **P&L Calculation**:
   - Entry/exit prices from actual option data
   - Commission deduction (Rs. 40 per lot)
   - Accurate profit/loss tracking

5. **Risk Management**:
   - One trade per week per signal
   - Automatic position closure on expiry
   - Stop loss based on strike price

### 5. **API Endpoints Available**

#### Backtest POST API (Port 8002):
```
http://localhost:8002/backtest
```
File: `backtest_api_post.py`
Start: `python backtest_api_post.py` or `start_backtest_api_post.bat`

#### Backtest GET API (Port 8001):
```
http://localhost:8001/backtest
```
File: `backtest_api_get.py`
Start: `python backtest_api_get.py` or `start_backtest_api_get.bat`

Both APIs have:
- Swagger UI for easy testing
- All parameters configurable
- Real-time results
- Detailed trade breakdowns

### 6. **Example: Test Full Year**

```python
# Test entire year 2025 with all signals
params = {
    "from_date": "2025-01-01",
    "to_date": "2025-12-31",
    "lot_size": 75,
    "lots_to_trade": 10,
    "signals_to_test": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
    "use_hedging": True,
    "hedge_offset": 200,
    "commission_per_lot": 40
}
```

This will:
- Test all 8 signals throughout 2025
- Show total trades for each signal
- Calculate overall P&L
- Provide detailed breakdown

The backtest is fully functional and ready to test any combination of signals for any time period!