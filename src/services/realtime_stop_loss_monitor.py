"""
Real-time Stop Loss Monitoring Service
Continuously monitors positions and triggers stop losses
"""

import threading
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RealtimeStopLossMonitor:
    """Monitors positions in real-time and triggers stop losses"""
    
    def __init__(self):
        self.monitoring_thread = None
        self.is_running = False
        self.monitoring_interval = 30  # seconds
        self.last_check = {}
        
    def start_monitoring(self):
        """Start the real-time monitoring thread"""
        if self.is_running:
            logger.info("Monitoring already running")
            return
            
        self.is_running = True
        self.monitoring_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Real-time stop loss monitoring started")
        
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Real-time stop loss monitoring stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop that runs continuously"""
        logger.info("Starting continuous monitoring loop")

        while self.is_running:
            try:
                # Import here to avoid circular imports
                from src.services.hybrid_data_manager import get_hybrid_data_manager
                from src.services.live_stoploss_monitor import get_live_stoploss_monitor
                from src.services.kite_market_data_service import KiteMarketDataService

                data_manager = get_hybrid_data_manager()
                monitor = get_live_stoploss_monitor()
                # Initialize Kite market data service
                kite_service = KiteMarketDataService()
                
                # Get all active positions
                positions = list(data_manager.memory_cache.get('active_positions', {}).values())
                
                if positions:
                    logger.debug(f"Monitoring {len(positions)} active positions")
                    
                    for position in positions:
                        try:
                            # Skip if checked recently (within 10 seconds)
                            position_id = position.id
                            if position_id in self.last_check:
                                if (datetime.now() - self.last_check[position_id]).seconds < 10:
                                    continue
                            
                            # Fetch current option prices
                            main_price = self._fetch_option_price(
                                kite_service,
                                position.main_strike,
                                position.main_type
                            )

                            hedge_price = 0
                            if position.hedge_quantity > 0:
                                hedge_price = self._fetch_option_price(
                                    kite_service,
                                    position.hedge_strike,
                                    position.hedge_type
                                )
                            
                            # Update prices in monitor
                            if main_price > 0:
                                monitor.update_option_prices(
                                    position_id,
                                    main_price,
                                    hedge_price
                                )
                                
                                # Calculate P&L
                                main_pnl = (position.main_entry_price - main_price) * position.main_quantity
                                hedge_pnl = 0
                                if hedge_price > 0:
                                    hedge_pnl = (hedge_price - position.hedge_entry_price) * position.hedge_quantity
                                
                                net_pnl = main_pnl + hedge_pnl
                                pnl_percent = (net_pnl / (position.main_entry_price * position.main_quantity)) * 100
                                
                                logger.info(f"Position {position_id}: Net P&L = ₹{net_pnl:.2f} ({pnl_percent:.2f}%)")
                                
                                # Force check all stop losses
                                monitor.check_position_now(position_id)
                                
                            self.last_check[position_id] = datetime.now()
                            
                        except Exception as e:
                            logger.error(f"Error monitoring position {position.id}: {e}")
                            
                # Sleep for monitoring interval
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)  # Brief pause on error
                
        logger.info("Monitoring loop stopped")
        
    def _fetch_option_price(self, kite_service, strike: int, option_type: str) -> float:
        """Fetch current option price from Kite"""
        try:
            # Get current expiry (next Thursday for weekly)
            from datetime import datetime
            today = datetime.now()
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0 and today.hour >= 15:  # After 3:30 PM on Thursday
                days_until_thursday = 7
            expiry = today + timedelta(days=days_until_thursday)

            # Format symbol for Kite (e.g., NFO:NIFTY24DEC25000CE)
            symbol = f"NFO:NIFTY{expiry.strftime('%y%b').upper()}{strike}{option_type[0]}E"

            # Fetch LTP from Kite
            ltp_data = kite_service.get_ltp([symbol])
            if symbol in ltp_data:
                ltp = ltp_data[symbol]
                logger.debug(f"Fetched {symbol} price from Kite: ₹{ltp}")
                return ltp
            else:
                logger.warning(f"No price data for {symbol}")
                return 0
                
        except Exception as e:
            logger.error(f"Error fetching option price for {strike}{option_type}: {e}")
            
        return 0
        
    def update_monitoring_interval(self, seconds: int):
        """Update the monitoring interval"""
        self.monitoring_interval = max(10, min(300, seconds))  # Between 10s and 5min
        logger.info(f"Monitoring interval updated to {self.monitoring_interval} seconds")

# Singleton instance
_realtime_monitor = None

def get_realtime_monitor() -> RealtimeStopLossMonitor:
    """Get singleton instance of realtime monitor"""
    global _realtime_monitor
    if _realtime_monitor is None:
        _realtime_monitor = RealtimeStopLossMonitor()
    return _realtime_monitor

def start_realtime_monitoring():
    """Convenience function to start monitoring"""
    monitor = get_realtime_monitor()
    monitor.start_monitoring()
    return monitor

def stop_realtime_monitoring():
    """Convenience function to stop monitoring"""
    monitor = get_realtime_monitor()
    monitor.stop_monitoring()