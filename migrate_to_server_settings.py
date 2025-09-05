#!/usr/bin/env python3
"""
Migrate trading settings from browser localStorage to server-side database
This ensures settings persist across sessions and browsers
"""

import requests
import json
from datetime import datetime

def setup_default_settings():
    """Setup default trading settings in the database"""
    
    base_url = "http://localhost:8000"
    
    # Default production settings
    default_settings = {
        # Position Configuration
        "position_size": "10",           # Number of lots
        "lot_quantity": "75",            # Quantity per lot (75 for NIFTY)
        "entry_timing": "immediate",     # immediate or second_candle
        
        # Risk Management
        "stop_loss_points": "200",       # Stop loss in points
        "enable_hedging": "true",        # Enable hedging
        "hedge_offset": "200",           # Hedge strike offset
        "max_drawdown": "50000",         # Max drawdown in Rs
        "max_positions": "5",            # Max concurrent positions
        
        # Auto Trading
        "auto_trade_enabled": "false",   # Auto-execute signals
        "trading_mode": "LIVE",          # LIVE or PAPER
        
        # Signal Configuration
        "signals_enabled": "S1,S2,S3,S4,S5,S6,S7,S8",  # All signals enabled
        "signal_S1_active": "true",
        "signal_S2_active": "true", 
        "signal_S3_active": "true",
        "signal_S4_active": "true",
        "signal_S5_active": "true",
        "signal_S6_active": "true",
        "signal_S7_active": "true",
        "signal_S8_active": "true",
        
        # Notifications
        "enable_notifications": "true",
        "telegram_alerts": "true",
        "email_alerts": "false",
        
        # Trading Hours
        "start_time": "09:15",
        "end_time": "15:15",
        "square_off_time": "15:15",
        
        # System Settings
        "debug_mode": "false",
        "paper_trading": "false"
    }
    
    print("=" * 60)
    print("MIGRATING SETTINGS TO SERVER DATABASE")
    print("=" * 60)
    print(f"Time: {datetime.now()}")
    print()
    
    # Save settings to server
    try:
        response = requests.post(
            f"{base_url}/settings",
            json=default_settings,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Settings saved to database successfully!")
            print(f"   Response: {result}")
        else:
            print(f"⚠️ Warning: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error saving settings: {e}")
    
    print()
    
    # Verify settings
    print("Verifying saved settings...")
    try:
        response = requests.get(f"{base_url}/settings")
        if response.status_code == 200:
            saved_settings = response.json().get("settings", {})
            print("✅ Settings retrieved from database:")
            for key, value in saved_settings.items():
                print(f"   {key}: {value}")
        else:
            print(f"⚠️ Could not verify settings: {response.status_code}")
    except Exception as e:
        print(f"❌ Error verifying settings: {e}")
    
    print()
    print("=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print()
    print("Next Steps:")
    print("1. The UI will now load settings from the database on startup")
    print("2. All setting changes will be saved to the database")
    print("3. Settings will persist across browser sessions")
    print("4. No more dependency on localStorage!")
    print()
    print("Configuration is now stored in SQL Server database:")
    print("- Table: UserSettings")
    print("- User: default (can be changed for multi-user support)")
    print()

if __name__ == "__main__":
    setup_default_settings()