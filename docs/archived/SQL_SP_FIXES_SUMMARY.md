# SQL Stored Procedure Fixes Summary

## Key Changes Made to Match Python Backtest Results

### 1. **Week Start Date Calculation**
- **Fixed**: Changed to use Sunday as week start consistently
```sql
DATEADD(day, 1-DATEPART(dw, [timestamp]), CAST([timestamp] AS DATE)) as WeekStartDate
```

### 2. **Strike Price Calculation**
- **Fixed**: Changed from using stop loss as strike to using ATM (At The Money) strike
- **Old**: `ROUND(StopLossPrice / 100, 0) * 100`
- **New**: `ROUND(ft.[close] / 50, 0) * 50` (rounds to nearest 50)

### 3. **Signal Detection Logic**
- **Fixed S1**: Now properly detects the Bear Trap signal on June 2nd
- **Fixed Bias Comparison**: Changed from string comparison to numeric
  - `WeeklyBias = 'Bullish'` → `WeeklyBias = 1`
  - `WeeklyBias = 'Bearish'` → `WeeklyBias = -1`

### 4. **Exit Time Logic**
- **Fixed**: Changed exit logic to match Python behavior
  - Normal days: Exit at next day 9:15 AM
  - Thursday (expiry): Exit at 3:15 PM same day
  - Stop loss hit: Exit at the candle where SL is breached

### 5. **Hedge Strike Direction**
- **Fixed**: Corrected hedge strike calculation
  - For PE (Put) options: Hedge strike = Main strike - offset
  - For CE (Call) options: Hedge strike = Main strike + offset

### 6. **Signal Direction vs Option Type**
- **Fixed**: Properly separated signal direction from option type
  - S1, S2, S4, S7 → BULLISH signals → Sell PUT
  - S3, S5, S6, S8 → BEARISH signals → Sell CALL

### 7. **Bias Display**
- **Fixed**: Returns numeric bias values that can be converted to text
  - 1 → BULL
  - -1 → BEAR
  - 0 → NEUTRAL

### 8. **P&L Calculation**
- **Fixed**: Proper P&L calculation for short option positions
  - Main position (SELL): PnL = (Entry Price - Exit Price) × Quantity
  - Hedge position (BUY): PnL = (Exit Price - Entry Price) × Quantity
  - Total PnL = Main PnL + Hedge PnL - Commission

### 9. **Market Hours Filter**
- **Added**: Filter to only consider market hours (9 AM to 4 PM)
```sql
AND DATEPART(hour, [timestamp]) >= 9 AND DATEPART(hour, [timestamp]) < 16
```

### 10. **S8 Signal Fix**
- **Fixed**: Changed S8 logic to check if upper zone was touched at any point during the week
```sql
AND EXISTS (  
    SELECT 1 FROM HourlyDataWithWeekInfo h2  
    WHERE h2.WeekStartDate = s.WeekStartDate  
    AND h2.[timestamp] <= s.[timestamp]  
    AND h2.[high] >= s.ResistanceZoneBottom  
)
```

## Result
The stored procedure now correctly identifies all 5 trades matching the Python API:
1. S1 on 2025-06-02 (previously missing)
2. S8 on 2025-06-12 (strike price fixed)
3. S7 on 2025-06-16
4. S7 on 2025-06-23
5. S3 on 2025-06-30

The P&L calculations should now also match the Python results when using 200 point hedge offset.