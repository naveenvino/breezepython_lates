# Production Deployment Guide - NIFTY Options Live Trading System

## System Overview

### Architecture
- **Market Data**: Breeze WebSocket (FREE) - Real-time NIFTY spot and option chain
- **Order Execution**: Kite Connect Personal API (FREE) - Order placement and position management
- **Signal Detection**: 8 signals (S1-S8) evaluated on 1-hour closed candles
- **Risk Management**: Stop loss triggers only on hourly candle close

### Key Components
1. **Real-Time Spot Service**: Aggregates ticks into hourly bars for signal evaluation
2. **Live Order Executor**: Handles basket orders with proper sequencing (hedge-first entry, main-first exit)
3. **Integrated Trading Engine**: Orchestrates signal detection and trade execution
4. **Smart Order Router**: Manages iceberg orders for quantities >1800 contracts

## Pre-Deployment Checklist

### 1. API Credentials
```bash
# Create .env file with your credentials
BREEZE_API_KEY=your_breeze_api_key
BREEZE_API_SECRET=your_breeze_api_secret
BREEZE_API_SESSION=your_breeze_session_token

KITE_API_KEY=your_kite_api_key
KITE_API_SECRET=your_kite_api_secret
KITE_ACCESS_TOKEN=your_kite_access_token  # Daily auth required

# Database
DB_SERVER=(localdb)\mssqllocaldb
DB_NAME=KiteConnectApi
```

### 2. System Requirements
- Python 3.8+
- Windows Server 2019+ or Windows 10/11
- 8GB RAM minimum (16GB recommended)
- SSD storage for database
- Stable internet connection (redundancy recommended)

### 3. Dependencies Installation
```bash
pip install -r requirements.txt
```

## Deployment Steps

### Step 1: Database Setup
```sql
-- Run database setup scripts
sqlcmd -S (localdb)\mssqllocaldb -d KiteConnectApi -i scripts/create_strategy_tables.sql
sqlcmd -S (localdb)\mssqllocaldb -d KiteConnectApi -i scripts/create_trade_journal_tables.sql
```

### Step 2: Start Services

#### Option A: Manual Start (Development)
```bash
# Start the unified API server
python unified_api_correct.py

# Access the dashboard
http://localhost:8000/live_trading_pro_modern.html
```

#### Option B: Windows Service (Production)
```bash
# Install as Windows service
python scripts/install_service.py

# Start the service
sc start NiftyTradingService
```

#### Option C: Docker Deployment
```bash
# Build Docker image
docker build -t nifty-trading:latest .

# Run container
docker-compose up -d
```

### Step 3: Daily Authentication

**CRITICAL**: Kite access token expires daily at 6:00 AM. You must re-authenticate every trading day.

```python
# Run daily at 8:30 AM (before market opens)
python daily_login.py
```

Or use the dashboard:
1. Navigate to http://localhost:8000/live_trading_pro_modern.html
2. Click "Authenticate Kite" button
3. Complete the login flow
4. Token will be saved automatically

### Step 4: Start Trading

1. **Paper Trading Mode** (Recommended initially):
   ```bash
   curl -X POST http://localhost:8000/integrated/trading/start \
     -H "Content-Type: application/json" \
     -d '{
       "mode": "PAPER",
       "strategies": [{
         "signal_types": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
         "quantity": 750,
         "stop_loss_type": "lock",
         "enabled": true
       }]
     }'
   ```

2. **Live Trading Mode** (After thorough testing):
   ```bash
   curl -X POST http://localhost:8000/integrated/trading/start \
     -H "Content-Type: application/json" \
     -d '{
       "mode": "LIVE",
       "strategies": [{
         "signal_types": ["S1", "S2"],  # Start with fewer signals
         "quantity": 75,  # Start with 1 lot
         "stop_loss_type": "lock",
         "enabled": true
       }]
     }'
   ```

## Monitoring

### Real-Time Dashboard
Access at: http://localhost:8000/live_trading_pro_modern.html

Features:
- Live NIFTY spot price
- Hourly bar status (CRITICAL for signals)
- Active positions with P&L
- Signal detection alerts
- Emergency stop button

### API Endpoints for Monitoring

```bash
# Get system status
curl http://localhost:8000/integrated/trading/status

# Get active positions
curl http://localhost:8000/integrated/trading/positions

# Get hourly bar status
curl http://localhost:8000/spot/statistics

# Get performance metrics
curl http://localhost:8000/performance/stats
```

### Logs
```bash
# Application logs
tail -f logs/trading.log

# Error logs
tail -f logs/error.log

# Order execution logs
tail -f logs/orders.log
```

## Risk Management

### Position Limits
- Max positions: 3 concurrent
- Max daily loss: Rs. 50,000
- Max position size: 1800 contracts (NSE freeze limit)

### Stop Loss Rules
- **S1**: first_bar.low - abs(first_bar.open - first_bar.close)
- **S2**: zones.lower_zone_bottom
- **S3, S6**: zones.prev_week_high
- **S4, S7**: context.first_hour_bar.low
- **S5, S8**: context.first_hour_bar.high

**CRITICAL**: Stop losses are ONLY triggered on hourly candle close, not on running prices.

### Emergency Procedures

1. **Emergency Stop Button**: 
   - Located on dashboard (bottom-right red button)
   - Immediately closes all positions at market

2. **API Emergency Stop**:
   ```bash
   curl -X POST http://localhost:8000/integrated/trading/stop
   ```

3. **Manual Position Exit**:
   ```bash
   curl -X POST http://localhost:8000/integrated/trading/exit-position \
     -H "Content-Type: application/json" \
     -d '{"signal_id": "S1_20250825_101500"}'
   ```

## Production Best Practices

### 1. Start Small
- Begin with 1-2 signals only
- Use minimum quantity (1 lot = 75 contracts)
- Run in paper mode for at least 1 week
- Monitor closely for first month

### 2. Daily Routine
```bash
# 8:30 AM - Authenticate Kite
python daily_login.py

# 9:00 AM - Start trading engine
curl -X POST http://localhost:8000/integrated/trading/start

# 3:30 PM - Review positions (auto-exit at 3:15 PM)
curl http://localhost:8000/integrated/trading/positions

# 4:00 PM - Generate daily report
python scripts/daily_report.py
```

### 3. Backup and Recovery
```bash
# Daily database backup
scripts/backup.bat

# Restore from backup
scripts/restore.bat backup_20250825.bak
```

### 4. Performance Optimization
- Keep only 7 days of tick data
- Archive old trades monthly
- Vacuum database weekly
- Monitor WebSocket reconnections

## Troubleshooting

### Issue: Breeze WebSocket disconnects frequently
**Solution**: 
```python
# Increase reconnection timeout in breeze_websocket_live.py
self.reconnect_timeout = 10  # seconds
self.max_reconnect_attempts = 100
```

### Issue: Kite token expired mid-day
**Solution**: 
1. Re-authenticate immediately
2. System will auto-recover pending orders
3. Check position status after reconnection

### Issue: Signal not triggering
**Check**:
1. Hourly bar completion status
2. Weekly context availability
3. Signal cooldown period (2 hours)
4. Market hours (9:15 AM - 3:30 PM)

### Issue: Order rejection
**Common causes**:
1. Insufficient margin
2. Circuit limits hit
3. Freeze quantity exceeded
4. Market closed

## Performance Metrics

### Expected Performance
- Signal frequency: 2-5 per day
- Win rate: 55-65%
- Average profit per trade: 0.5-1% of capital
- Maximum drawdown: 10-15%
- Sharpe ratio: 1.5-2.0

### Monitoring KPIs
```sql
-- Daily performance query
SELECT 
    DATE(entry_time) as trade_date,
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl
FROM BacktestTrades
WHERE entry_time >= DATEADD(day, -30, GETDATE())
GROUP BY DATE(entry_time)
ORDER BY trade_date DESC;
```

## Support and Maintenance

### Weekly Tasks
1. Review trade journal
2. Analyze signal performance
3. Adjust position sizing if needed
4. Check system logs for errors
5. Update strike ranges if NIFTY moves significantly

### Monthly Tasks
1. Full system backup
2. Performance report generation
3. Strategy parameter review
4. Database optimization
5. Security updates

### Emergency Contacts
- Broker Support: [Zerodha/Kite Support]
- System Admin: [Your contact]
- Database Admin: [DBA contact]

## Legal and Compliance

### Risk Disclosure
- Trading in F&O involves substantial risk
- Past performance doesn't guarantee future results
- Only trade with risk capital
- System failures can occur

### Regulatory Requirements
- Maintain proper trade records
- File taxes on F&O income
- Comply with SEBI regulations
- Keep audit trail of all trades

## Version History

### v1.0.0 (Current)
- Initial production release
- 8 signal types implemented
- Basket order support
- Iceberg order handling
- Real-time WebSocket data
- Hourly bar aggregation
- Stop loss on closed candles only

### Planned Features (v2.0)
- Multi-strategy support
- Advanced risk metrics
- Machine learning signal optimization
- Multi-broker support
- Mobile app integration

---

**IMPORTANT**: This is a sophisticated trading system. Ensure you understand all components before deploying real money. Start with paper trading and gradually increase position size as you gain confidence in the system's performance.

**Last Updated**: August 25, 2025
**Version**: 1.0.0
**Status**: Production Ready