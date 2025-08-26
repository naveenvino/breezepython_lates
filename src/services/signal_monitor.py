"""
Automated Signal Monitoring Service
Monitors market conditions and generates trading signals in real-time
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
import pandas as pd
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class SignalType(Enum):
    S1 = "Bear Trap"  # Bullish
    S2 = "Support Hold"  # Bullish
    S3 = "Resistance Hold"  # Bearish
    S4 = "Bias Failure Bull"  # Bullish
    S5 = "Bias Failure Bear"  # Bearish
    S6 = "Weakness Confirmed"  # Bearish
    S7 = "Breakout Confirmed"  # Bullish
    S8 = "Breakdown Confirmed"  # Bearish

@dataclass
class Signal:
    signal_type: SignalType
    timestamp: datetime
    spot_price: float
    strike_price: int
    action: str  # "BUY" or "SELL"
    option_type: str  # "CE" or "PE"
    confidence: float
    reason: str

class SignalMonitor:
    """Real-time signal monitoring and generation"""
    
    def __init__(self, breeze_client=None):
        self.breeze_client = breeze_client
        self.signals: List[Signal] = []
        self.active_positions = {}
        self.market_data_buffer = []
        self.is_monitoring = False
        
        # Signal detection parameters
        self.support_levels = []
        self.resistance_levels = []
        self.last_signal_time = None
        self.min_signal_gap = 300  # 5 minutes between signals
        
    async def start_monitoring(self):
        """Start the signal monitoring service"""
        self.is_monitoring = True
        logger.info("Signal monitoring started")
        
        # Start parallel monitoring tasks
        tasks = [
            self._monitor_market_data(),
            self._detect_signals(),
            self._manage_positions()
        ]
        
        await asyncio.gather(*tasks)
        
    async def stop_monitoring(self):
        """Stop the signal monitoring service"""
        self.is_monitoring = False
        logger.info("Signal monitoring stopped")
        
    async def _monitor_market_data(self):
        """Continuously monitor market data"""
        while self.is_monitoring:
            try:
                # Get current market data
                spot_price = await self._get_spot_price()
                
                if spot_price:
                    self.market_data_buffer.append({
                        'timestamp': datetime.now(),
                        'spot_price': spot_price
                    })
                    
                    # Keep only last 100 data points
                    if len(self.market_data_buffer) > 100:
                        self.market_data_buffer.pop(0)
                        
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring market data: {e}")
                await asyncio.sleep(10)
                
    async def _detect_signals(self):
        """Detect trading signals based on market conditions"""
        while self.is_monitoring:
            try:
                if not self._is_market_open():
                    await asyncio.sleep(60)
                    continue
                    
                if len(self.market_data_buffer) < 10:
                    await asyncio.sleep(10)
                    continue
                    
                # Analyze recent price action
                df = pd.DataFrame(self.market_data_buffer)
                
                # Calculate technical indicators
                df['sma_5'] = df['spot_price'].rolling(5).mean()
                df['price_change'] = df['spot_price'].pct_change()
                
                current_price = df['spot_price'].iloc[-1]
                sma_5 = df['sma_5'].iloc[-1]
                
                # Detect signals
                signal = None
                
                # S1: Bear Trap (Bullish) - Price dips below support and recovers
                if self._check_bear_trap(df, current_price):
                    signal = self._create_signal(SignalType.S1, current_price, "SELL", "PE")
                    
                # S2: Support Hold (Bullish) - Price holds above support
                elif self._check_support_hold(df, current_price):
                    signal = self._create_signal(SignalType.S2, current_price, "SELL", "PE")
                    
                # S3: Resistance Hold (Bearish) - Price fails at resistance
                elif self._check_resistance_hold(df, current_price):
                    signal = self._create_signal(SignalType.S3, current_price, "SELL", "CE")
                    
                # S7: Breakout Confirmed (Bullish)
                elif self._check_breakout(df, current_price):
                    signal = self._create_signal(SignalType.S7, current_price, "SELL", "PE")
                    
                # S8: Breakdown Confirmed (Bearish)
                elif self._check_breakdown(df, current_price):
                    signal = self._create_signal(SignalType.S8, current_price, "SELL", "CE")
                    
                if signal and self._can_generate_signal():
                    await self._process_signal(signal)
                    
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error detecting signals: {e}")
                await asyncio.sleep(60)
                
    async def _manage_positions(self):
        """Manage active positions and stop losses"""
        while self.is_monitoring:
            try:
                if not self.active_positions:
                    await asyncio.sleep(30)
                    continue
                    
                current_price = await self._get_spot_price()
                
                for position_id, position in list(self.active_positions.items()):
                    # Check stop loss
                    if self._should_exit(position, current_price):
                        await self._exit_position(position_id)
                        
                    # Check target
                    elif self._target_reached(position, current_price):
                        await self._exit_position(position_id)
                        
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error managing positions: {e}")
                await asyncio.sleep(30)
                
    def _check_bear_trap(self, df: pd.DataFrame, current_price: float) -> bool:
        """Check for bear trap pattern"""
        if len(df) < 5:
            return False
            
        # Look for a dip and recovery
        min_price = df['spot_price'].iloc[-5:].min()
        recovery = (current_price - min_price) / min_price
        
        return recovery > 0.002 and current_price > df['sma_5'].iloc[-1]
        
    def _check_support_hold(self, df: pd.DataFrame, current_price: float) -> bool:
        """Check if price is holding above support"""
        if not self.support_levels:
            self._calculate_support_resistance(df)
            
        for support in self.support_levels:
            if abs(current_price - support) / support < 0.001:
                return True
        return False
        
    def _check_resistance_hold(self, df: pd.DataFrame, current_price: float) -> bool:
        """Check if price is failing at resistance"""
        if not self.resistance_levels:
            self._calculate_support_resistance(df)
            
        for resistance in self.resistance_levels:
            if abs(current_price - resistance) / resistance < 0.001:
                return True
        return False
        
    def _check_breakout(self, df: pd.DataFrame, current_price: float) -> bool:
        """Check for breakout above resistance"""
        if len(df) < 10:
            return False
            
        high_10 = df['spot_price'].iloc[-10:-1].max()
        return current_price > high_10 * 1.001
        
    def _check_breakdown(self, df: pd.DataFrame, current_price: float) -> bool:
        """Check for breakdown below support"""
        if len(df) < 10:
            return False
            
        low_10 = df['spot_price'].iloc[-10:-1].min()
        return current_price < low_10 * 0.999
        
    def _calculate_support_resistance(self, df: pd.DataFrame):
        """Calculate support and resistance levels"""
        if len(df) < 20:
            return
            
        prices = df['spot_price'].values
        
        # Simple pivot point calculation
        high = prices.max()
        low = prices.min()
        close = prices[-1]
        
        pivot = (high + low + close) / 3
        
        self.support_levels = [
            pivot - (high - low),  # S1
            pivot - 2 * (high - low)  # S2
        ]
        
        self.resistance_levels = [
            pivot + (high - low),  # R1
            pivot + 2 * (high - low)  # R2
        ]
        
    def _create_signal(self, signal_type: SignalType, spot_price: float, 
                      action: str, option_type: str) -> Signal:
        """Create a new signal"""
        strike_price = self._calculate_strike_price(spot_price, option_type)
        
        return Signal(
            signal_type=signal_type,
            timestamp=datetime.now(),
            spot_price=spot_price,
            strike_price=strike_price,
            action=action,
            option_type=option_type,
            confidence=0.7,  # Default confidence
            reason=f"{signal_type.value} pattern detected at {spot_price:.2f}"
        )
        
    def _calculate_strike_price(self, spot_price: float, option_type: str) -> int:
        """Calculate the appropriate strike price"""
        # Round to nearest 50
        base_strike = round(spot_price / 50) * 50
        
        if option_type == "CE":
            # For calls, use slightly OTM
            return base_strike + 50
        else:
            # For puts, use slightly OTM
            return base_strike - 50
            
    def _can_generate_signal(self) -> bool:
        """Check if we can generate a new signal"""
        if not self.last_signal_time:
            return True
            
        time_since_last = (datetime.now() - self.last_signal_time).seconds
        return time_since_last >= self.min_signal_gap
        
    async def _process_signal(self, signal: Signal):
        """Process and execute a signal"""
        logger.info(f"Signal generated: {signal.signal_type.name} at {signal.spot_price:.2f}")
        
        self.signals.append(signal)
        self.last_signal_time = datetime.now()
        
        # Send signal notification
        await self._send_signal_notification(signal)
        
        # Optionally execute trade
        if self._should_auto_trade(signal):
            await self._execute_trade(signal)
            
    async def _send_signal_notification(self, signal: Signal):
        """Send signal notification via WebSocket or other channels"""
        try:
            # This would send to connected WebSocket clients
            notification = {
                "type": "signal",
                "data": {
                    "signal_type": signal.signal_type.name,
                    "timestamp": signal.timestamp.isoformat(),
                    "spot_price": signal.spot_price,
                    "strike_price": signal.strike_price,
                    "action": signal.action,
                    "option_type": signal.option_type,
                    "confidence": signal.confidence,
                    "reason": signal.reason
                }
            }
            
            # Log for now, would send via WebSocket in production
            logger.info(f"Signal notification: {notification}")
            
        except Exception as e:
            logger.error(f"Error sending signal notification: {e}")
            
    def _should_auto_trade(self, signal: Signal) -> bool:
        """Determine if signal should be auto-traded"""
        # Check confidence threshold
        if signal.confidence < 0.8:
            return False
            
        # Check if we already have positions
        if len(self.active_positions) >= 3:
            return False
            
        return True
        
    async def _execute_trade(self, signal: Signal):
        """Execute trade based on signal"""
        try:
            # This would place actual orders
            logger.info(f"Executing trade for signal: {signal.signal_type.name}")
            
            # Add to active positions
            position_id = f"{signal.signal_type.name}_{datetime.now().timestamp()}"
            self.active_positions[position_id] = {
                'signal': signal,
                'entry_time': datetime.now(),
                'status': 'active'
            }
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            
    def _should_exit(self, position: dict, current_price: float) -> bool:
        """Check if position should be exited based on stop loss"""
        signal = position['signal']
        
        # Check stop loss
        if signal.option_type == "CE":
            # For call sells, exit if price goes above strike
            return current_price > signal.strike_price
        else:
            # For put sells, exit if price goes below strike
            return current_price < signal.strike_price
            
    def _target_reached(self, position: dict, current_price: float) -> bool:
        """Check if target is reached"""
        # Simple target: 2% move in favorable direction
        signal = position['signal']
        
        if signal.option_type == "CE":
            # For call sells, target when price drops
            return current_price < signal.spot_price * 0.98
        else:
            # For put sells, target when price rises
            return current_price > signal.spot_price * 1.02
            
    async def _exit_position(self, position_id: str):
        """Exit a position"""
        try:
            logger.info(f"Exiting position: {position_id}")
            
            # This would place exit orders
            position = self.active_positions.pop(position_id, None)
            
            if position:
                position['status'] = 'closed'
                position['exit_time'] = datetime.now()
                
        except Exception as e:
            logger.error(f"Error exiting position: {e}")
            
    async def _get_spot_price(self) -> Optional[float]:
        """Get current NIFTY spot price"""
        try:
            if self.breeze_client:
                # Get from Breeze
                response = self.breeze_client.get_quotes(
                    stock_code="NIFTY",
                    exchange_code="NSE"
                )
                if response.get('Success'):
                    return float(response['Success'][0]['ltp'])
                    
            # Fallback to last known price
            if self.market_data_buffer:
                return self.market_data_buffer[-1]['spot_price']
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting spot price: {e}")
            return None
            
    def _is_market_open(self) -> bool:
        """Check if market is open"""
        now = datetime.now()
        
        # Check if weekday
        if now.weekday() > 4:  # Saturday = 5, Sunday = 6
            return False
            
        # Check market hours (9:15 AM to 3:30 PM)
        market_open = time(9, 15)
        market_close = time(15, 30)
        
        return market_open <= now.time() <= market_close
        
    def get_active_signals(self) -> List[Signal]:
        """Get list of active signals"""
        # Return signals from last hour
        cutoff = datetime.now().timestamp() - 3600
        return [s for s in self.signals if s.timestamp.timestamp() > cutoff]
        
    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        total_signals = len(self.signals)
        active_positions = len(self.active_positions)
        
        # Calculate success rate
        successful = 0
        for signal in self.signals:
            # This would check actual trade outcomes
            successful += 1 if signal.confidence > 0.7 else 0
            
        success_rate = (successful / total_signals * 100) if total_signals > 0 else 0
        
        return {
            'total_signals': total_signals,
            'active_positions': active_positions,
            'success_rate': success_rate,
            'last_signal': self.signals[-1] if self.signals else None
        }

# Singleton instance
_signal_monitor = None

def get_signal_monitor(breeze_client=None) -> SignalMonitor:
    """Get or create signal monitor instance"""
    global _signal_monitor
    if _signal_monitor is None:
        _signal_monitor = SignalMonitor(breeze_client)
    return _signal_monitor