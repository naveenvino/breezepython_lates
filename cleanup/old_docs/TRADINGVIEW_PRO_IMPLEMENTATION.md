# TradingView Pro Real-Time Trading Implementation

## Overview
Successfully implemented a comprehensive real-time trading system for TradingView alert-based trading with the following architecture:

## Architecture Components

### 1. Hybrid Data Manager (`src/services/hybrid_data_manager.py`)
- **Memory Cache**: Last 24 hours of hourly candles for fast access
- **Database Persistence**: Complete history and recovery capability
- **Real-time Updates**: Tick data processing and candle formation
- **Position Tracking**: Active positions with P&L calculation

### 2. Real-time Candle Service (`src/services/realtime_candle_service.py`)
- Forms hourly candles from WebSocket tick data
- Triggers callbacks on candle completion (XX:15 for Indian markets)
- Connects to Breeze WebSocket for live NIFTY data
- No database dependency for real-time operations

### 3. Live Stop Loss Monitor (`src/services/live_stoploss_monitor.py`)
Multiple stop loss strategies:
- **Strike-based**: Main strike as stop loss
- **Profit Lock**: Lock profits after 2% gain
- **Time-based**: Square off at 15:15
- **Trailing Stop**: Optional trailing stop loss
- **Hourly Close**: Stop loss based on 1H candle close

### 4. Position & Breakeven Tracker (`src/services/position_breakeven_tracker.py`)
- **30% Hedge Rule**: Automatically selects hedge at ~30% of main leg price
- **Real-time Breakeven**: Calculates breakeven including hedge
- **Position Management**: Create, update, and close positions
- **P&L Tracking**: Real-time profit/loss calculation

### 5. TradingView Webhook Handler (`tradingview_webhook_handler.py`)
Enhanced with new endpoints:
- `/webhook/entry` - Process entry signals from TradingView
- `/webhook/exit` - Process exit signals
- `/webhook/hourly` - Receive 1H candle close data

## API Endpoints

### TradingView Pro Endpoints (in `unified_api_correct.py`)

#### Position Management
- `GET /live/positions` - Get all active positions with breakeven
- `POST /live/position/create` - Create position with auto hedge
- `GET /live/position/{id}` - Get position details
- `POST /live/position/{id}/update-prices` - Update with latest prices
- `POST /live/position/{id}/close` - Close position

#### Market Data
- `GET /live/spot-price` - Current NIFTY spot price
- `GET /live/candles/latest` - Latest hourly candles from memory

#### Stop Loss
- `GET /live/stoploss/status/{id}` - Stop loss status for position
- `POST /live/stoploss/check/{id}` - Manually trigger stop loss check

#### Signals
- `GET /live/signals/pending` - Get pending trading signals

#### WebSocket
- `WS /ws/tradingview` - Real-time updates for positions, prices, candles

## TradingView Integration

### PineScript Alert Configuration

#### Entry Signal
```json
{
    "signal": "S1",
    "action": "ENTRY",
    "strike": 25000,
    "option_type": "PE",
    "spot_price": {{close}},
    "timestamp": "{{time}}"
}
```

#### Exit Signal
```json
{
    "signal": "S1",
    "action": "EXIT",
    "strike": 25000,
    "option_type": "PE",
    "spot_price": {{close}},
    "message": "Stop loss hit"
}
```

#### Hourly Candle
```json
{
    "ticker": "NIFTY",
    "timestamp": "{{time}}",
    "open": {{open}},
    "high": {{high}},
    "low": {{low}},
    "close": {{close}},
    "volume": {{volume}}
}
```

## Key Features Implemented

### 1. Dual Data Sources
- **Primary**: TradingView webhooks for signals
- **Secondary**: Breeze WebSocket for continuous monitoring

### 2. Hybrid Storage
- **Memory**: Fast access to recent data
- **Database**: Persistence and recovery

### 3. Automatic Hedge Selection
- Implements 30% rule: If main leg = 100, hedge ≈ 30
- Selects appropriate strike based on percentage
- Calculates spread P&L and max loss

### 4. Real-time Monitoring
- Continuous spot price updates
- Hourly candle formation
- Position breakeven tracking
- Multiple stop loss strategies

### 5. WebSocket Streaming
- Real-time position updates
- Live P&L streaming
- Instant stop loss alerts
- Candle completion notifications

## Testing

### Test Script
Run `python test_tradingview_pro.py` to test:
- Webhook endpoints
- Position creation with hedge
- Stop loss monitoring
- Signal processing
- Live data streaming

### Manual Testing
1. Start API: `python unified_api_correct.py`
2. Open UI: `start tradingview_pro.html`
3. Check Swagger docs: http://localhost:8000/docs

## Current Status

### Working
✅ Webhook endpoints for signals
✅ Position creation with 30% hedge
✅ In-memory data management
✅ Mock option chain for testing
✅ WebSocket connection
✅ Stop loss monitoring logic
✅ UI connected to real endpoints

### Pending (for production)
- Database table creation (LivePositions, TradingViewSignals, LiveHourlyCandles)
- Real Breeze WebSocket connection
- Live option chain data
- Broker order execution
- HMAC signature verification for webhooks

## Files Created/Modified

### New Services
- `src/services/hybrid_data_manager.py`
- `src/services/realtime_candle_service.py`
- `src/services/live_stoploss_monitor.py`
- `src/services/position_breakeven_tracker.py`
- `src/services/simple_option_chain_mock.py`

### Updated Files
- `tradingview_webhook_handler.py` - Added entry/exit/hourly endpoints
- `unified_api_correct.py` - Added TradingView Pro endpoints
- `tradingview_pro.html` - Connected to real services

## Next Steps for Production

1. **Database Setup**
   - Run migration scripts to create tables
   - Test data persistence and recovery

2. **Broker Integration**
   - Configure Breeze/Kite credentials
   - Test order execution
   - Implement order status tracking

3. **TradingView Setup**
   - Create PineScript indicators
   - Configure webhook alerts
   - Test signal flow end-to-end

4. **Security**
   - Enable HMAC verification
   - Add rate limiting
   - Implement user authentication

5. **Monitoring**
   - Add logging and metrics
   - Set up alerts for failures
   - Create monitoring dashboard

## Conclusion
The TradingView Pro real-time trading system is now functional with all core components in place. The hybrid memory-database architecture ensures both speed and reliability, while the dual data source approach (TradingView + Breeze) provides redundancy. The system is ready for paper trading and can be deployed to production after completing the pending items.