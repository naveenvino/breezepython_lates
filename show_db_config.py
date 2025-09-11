"""
Show current database configuration
"""
from src.services.trade_config_service import get_trade_config_service
import json

# Get configuration service
service = get_trade_config_service()

# Load configuration from database
config = service.load_trade_config(user_id='default', config_name='default')

print("\n" + "="*60)
print("DATABASE CONFIGURATION (Current Settings)")
print("="*60)

# Show key configuration values
print("\n[POSITION SETTINGS]")
print(f"  - Number of Lots: {config.get('num_lots', 'Not set')}")
print(f"  - Entry Timing: {config.get('entry_timing', 'Not set')}")
print(f"  - AMO Enabled: {config.get('amo_enabled', 'Not set')}")
print(f"  - Position Size Mode: {config.get('position_size_mode', 'Not set')}")

print("\n[HEDGE CONFIGURATION]")
print(f"  - Hedge Enabled: {config.get('hedge_enabled', 'Not set')}")
print(f"  - Hedge Method: {config.get('hedge_method', 'Not set')}")
print(f"  - Hedge Percentage: {config.get('hedge_percent', 'Not set')}%")
print(f"  - Hedge Offset: {config.get('hedge_offset', 'Not set')} points")

print("\n[STOP LOSS SETTINGS]")
print(f"  - Profit Lock Enabled: {config.get('profit_lock_enabled', 'Not set')}")
print(f"  - Profit Target: {config.get('profit_target', 'Not set')}%")
print(f"  - Profit Lock: {config.get('profit_lock', 'Not set')}%")
print(f"  - Trailing Stop Enabled: {config.get('trailing_stop_enabled', 'Not set')}")
print(f"  - Trail Percent: {config.get('trail_percent', 'Not set')}%")

print("\n[AUTO TRADING]")
print(f"  - Auto Trade Enabled: {config.get('auto_trade_enabled', 'Not set')}")
print(f"  - Active Signals: {config.get('active_signals', 'Not set')}")
print(f"  - Daily Profit Target: Rs.{config.get('daily_profit_target', 'Not set')}")

print("\n[RISK MANAGEMENT]")
print(f"  - Max Positions: {config.get('max_positions', 'Not set')}")
print(f"  - Max Loss Per Trade: Rs.{config.get('max_loss_per_trade', 'Not set')}")
print(f"  - Max Exposure: Rs.{config.get('max_exposure', 'Not set')}")

print("\n[EXIT CONFIGURATION]")
print(f"  - Selected Expiry: {config.get('selected_expiry', 'Not set')}")
print(f"  - Exit Day Offset: {config.get('exit_day_offset', 'Not set')} days")
print(f"  - Exit Time: {config.get('exit_time', 'Not set')}")
print(f"  - Auto Square Off Enabled: {config.get('auto_square_off_enabled', 'Not set')}")

# Show weekday configuration if exists
weekday_config = config.get('weekday_config', {})
if weekday_config:
    print("\n[WEEKDAY EXPIRY CONFIG]")
    for day, expiry in weekday_config.items():
        print(f"  - {day.capitalize()}: {expiry}")

print("\n" + "="*60)
print(f"Database Path: data/trading_settings.db")
print(f"User ID: default")
print(f"Config Name: default")
print("="*60)

# Calculate actual quantity that will be used
lots = config.get('num_lots', 10)
quantity = lots * 75
print(f"\n✅ ACTUAL ORDER QUANTITY: {lots} lots × 75 = {quantity} qty")
print("="*60)