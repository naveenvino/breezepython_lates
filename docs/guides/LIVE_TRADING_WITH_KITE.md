# Live Trading with Kite (Zerodha) - Complete Setup

## System Architecture

Your trading system uses a **hybrid approach**:

```
Historical Data & Backtesting → BREEZE (ICICI Direct)
                    ↓
            Signal Generation
                    ↓
Live Trading Execution → KITE (Zerodha)
```

## Why This Setup?

1. **Breeze** provides excellent historical data for Indian markets
2. **Zerodha Kite** offers superior execution and lower brokerage for live trading
3. Best of both worlds: Quality data + Efficient execution

## Current Configuration

### Breeze (Data Provider)
```env
BREEZE_API_KEY=w5905l77Q7Xb7138$7149Y9R40u0908I
BREEZE_API_SECRET=94%1b#41CZ581035971652r1pN%u72s5
BREEZE_API_SESSION=52547699  # For data fetching
```

### Kite (Live Trading)
```env
KITE_API_KEY=a3vacbrbn3fs98ie
KITE_API_SECRET=zy2zaws481kifjmsv3v6pchu13ng2cbz
KITE_ACCESS_TOKEN=  # Generate daily
```

## Existing Kite Integration

Your codebase already has:

1. **KiteClient** (`src/infrastructure/brokers/kite/kite_client.py`)
   - Order placement
   - Position management
   - Market data access

2. **KiteWebSocketService** (`src/infrastructure/brokers/kite/kite_websocket_service.py`)
   - Real-time price feeds
   - Live position updates

3. **Live Trading Use Cases** (`src/application/use_cases/live_trading/`)
   - Execute signals
   - Manage stop loss
   - Monitor positions

## Daily Setup Process

### 1. Generate Kite Access Token (Every Morning)

```bash
# Run the daily auth script
python scripts/kite_daily_auth.py
```

Or manually:
1. Get login URL: `http://localhost:8000/live/auth/login-url`
2. Login at Zerodha
3. Complete auth: `http://localhost:8000/live/auth/complete?request_token=TOKEN`

### 2. Start Live Trading

```bash
curl -X POST http://localhost:8000/live/start-trading \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "lot_size": 75,
    "num_lots": 10,
    "use_hedging": true,
    "max_positions": 3
  }'
```

## API Endpoints Available

### Authentication
- `GET /live/auth/login-url` - Get Kite login URL
- `POST /live/auth/complete` - Complete authentication
- `GET /live/auth/status` - Check auth status

### Trading Control
- `POST /live/start-trading` - Enable live trading
- `POST /live/stop-trading` - Stop all trading
- `GET /live/status` - Get trading status

### Position Management
- `GET /live/positions` - Get open positions
- `POST /live/close-position/{id}` - Close specific position
- `POST /live/close-all` - Emergency close all

### Order Management
- `POST /live/place-order` - Place manual order
- `GET /live/orders` - Get order history
- `POST /live/cancel-order/{id}` - Cancel pending order

## Live Trading Flow

```
1. Morning Setup
   ↓
2. Generate Kite Token (9:00 AM)
   ↓
3. Start Live Trading (9:15 AM)
   ↓
4. System Monitors Signals (Breeze Data)
   ↓
5. Signal Detected → Place Order (Kite)
   ↓
6. Monitor Position & P&L (Kite WebSocket)
   ↓
7. Exit at Target/Stop/3:15 PM
   ↓
8. End of Day Report
```

## Safety Features

1. **Daily Token Expiry** - Prevents unauthorized access
2. **Max Position Limits** - Controls exposure
3. **Automatic Stop Loss** - Risk management
4. **Emergency Stop** - Close all positions instantly
5. **Capital Limits** - Prevents over-trading

## Testing Live Trading

### Paper Trading Mode
```python
# In unified_api_correct.py, set:
PAPER_TRADING_MODE = True  # Orders logged but not placed
```

### Test Order Placement
```bash
# Test with small quantity first
curl -X POST http://localhost:8000/live/test-order \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "NIFTY25JUL25000PE",
    "quantity": 75,
    "order_type": "MARKET"
  }'
```

## Important Notes

1. **Token Generation**: Kite access token expires daily at 8:00 AM
2. **Market Hours**: System trades from 9:15 AM to 3:15 PM
3. **Wednesday Exit**: Special logic for weekly expiry
4. **Margin Requirements**: Ensure sufficient margin for options selling
5. **Brokerage**: Zerodha charges ₹20 per executed order

## Troubleshooting

### Token Issues
```bash
# Check token status
curl http://localhost:8000/live/auth/status

# If expired, regenerate
python scripts/kite_daily_auth.py
```

### Connection Issues
```bash
# Test Kite connection
curl http://localhost:8000/live/test-connection

# Check WebSocket status
curl http://localhost:8000/live/websocket/status
```

### Order Failures
- Check margin availability
- Verify symbol format (NIFTY25JUL25000PE)
- Ensure market hours (9:15 AM - 3:30 PM)
- Check for trading holidays

## Live Trading Dashboard

Access the live trading UI at:
```
http://localhost:8000/live_trading.html
```

Features:
- Real-time position monitoring
- Live P&L tracking
- Signal execution status
- Emergency controls
- Trading logs

## Risk Warning

⚠️ **IMPORTANT**:
- Always test in paper trading mode first
- Start with minimum quantities
- Monitor positions closely
- Have emergency stop ready
- Never leave system unattended

The system is fully configured to use Zerodha Kite for live trading execution while using Breeze for data and signal generation!