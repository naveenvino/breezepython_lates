"""
Test Order Status API Endpoints
Tests the new order tracking functionality
"""

import requests
import json
from datetime import datetime
import time

# API base URL
BASE_URL = "http://localhost:8000"

def test_get_all_orders():
    """Test fetching all orders"""
    print("\n1. Testing GET /orders - All Orders")
    print("-" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/orders")
        if response.status_code == 200:
            data = response.json()
            orders = data.get('orders', [])
            print(f"[SUCCESS] Retrieved {len(orders)} total orders")
            
            # Display first 3 orders if any
            for order in orders[:3]:
                print(f"  Order ID: {order.get('order_id')}")
                print(f"    Symbol: {order.get('tradingsymbol')}")
                print(f"    Status: {order.get('status')}")
                print(f"    Type: {order.get('transaction_type')}")
                print(f"    Qty: {order.get('filled_quantity')}/{order.get('quantity')}")
                print()
            
            return orders
        else:
            print(f"[FAIL] Status: {response.status_code}")
            print(f"  Error: {response.text}")
            return []
    except Exception as e:
        print(f"[ERROR] {e}")
        return []

def test_get_active_orders():
    """Test fetching only active orders"""
    print("\n2. Testing GET /api/orders/active - Active Orders Only")
    print("-" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/api/orders/active")
        if response.status_code == 200:
            data = response.json()
            orders = data.get('orders', [])
            count = data.get('count', 0)
            
            print(f"[SUCCESS] Found {count} active orders")
            
            # Display active orders
            for order in orders:
                status = order.get('status')
                color = order.get('status_color')
                print(f"  Order ID: {order.get('order_id')}")
                print(f"    Symbol: {order.get('tradingsymbol')}")
                print(f"    Status: {status} (Color: {color})")
                print(f"    Type: {order.get('transaction_type')}")
                print(f"    Price: {order.get('price', 'MARKET')}")
                print(f"    Qty: {order.get('filled_quantity')}/{order.get('quantity')}")
                print(f"    Time: {order.get('order_timestamp')}")
                print()
            
            if count == 0:
                print("  No active orders found (this is normal outside market hours)")
            
            return orders
        else:
            print(f"[FAIL] Status: {response.status_code}")
            print(f"  Error: {response.text}")
            return []
    except Exception as e:
        print(f"[ERROR] {e}")
        return []

def test_get_order_history(order_id):
    """Test fetching specific order history"""
    print(f"\n3. Testing GET /api/orders/history/{order_id} - Order History")
    print("-" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/api/orders/history/{order_id}")
        if response.status_code == 200:
            data = response.json()
            current = data.get('current_status', {})
            history = data.get('history', [])
            transitions = data.get('status_transitions', 0)
            
            print(f"[SUCCESS] Order {order_id} has {transitions} status transitions")
            
            # Display current status
            if current:
                print(f"\n  Current Status:")
                print(f"    Status: {current.get('status')}")
                print(f"    Symbol: {current.get('tradingsymbol')}")
                print(f"    Filled: {current.get('filled_quantity')}/{current.get('quantity')}")
                print(f"    Price: {current.get('price', 'MARKET')}")
                print(f"    Message: {current.get('status_message', 'N/A')}")
            
            # Display status history
            print(f"\n  Status History:")
            for i, state in enumerate(history):
                timestamp = state.get('order_timestamp', state.get('exchange_update_timestamp', ''))
                print(f"    {i+1}. {state.get('status')} at {timestamp}")
            
            return data
        else:
            print(f"[FAIL] Status: {response.status_code}")
            print(f"  Error: {response.text}")
            return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None

def test_order_status_flow():
    """Monitor order status changes in real-time"""
    print("\n4. Testing Real-time Order Status Monitoring")
    print("-" * 50)
    print("This will poll active orders every 3 seconds for 15 seconds...")
    
    start_time = time.time()
    poll_count = 0
    
    while time.time() - start_time < 15:
        poll_count += 1
        print(f"\n  Poll #{poll_count} at {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            response = requests.get(f"{BASE_URL}/api/orders/active")
            if response.status_code == 200:
                data = response.json()
                count = data.get('count', 0)
                
                if count > 0:
                    print(f"    Active Orders: {count}")
                    for order in data.get('orders', []):
                        print(f"      {order.get('order_id')}: {order.get('status')} - {order.get('tradingsymbol')}")
                else:
                    print("    No active orders")
            else:
                print(f"    Error: {response.status_code}")
        except Exception as e:
            print(f"    Error: {e}")
        
        time.sleep(3)
    
    print("\n  Monitoring complete")

def main():
    """Run all tests"""
    print("="*60)
    print("ORDER STATUS API TEST SUITE")
    print("="*60)
    print(f"Testing at: {datetime.now()}")
    print(f"API URL: {BASE_URL}")
    
    # Test 1: Get all orders
    all_orders = test_get_all_orders()
    
    # Test 2: Get active orders
    active_orders = test_get_active_orders()
    
    # Test 3: Get order history (if we have any orders)
    if all_orders and len(all_orders) > 0:
        first_order_id = all_orders[0].get('order_id')
        if first_order_id:
            test_get_order_history(first_order_id)
    else:
        print("\n3. Skipping Order History Test - No orders available")
    
    # Test 4: Real-time monitoring
    test_order_status_flow()
    
    print("\n" + "="*60)
    print("TEST SUITE COMPLETE")
    print("="*60)
    
    # Summary
    print("\nSummary:")
    print(f"  Total Orders: {len(all_orders)}")
    print(f"  Active Orders: {len(active_orders)}")
    
    if len(active_orders) > 0:
        print("\n  Active Order Statuses:")
        status_counts = {}
        for order in active_orders:
            status = order.get('status', 'UNKNOWN')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            print(f"    {status}: {count}")
    
    print("\nNote: For best results, run this during market hours with some active orders")

if __name__ == "__main__":
    main()