# Complete API Guide - With Corrected Logic

## Important: Restart Required

After the code updates, you need to restart the API:
```bash
# Stop current API (Ctrl+C)
python run.py
```

## Available Methods to Collect and Check Data

### Method 1: Using Main API (Port 8100)

#### Step 1: Collect NIFTY Data

Since the screenshot shows the `/api/v2/data/collect/nifty` endpoint might not be visible, you have these options:

**Option A: Try the Weekly Endpoint** (Visible in your screenshot)
```json
POST /api/v2/data/collect/weekly
{
  "from_date": "2025-01-24",
  "to_date": "2025-01-24",
  "symbol": "NIFTY",
  "strike_range": 0,
  "use_parallel": false
}
```

**Option B: Check if NIFTY endpoint is available after restart**
```json
POST /api/v2/data/collect/nifty
{
  "from_date": "2025-01-24",
  "to_date": "2025-01-24",
  "symbol": "NIFTY",
  "force_refresh": false
}
```

#### Step 2: Check Data Availability

**NEW GET Endpoints** (Added to analysis router):

1. **Check Data Availability**
   ```
   GET /api/v2/analysis/data-availability?from_date=2025-01-24&to_date=2025-01-24&symbol=NIFTY
   ```
   
   Returns:
   - Total 5-minute and hourly records
   - Expected vs actual counts
   - Daily breakdown
   - Data completeness percentage

2. **Get Hourly Candles**
   ```
   GET /api/v2/analysis/hourly-candles?date=2025-01-24&symbol=NIFTY
   ```
   
   Returns:
   - All hourly candles for the date
   - OHLC values for each hour
   - Verification of data completeness

### Method 2: Using Test API (Port 8002) - GUARANTEED TO WORK

```bash
# Terminal 1: Start the test API
python test_direct_endpoint_only.py

# Terminal 2: Collect data
curl -X POST "http://localhost:8002/api/v1/collect/nifty-direct" \
  -H "Content-Type: application/json" \
  -d '{"from_date": "2025-01-24", "to_date": "2025-01-24", "symbol": "NIFTY"}'
```

### Method 3: Using Command Line Scripts

```bash
# Collect data
python collect_specific_period.py 2025-01-24 2025-01-24

# Check existing data
python quick_data_check.py 2025-01-24

# Check data range
python quick_data_check.py 2025-01-20 --to-date 2025-01-24 --summary
```

## Verification Steps

### Expected Results

For each trading day, you should see:
- **74 five-minute records** (from 9:20 to 15:25)
- **7 hourly records** (9:15, 10:15, 11:15, 12:15, 13:15, 14:15, 15:15)

### Hourly Candle Aggregation

Verify the logic is correct:
- 9:15 candle = aggregates 9:20 to 10:20 five-minute data
- 10:15 candle = aggregates 10:20 to 11:20 five-minute data
- And so on...

## Quick Test Workflow

1. **Delete old data** (if needed):
   ```bash
   python delete_all_nifty_data_auto.py
   ```

2. **Collect fresh data**:
   - Use any method above

3. **Verify in Swagger**:
   - Go to http://localhost:8100/docs
   - Find "Data Analysis" section
   - Use `GET /api/v2/analysis/data-availability`
   - Use `GET /api/v2/analysis/hourly-candles`

## Troubleshooting

### If endpoints are not visible in Swagger:

1. **Check if API restarted properly**:
   ```bash
   curl http://localhost:8100/health
   ```

2. **Use the test API instead**:
   ```bash
   python test_direct_endpoint_only.py
   ```

3. **Check logs** for any startup errors

### If data looks incorrect:

1. **Verify timestamps**:
   - Should start at 9:20 and end at 15:25
   - Check using `quick_data_check.py`

2. **Verify hourly aggregation**:
   - Use the hourly-candles endpoint
   - Check that 9:15 candle uses 9:20-10:20 data

## Key Points

1. The corrected logic is implemented in:
   - `NiftyIndexData.from_breeze_data()` - filters to 9:20-15:25
   - `HourlyAggregationService` - uses 9:20-10:20 for 9:15 candle
   - `DataCollectionService` - orchestrates the collection

2. Any endpoint that uses these services has the correct logic

3. The test API (port 8002) is guaranteed to work with correct logic

4. New GET endpoints make it easy to verify data without complex POST requests