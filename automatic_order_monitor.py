"""
Automatic Order Status Monitor
Runs in background and continuously checks pending orders
"""
import time
import threading
import logging
from datetime import datetime, timedelta
from check_order_status import KiteOrderStatusChecker
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutomaticOrderMonitor:
    def __init__(self, check_interval=30):
        """
        Initialize automatic order monitor
        
        Args:
            check_interval: Seconds between status checks (default 30)
        """
        self.check_interval = check_interval
        self.checker = KiteOrderStatusChecker()
        self.is_running = False
        self.monitor_thread = None
        
    def has_pending_orders(self):
        """Check if there are any pending orders in database"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM OrderTracking 
                WHERE status = 'pending'
            """)
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception as e:
            logger.error(f"Error checking pending orders: {e}")
            return False
    
    def monitor_loop(self):
        """Main monitoring loop"""
        logger.info(f"Order monitor started - checking every {self.check_interval} seconds")
        
        consecutive_no_pending = 0
        
        while self.is_running:
            try:
                if self.has_pending_orders():
                    logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Checking pending orders...")
                    self.checker.update_order_tracking_status()
                    consecutive_no_pending = 0
                else:
                    consecutive_no_pending += 1
                    
                    # Log less frequently when no pending orders
                    if consecutive_no_pending % 10 == 1:  # Every 5 minutes
                        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] No pending orders to check")
                
                # Sleep for interval
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(self.check_interval)
    
    def start(self):
        """Start the automatic monitoring"""
        if self.is_running:
            logger.warning("Monitor already running")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Automatic order monitoring started")
    
    def stop(self):
        """Stop the automatic monitoring"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Automatic order monitoring stopped")

# Global monitor instance
_monitor_instance = None

def get_order_monitor():
    """Get or create the global order monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = AutomaticOrderMonitor()
    return _monitor_instance

def start_automatic_monitoring(interval=30):
    """Start automatic order status monitoring"""
    monitor = get_order_monitor()
    monitor.check_interval = interval
    monitor.start()
    return monitor

def stop_automatic_monitoring():
    """Stop automatic order status monitoring"""
    monitor = get_order_monitor()
    monitor.stop()

if __name__ == "__main__":
    # Test the automatic monitor
    print("Starting automatic order status monitor...")
    print("Press Ctrl+C to stop")
    
    monitor = AutomaticOrderMonitor(check_interval=30)
    
    try:
        monitor.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.stop()
        print("Monitor stopped")