"""
Show ALL trade settings from database in detail
"""
import sqlite3
from pathlib import Path
import json

db_path = Path("data/trading_settings.db")

print("=" * 80)
print("COMPLETE DATABASE TRADE SETTINGS")
print("=" * 80)

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all columns from TradeConfiguration table
    cursor.execute("PRAGMA table_info(TradeConfiguration)")
    columns = cursor.fetchall()
    
    print("\n[TABLE SCHEMA - TradeConfiguration]")
    print("-" * 80)
    for col in columns:
        print(f"  {col['name']:30} {col['type']:15} (default: {col['dflt_value']})")
    
    # Fetch all settings
    cursor.execute("""
        SELECT * FROM TradeConfiguration
        WHERE user_id = 'default' AND config_name = 'default' AND is_active = 1
    """)
    
    row = cursor.fetchone()
    
    if row:
        print("\n[CURRENT SETTINGS - User: default, Config: default]")
        print("-" * 80)
        
        # Convert to dictionary for easier access
        settings = dict(row)
        
        # Group 1: Basic Settings
        print("\n1. BASIC CONFIGURATION:")
        print(f"   - ID: {settings.get('id')}")
        print(f"   - User ID: {settings.get('user_id')}")
        print(f"   - Config Name: {settings.get('config_name')}")
        print(f"   - Active: {settings.get('is_active')}")
        print(f"   - Created: {settings.get('created_at')}")
        print(f"   - Updated: {settings.get('updated_at')}")
        
        # Group 2: Position Settings
        print("\n2. POSITION SETTINGS:")
        print(f"   - Number of Lots: {settings.get('num_lots')} lots")
        print(f"   - ACTUAL QUANTITY: {settings.get('num_lots')} x 75 = {settings.get('num_lots', 0) * 75} qty")
        print(f"   - Entry Timing: {settings.get('entry_timing')}")
        print(f"   - AMO Enabled: {bool(settings.get('amo_enabled'))}")
        print(f"   - Position Size Mode: {settings.get('position_size_mode')}")
        
        # Group 3: Hedge Configuration
        print("\n3. HEDGE CONFIGURATION:")
        print(f"   - Hedge Enabled: {bool(settings.get('hedge_enabled'))}")
        print(f"   - Hedge Method: {settings.get('hedge_method')}")
        print(f"   - Hedge Percentage: {settings.get('hedge_percent')}%")
        print(f"   - Hedge Offset: {settings.get('hedge_offset')} points")
        
        # Group 4: Stop Loss & Profit Settings
        print("\n4. STOP LOSS & PROFIT SETTINGS:")
        print(f"   - Profit Lock Enabled: {bool(settings.get('profit_lock_enabled'))}")
        print(f"   - Profit Target: {settings.get('profit_target')}%")
        print(f"   - Profit Lock Level: {settings.get('profit_lock')}%")
        print(f"   - Trailing Stop Enabled: {bool(settings.get('trailing_stop_enabled'))}")
        print(f"   - Trail Percentage: {settings.get('trail_percent')}%")
        
        # Group 5: Auto Trading
        print("\n5. AUTO TRADING SETTINGS:")
        print(f"   - Auto Trade Enabled: {bool(settings.get('auto_trade_enabled'))}")
        try:
            active_signals = json.loads(settings.get('active_signals', '[]'))
            print(f"   - Active Signals: {active_signals}")
        except:
            print(f"   - Active Signals: {settings.get('active_signals')}")
        print(f"   - Daily Profit Target: Rs.{settings.get('daily_profit_target')}")
        
        # Group 6: Risk Management
        print("\n6. RISK MANAGEMENT:")
        print(f"   - Max Positions: {settings.get('max_positions')}")
        print(f"   - Max Loss Per Trade: Rs.{settings.get('max_loss_per_trade')}")
        print(f"   - Max Exposure: Rs.{settings.get('max_exposure')}")
        
        # Group 7: Exit Configuration
        print("\n7. EXIT CONFIGURATION:")
        print(f"   - Selected Expiry: {settings.get('selected_expiry')}")
        print(f"   - Exit Day Offset: {settings.get('exit_day_offset')} days")
        print(f"   - Exit Time: {settings.get('exit_time')}")
        print(f"   - Auto Square Off Enabled: {bool(settings.get('auto_square_off_enabled'))}")
        
        # Group 8: Weekday Configuration
        print("\n8. WEEKDAY CONFIGURATION:")
        try:
            weekday_config = json.loads(settings.get('weekday_config', '{}'))
            if weekday_config:
                for day, expiry in weekday_config.items():
                    print(f"   - {day.capitalize()}: {expiry}")
            else:
                print("   - No weekday configuration set")
        except:
            print(f"   - Raw data: {settings.get('weekday_config')}")
        
        # Show any additional columns not covered above
        covered_columns = {
            'id', 'user_id', 'config_name', 'is_active', 'created_at', 'updated_at',
            'num_lots', 'entry_timing', 'amo_enabled', 'position_size_mode',
            'hedge_enabled', 'hedge_method', 'hedge_percent', 'hedge_offset',
            'profit_lock_enabled', 'profit_target', 'profit_lock', 
            'trailing_stop_enabled', 'trail_percent',
            'auto_trade_enabled', 'active_signals', 'daily_profit_target',
            'max_positions', 'max_loss_per_trade', 'max_exposure',
            'selected_expiry', 'exit_day_offset', 'exit_time', 
            'auto_square_off_enabled', 'weekday_config'
        }
        
        additional = [k for k in settings.keys() if k not in covered_columns]
        if additional:
            print("\n9. ADDITIONAL SETTINGS:")
            for key in additional:
                print(f"   - {key}: {settings.get(key)}")
    else:
        print("\n[NO ACTIVE CONFIGURATION FOUND]")
        print("No configuration exists for user='default', config='default'")

print("\n" + "=" * 80)
print("KEY TRADING CALCULATION:")
print(f"Order Quantity = Number of Lots x 75")
print(f"Current: {settings.get('num_lots', 0)} lots x 75 = {settings.get('num_lots', 0) * 75} qty per order")
print("=" * 80)