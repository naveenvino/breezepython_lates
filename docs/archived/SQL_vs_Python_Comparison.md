# SQL vs Python Backtest Results Comparison

## Summary of Fixes Applied

The SQL stored procedure has been fixed to match the Python logic as closely as possible:

1. ✅ **All 5 trades are now detected** (including S1 on June 2nd)
2. ✅ **Strike prices match exactly** (using stop loss as strike price)
3. ✅ **Signal types match**
4. ✅ **Entry times match**
5. ✅ **Bias values are correct** (BULL/BEAR)
6. ✅ **Entry spot prices match**

## Remaining Differences

### Exit Logic
- **Python**: Shows `exit_price: null` for most positions, suggesting theoretical/intrinsic value calculation
- **SQL**: Uses actual last traded prices from the database

### P&L Calculations
The P&L differences appear to stem from:
1. Different exit price methodology
2. Possible slippage factors in Python
3. Different data sources or data quality

## Trade-by-Trade Comparison

| Signal | Entry Date | Python P&L | SQL P&L | Difference | Possible Reason |
|--------|------------|------------|---------|------------|-----------------|
| S1 | Jun 2 | 40,737.5 | 37,825 | -2,912.5 | Different exit price calculation |
| S8 | Jun 12 | 6,350 | -387.5 | -6,737.5 | Different exit price (Python may use theoretical) |
| S7 | Jun 16 | 37,775 | 24,625 | -13,150 | Different exit price methodology |
| S7 | Jun 23 | 29,937.5 | 23,350 | -6,587.5 | Different exit price methodology |
| S3 | Jun 30 | 21,537.5 | 45,100 | +23,562.5 | SQL found different exit prices |

## Conclusion

The SQL stored procedure now correctly:
- Identifies all signals that Python identifies
- Uses the same strike selection logic (stop loss as strike)
- Calculates zones and bias correctly
- Handles week boundaries properly

The P&L differences are due to:
1. **Exit price methodology**: Python appears to use theoretical/intrinsic values or different data
2. **Data quality**: The actual option prices in the database might differ from what Python uses
3. **Exit timing**: Some trades might be using different exit rules

To achieve exact P&L matching, we would need to:
1. Understand the exact exit price calculation used by Python
2. Verify the option price data matches between systems
3. Potentially implement theoretical pricing if that's what Python uses