"""
Fix trade settings - remove unwanted restrictions and ensure all settings are saved
"""
from src.services.trade_config_service import get_trade_config_service
import json

# Get configuration service
service = get_trade_config_service()

# Load current configuration
current_config = service.load_trade_config(user_id='default', config_name='default')

print("CURRENT Configuration (Before Fix):")
print(json.dumps(current_config, indent=2))

# Update configuration with proper values (remove restrictions, add all settings)
updated_config = {
    # Position Settings
    'num_lots': 5,  # Keep as 5 as you wanted
    'entry_timing': 'immediate',
    'amo_enabled': False,
    'position_size_mode': 'fixed',
    
    # Hedge Configuration
    'hedge_enabled': True,
    'hedge_method': 'percentage', 
    'hedge_percent': 30.0,
    'hedge_offset': 200,
    
    # Stop Loss & Profit Settings
    'profit_lock_enabled': True,  # Enable profit lock
    'profit_target': 10.0,
    'profit_lock': 5.0,
    'trailing_stop_enabled': True,  # Enable trailing stop
    'trail_percent': 1.0,
    
    # Auto Trading Settings
    'auto_trade_enabled': True,  # Enable auto trade
    'active_signals': ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'],  # All signals enabled
    'daily_profit_target': 0,  # Remove restriction (0 = no limit)
    
    # Risk Management - REMOVE RESTRICTIONS
    'max_positions': 999,  # Effectively no limit
    'max_loss_per_trade': 0,  # Remove restriction (0 = no limit)
    'max_exposure': 0,  # Remove restriction (0 = no limit)
    'daily_loss_limit': 0,  # Remove restriction (0 = no limit)
    
    # Exit Configuration
    'selected_expiry': 'current',
    'exit_day_offset': 0,  # Exit on expiry day
    'exit_time': '15:15',
    'auto_square_off_enabled': True,
    
    # Weekday Configuration
    'weekday_config': {
        'monday': 'current',
        'tuesday': 'current', 
        'wednesday': 'current',
        'thursday': 'current',
        'friday': 'current'
    }
}

# Save updated configuration
result = service.save_trade_config(updated_config, user_id='default', config_name='default')
print("\nUPDATE Result:", result)

# Verify the update
updated = service.load_trade_config(user_id='default', config_name='default')

print("\n" + "="*80)
print("UPDATED CONFIGURATION (After Fix):")
print("="*80)

print("\n[POSITION SETTINGS]")
print(f"  - Number of Lots: {updated.get('num_lots')} (Quantity: {updated.get('num_lots') * 75})")
print(f"  - Entry Timing: {updated.get('entry_timing')}")
print(f"  - AMO Enabled: {updated.get('amo_enabled')}")
print(f"  - Position Size Mode: {updated.get('position_size_mode')}")

print("\n[HEDGE CONFIGURATION]")
print(f"  - Hedge Enabled: {updated.get('hedge_enabled')}")
print(f"  - Hedge Method: {updated.get('hedge_method')}")
print(f"  - Hedge Percentage: {updated.get('hedge_percent')}%")
print(f"  - Hedge Offset: {updated.get('hedge_offset')} points")

print("\n[STOP LOSS & PROFIT SETTINGS]")
print(f"  - Profit Lock Enabled: {updated.get('profit_lock_enabled')}")
print(f"  - Profit Target: {updated.get('profit_target')}%")
print(f"  - Profit Lock Level: {updated.get('profit_lock')}%")
print(f"  - Trailing Stop Enabled: {updated.get('trailing_stop_enabled')}")
print(f"  - Trail Percentage: {updated.get('trail_percent')}%")

print("\n[AUTO TRADING]")
print(f"  - Auto Trade Enabled: {updated.get('auto_trade_enabled')}")
print(f"  - Active Signals: {updated.get('active_signals')}")
print(f"  - Daily Profit Target: {'No Limit' if updated.get('daily_profit_target') == 0 else updated.get('daily_profit_target')}")

print("\n[RISK MANAGEMENT]")
print(f"  - Max Positions: {'No Limit' if updated.get('max_positions', 0) >= 999 else updated.get('max_positions')}")
print(f"  - Max Loss Per Trade: {'No Limit' if updated.get('max_loss_per_trade', 0) == 0 else updated.get('max_loss_per_trade')}")
print(f"  - Max Exposure: {'No Limit' if updated.get('max_exposure', 0) == 0 else updated.get('max_exposure')}")
print(f"  - Daily Loss Limit: {'No Limit' if updated.get('daily_loss_limit', 0) == 0 else updated.get('daily_loss_limit')}")

print("\n[EXIT CONFIGURATION]")
print(f"  - Selected Expiry: {updated.get('selected_expiry')}")
print(f"  - Exit Day Offset: {updated.get('exit_day_offset')} days")
print(f"  - Exit Time: {updated.get('exit_time')}")
print(f"  - Auto Square Off: {updated.get('auto_square_off_enabled')}")

print("\n[WEEKDAY CONFIGURATION]")
weekday_config = updated.get('weekday_config', {})
for day, expiry in weekday_config.items():
    print(f"  - {day.capitalize()}: {expiry}")

print("\n" + "="*80)
print("SUMMARY OF CHANGES:")
print("  ✓ Removed all risk limit restrictions")
print("  ✓ Enabled Auto Trading")
print("  ✓ Enabled all signals (S1-S8)")
print("  ✓ Enabled Profit Lock")
print("  ✓ Enabled Trailing Stop")
print("  ✓ Set expiry to current week")
print("  ✓ Kept lot size at 5 (375 qty)")
print("="*80)