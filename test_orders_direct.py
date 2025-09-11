"""
Direct test of Kite orders functionality
Tests without going through the API
"""

import os
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import json
from datetime import datetime

# Load environment variables
load_dotenv()

def test_kite_orders():
    """Test fetching orders directly from Kite"""
    
    print("="*60)
    print("DIRECT KITE ORDERS TEST")
    print("="*60)
    
    # Get credentials
    api_key = os.getenv('KITE_API_KEY')
    access_token = None
    
    print(f"\n1. Checking credentials:")
    print(f"   API Key: {'Found' if api_key else 'Missing'}")
    
    # Check for saved access token
    token_file = 'logs/kite_auth_cache.json'
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r') as f:
                data = json.load(f)
                access_token = data.get('access_token')
                timestamp = data.get('timestamp', data.get('cached_at'))
                print(f"   Access Token: Found (from {timestamp})")
        except Exception as e:
            print(f"   Error reading token file: {e}")
    else:
        print(f"   Access Token: Not found (need to authenticate)")
    
    if not api_key or not access_token:
        print("\n❌ Missing credentials. Please ensure:")
        print("   1. KITE_API_KEY is set in .env file")
        print("   2. You've authenticated and have a valid access token")
        return
    
    # Initialize Kite
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        print("\n2. Testing Kite connection:")
        profile = kite.profile()
        print(f"   ✅ Connected as: {profile.get('user_name')} ({profile.get('user_id')})")
        
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        print("\n   This usually means:")
        print("   - Access token has expired (expires daily at 6 AM)")
        print("   - Need to re-authenticate through Kite login")
        return
    
    # Fetch orders
    try:
        print("\n3. Fetching all orders for today:")
        all_orders = kite.orders()
        print(f"   Total orders: {len(all_orders)}")
        
        if all_orders:
            print("\n   Order Summary:")
            status_count = {}
            for order in all_orders:
                status = order.get('status', 'UNKNOWN')
                status_count[status] = status_count.get(status, 0) + 1
            
            for status, count in status_count.items():
                print(f"     {status}: {count}")
            
            # Show first 3 orders
            print("\n   Sample Orders:")
            for order in all_orders[:3]:
                print(f"\n     Order ID: {order.get('order_id')}")
                print(f"     Symbol: {order.get('tradingsymbol')}")
                print(f"     Type: {order.get('transaction_type')}")
                print(f"     Status: {order.get('status')}")
                print(f"     Qty: {order.get('filled_quantity')}/{order.get('quantity')}")
                print(f"     Price: {order.get('price', 'MARKET')}")
                print(f"     Time: {order.get('order_timestamp')}")
        else:
            print("   No orders found for today")
            print("   (This is normal if you haven't placed any orders today)")
        
        # Filter active orders
        print("\n4. Filtering active orders:")
        active_statuses = ['OPEN', 'TRIGGER PENDING', 'OPEN PENDING', 'VALIDATION PENDING', 'MODIFY PENDING']
        active_orders = [order for order in all_orders if order.get('status') in active_statuses]
        
        print(f"   Active orders: {len(active_orders)}")
        
        if active_orders:
            print("\n   Active Order Details:")
            for order in active_orders:
                print(f"\n     Order ID: {order.get('order_id')}")
                print(f"     Symbol: {order.get('tradingsymbol')}")
                print(f"     Status: {order.get('status')}")
                print(f"     Type: {order.get('transaction_type')}")
                print(f"     Filled: {order.get('filled_quantity')}/{order.get('quantity')}")
        else:
            print("   No active orders")
            print("   (All orders are either completed, cancelled, or rejected)")
        
        print("\n5. Testing order history (if orders exist):")
        if all_orders and len(all_orders) > 0:
            first_order_id = all_orders[0].get('order_id')
            try:
                history = kite.order_history(first_order_id)
                print(f"   Order {first_order_id} has {len(history)} status transitions:")
                for i, state in enumerate(history):
                    print(f"     {i+1}. {state.get('status')} at {state.get('order_timestamp')}")
            except Exception as e:
                print(f"   Error fetching history: {e}")
        
    except Exception as e:
        print(f"\n❌ Error fetching orders: {e}")
        return
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    
    print("\nSummary:")
    print(f"  ✅ Kite connection: Working")
    print(f"  📊 Total orders today: {len(all_orders)}")
    print(f"  🔄 Active orders: {len(active_orders)}")
    
    if len(active_orders) > 0:
        print("\n  ⚠️ You have active orders that will show in the UI!")
    else:
        print("\n  ℹ️ No active orders. Place an order in Kite to see it in the UI.")
    
    return {
        "success": True,
        "total_orders": len(all_orders),
        "active_orders": len(active_orders),
        "orders": all_orders
    }

if __name__ == "__main__":
    result = test_kite_orders()