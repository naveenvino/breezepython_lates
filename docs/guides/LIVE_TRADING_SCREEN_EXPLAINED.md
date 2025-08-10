# Live Trading Screen - Complete Guide

## What is the Live Trading Screen?

The Live Trading screen is for **executing real trades in the live market** using your signals. It provides:

1. **Real-time Trading Controls** - Start/Stop/Pause trading
2. **Market Data Monitoring** - Live NIFTY prices and indicators
3. **Position Management** - Track open positions and P&L
4. **Risk Controls** - Stop loss, position limits
5. **Trading Log** - Real-time activity logging

## Key Features

### 1. Trading Configuration (Left Panel)
- **Trading Capital**: Set your available capital
- **Lots per Trade**: Number of lots for each position (default: 10)
- **Max Open Positions**: Limit concurrent positions (default: 3)
- **Stop Loss %**: Automatic stop loss percentage
- **Active Signals**: Choose which signals (S1-S8) to trade

### 2. Trading Controls
- **START**: Begin live trading with selected signals
- **PAUSE**: Temporarily pause signal detection
- **STOP**: Close all positions and stop trading
- **EMERGENCY STOP**: Big red button for immediate exit

### 3. Market Data Display (Center)
Shows real-time:
- **NIFTY Price**: Current index level with % change
- **VIX**: Volatility index
- **PCR**: Put-Call Ratio
- **OI**: Open Interest

### 4. Active Positions Table
Displays all open positions with:
- Entry time and signal
- Strike price and type (CE/PE)
- Entry price vs current price
- Real-time P&L
- Position status

### 5. Trading Log (Right Panel)
Real-time activity log showing:
- Signal detections
- Position entries/exits
- System messages
- Errors and warnings

### 6. Today's Statistics
Live performance metrics:
- Total trades today
- Win rate percentage
- Total P&L
- Active positions count

## How It Works

### Starting Live Trading
1. Configure your settings (capital, lots, signals)
2. Click **START** button
3. System begins monitoring for signals
4. When signal detected → Automatic position entry
5. Positions managed according to rules

### Risk Management
- **Max Positions**: Limits exposure (e.g., max 3 open)
- **Stop Loss**: Automatic exit at loss threshold
- **Emergency Stop**: Instant close all positions
- **Position Sizing**: Fixed lots per trade

### Trading Flow
```
Signal Detection → Entry Validation → Position Entry → Monitor P&L → Exit at Target/Stop
```

## Status Indicators

- **ACTIVE** (Green): Trading is live
- **PAUSED** (Yellow): Trading paused, positions held
- **INACTIVE** (Red): Trading stopped

## Safety Features

### 1. Emergency Stop Button
- Large red button (bottom right)
- Immediately closes ALL positions
- Stops all trading activity
- Requires confirmation

### 2. Position Limits
- Max open positions enforced
- Prevents over-leverage
- Automatic rejection if limit reached

### 3. Capital Management
- Tracks available capital
- Prevents trades beyond capital
- Real-time P&L monitoring

## Current Implementation

**IMPORTANT**: This is currently a **DEMO interface**. For actual live trading, you would need:

1. **Real Breeze API Integration**:
   - Live price feeds
   - Order placement API
   - Position tracking

2. **Signal Detection Service**:
   - Real-time NIFTY data analysis
   - Signal generation logic
   - Alert system

3. **Order Management**:
   - Order placement
   - Order modification
   - Order cancellation

4. **Risk Management System**:
   - Real-time stop loss
   - Position sizing
   - Margin calculations

## API Endpoints Needed

For full functionality, these endpoints would be required:

```python
POST /live-trading/start       # Start live trading
POST /live-trading/stop        # Stop trading
POST /live-trading/pause       # Pause/Resume
GET  /live-trading/positions   # Get open positions
GET  /live-trading/status      # Trading status
POST /live-trading/close/{id}  # Close specific position
GET  /market-data/live         # Live market data
```

## Use Cases

1. **Day Trading**: Execute signals during market hours
2. **Automated Trading**: Hands-free signal execution
3. **Risk Monitoring**: Track positions and P&L
4. **Performance Tracking**: Monitor daily results

## Warning & Disclaimer

⚠️ **IMPORTANT**: 
- This is a DEMO interface for visualization
- Actual live trading requires proper API integration
- Always test thoroughly in paper trading first
- Real money trading involves significant risk
- Ensure proper risk management before live trading

## Access

Navigate to: http://localhost:8000/live_trading.html

Or click "Live Trading" in the dashboard sidebar

## Next Steps

To make this functional for real trading:

1. Integrate Breeze WebSocket for live prices
2. Implement actual order placement API
3. Add real signal detection service
4. Implement proper risk management
5. Add paper trading mode for testing
6. Add order history and trade logs
7. Implement profit target and trailing stop loss

The Live Trading screen provides a professional interface for executing your trading signals in real-time with proper risk controls!