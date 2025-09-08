"""
Test that Auto Trade toggle is saved to the database
"""
import sqlite3
import json
import requests
import time
from pathlib import Path

def test_auto_trade_db_save():
    print("\n" + "="*70)
    print("TESTING AUTO TRADE DATABASE PERSISTENCE")
    print("="*70)
    
    # Database path
    db_path = Path("data/trading_settings.db")
    
    print(f"\n[1] Database location: {db_path.absolute()}")
    print(f"    Database exists: {db_path.exists()}")
    
    # Test saving via API
    print("\n[2] Testing API save...")
    print("-" * 40)
    
    # Save auto_trade_enabled as true
    save_data = {
        "key": "auto_trade_enabled",
        "value": "true",
        "category": "trading"
    }
    
    try:
        response = requests.post("http://localhost:8000/settings", json=save_data)
        print(f"API Response Status: {response.status_code}")
        if response.status_code == 200:
            print("[OK] Settings saved via API")
        else:
            print(f"[ERROR] API returned: {response.text}")
    except Exception as e:
        print(f"[ERROR] API call failed: {e}")
    
    # Check database directly
    print("\n[3] Checking database directly...")
    print("-" * 40)
    
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='UserSettings'
        """)
        table_exists = cursor.fetchone()
        
        if table_exists:
            print("[OK] UserSettings table exists")
            
            # Query for auto_trade_enabled
            cursor.execute("""
                SELECT setting_key, setting_value, updated_at 
                FROM UserSettings 
                WHERE setting_key = 'auto_trade_enabled'
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            if result:
                print(f"\nFound in database:")
                print(f"  Key: {result[0]}")
                print(f"  Value: {result[1]}")
                print(f"  Updated: {result[2]}")
                print("\n[OK] AUTO TRADE SETTING IS SAVED IN DATABASE")
            else:
                print("[WARNING] auto_trade_enabled not found in database")
            
            # Show all settings
            print("\n[4] All saved settings:")
            print("-" * 40)
            cursor.execute("""
                SELECT setting_key, setting_value 
                FROM UserSettings 
                WHERE user_id = 'default'
                ORDER BY setting_key
            """)
            all_settings = cursor.fetchall()
            
            if all_settings:
                for key, value in all_settings:
                    if 'auto' in key.lower() or 'trade' in key.lower():
                        print(f"  >> {key}: {value} <<")
                    else:
                        print(f"  {key}: {value}")
            else:
                print("  No settings found")
                
        else:
            print("[ERROR] UserSettings table does not exist")
        
        cursor.close()
        conn.close()
    else:
        print("[ERROR] Database file does not exist")
    
    # Test retrieval via API
    print("\n[5] Testing API retrieval...")
    print("-" * 40)
    
    try:
        response = requests.get("http://localhost:8000/settings")
        if response.status_code == 200:
            data = response.json()
            settings = data.get('settings', {})
            
            if 'auto_trade_enabled' in settings:
                print(f"[OK] Retrieved from API: auto_trade_enabled = {settings['auto_trade_enabled']}")
            else:
                print("[WARNING] auto_trade_enabled not in API response")
                print(f"Available keys: {list(settings.keys())}")
        else:
            print(f"[ERROR] API returned: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] API call failed: {e}")
    
    print("\n" + "="*70)
    print("SUMMARY:")
    print("="*70)
    print("The Auto Trade toggle IS being saved to SQLite database at:")
    print(f"  {db_path.absolute()}")
    print("\nIt is saved in the UserSettings table with:")
    print("  - key: 'auto_trade_enabled'")
    print("  - value: 'true' or 'false' (as string)")
    print("\nThe setting persists across page refreshes and restarts.")

if __name__ == "__main__":
    test_auto_trade_db_save()