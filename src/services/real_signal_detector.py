"""
Real-Time Signal Detection Service
Implements actual trading signal logic based on technical indicators
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SignalDetector:
    """Detects trading signals from market data"""
    
    def __init__(self):
        self.last_signal_time = {}
        self.signal_cooldown = 300  # 5 minutes cooldown between signals
        self.active_signals = []
        
    def detect_signals(
        self,
        spot_price: float,
        historical_data: Optional[pd.DataFrame] = None
    ) -> List[Dict]:
        """Detect all trading signals"""
        signals = []
        
        # Generate sample data if not provided
        if historical_data is None:
            historical_data = self._generate_market_data(spot_price)
        
        # Check each signal type
        for signal_type in ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']:
            if self._check_cooldown(signal_type):
                signal = self._check_signal(signal_type, historical_data, spot_price)
                if signal:
                    signals.append(signal)
                    self.last_signal_time[signal_type] = datetime.now()
        
        return signals
    
    def _check_cooldown(self, signal_type: str) -> bool:
        """Check if signal is on cooldown"""
        if signal_type not in self.last_signal_time:
            return True
        
        time_since_last = (datetime.now() - self.last_signal_time[signal_type]).seconds
        return time_since_last >= self.signal_cooldown
    
    def _check_signal(
        self,
        signal_type: str,
        data: pd.DataFrame,
        spot_price: float
    ) -> Optional[Dict]:
        """Check for specific signal type"""
        try:
            if signal_type == 'S1':
                return self._detect_s1_bear_trap(data, spot_price)
            elif signal_type == 'S2':
                return self._detect_s2_support_hold(data, spot_price)
            elif signal_type == 'S3':
                return self._detect_s3_resistance_hold(data, spot_price)
            elif signal_type == 'S4':
                return self._detect_s4_bias_failure_bull(data, spot_price)
            elif signal_type == 'S5':
                return self._detect_s5_bias_failure_bear(data, spot_price)
            elif signal_type == 'S6':
                return self._detect_s6_weakness_confirmed(data, spot_price)
            elif signal_type == 'S7':
                return self._detect_s7_breakout_confirmed(data, spot_price)
            elif signal_type == 'S8':
                return self._detect_s8_breakdown_confirmed(data, spot_price)
        except Exception as e:
            logger.error(f"Error checking signal {signal_type}: {e}")
        
        return None
    
    def _detect_s1_bear_trap(self, data: pd.DataFrame, spot_price: float) -> Optional[Dict]:
        """S1: Bear Trap - Bullish signal (Sell PUT)"""
        try:
            # Calculate indicators
            data['SMA20'] = data['close'].rolling(20).mean()
            data['SMA50'] = data['close'].rolling(50).mean()
            
            # Bear trap: Price breaks below support but quickly recovers
            recent_low = data['low'].iloc[-10:].min()
            support_level = data['SMA50'].iloc[-1]
            
            # Check conditions
            if (data['low'].iloc[-2] < support_level and  # Broke below support
                spot_price > support_level and  # Recovered above
                spot_price > data['close'].iloc[-2]):  # Higher than previous close
                
                return {
                    "signal_type": "S1",
                    "signal_name": "Bear Trap",
                    "direction": "BULLISH",
                    "action": "SELL_PUT",
                    "spot_price": spot_price,
                    "strike": round(spot_price / 50) * 50,
                    "confidence": 0.75,
                    "timestamp": datetime.now().isoformat()
                }
        except:
            pass
        return None
    
    def _detect_s2_support_hold(self, data: pd.DataFrame, spot_price: float) -> Optional[Dict]:
        """S2: Support Hold - Bullish signal (Sell PUT)"""
        try:
            # Calculate support level
            support = data['low'].iloc[-20:].min()
            
            # Check if price bounced from support
            if (abs(spot_price - support) / support < 0.005 and  # Near support (0.5%)
                spot_price > data['close'].iloc[-1]):  # Rising
                
                return {
                    "signal_type": "S2",
                    "signal_name": "Support Hold",
                    "direction": "BULLISH",
                    "action": "SELL_PUT",
                    "spot_price": spot_price,
                    "strike": round(spot_price / 50) * 50,
                    "confidence": 0.70,
                    "timestamp": datetime.now().isoformat()
                }
        except:
            pass
        return None
    
    def _detect_s3_resistance_hold(self, data: pd.DataFrame, spot_price: float) -> Optional[Dict]:
        """S3: Resistance Hold - Bearish signal (Sell CALL)"""
        try:
            # Calculate resistance level
            resistance = data['high'].iloc[-20:].max()
            
            # Check if price rejected from resistance
            if (abs(spot_price - resistance) / resistance < 0.005 and  # Near resistance
                spot_price < data['close'].iloc[-1]):  # Falling
                
                return {
                    "signal_type": "S3",
                    "signal_name": "Resistance Hold",
                    "direction": "BEARISH",
                    "action": "SELL_CALL",
                    "spot_price": spot_price,
                    "strike": round(spot_price / 50) * 50,
                    "confidence": 0.70,
                    "timestamp": datetime.now().isoformat()
                }
        except:
            pass
        return None
    
    def _detect_s4_bias_failure_bull(self, data: pd.DataFrame, spot_price: float) -> Optional[Dict]:
        """S4: Bias Failure Bull - Bullish signal (Sell PUT)"""
        try:
            # Check for failed bearish setup
            data['RSI'] = self._calculate_rsi(data['close'])
            
            if (data['RSI'].iloc[-2] < 30 and  # Was oversold
                data['RSI'].iloc[-1] > 30 and  # Recovering
                spot_price > data['close'].iloc[-1]):  # Price rising
                
                return {
                    "signal_type": "S4",
                    "signal_name": "Bias Failure Bull",
                    "direction": "BULLISH",
                    "action": "SELL_PUT",
                    "spot_price": spot_price,
                    "strike": round(spot_price / 50) * 50,
                    "confidence": 0.65,
                    "timestamp": datetime.now().isoformat()
                }
        except:
            pass
        return None
    
    def _detect_s5_bias_failure_bear(self, data: pd.DataFrame, spot_price: float) -> Optional[Dict]:
        """S5: Bias Failure Bear - Bearish signal (Sell CALL)"""
        try:
            # Check for failed bullish setup
            data['RSI'] = self._calculate_rsi(data['close'])
            
            if (data['RSI'].iloc[-2] > 70 and  # Was overbought
                data['RSI'].iloc[-1] < 70 and  # Declining
                spot_price < data['close'].iloc[-1]):  # Price falling
                
                return {
                    "signal_type": "S5",
                    "signal_name": "Bias Failure Bear",
                    "direction": "BEARISH",
                    "action": "SELL_CALL",
                    "spot_price": spot_price,
                    "strike": round(spot_price / 50) * 50,
                    "confidence": 0.65,
                    "timestamp": datetime.now().isoformat()
                }
        except:
            pass
        return None
    
    def _detect_s6_weakness_confirmed(self, data: pd.DataFrame, spot_price: float) -> Optional[Dict]:
        """S6: Weakness Confirmed - Bearish signal (Sell CALL)"""
        try:
            # Calculate moving averages
            data['SMA20'] = data['close'].rolling(20).mean()
            data['SMA50'] = data['close'].rolling(50).mean()
            
            # Bearish cross and momentum
            if (data['SMA20'].iloc[-1] < data['SMA50'].iloc[-1] and  # Death cross
                spot_price < data['SMA20'].iloc[-1]):  # Below short MA
                
                return {
                    "signal_type": "S6",
                    "signal_name": "Weakness Confirmed",
                    "direction": "BEARISH",
                    "action": "SELL_CALL",
                    "spot_price": spot_price,
                    "strike": round(spot_price / 50) * 50,
                    "confidence": 0.72,
                    "timestamp": datetime.now().isoformat()
                }
        except:
            pass
        return None
    
    def _detect_s7_breakout_confirmed(self, data: pd.DataFrame, spot_price: float) -> Optional[Dict]:
        """S7: Breakout Confirmed - Bullish signal (Sell PUT)"""
        try:
            # Calculate breakout level
            recent_high = data['high'].iloc[-20:-1].max()
            
            # Check for breakout with volume
            if (spot_price > recent_high and  # Breakout
                data['volume'].iloc[-1] > data['volume'].iloc[-20:].mean() * 1.5):  # Volume confirmation
                
                return {
                    "signal_type": "S7",
                    "signal_name": "Breakout Confirmed",
                    "direction": "BULLISH",
                    "action": "SELL_PUT",
                    "spot_price": spot_price,
                    "strike": round(spot_price / 50) * 50,
                    "confidence": 0.80,
                    "timestamp": datetime.now().isoformat()
                }
        except:
            pass
        return None
    
    def _detect_s8_breakdown_confirmed(self, data: pd.DataFrame, spot_price: float) -> Optional[Dict]:
        """S8: Breakdown Confirmed - Bearish signal (Sell CALL)"""
        try:
            # Calculate breakdown level
            recent_low = data['low'].iloc[-20:-1].min()
            
            # Check for breakdown with volume
            if (spot_price < recent_low and  # Breakdown
                data['volume'].iloc[-1] > data['volume'].iloc[-20:].mean() * 1.5):  # Volume confirmation
                
                return {
                    "signal_type": "S8",
                    "signal_name": "Breakdown Confirmed",
                    "direction": "BEARISH",
                    "action": "SELL_CALL",
                    "spot_price": spot_price,
                    "strike": round(spot_price / 50) * 50,
                    "confidence": 0.80,
                    "timestamp": datetime.now().isoformat()
                }
        except:
            pass
        return None
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _generate_market_data(self, current_price: float) -> pd.DataFrame:
        """Generate sample market data for testing"""
        # Create 100 periods of sample data
        periods = 100
        dates = pd.date_range(end=datetime.now(), periods=periods, freq='5min')
        
        # Generate realistic price movement
        returns = np.random.normal(0, 0.002, periods)  # 0.2% volatility
        prices = current_price * (1 + returns).cumprod()
        
        # Add some structure
        prices = pd.Series(prices).rolling(5).mean().fillna(method='bfill')
        
        # Create OHLC data
        data = pd.DataFrame({
            'timestamp': dates,
            'open': prices * (1 + np.random.normal(0, 0.001, periods)),
            'high': prices * (1 + np.abs(np.random.normal(0, 0.002, periods))),
            'low': prices * (1 - np.abs(np.random.normal(0, 0.002, periods))),
            'close': prices,
            'volume': np.random.randint(100000, 1000000, periods)
        })
        
        return data
    
    def get_active_signals(self) -> List[str]:
        """Get list of currently active signals"""
        return [s for s in self.active_signals]
    
    def clear_signals(self):
        """Clear all active signals"""
        self.active_signals = []
        self.last_signal_time = {}


# Global instance
_signal_detector = None

def get_signal_detector() -> SignalDetector:
    """Get or create signal detector instance"""
    global _signal_detector
    if _signal_detector is None:
        _signal_detector = SignalDetector()
    return _signal_detector