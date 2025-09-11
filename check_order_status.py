"""
Check and update order status from Kite
This script checks the actual status of orders placed via Kite API
"""
import sqlite3
from datetime import datetime
from kiteconnect import KiteConnect
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KiteOrderStatusChecker:
    def __init__(self):
        self.api_key = os.getenv('KITE_API_KEY')
        self.access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not self.api_key or not self.access_token:
            raise ValueError("Kite API credentials not found")
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
    
    def get_order_status(self, order_id: str) -> dict:
        """Get the current status of an order from Kite"""
        try:
            orders = self.kite.orders()
            for order in orders:
                if str(order['order_id']) == str(order_id):
                    return {
                        'status': order['status'],  # COMPLETE, OPEN, CANCELLED, REJECTED, etc.
                        'filled_quantity': order.get('filled_quantity', 0),
                        'pending_quantity': order.get('pending_quantity', 0),
                        'average_price': order.get('average_price', 0),
                        'exchange_order_id': order.get('exchange_order_id'),
                        'status_message': order.get('status_message', '')
                    }
            return {'status': 'NOT_FOUND', 'status_message': 'Order ID not found'}
        except Exception as e:
            logger.error(f"Error fetching order status: {e}")
            return {'status': 'ERROR', 'status_message': str(e)}
    
    def update_order_tracking_status(self):
        """Update OrderTracking table with actual order status from Kite"""
        conn = sqlite3.connect('data/trading_settings.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all pending/open orders that need status check
        cursor.execute("""
            SELECT * FROM OrderTracking 
            WHERE status IN ('pending', 'open') 
            AND (main_order_id IS NOT NULL OR hedge_order_id IS NOT NULL)
            ORDER BY entry_time DESC
        """)
        
        orders = cursor.fetchall()
        
        if not orders:
            logger.info("No pending/open orders to check")
            return
        
        logger.info(f"Checking status for {len(orders)} orders...")
        
        for order in orders:
            webhook_id = order['webhook_id']
            main_order_id = order['main_order_id']
            hedge_order_id = order['hedge_order_id']
            current_status = order['status']
            
            logger.info(f"\nChecking order {webhook_id}:")
            
            # Check main order status
            main_status = None
            if main_order_id:
                main_info = self.get_order_status(main_order_id)
                main_status = main_info['status']
                logger.info(f"  Main order {main_order_id}: {main_status}")
                
                # Update price if filled
                if main_status == 'COMPLETE' and main_info.get('average_price'):
                    cursor.execute("""
                        UPDATE OrderTracking 
                        SET entry_price_main = ? 
                        WHERE webhook_id = ?
                    """, (main_info['average_price'], webhook_id))
            
            # Check hedge order status
            hedge_status = None
            if hedge_order_id:
                hedge_info = self.get_order_status(hedge_order_id)
                hedge_status = hedge_info['status']
                logger.info(f"  Hedge order {hedge_order_id}: {hedge_status}")
                
                # Update price if filled
                if hedge_status == 'COMPLETE' and hedge_info.get('average_price'):
                    cursor.execute("""
                        UPDATE OrderTracking 
                        SET entry_price_hedge = ? 
                        WHERE webhook_id = ?
                    """, (hedge_info['average_price'], webhook_id))
            
            # Determine overall position status
            new_status = current_status
            
            # Both orders must be complete for position to be 'open'
            if main_status and hedge_status:
                if main_status == 'COMPLETE' and hedge_status == 'COMPLETE':
                    new_status = 'open'
                    logger.info(f"  ✅ Both orders filled - Position OPEN")
                elif main_status in ['CANCELLED', 'REJECTED'] or hedge_status in ['CANCELLED', 'REJECTED']:
                    new_status = 'failed'
                    failure_reason = []
                    if main_status in ['CANCELLED', 'REJECTED']:
                        failure_reason.append(f"Main: {main_status}")
                    if hedge_status in ['CANCELLED', 'REJECTED']:
                        failure_reason.append(f"Hedge: {hedge_status}")
                    
                    cursor.execute("""
                        UPDATE OrderTracking 
                        SET exit_reason = ? 
                        WHERE webhook_id = ?
                    """, (', '.join(failure_reason), webhook_id))
                    logger.info(f"  ❌ Order failed: {', '.join(failure_reason)}")
                elif main_status in ['OPEN', 'PENDING'] or hedge_status in ['OPEN', 'PENDING']:
                    new_status = 'pending'
                    logger.info(f"  ⏳ Orders still pending")
            
            # Update status if changed
            if new_status != current_status:
                cursor.execute("""
                    UPDATE OrderTracking 
                    SET status = ?, updated_at = ? 
                    WHERE webhook_id = ?
                """, (new_status, datetime.now().isoformat(), webhook_id))
                logger.info(f"  Status updated: {current_status} -> {new_status}")
        
        conn.commit()
        conn.close()
        logger.info("\nOrder status check completed")
    
    def display_current_positions(self):
        """Display current positions from OrderTracking table"""
        conn = sqlite3.connect('data/trading_settings.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT webhook_id, signal, main_strike, option_type, status, 
                   entry_time, main_order_id, hedge_order_id,
                   entry_price_main, entry_price_hedge
            FROM OrderTracking 
            WHERE status IN ('pending', 'open')
            ORDER BY entry_time DESC
        """)
        
        positions = cursor.fetchall()
        
        print("\n" + "=" * 100)
        print("CURRENT POSITIONS (After Status Check)")
        print("=" * 100)
        
        for pos in positions:
            status_emoji = {
                'open': '✅',
                'pending': '⏳',
                'failed': '❌'
            }.get(pos['status'], '❓')
            
            print(f"\n{status_emoji} {pos['signal']} @ {pos['main_strike']} {pos['option_type']}")
            print(f"   Status: {pos['status'].upper()}")
            print(f"   Entry Time: {pos['entry_time']}")
            print(f"   Main Order: {pos['main_order_id']} (Price: {pos['entry_price_main'] or 'Pending'})")
            print(f"   Hedge Order: {pos['hedge_order_id']} (Price: {pos['entry_price_hedge'] or 'Pending'})")
        
        if not positions:
            print("\nNo active positions found")
        
        conn.close()

def main():
    """Main function to check and update order status"""
    try:
        checker = KiteOrderStatusChecker()
        
        # Update order status from Kite
        checker.update_order_tracking_status()
        
        # Display current positions
        checker.display_current_positions()
        
        # Option to continuously monitor
        print("\n" + "-" * 50)
        response = input("Monitor continuously? (y/n): ")
        
        if response.lower() == 'y':
            print("Starting continuous monitoring (Press Ctrl+C to stop)...")
            while True:
                time.sleep(30)  # Check every 30 seconds
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking order status...")
                checker.update_order_tracking_status()
                checker.display_current_positions()
                
    except KeyboardInterrupt:
        print("\nMonitoring stopped")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()