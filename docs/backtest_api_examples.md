# Backtest API Documentation - Enhanced with Date Queries

This document shows examples of the enhanced backtest API that supports both backtest ID and date-based queries.

## Key Features

1. **No need to remember backtest IDs** - Query by date range instead
2. **Detailed zone information** - See exact support/resistance zones when trades were triggered
3. **Complete market context** - Understand market bias and conditions
4. **Signal trigger details** - Know exactly why each signal fired

## API Endpoints

### 1. Get Backtest Results

#### Query by Backtest ID (Original)
```http
GET /api/v2/backtest/results?backtest_id=abc123
```

#### Query by Date Range (New)
```http
GET /api/v2/backtest/results?from_date=2024-01-01&to_date=2024-01-31
```

**Response for Date Range Query:**
```json
{
  "query": {
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "backtest_count": 3
  },
  "aggregated_results": {
    "total_trades": 45,
    "winning_trades": 28,
    "losing_trades": 17,
    "win_rate": 62.22,
    "total_pnl": 125000
  },
  "backtests": [
    {
      "backtest_id": "abc123",
      "from_date": "2024-01-01T00:00:00",
      "to_date": "2024-01-15T23:59:59",
      "total_trades": 20,
      "win_rate": 65.0,
      "total_pnl": 75000
    },
    {
      "backtest_id": "def456",
      "from_date": "2024-01-16T00:00:00",
      "to_date": "2024-01-31T23:59:59",
      "total_trades": 25,
      "win_rate": 60.0,
      "total_pnl": 50000
    }
  ]
}
```

### 2. Get Trades with Full Details

#### Query Today's Trades (Convenience Endpoint)
```http
GET /api/v2/backtest/today?signal_type=S1
```

#### Query by Date Range
```http
GET /api/v2/backtest/trades?from_date=2024-01-24&to_date=2024-01-24&include_zones=true
```

**Enhanced Response with Zone Information:**
```json
{
  "total_trades": 2,
  "query": {
    "from_date": "2024-01-24",
    "to_date": "2024-01-24",
    "signal_type": null,
    "outcome": null
  },
  "trades": [
    {
      "trade_id": "abc123",
      "backtest_id": "run1",
      "week_start_date": "2024-01-22T09:15:00",
      "signal_type": "S1",
      "direction": "BULLISH",
      "entry_time": "2024-01-24T10:30:00",
      "exit_time": "2024-01-24T14:30:00",
      "exit_reason": "Stop Loss Hit",
      "index_price_at_entry": 23500,
      "index_price_at_exit": 23400,
      "stop_loss_price": 23400,
      "total_pnl": -52875,
      "outcome": "LOSS",
      "zones": {
        "resistance_zone_top": 23650,
        "resistance_zone_bottom": 23600,
        "support_zone_top": 23350,
        "support_zone_bottom": 23300,
        "margin_high": 0.0025,
        "margin_low": 0.0025
      },
      "market_context": {
        "bias": "BULLISH",
        "bias_strength": 0.75,
        "distance_to_resistance": 0.0064,
        "distance_to_support": 0.0064,
        "weekly_max_high": 23550,
        "weekly_min_low": 23320
      },
      "signal_trigger": {
        "trigger_condition": "Bear Trap - Fake breakdown below support that recovers",
        "first_bar_open": 23340,
        "first_bar_close": 23280,
        "first_bar_high": 23360,
        "first_bar_low": 23270,
        "signal_bar_close": 23500
      },
      "positions": [
        {
          "position_type": "MAIN",
          "option_type": "PE",
          "strike_price": 23400,
          "entry_price": 250.50,
          "exit_price": 180.00,
          "quantity": -750,
          "lots": 10,
          "net_pnl": -52875
        },
        {
          "position_type": "HEDGE",
          "option_type": "PE",
          "strike_price": 22900,
          "entry_price": 120.00,
          "exit_price": 150.00,
          "quantity": 750,
          "lots": 10,
          "net_pnl": 22500
        }
      ]
    },
    {
      "trade_id": "def456",
      "backtest_id": "run1",
      "week_start_date": "2024-01-22T09:15:00",
      "signal_type": "S3",
      "direction": "BEARISH",
      "entry_time": "2024-01-24T11:15:00",
      "exit_time": "2024-01-25T15:15:00",
      "exit_reason": "Weekly Expiry",
      "index_price_at_entry": 23580,
      "index_price_at_exit": 23450,
      "stop_loss_price": 23650,
      "total_pnl": 75000,
      "outcome": "WIN",
      "zones": {
        "resistance_zone_top": 23650,
        "resistance_zone_bottom": 23600,
        "support_zone_top": 23350,
        "support_zone_bottom": 23300,
        "margin_high": 0.0025,
        "margin_low": 0.0025
      },
      "market_context": {
        "bias": "BEARISH",
        "bias_strength": 0.80,
        "distance_to_resistance": -0.0030,
        "distance_to_support": 0.0098,
        "weekly_max_high": 23620,
        "weekly_min_low": 23320
      },
      "signal_trigger": {
        "trigger_condition": "Resistance Hold - Price fails at resistance with bearish bias",
        "first_bar_open": 23590,
        "first_bar_close": 23570,
        "first_bar_high": 23610,
        "first_bar_low": 23560,
        "signal_bar_close": 23580
      },
      "positions": [
        {
          "position_type": "MAIN",
          "option_type": "CE",
          "strike_price": 23600,
          "entry_price": 280.00,
          "exit_price": 150.00,
          "quantity": -750,
          "lots": 10,
          "net_pnl": 97500
        },
        {
          "position_type": "HEDGE",
          "option_type": "CE",
          "strike_price": 24100,
          "entry_price": 100.00,
          "exit_price": 50.00,
          "quantity": 750,
          "lots": 10,
          "net_pnl": -37500
        }
      ]
    }
  ],
  "pagination": {
    "limit": 100,
    "offset": 0,
    "has_more": false
  }
}
```

### 3. Get Signal Performance

#### By Date Range
```http
GET /api/v2/backtest/signal-performance?from_date=2024-01-01&to_date=2024-01-31
```

**Response:**
```json
{
  "signal_performance": [
    {
      "signal_type": "S3",
      "total_trades": 12,
      "winning_trades": 9,
      "losing_trades": 3,
      "win_rate": 75.0,
      "total_pnl": 180000,
      "avg_pnl_per_trade": 15000,
      "best_trade_pnl": 45000,
      "worst_trade_pnl": -15000
    },
    {
      "signal_type": "S1",
      "total_trades": 10,
      "winning_trades": 6,
      "losing_trades": 4,
      "win_rate": 60.0,
      "total_pnl": 120000,
      "avg_pnl_per_trade": 12000,
      "best_trade_pnl": 35000,
      "worst_trade_pnl": -20000
    }
  ]
}
```

### 4. Get Daily P&L

#### By Date Range
```http
GET /api/v2/backtest/daily-pnl?from_date=2024-01-01&to_date=2024-01-07
```

**Response:**
```json
{
  "daily_pnl": [
    {
      "date": "2024-01-01",
      "starting_capital": 500000,
      "ending_capital": 515000,
      "daily_pnl": 15000,
      "daily_return_percent": 3.0,
      "trades_opened": 2,
      "trades_closed": 1,
      "open_positions": 1
    },
    {
      "date": "2024-01-02",
      "starting_capital": 515000,
      "ending_capital": 508000,
      "daily_pnl": -7000,
      "daily_return_percent": -1.36,
      "trades_opened": 1,
      "trades_closed": 2,
      "open_positions": 0
    }
  ]
}
```

### 5. Get Latest Backtest

```http
GET /api/v2/backtest/latest
```

Returns the most recent completed backtest with full details.

## Understanding the Response Fields

### Zone Information
- **resistance_zone_top/bottom**: The upper price zone where selling pressure is expected
- **support_zone_top/bottom**: The lower price zone where buying pressure is expected
- **margin_high/low**: The margin percentage used for proximity calculations

### Market Context
- **bias**: Overall market direction (BULLISH/BEARISH)
- **bias_strength**: How strong the bias is (0.0 to 1.0)
- **distance_to_resistance**: How far current price is from resistance (negative if above)
- **distance_to_support**: How far current price is from support
- **weekly_max_high/min_low**: The weekly extremes before the signal

### Signal Trigger
- **trigger_condition**: Human-readable description of why the signal fired
- **first_bar_***: OHLC data of the first hourly bar of the week
- **signal_bar_close**: The closing price when the signal was triggered

### Position Details
- **position_type**: MAIN (primary position) or HEDGE (protective position)
- **option_type**: CE (Call) or PE (Put)
- **strike_price**: The strike price of the option
- **quantity**: Number of contracts (negative for sell positions)
- **lots**: Number of lots (NIFTY lot size = 75)
- **net_pnl**: Net profit/loss after commissions

## Examples of Common Queries

### 1. "Show me all S1 trades from last week"
```http
GET /api/v2/backtest/trades?from_date=2024-01-15&to_date=2024-01-21&signal_type=S1
```

### 2. "What were my winning trades today?"
```http
GET /api/v2/backtest/trades?from_date=2024-01-24&to_date=2024-01-24&outcome=WIN
```

### 3. "Show signal performance for this month"
```http
GET /api/v2/backtest/signal-performance?from_date=2024-01-01&to_date=2024-01-31
```

### 4. "Get daily P&L for the current week"
```http
GET /api/v2/backtest/daily-pnl?from_date=2024-01-22&to_date=2024-01-28
```

## Running a New Backtest

```http
POST /api/v2/backtest/run
Content-Type: application/json

{
  "from_date": "2024-01-01",
  "to_date": "2024-01-31",
  "initial_capital": 500000,
  "lot_size": 75,
  "lots_to_trade": 10,
  "signals_to_test": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
  "use_hedging": true,
  "hedge_offset": 500,
  "commission_per_lot": 40,
  "slippage_percent": 0.001
}
```

**Response:**
```json
{
  "success": true,
  "backtest_id": "abc123",
  "message": "Backtest started successfully",
  "status_url": "/api/v2/backtest/status/abc123",
  "results_url": "/api/v2/backtest/results/abc123"
}
```

## Benefits of the Enhanced API

1. **No ID Management**: Query trades by date range without remembering backtest IDs
2. **Complete Context**: See exact market conditions when each trade was taken
3. **Zone Visualization**: Understand support/resistance levels at trade entry
4. **Signal Analysis**: Know precisely why each signal triggered
5. **Flexible Queries**: Mix and match date ranges, signal types, and outcomes
6. **Convenience Endpoints**: Quick access to latest results and today's trades

## Migration Note

To use the enhanced features, run the migration script:
```bash
python run_migration.py
```

This will add the necessary columns to store zone and context information.