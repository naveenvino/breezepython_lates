"""
Kite Daily Authentication Script
Helps with daily authentication process for Kite Connect
"""
import os
import sys
import webbrowser
from datetime import datetime
from dotenv import load_dotenv, set_key

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.brokers.kite import KiteClient, KiteAuthService

def main():
    """Main authentication flow"""
    print("Kite Connect Daily Authentication")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Check if API credentials are set
    api_key = os.getenv('KITE_API_KEY')
    api_secret = os.getenv('KITE_API_SECRET')
    
    if not api_key or not api_secret:
        print("ERROR: Kite API credentials not found in .env file")
        print("Please set KITE_API_KEY and KITE_API_SECRET")
        return
    
    print(f"API Key: {api_key}")
    print(f"API Secret: {'*' * 20}")
    
    try:
        # Initialize Kite client
        kite_client = KiteClient()
        auth_service = KiteAuthService(kite_client)
        
        # Check current auth status
        print("\nChecking authentication status...")
        auth_status = auth_service.get_auth_status()
        
        if auth_status['authenticated']:
            print("✓ Already authenticated!")
            print(f"Token timestamp: {auth_status.get('token_timestamp')}")
            
            # Ask if user wants to re-authenticate
            response = input("\nDo you want to re-authenticate? (y/n): ").lower()
            if response != 'y':
                return
        
        # Get login URL
        login_url = kite_client.get_login_url()
        print(f"\nLogin URL: {login_url}")
        
        # Open in browser
        print("\nOpening browser for authentication...")
        webbrowser.open(login_url)
        
        print("\nSteps:")
        print("1. Log in with your Zerodha credentials")
        print("2. Complete 2FA authentication")
        print("3. You'll be redirected to a URL with 'request_token' parameter")
        print("4. Copy the entire URL or just the request_token value")
        
        # Wait for user to complete login
        print("\n" + "-" * 50)
        request_input = input("Paste the redirect URL or request_token here: ").strip()
        
        # Extract request token
        if 'request_token=' in request_input:
            # User pasted full URL
            request_token = request_input.split('request_token=')[1].split('&')[0]
        else:
            # User pasted just the token
            request_token = request_input
        
        print(f"\nRequest token: {request_token[:20]}...")
        
        # Complete authentication
        print("\nGenerating access token...")
        try:
            user_data = auth_service.complete_authentication(request_token)
            
            print("\n✓ Authentication successful!")
            print(f"User ID: {user_data.get('user_id')}")
            print(f"User Name: {user_data.get('user_name')}")
            print(f"Email: {user_data.get('email')}")
            
            # Update .env file with access token
            access_token = user_data.get('access_token')
            if access_token:
                env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
                set_key(env_path, 'KITE_ACCESS_TOKEN', access_token)
                print("\n✓ Access token saved to .env file")
            
            # Show trading limits
            print("\nTrading Limits:")
            print(f"Exchange: {user_data.get('exchanges', [])}")
            print(f"Products: {user_data.get('products', [])}")
            print(f"Order Types: {user_data.get('order_types', [])}")
            
            # Test connection
            print("\nTesting connection...")
            try:
                profile = kite_client.kite.profile()
                print("✓ Connection test successful!")
            except Exception as e:
                print(f"✗ Connection test failed: {e}")
            
        except Exception as e:
            print(f"\n✗ Authentication failed: {e}")
            print("\nCommon issues:")
            print("- Invalid request token (tokens expire quickly)")
            print("- API secret mismatch")
            print("- Network issues")
            return
        
    except Exception as e:
        print(f"\nError: {e}")
        return
    
    print("\n" + "=" * 50)
    print("Authentication complete!")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nNote: Access token expires daily at 6:00 AM")
    print("Run this script each trading day before market opens.")

if __name__ == "__main__":
    main()