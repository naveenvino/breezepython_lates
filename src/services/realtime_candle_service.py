"""
Realtime Candle Service
Forms hourly candles from live WebSocket data and triggers stop loss checks
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Callable, List, Dict, Any
import threading

from src.services.hybrid_data_manager import get_hybrid_data_manager, HourlyCandle
from src.services.breeze_websocket_live import get_breeze_websocket

logger = logging.getLogger(__name__)

class RealtimeCandleService:
    """
    Service for real-time hourly candle formation
    Connects to Breeze WebSocket for tick data
    """
    
    def __init__(self):
        self.data_manager = get_hybrid_data_manager()
        self.breeze_ws = get_breeze_websocket()
        self.is_running = False
        
        # Callbacks
        self.on_candle_complete: Optional[Callable[[HourlyCandle], None]] = None
        self.on_tick: Optional[Callable[[float, datetime], None]] = None
        self.on_stop_loss_check: Optional[Callable[[HourlyCandle], None]] = None
        
        # Market hours (IST)
        self.market_open = time(9, 15)
        self.market_close = time(15, 30)
        
        # Hourly checkpoints (when to close candles)
        self.hourly_checkpoints = [
            time(10, 15),  # Close 9:15-10:15 candle
            time(11, 15),  # Close 10:15-11:15 candle
            time(12, 15),  # Close 11:15-12:15 candle
            time(13, 15),  # Close 12:15-13:15 candle
            time(14, 15),  # Close 13:15-14:15 candle
            time(15, 15),  # Close 14:15-15:15 candle
            time(15, 30),  # Close 15:15-15:30 candle (end of day)
        ]
        
        self._lock = threading.Lock()
        self._monitoring_task = None
    
    def _on_spot_update(self, data: Dict[str, Any]):
        """Callback for spot price updates from WebSocket"""
        try:
            if data.get('type') == 'spot' and 'price' in data:
                price = float(data['price'])
                timestamp = datetime.now()
                
                # Validate price
                if not self._is_valid_price(price):
                    logger.warning(f"Invalid price received: {price}")
                    return
                
                # Update data manager
                self.data_manager.update_tick(price, timestamp)
                
                # Trigger tick callback
                if self.on_tick:
                    self.on_tick(price, timestamp)
                
                # Check if we need to complete a candle
                self._check_candle_completion(timestamp)
                
        except Exception as e:
            logger.error(f"Error processing spot update: {e}")
    
    def _is_valid_price(self, price: float) -> bool:
        """Validate if price is reasonable for NIFTY"""
        return 15000 <= price <= 35000
    
    def _check_candle_completion(self, timestamp: datetime):
        """Check if we need to complete current candle"""
        current_time = timestamp.time()
        
        # Check if we're at a checkpoint
        for checkpoint in self.hourly_checkpoints:
            # Allow 30 second window for candle completion
            checkpoint_dt = datetime.combine(timestamp.date(), checkpoint)
            time_diff = abs((timestamp - checkpoint_dt).total_seconds())
            
            if time_diff <= 30:  # Within 30 seconds of checkpoint
                self._complete_current_candle(timestamp)
                break
    
    def _complete_current_candle(self, timestamp: datetime):
        """Complete the current candle and trigger callbacks"""
        with self._lock:
            current_candle = self.data_manager.current_candle
            
            if current_candle and not current_candle.is_complete:
                # Mark candle as complete
                current_candle.is_complete = True
                
                # Trigger candle complete callback
                if self.on_candle_complete:
                    self.on_candle_complete(current_candle)
                
                # Trigger stop loss check
                if self.on_stop_loss_check:
                    self.on_stop_loss_check(current_candle)
                
                logger.info(f"Completed hourly candle at {timestamp}: "
                          f"O:{current_candle.open} H:{current_candle.high} "
                          f"L:{current_candle.low} C:{current_candle.close}")
                
                # Start new candle
                self.data_manager._complete_candle()
    
    async def start(self):
        """Start the realtime candle service"""
        if self.is_running:
            logger.warning("Realtime candle service already running")
            return
        
        self.is_running = True
        self.data_manager.start()
        
        # Connect to WebSocket
        if not self.breeze_ws.is_connected:
            self.breeze_ws.connect()
        
        # Register callback for spot updates
        self.breeze_ws.callbacks.append(self._on_spot_update)
        
        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitor_candles())
        
        logger.info("Realtime candle service started")
    
    async def stop(self):
        """Stop the realtime candle service"""
        self.is_running = False
        
        # Complete current candle if any
        if self.data_manager.current_candle:
            self._complete_current_candle(datetime.now())
        
        # Stop monitoring task
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Remove callback
        if self._on_spot_update in self.breeze_ws.callbacks:
            self.breeze_ws.callbacks.remove(self._on_spot_update)
        
        self.data_manager.stop()
        
        logger.info("Realtime candle service stopped")
    
    async def _monitor_candles(self):
        """Monitor for candle completion times"""
        while self.is_running:
            try:
                now = datetime.now()
                current_time = now.time()
                
                # Check if market is open
                if not self._is_market_open(current_time):
                    await asyncio.sleep(60)  # Check every minute when market closed
                    continue
                
                # Check for candle completion
                for checkpoint in self.hourly_checkpoints:
                    if self._is_near_checkpoint(current_time, checkpoint):
                        # Wait for exact time
                        wait_seconds = self._seconds_until(checkpoint)
                        if 0 < wait_seconds <= 60:
                            await asyncio.sleep(wait_seconds)
                            self._complete_current_candle(datetime.now())
                            break
                
                # Sleep for 30 seconds before next check
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in candle monitor: {e}")
                await asyncio.sleep(30)
    
    def _is_market_open(self, current_time: time) -> bool:
        """Check if market is open"""
        return self.market_open <= current_time <= self.market_close
    
    def _is_near_checkpoint(self, current_time: time, checkpoint: time) -> bool:
        """Check if we're near a checkpoint time"""
        current_minutes = current_time.hour * 60 + current_time.minute
        checkpoint_minutes = checkpoint.hour * 60 + checkpoint.minute
        diff = checkpoint_minutes - current_minutes
        return 0 < diff <= 2  # Within 2 minutes
    
    def _seconds_until(self, target_time: time) -> float:
        """Calculate seconds until target time"""
        now = datetime.now()
        target = datetime.combine(now.date(), target_time)
        
        if target < now:
            target += timedelta(days=1)
        
        return (target - now).total_seconds()
    
    def get_latest_candles(self, count: int = 24) -> List[Dict]:
        """Get latest hourly candles"""
        return self.data_manager.get_latest_candles(count)
    
    def get_current_spot(self) -> Optional[float]:
        """Get current NIFTY spot price"""
        return self.data_manager.memory_cache.get('spot_price')
    
    def force_candle_completion(self):
        """Force complete current candle (for testing)"""
        self._complete_current_candle(datetime.now())

# Singleton instance
_instance = None

def get_realtime_candle_service() -> RealtimeCandleService:
    """Get singleton instance of realtime candle service"""
    global _instance
    if _instance is None:
        _instance = RealtimeCandleService()
    return _instance