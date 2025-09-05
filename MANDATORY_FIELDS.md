# Mandatory Trading Configuration Fields

## Absolutely Mandatory Fields (No Defaults)

### 1. **Number of Lots** ⭐ REQUIRED
- **Field**: `num_lots`
- **Range**: 1-100 lots
- **Default**: NONE - User must specify
- **Why Mandatory**: Core position sizing parameter

### 2. **Daily Loss Limit** ⭐ REQUIRED  
- **Field**: `daily_loss_limit`
- **Range**: Rs.10,000 - Rs.500,000
- **Default**: NONE - User must specify
- **Why Mandatory**: Critical risk management parameter

## Fields with Defaults (Auto-Applied)

### 3. **Entry Timing** ✅ Has Default
- **Field**: `entry_timing`
- **Values**: 'immediate' or 'delayed'
- **Default**: 'immediate' (as requested)
- **Impact**: Determines when to enter after signal

### 4. **Hedge Configuration** ✅ Has Default
- **Field**: `hedge_enabled`
- **Default**: true
- **Related Fields**:
  - `hedge_method`: 'percentage' (default)
  - `hedge_percent`: 30% (default)
  - `hedge_offset`: 200 points (default)

### 5. **Stop Loss Settings** ✅ Has Default
- **Fields**: 
  - `profit_lock_enabled`: false (default)
  - `profit_target`: 10% (default)
  - `profit_lock`: 5% (default)
  - `trailing_stop_enabled`: false (default)
  - `trail_percent`: 1% (default)

### 6. **Risk Management** ✅ Partial Defaults
- **Fields**:
  - `max_positions`: 5 (default)
  - `max_loss_per_trade`: Rs.20,000 (default)
  - `daily_profit_target`: Rs.100,000 (default)

## Validation Flow

```
User Saves Configuration
         ↓
Check Mandatory Fields:
  - num_lots present? ❌ → Show Error
  - daily_loss_limit present? ❌ → Show Error
         ↓
Apply Defaults:
  - entry_timing = 'immediate' if missing
  - hedge settings = defaults if missing
         ↓
Validate Ranges:
  - num_lots: 1-100
  - daily_loss_limit: 10k-500k
         ↓
Conditional Validation:
  - If hedge enabled → check method
  - If profit lock enabled → check targets
         ↓
Save if Valid ✅
```

## Frontend Implementation

### Visual Indicators
- Red asterisk (*) for mandatory fields
- Red border on validation failure
- Error messages showing what's missing

### JavaScript Validation
```javascript
const errors = [];
if (!config.num_lots || config.num_lots < 1) {
    errors.push('Number of lots is required (minimum 1)');
}
if (!config.daily_loss_limit || config.daily_loss_limit < 10000) {
    errors.push('Daily loss limit is required (minimum Rs.10,000)');
}
```

## Backend Validation

### Validator Service
- File: `src/services/trade_config_validator.py`
- Validates all mandatory fields
- Applies defaults automatically
- Returns detailed error messages

### API Endpoints
- `POST /api/trade-config/save` - Validates before saving
- `POST /api/trade-config/validate` - Test validation without saving

## What Happens if Mandatory Fields Missing?

1. **Frontend**: Shows error notification, highlights fields in red
2. **Backend**: Returns validation errors, refuses to save
3. **Trading**: Cannot execute trades without valid configuration

## Summary

Only **2 fields are truly mandatory**:
1. **Number of Lots** - No default, user must specify
2. **Daily Loss Limit** - No default, critical for risk

All other fields have sensible defaults including:
- **Entry Timing**: Defaults to 'immediate' as requested
- **Hedge Settings**: Default 30% hedge enabled
- **Stop Loss**: Defaults disabled but configurable