
# PRODUCTION DEPLOYMENT CHECKLIST

## [OK] Pre-Deployment Checks

### 1. Configuration
- [ ] `.env` file configured with real API keys
- [ ] Database connection string updated
- [ ] Telegram bot token configured
- [ ] Risk limits set appropriately

### 2. Broker Setup
- [ ] Breeze/Zerodha API keys active
- [ ] API session token valid
- [ ] Sufficient funds in trading account
- [ ] Margin requirements understood

### 3. Code Verification
- [ ] All production fixes applied
- [ ] Backup of original files created
- [ ] Test environment validated
- [ ] Error handling tested

## Deployment Steps

### 1. Start Backend Services
```bash
# Start the API server
python unified_api_correct.py

# Verify API is running
curl http://localhost:8000/health
```

### 2. Open Trading Dashboard
```bash
# Open in browser
start tradingview_pro.html
```

### 3. Initial Configuration
- Set default lot size (start with 1 for testing)
- Enable/disable hedge protection
- Configure stop loss parameters
- Set risk limits

## Testing Protocol

### Phase 1: Paper Trading (Recommended)
1. Use small position size (1 lot)
2. Test all signal types
3. Verify hedge execution
4. Check stop loss triggers
5. Monitor for 1 full trading day

### Phase 2: Limited Live Trading
1. Start with 1-2 lots max
2. Trade only high-confidence signals (S1, S3)
3. Always use hedge protection
4. Set tight stop losses
5. Monitor actively for 1 week

### Phase 3: Full Production
1. Gradually increase position size
2. Enable all signals
3. Use automated stop loss
4. Regular monitoring

## [WARNING] CRITICAL CHECKS

### Before Each Trade
- [ ] Market hours (9:15 AM - 3:30 PM)
- [ ] Sufficient margin available
- [ ] No existing max position limit
- [ ] Signal is valid and enabled
- [ ] Hedge configuration correct

### During Trading
- [ ] Monitor position P&L
- [ ] Check stop loss triggers
- [ ] Watch for API errors
- [ ] Track order execution
- [ ] Monitor margin usage

### End of Day
- [ ] Square off all positions
- [ ] Review trade log
- [ ] Check daily P&L
- [ ] Backup trade data
- [ ] Plan for next day

## Emergency Procedures

### If API Fails
1. Open broker terminal directly
2. Square off all positions manually
3. Check error logs
4. Restart services

### If Large Loss Occurs
1. Square off all positions immediately
2. Disable auto trading
3. Review what went wrong
4. Adjust risk parameters
5. Paper trade before resuming

### If Network Issues
1. Use mobile app as backup
2. Have broker support number ready
3. Keep backup internet connection
4. Use phone hotspot if needed

## Support Contacts

- Broker Support: [Add number]
- Technical Support: [Add contact]
- Emergency Contact: [Add number]

## Daily Checklist

### Morning (9:00 AM)
- [ ] Check market news
- [ ] Verify API connection
- [ ] Check margin available
- [ ] Review previous day trades
- [ ] Set daily targets

### During Market (9:15 AM - 3:30 PM)
- [ ] Monitor positions
- [ ] Track signals
- [ ] Check stop losses
- [ ] Watch P&L
- [ ] Manage risk

### Evening (After 3:30 PM)
- [ ] Review all trades
- [ ] Calculate daily P&L
- [ ] Update trade journal
- [ ] Plan for tomorrow
- [ ] Backup data

---
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
