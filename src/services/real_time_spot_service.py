"""
Real-Time Spot Price Service with Hourly Bar Aggregation
Critical for signal evaluation which ONLY uses closed hourly bars
"""

import os
import logging
import asyncio
from datetime import datetime, time, timedelta
from typing import Optional, Dict, List, Callable, Any
from collections import deque
import statistics
import threading

logger = logging.getLogger(__name__)

class HourlyBar:
    """Represents an hourly OHLC bar for signal evaluation"""
    
    def __init__(self, timestamp: datetime):
        self.timestamp = timestamp.replace(minute=0, second=0, microsecond=0)
        self.hour = timestamp.hour
        self.open = None
        self.high = None
        self.low = None
        self.close = None
        self.volume = 0
        self.tick_count = 0
        self.is_complete = False
        
    def update(self, price: float):
        """Update bar with new price tick"""
        if self.open is None:
            self.open = price
        
        if self.high is None or price > self.high:
            self.high = price
            
        if self.low is None or price < self.low:
            self.low = price
            
        self.close = price
        self.tick_count += 1
        
    def to_dict(self) -> Dict:
        """Convert to dictionary format for signal evaluation"""
        return {
            'timestamp': self.timestamp,
            'hour': self.hour,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'tick_count': self.tick_count,
            'is_complete': self.is_complete
        }

class RealTimeSpotService:
    """
    Service for real-time spot price with hourly bar aggregation
    CRITICAL: Signals are evaluated ONLY on closed hourly bars
    """
    
    def __init__(self):
        self.breeze = None
        self.spot_price = None
        self.last_update = None
        self.connected = False
        
        # Hourly bar management
        self.current_bar = None
        self.completed_bars = deque(maxlen=168)  # Keep 1 week of hourly bars
        self.tick_buffer = deque(maxlen=3600)  # Buffer for 1 hour of ticks
        
        # Callbacks
        self.tick_callbacks = []  # Called on every tick
        self.bar_callbacks = []   # Called on hourly bar completion (for signals)
        
        # Price validation
        self.min_valid_price = 15000  # NIFTY unlikely below this
        self.max_valid_price = 35000  # NIFTY unlikely above this
        self.last_valid_price = None
        
        # Threading
        self.is_running = False
        self.update_thread = None
        self._lock = threading.Lock()
        
    def connect(self):
        """Connect to Breeze WebSocket for real-time data"""
        try:
            # We use WebSocket for real-time data, not direct API
            from src.services.breeze_websocket_live import get_breeze_websocket
            ws = get_breeze_websocket()
            
            # Register our callback for spot price updates
            def on_spot_update(data):
                if data.get('type') == 'spot' and data.get('price'):
                    self.update_spot_price(data['price'])
                    
            ws.add_callback(on_spot_update)
            
            if not ws.is_connected:
                ws.connect()
                
            self.connected = True
            logger.info("Connected to Breeze WebSocket for real-time spot prices")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Breeze WebSocket: {e}")
            return False
    
    def update_spot_price(self, price: float, timestamp: Optional[datetime] = None):
        """
        Update spot price and manage hourly bars
        This is called by WebSocket on every tick
        """
        with self._lock:
            # Validate price
            if not self._validate_price(price):
                logger.warning(f"Invalid spot price rejected: {price}")
                return
                
            timestamp = timestamp or datetime.now()
            
            # Update current spot
            self.spot_price = price
            self.last_valid_price = price
            self.last_update = timestamp
            
            # Add to tick buffer
            self.tick_buffer.append({
                'timestamp': timestamp,
                'price': price
            })
            
            # Update or create hourly bar
            current_hour = timestamp.hour
            
            if self.current_bar is None:
                # Create first bar
                self.current_bar = HourlyBar(timestamp)
                self.current_bar.update(price)
                logger.info(f"Created new hourly bar for hour {current_hour:02d}:00")
                
            elif self.current_bar.hour != current_hour:
                # Hour changed - complete previous bar and create new one
                self._complete_current_bar()
                
                # Create new bar for current hour
                self.current_bar = HourlyBar(timestamp)
                self.current_bar.update(price)
                logger.info(f"Started new hourly bar for hour {current_hour:02d}:00")
                
            else:
                # Update current bar
                self.current_bar.update(price)
                
            # Notify tick callbacks
            for callback in self.tick_callbacks:
                try:
                    callback({
                        'timestamp': timestamp,
                        'price': price,
                        'current_bar': self.current_bar.to_dict() if self.current_bar else None
                    })
                except Exception as e:
                    logger.error(f"Tick callback error: {e}")
                    
    def _complete_current_bar(self):
        """
        Mark current bar as complete and notify signal evaluation callbacks
        THIS IS CRITICAL - Signals are ONLY evaluated on completed bars
        """
        if self.current_bar is None:
            return
            
        self.current_bar.is_complete = True
        completed_bar = self.current_bar.to_dict()
        
        # Add to completed bars history
        self.completed_bars.append(completed_bar)
        
        logger.info(f"Hourly bar completed: {self.current_bar.hour:02d}:00 "
                   f"O:{self.current_bar.open:.2f} H:{self.current_bar.high:.2f} "
                   f"L:{self.current_bar.low:.2f} C:{self.current_bar.close:.2f} "
                   f"Ticks:{self.current_bar.tick_count}")
        
        # Notify bar completion callbacks - THIS TRIGGERS SIGNAL EVALUATION
        for callback in self.bar_callbacks:
            try:
                callback(completed_bar)
            except Exception as e:
                logger.error(f"Bar callback error: {e}")
                
    def _validate_price(self, price: float) -> bool:
        """Validate if price is reasonable for NIFTY"""
        if price < self.min_valid_price or price > self.max_valid_price:
            return False
            
        # Check against last valid price if available
        if self.last_valid_price:
            # Reject if change is more than 5% (circuit breaker)
            change_pct = abs(price - self.last_valid_price) / self.last_valid_price
            if change_pct > 0.05:
                return False
                
        return True
    
    def get_spot_price(self) -> Optional[float]:
        """Get current NIFTY spot price"""
        return self.spot_price
    
    def get_current_bar(self) -> Optional[Dict]:
        """Get current (incomplete) hourly bar"""
        with self._lock:
            if self.current_bar:
                return self.current_bar.to_dict()
        return None
    
    def get_last_closed_bar(self) -> Optional[Dict]:
        """
        Get last completed hourly bar - USED FOR SIGNAL EVALUATION
        Signals are NEVER evaluated on incomplete bars
        """
        with self._lock:
            if self.completed_bars:
                return self.completed_bars[-1]
        return None
    
    def get_completed_bars(self, count: int = 24) -> List[Dict]:
        """Get recent completed hourly bars for analysis"""
        with self._lock:
            bars = list(self.completed_bars)
            return bars[-count:] if len(bars) > count else bars
    
    def add_tick_callback(self, callback: Callable):
        """Add callback for every tick update"""
        if callback not in self.tick_callbacks:
            self.tick_callbacks.append(callback)
            logger.info(f"Added tick callback: {callback.__name__}")
    
    def add_bar_callback(self, callback: Callable):
        """
        Add callback for completed hourly bars
        THIS IS USED FOR SIGNAL EVALUATION
        """
        if callback not in self.bar_callbacks:
            self.bar_callbacks.append(callback)
            logger.info(f"Added bar callback for signal evaluation: {callback.__name__}")
    
    def remove_tick_callback(self, callback: Callable):
        """Remove tick callback"""
        if callback in self.tick_callbacks:
            self.tick_callbacks.remove(callback)
    
    def remove_bar_callback(self, callback: Callable):
        """Remove bar callback"""
        if callback in self.bar_callbacks:
            self.bar_callbacks.remove(callback)
    
    def start_real_time_updates(self, interval=1):
        """Start monitoring for hourly bar changes"""
        if self.is_running:
            return
            
        self.is_running = True
        
        def monitor_bars():
            """Monitor for hour changes to complete bars"""
            last_hour = datetime.now().hour
            
            while self.is_running:
                try:
                    current_time = datetime.now()
                    current_hour = current_time.hour
                    
                    # Check if hour has changed
                    if current_hour != last_hour:
                        with self._lock:
                            # Force complete the previous hour's bar
                            if self.current_bar and not self.current_bar.is_complete:
                                self._complete_current_bar()
                                
                                # Create new bar for current hour if we have spot price
                                if self.spot_price:
                                    self.current_bar = HourlyBar(current_time)
                                    self.current_bar.update(self.spot_price)
                                    
                        last_hour = current_hour
                        
                    # Sleep until next check
                    threading.Event().wait(interval)
                    
                except Exception as e:
                    logger.error(f"Bar monitor error: {e}")
                    threading.Event().wait(5)
                    
        self.update_thread = threading.Thread(target=monitor_bars, daemon=True)
        self.update_thread.start()
        logger.info("Started hourly bar monitoring")
    
    def stop_real_time_updates(self):
        """Stop real-time updates"""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=2)
    
    def force_complete_bar(self):
        """Force complete current bar (for testing or EOD)"""
        with self._lock:
            if self.current_bar and not self.current_bar.is_complete:
                self._complete_current_bar()
                logger.info("Forced bar completion")
    
    def get_statistics(self) -> Dict:
        """Get service statistics"""
        with self._lock:
            return {
                'current_spot': self.spot_price,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'current_bar': self.get_current_bar(),
                'last_closed_bar': self.get_last_closed_bar(),
                'completed_bars_count': len(self.completed_bars),
                'tick_buffer_size': len(self.tick_buffer),
                'is_running': self.is_running,
                'connected': self.connected
            }
    
    def calculate_vwap(self, period_minutes: int = 60) -> Optional[float]:
        """Calculate VWAP for given period"""
        with self._lock:
            if not self.tick_buffer:
                return None
                
            cutoff = datetime.now() - timedelta(minutes=period_minutes)
            recent_ticks = [t for t in self.tick_buffer if t['timestamp'] > cutoff]
            
            if not recent_ticks:
                return None
                
            # Simple VWAP calculation
            total = sum(t['price'] for t in recent_ticks)
            return total / len(recent_ticks)
    
    def calculate_volatility(self, period_minutes: int = 60) -> Optional[float]:
        """Calculate price volatility for given period"""
        with self._lock:
            if not self.tick_buffer or len(self.tick_buffer) < 2:
                return None
                
            cutoff = datetime.now() - timedelta(minutes=period_minutes)
            recent_prices = [t['price'] for t in self.tick_buffer if t['timestamp'] > cutoff]
            
            if len(recent_prices) < 2:
                return None
                
            return statistics.stdev(recent_prices)
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now()
        
        # Check if weekday
        if now.weekday() > 4:  # Saturday = 5, Sunday = 6
            return False
            
        # Check market hours (9:15 AM to 3:30 PM)
        market_open = time(9, 15)
        market_close = time(15, 30)
        
        return market_open <= now.time() <= market_close
    
    def get_option_chain_real(self, strikes: int = 20) -> Dict:
        """Get option chain data from WebSocket"""
        try:
            from src.services.breeze_websocket_live import get_breeze_websocket
            ws = get_breeze_websocket()
            
            # Get option chain snapshot from WebSocket
            return ws.get_option_chain_snapshot()
            
        except Exception as e:
            logger.error(f"Failed to get option chain: {e}")
            return {}

# Global instance
_spot_service = None

def get_spot_service() -> RealTimeSpotService:
    """Get or create spot service instance"""
    global _spot_service
    if _spot_service is None:
        _spot_service = RealTimeSpotService()
        _spot_service.connect()
        _spot_service.start_real_time_updates()
    return _spot_service

def register_signal_evaluator():
    """Register signal evaluator to receive completed hourly bars"""
    from src.domain.services.signal_evaluator import SignalEvaluator
    from src.domain.services.weekly_context_manager import WeeklyContextManager
    
    spot_service = get_spot_service()
    evaluator = SignalEvaluator()
    context_mgr = WeeklyContextManager()
    
    def on_bar_complete(bar: Dict):
        """Called when hourly bar completes - evaluate all signals"""
        try:
            logger.info(f"Evaluating signals for completed bar at {bar['timestamp']}")
            
            # Get weekly context
            context = context_mgr.get_current_context()
            if not context:
                logger.warning("No weekly context available for signal evaluation")
                return
                
            # Evaluate each signal type
            for signal_type in ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']:
                result = evaluator.evaluate_signal(signal_type, bar, context)
                
                if result and result.get('triggered'):
                    logger.info(f"Signal {signal_type} triggered at {bar['close']:.2f}")
                    # Signal would be processed by trading engine
                    
        except Exception as e:
            logger.error(f"Signal evaluation error: {e}")
            
    # Register the callback
    spot_service.add_bar_callback(on_bar_complete)
    logger.info("Signal evaluator registered for hourly bar completion")