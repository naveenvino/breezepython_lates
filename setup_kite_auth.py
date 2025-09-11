"""
Setup Kite Authentication
Helps configure Kite API credentials
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

def setup_kite_credentials():
    """Setup Kite API credentials in .env file"""
    
    print("="*60)
    print("KITE API SETUP HELPER")
    print("="*60)
    
    print("\nThis script will help you set up Kite API credentials.")
    print("\nYou need:")
    print("1. Kite API Key (from https://developers.kite.trade/apps)")
    print("2. Kite API Secret")
    print("3. Access Token (generated daily after login)")
    
    # Check current status
    load_dotenv()
    current_key = os.getenv('KITE_API_KEY')
    current_secret = os.getenv('KITE_API_SECRET')
    current_token = os.getenv('KITE_ACCESS_TOKEN')
    
    print("\nCurrent Status:")
    print(f"  API Key: {'Set' if current_key else 'Not set'}")
    print(f"  API Secret: {'Set' if current_secret else 'Not set'}")
    print(f"  Access Token: {'Set' if current_token else 'Not set'}")
    
    # Check for token in kite_login_status.json
    token_from_file = None
    if os.path.exists('logs/kite_login_status.json'):
        with open('logs/kite_login_status.json', 'r') as f:
            data = json.load(f)
            if 'message' in data and len(data['message']) == 32:
                token_from_file = data['message']
                print(f"\n[INFO] Found potential access token in kite_login_status.json")
                print(f"       Token: {token_from_file[:10]}...")
    
    # Get user input
    print("\n" + "-"*40)
    
    if not current_key:
        api_key = input("\nEnter your Kite API Key: ").strip()
        if api_key:
            set_key('.env', 'KITE_API_KEY', api_key)
            print("[OK] API Key saved to .env")
    else:
        print(f"\nAPI Key already set: {current_key[:10]}...")
    
    if not current_secret:
        api_secret = input("\nEnter your Kite API Secret: ").strip()
        if api_secret:
            set_key('.env', 'KITE_API_SECRET', api_secret)
            print("[OK] API Secret saved to .env")
    else:
        print("\nAPI Secret already set")
    
    if not current_token:
        if token_from_file:
            use_found = input(f"\nUse token from kite_login_status.json? (y/n): ").lower()
            if use_found == 'y':
                set_key('.env', 'KITE_ACCESS_TOKEN', token_from_file)
                print("[OK] Access Token saved to .env")
            else:
                access_token = input("\nEnter your Access Token: ").strip()
                if access_token:
                    set_key('.env', 'KITE_ACCESS_TOKEN', access_token)
                    print("[OK] Access Token saved to .env")
        else:
            access_token = input("\nEnter your Access Token (or press Enter to skip): ").strip()
            if access_token:
                set_key('.env', 'KITE_ACCESS_TOKEN', access_token)
                print("[OK] Access Token saved to .env")
    else:
        print("\nAccess Token already set")
    
    # Test connection
    print("\n" + "-"*40)
    print("Testing connection...")
    
    try:
        from kiteconnect import KiteConnect
        
        # Reload env to get new values
        load_dotenv(override=True)
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if api_key and access_token:
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            profile = kite.profile()
            print("\n[SUCCESS] Connected to Kite!")
            print(f"  User: {profile.get('user_name')}")
            print(f"  Email: {profile.get('email')}")
            
            # Test orders
            orders = kite.orders()
            print(f"\n  Orders today: {len(orders)}")
            
            active = [o for o in orders if o.get('status') in ['OPEN', 'TRIGGER PENDING']]
            print(f"  Active orders: {len(active)}")
            
        else:
            print("\n[WARNING] Missing credentials. Please set them up first.")
    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")
        print("\nPossible issues:")
        print("1. Access token expired (expires daily at 6 AM)")
        print("2. Invalid API credentials")
        print("3. Need to generate new access token")
    
    print("\n" + "="*60)
    print("Setup complete!")
    print("\nNext steps:")
    print("1. Restart the API server: python unified_api_correct.py")
    print("2. Open the UI and check Active Orders section")
    print("3. Place an order in Kite to see it appear")

if __name__ == "__main__":
    setup_kite_credentials()