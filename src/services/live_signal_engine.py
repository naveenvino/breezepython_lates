"""
Live Signal Engine for Real-time Trading
Monitors market data and triggers signals S1-S8
"""

import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any
import asyncio
import json
from dataclasses import dataclass
from enum import Enum

# Import existing services
from src.domain.services.signal_evaluator import SignalEvaluator
from src.domain.services.weekly_context_manager import WeeklyContextManager
from src.services.breeze_websocket_live import get_breeze_websocket
from src.services.kite_order_manager import get_kite_manager

logger = logging.getLogger(__name__)

class SignalStatus(Enum):
    MONITORING = "monitoring"
    TRIGGERED = "triggered"
    EXECUTED = "executed"
    STOPPED = "stopped"
    EXPIRED = "expired"

@dataclass
class LiveSignal:
    """Represents a live trading signal"""
    signal_type: str  # S1-S8
    strike_price: int
    option_type: str  # CE or PE
    trigger_time: datetime
    confidence: float
    status: SignalStatus
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    order_info: Optional[Dict] = None

class LiveSignalEngine:
    """Monitors and executes trading signals in real-time"""
    
    def __init__(self, mode: str = "paper"):
        """
        Initialize signal engine
        
        Args:
            mode: 'paper' or 'live'
        """
        self.mode = mode
        self.is_running = False
        
        # Services
        self.signal_evaluator = SignalEvaluator()
        self.context_manager = WeeklyContextManager()
        self.breeze_ws = get_breeze_websocket()
        self.kite_manager = get_kite_manager() if mode == "live" else None
        
        # Signal tracking
        self.active_signals: List[LiveSignal] = []
        self.triggered_signals: List[LiveSignal] = []
        self.signal_history = []
        
        # Market data
        self.current_candle = None
        self.previous_candle = None
        self.hourly_candles = []
        self.spot_price = None
        
        # Trading parameters
        self.signals_to_monitor = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
        self.max_positions = 3
        self.entry_time = time(11, 15)  # 11:15 AM
        self.market_open = time(9, 15)
        self.market_close = time(15, 30)
        self.square_off_time = time(15, 15)
        
        # Monitoring
        self.last_check = None
        self.monitoring_task = None
        
    async def start(self):
        """Start signal monitoring"""
        if self.is_running:
            logger.warning("Signal engine already running")
            return
        
        logger.info(f"Starting signal engine in {self.mode} mode")
        
        # Connect to data feed
        if not self.breeze_ws.is_connected:
            self.breeze_ws.connect()
        
        # Connect to Kite if live mode
        if self.mode == "live" and self.kite_manager:
            if not self.kite_manager.is_connected:
                logger.warning("Kite not connected for live trading")
        
        # Load weekly context
        await self._load_weekly_context()
        
        # Register data callback
        self.breeze_ws.register_callback(self._on_market_data)
        
        # Start monitoring
        self.is_running = True
        self.monitoring_task = asyncio.create_task(self._monitor_signals())
        
        logger.info("Signal engine started successfully")
    
    async def stop(self):
        """Stop signal monitoring"""
        if not self.is_running:
            return
        
        logger.info("Stopping signal engine")
        
        self.is_running = False
        
        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        # Square off all positions if live
        if self.mode == "live" and self.kite_manager:
            self.kite_manager.square_off_all()
        
        logger.info("Signal engine stopped")
    
    async def _monitor_signals(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                current_time = datetime.now().time()
                
                # Check if market is open
                if not self._is_market_open(current_time):
                    await asyncio.sleep(60)
                    continue
                
                # Check for square off time
                if current_time >= self.square_off_time:
                    await self._square_off_all()
                    await asyncio.sleep(60)
                    continue
                
                # Build hourly candle
                await self._build_hourly_candle()
                
                # Check for signal triggers at 11:15
                if current_time.hour == 11 and current_time.minute == 15:
                    await self._check_signals()
                
                # Monitor stop losses
                await self._monitor_stop_losses()
                
                # Sleep for 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
    
    async def _load_weekly_context(self):
        """Load weekly zones and bias"""
        try:
            # Get current week's Monday
            today = datetime.now()
            days_since_monday = today.weekday()
            monday = today - timedelta(days=days_since_monday)
            
            # Load zones from previous week
            zones = self.context_manager.calculate_weekly_zones(
                monday - timedelta(weeks=1)
            )
            
            # Calculate bias
            bias = self.context_manager.calculate_weekly_bias(
                monday - timedelta(weeks=1)
            )
            
            self.weekly_zones = zones
            self.weekly_bias = bias
            
            logger.info(f"Loaded weekly context - Bias: {bias}")
            logger.info(f"Support: {zones.lower_zone_bottom}-{zones.lower_zone_top}")
            logger.info(f"Resistance: {zones.upper_zone_bottom}-{zones.upper_zone_top}")
            
        except Exception as e:
            logger.error(f"Failed to load weekly context: {e}")
    
    async def _build_hourly_candle(self):
        """Build current hourly candle from tick data"""
        try:
            current_time = datetime.now()
            hour_start = current_time.replace(minute=0, second=0, microsecond=0)
            
            # Get spot price
            self.spot_price = self.breeze_ws.get_spot_price()
            
            if not self.spot_price:
                return
            
            # Create/update current candle
            if not self.current_candle or self.current_candle['timestamp'] != hour_start:
                # New hour, save previous candle
                if self.current_candle:
                    self.previous_candle = self.current_candle
                    self.hourly_candles.append(self.current_candle)
                
                # Start new candle
                self.current_candle = {
                    'timestamp': hour_start,
                    'open': self.spot_price,
                    'high': self.spot_price,
                    'low': self.spot_price,
                    'close': self.spot_price
                }
            else:
                # Update current candle
                self.current_candle['high'] = max(self.current_candle['high'], self.spot_price)
                self.current_candle['low'] = min(self.current_candle['low'], self.spot_price)
                self.current_candle['close'] = self.spot_price
            
        except Exception as e:
            logger.error(f"Error building candle: {e}")
    
    async def _check_signals(self):
        """Check for signal triggers"""
        if not self.previous_candle or not self.current_candle:
            logger.info("Not enough candle data for signal evaluation")
            return
        
        if not self.weekly_zones or not self.weekly_bias:
            logger.warning("Weekly context not loaded")
            return
        
        logger.info("Checking for signal triggers at 11:15")
        
        # Evaluate each signal type
        for signal_type in self.signals_to_monitor:
            try:
                result = self.signal_evaluator.evaluate_signal(
                    signal_type=signal_type,
                    first_bar=self.previous_candle,
                    second_bar=self.current_candle,
                    zones=self.weekly_zones,
                    weekly_bias=self.weekly_bias
                )
                
                if result and result.triggered:
                    logger.info(f"Signal {signal_type} triggered!")
                    
                    # Create live signal
                    live_signal = LiveSignal(
                        signal_type=signal_type,
                        strike_price=result.strike_price,
                        option_type=result.option_type,
                        trigger_time=datetime.now(),
                        confidence=result.confidence or 0.75,
                        status=SignalStatus.TRIGGERED,
                        stop_loss=result.stop_loss
                    )
                    
                    self.triggered_signals.append(live_signal)
                    
                    # Execute trade
                    await self._execute_signal(live_signal)
                    
                    # Only take first signal
                    break
                    
            except Exception as e:
                logger.error(f"Error evaluating signal {signal_type}: {e}")
    
    async def _execute_signal(self, signal: LiveSignal):
        """Execute a triggered signal"""
        try:
            # Check position limits
            active_count = len([s for s in self.active_signals if s.status == SignalStatus.EXECUTED])
            if active_count >= self.max_positions:
                logger.warning(f"Max positions reached ({self.max_positions})")
                signal.status = SignalStatus.EXPIRED
                return
            
            if self.mode == "paper":
                # Paper trading
                logger.info(f"PAPER TRADE: {signal.signal_type}")
                logger.info(f"  Strike: {signal.strike_price} {signal.option_type}")
                logger.info(f"  Stop Loss: {signal.stop_loss}")
                
                # Simulate order
                signal.order_info = {
                    'mode': 'paper',
                    'executed_at': datetime.now().isoformat(),
                    'strike': signal.strike_price,
                    'type': signal.option_type
                }
                signal.status = SignalStatus.EXECUTED
                
            else:
                # Live trading
                logger.info(f"LIVE TRADE: Executing {signal.signal_type}")
                
                result = self.kite_manager.place_hedge_basket(
                    signal_type=signal.signal_type,
                    strike=signal.strike_price,
                    option_type=signal.option_type
                )
                
                if result['status'] == 'success':
                    signal.order_info = result['order_info']
                    signal.status = SignalStatus.EXECUTED
                    logger.info(f"Trade executed successfully: {result['order_ids']}")
                else:
                    logger.error(f"Trade execution failed: {result['message']}")
                    signal.status = SignalStatus.EXPIRED
            
            self.active_signals.append(signal)
            
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            signal.status = SignalStatus.EXPIRED
    
    async def _monitor_stop_losses(self):
        """Monitor stop losses for active positions"""
        if not self.spot_price:
            return
        
        for signal in self.active_signals:
            if signal.status != SignalStatus.EXECUTED:
                continue
            
            # Check if stop loss hit (spot reaches strike)
            if signal.stop_loss and self.spot_price >= signal.strike_price:
                logger.warning(f"Stop loss hit for {signal.signal_type}")
                
                if self.mode == "paper":
                    logger.info(f"PAPER: Closing position at stop loss")
                    signal.status = SignalStatus.STOPPED
                else:
                    # Square off position
                    result = self.kite_manager.square_off_position(signal.signal_type)
                    if result['status'] == 'success':
                        signal.status = SignalStatus.STOPPED
                        logger.info(f"Position squared off at stop loss")
    
    async def _square_off_all(self):
        """Square off all positions at end of day"""
        logger.info("Square off time reached - closing all positions")
        
        for signal in self.active_signals:
            if signal.status == SignalStatus.EXECUTED:
                if self.mode == "paper":
                    logger.info(f"PAPER: Squaring off {signal.signal_type}")
                    signal.status = SignalStatus.EXPIRED
                else:
                    result = self.kite_manager.square_off_position(signal.signal_type)
                    if result['status'] == 'success':
                        signal.status = SignalStatus.EXPIRED
                        logger.info(f"Squared off {signal.signal_type}")
    
    def _on_market_data(self, tick):
        """Handle incoming market data"""
        # Update spot price if NIFTY tick
        if tick.get('symbol') == 'NIFTY':
            self.spot_price = tick['ltp']
    
    def _is_market_open(self, current_time: time) -> bool:
        """Check if market is open"""
        return self.market_open <= current_time <= self.market_close
    
    def get_status(self) -> Dict:
        """Get engine status"""
        return {
            'running': self.is_running,
            'mode': self.mode,
            'spot_price': self.spot_price,
            'active_signals': len(self.active_signals),
            'triggered_today': len(self.triggered_signals),
            'weekly_bias': self.weekly_bias,
            'last_check': self.last_check.isoformat() if self.last_check else None
        }
    
    def get_active_signals(self) -> List[Dict]:
        """Get active signals"""
        return [
            {
                'signal_type': s.signal_type,
                'strike': s.strike_price,
                'option_type': s.option_type,
                'status': s.status.value,
                'trigger_time': s.trigger_time.isoformat()
            }
            for s in self.active_signals
        ]

# Global instance
_signal_engine = None

def get_signal_engine(mode: str = "paper") -> LiveSignalEngine:
    """Get or create signal engine instance"""
    global _signal_engine
    if _signal_engine is None:
        _signal_engine = LiveSignalEngine(mode)
    return _signal_engine

async def start_signal_monitoring(mode: str = "paper"):
    """Start signal monitoring"""
    engine = get_signal_engine(mode)
    await engine.start()

async def stop_signal_monitoring():
    """Stop signal monitoring"""
    engine = get_signal_engine()
    await engine.stop()

if __name__ == "__main__":
    # Test the signal engine
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        engine = get_signal_engine("paper")
        await engine.start()
        
        # Run for 60 seconds
        await asyncio.sleep(60)
        
        # Get status
        print(f"Status: {engine.get_status()}")
        
        await engine.stop()
    
    asyncio.run(test())