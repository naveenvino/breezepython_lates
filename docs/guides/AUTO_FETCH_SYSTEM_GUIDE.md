# Auto-Fetch Missing Options Data System

## Overview
The auto-fetch system automatically downloads missing options data at the end of a backtest run, ensuring future runs have complete data without manual intervention.

## How It Works

### 1. **Tracking Phase** (During Backtest)
- As the backtest runs, it tracks any missing option strikes it encounters
- Missing strikes are stored in a set: `(strike_price, option_type, expiry_date)`
- Both main and hedge positions are tracked

### 2. **Fetching Phase** (After Backtest)
- At the end of the backtest, if `auto_fetch_missing_data=True`:
  - Groups missing strikes by week for efficient API calls
  - Fetches data in batches (default 100 strikes per API call)
  - Uses the existing `/collect/options-specific` endpoint
  - Stores fetched data in the database permanently

### 3. **Reporting Phase**
- Returns information about fetched data in the API response:
  - `total_missing`: Number of missing option contracts found
  - `records_fetched`: Total records added to database
  - `unique_strikes`: Number of unique strike prices processed

## Configuration

### API Parameters
```python
{
    "auto_fetch_missing_data": True,  # Enable/disable auto-fetch (default: True)
    "fetch_batch_size": 100           # Strikes per API call (default: 100)
}
```

### Example Request
```bash
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "from_date": "2025-01-01",
    "to_date": "2025-07-31",
    "signals_to_test": ["S1"],
    "auto_fetch_missing_data": true,
    "fetch_batch_size": 100
  }'
```

## Response Format

### With Missing Data Fetched
```json
{
    "status": "success",
    "backtest_id": "abc-123",
    "summary": { ... },
    "missing_data_fetched": {
        "total_missing": 450,
        "records_fetched": 8932,
        "unique_strikes": 45
    },
    "trades": [ ... ]
}
```

### No Missing Data
If all data is already available, the `missing_data_fetched` field won't appear in the response.

## Benefits

1. **Automatic**: No manual intervention needed
2. **Efficient**: Batched API calls prevent overload
3. **Comprehensive**: Fetches ALL missing data, not just a subset
4. **Permanent**: Data stored in database for future use
5. **Progressive**: Each run improves data completeness

## Testing

### Quick Test
```python
python test_auto_fetch_complete.py
```

### Verify It's Working
1. Run a backtest for a period with missing data
2. Check the response for `missing_data_fetched` info
3. Run the same backtest again - should have no missing data warnings

### Large-Scale Test
```python
# Test with Jan-July 2025 (extensive data)
python test_backtest_large_range.py
```

## Implementation Details

### Files Modified
1. **unified_api_correct.py**
   - Added `auto_fetch_missing_data` and `fetch_batch_size` to BacktestRequest
   - Modified response to include fetched data info

2. **src/application/use_cases/run_backtest.py**
   - Added `missing_options_data` set to track missing strikes
   - Created `_auto_fetch_all_missing_options()` method
   - Modified `_open_trade()` to track missing strikes

3. **src/application/use_cases/run_backtest_async.py**
   - Same changes as above for async version

## Troubleshooting

### Missing Data Not Being Fetched
- Check that `auto_fetch_missing_data=true` in request
- Verify API is running on port 8000
- Check logs for fetch progress messages

### Fetch Taking Too Long
- Reduce `fetch_batch_size` to 50 for slower connections
- Consider running backtest for smaller date ranges

### Database Not Updated
- Check SQL Server connection
- Verify write permissions on OptionsData table
- Check for duplicate key errors in logs

## Performance Considerations

- **Batch Size**: 100 strikes optimal for most cases
- **API Delays**: 1 second between batches prevents overload
- **Memory Usage**: Minimal - only stores unique strikes
- **Network**: Each batch is ~5KB request, ~50KB response

## Future Enhancements

Potential improvements:
1. Parallel fetching for multiple weeks
2. Progress callback for UI updates
3. Caching of frequently missing strikes
4. Predictive pre-fetching based on patterns