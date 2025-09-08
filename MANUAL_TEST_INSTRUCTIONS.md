# Manual Test Instructions - Configuration Persistence

## How to Test Configuration Save/Load

### Step 1: Open the Page
1. Open your browser
2. Go to: http://localhost:8000/tradingview_pro.html
3. Wait for page to fully load

### Step 2: Set Test Values
Set these specific values:
- **Number of Lots**: Select "30 lots"
- **Entry Timing**: Select "Next Candle (11:15)"
- **Exit Day (T+N)**: Select "Expiry Day"
- **Exit Time**: Select "9:30 AM"
- **Monday**: Select "Current Week (This Tuesday)"
- **Wednesday**: Select "Next Week Tuesday"

### Step 3: Take Screenshot #1 (BEFORE SAVE)
- Press `Windows + Shift + S` to take a screenshot
- Save as "before_save.png"

### Step 4: Save Configuration
- Click the **"Save Config"** button
- You should see a success message (no circuit breaker error)

### Step 5: Take Screenshot #2 (AFTER SAVE)
- Press `Windows + Shift + S` to take a screenshot
- Save as "after_save.png"

### Step 6: Refresh the Page
- Press `F5` to refresh the page
- Wait for page to fully load (about 3-4 seconds)

### Step 7: Take Screenshot #3 (AFTER REFRESH)
- Press `Windows + Shift + S` to take a screenshot
- Save as "after_refresh.png"

## What to Check

### ✅ SUCCESS if:
- Screenshot #2 and #3 show the SAME values:
  - Number of Lots: 30
  - Entry Timing: Next Candle
  - Exit Day: Expiry Day
  - Exit Time: 9:30 AM
  - Monday: Current Week
  - Wednesday: Next Week

### ❌ FAILURE if:
- Screenshot #3 shows DEFAULT values instead:
  - Number of Lots: 10 (default)
  - Entry Timing: Immediate (default)
  - Exit Day: T+2 (default)
  - Exit Time: 3:15 PM (default)

## API Verification (Optional)

You can also verify via API by running this command:
```bash
curl http://localhost:8000/api/trade-config/load/default?user_id=default
```

Look for these values in the response:
- `"num_lots": 30`
- `"exit_day_offset": 0`
- `"exit_time": "09:30"`
- `"entry_timing": "next_candle"`

## Fixed Issues
1. ✅ Circuit breaker error on save - FIXED
2. ✅ Configuration not loading on refresh - FIXED
3. ✅ Default values showing instead of saved - FIXED
4. ✅ Dropdown value mismatches - FIXED