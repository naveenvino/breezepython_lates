# Signals Page - Complete Overview

## What is the Signals Page?

The Signals page displays all 8 trading signals (S1-S8) used by your backtesting system. It shows:

1. **Signal Definitions** - What each signal means
2. **Performance Statistics** - How well each signal performs
3. **Recent Occurrences** - When signals were triggered
4. **Visual Indicators** - Bullish vs Bearish signals

## The 8 Trading Signals

### Bullish Signals (Sell PUT)
- **S1: Bear Trap** - Price breaks below support but quickly reverses
- **S2: Support Hold** - Price tests support but holds above
- **S4: Bias Failure Bull** - Bearish bias fails, price reverses up
- **S7: Breakout Confirmed** - Price breaks above resistance with volume

### Bearish Signals (Sell CALL)
- **S3: Resistance Hold** - Price tests resistance but fails to break
- **S5: Bias Failure Bear** - Bullish bias fails, price reverses down
- **S6: Weakness Confirmed** - Multiple indicators confirm weakness
- **S8: Breakdown Confirmed** - Price breaks below support with volume

## How to Access

1. **From Dashboard**: Click "Signals" in the sidebar
2. **Direct URL**: http://localhost:8000/signals.html

## Features

### 1. Signal Cards
Each signal has a card showing:
- Signal ID (S1-S8)
- Bullish/Bearish indicator
- Signal name and description
- Trading action (Sell PUT or CALL)

### 2. Performance Overview
Top statistics section shows:
- Total signals (8)
- Best performing signal
- Average win rate across all signals
- Total P&L from all signals

### 3. Recent Signals Table
Shows recent signal occurrences with:
- Date & time of signal
- Entry and exit prices
- P&L for each trade
- Current status

### 4. Auto-Refresh
- Page refreshes every 60 seconds
- Manual refresh button available
- Real-time data from database

## API Endpoints

The signals page uses two endpoints:

1. **`GET /signals/statistics`**
   - Returns performance stats for all signals
   - Groups by signal type
   - Calculates win rates and P&L

2. **`GET /signals/recent`**
   - Returns recent signal occurrences
   - Shows last 20 trades by default
   - Includes entry/exit details

## Example API Response

### Statistics
```json
{
  "status": "success",
  "total_signals": 8,
  "best_performer": "S3",
  "avg_win_rate": 87.5,
  "total_pnl": 758562.5,
  "signal_details": [
    {
      "signal": "S3",
      "trades": 7,
      "wins": 7,
      "win_rate": 100.0,
      "total_pnl": 231200.0
    }
  ]
}
```

### Recent Signals
```json
{
  "signals": [
    {
      "signal_type": "S1",
      "datetime": "2025-07-18T11:15:00",
      "entry_price": 25000,
      "exit_price": 25150,
      "pnl": 11250,
      "bias": "bullish",
      "status": "CLOSED"
    }
  ]
}
```

## Visual Design

- **Clean Card Layout** - Each signal in its own card
- **Color Coding**:
  - Green for bullish signals
  - Red for bearish signals
  - Green/Red for positive/negative P&L
- **Glassmorphism Design** - Consistent with dashboard
- **Responsive Grid** - Adapts to screen size

## Use Cases

1. **Learn Signals**: Understand what each signal means
2. **Analyze Performance**: See which signals work best
3. **Review History**: Check recent signal triggers
4. **Strategy Optimization**: Identify profitable signals

## Next Steps

You could enhance the signals page by adding:
- Signal filtering (show only bullish/bearish)
- Date range selection for history
- Detailed signal charts
- Signal correlation analysis
- Export functionality

The Signals page provides a comprehensive view of your trading signals and their performance!