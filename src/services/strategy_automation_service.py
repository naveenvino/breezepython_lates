"""
Strategy Automation Service - S1-S8 Signal Automation
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, time
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class SignalType(Enum):
    S1 = "Bear Trap"  # Bullish - Sell PUT
    S2 = "Support Hold"  # Bullish - Sell PUT
    S3 = "Resistance Hold"  # Bearish - Sell CALL
    S4 = "Bias Failure Bull"  # Bullish - Sell PUT
    S5 = "Bias Failure Bear"  # Bearish - Sell CALL
    S6 = "Weakness Confirmed"  # Bearish - Sell CALL
    S7 = "Breakout Confirmed"  # Bullish - Sell PUT
    S8 = "Breakdown Confirmed"  # Bearish - Sell CALL

@dataclass
class SignalConfig:
    signal_type: SignalType
    action: str  # "SELL_PUT" or "SELL_CALL"
    quantity_lots: int = 10
    stop_loss_points: int = 50
    target_points: int = 100
    hedge_enabled: bool = True
    hedge_percentage: float = 30
    trailing_stop: int = 0

@dataclass
class SignalTrigger:
    signal_type: SignalType
    timestamp: datetime
    spot_price: float
    strike_price: int
    confidence: float
    triggered: bool = False
    order_id: Optional[str] = None

class StrategyAutomationService:
    def __init__(self, trading_service=None, market_service=None):
        self.trading_service = trading_service
        self.market_service = market_service
        self.signal_configs = self._initialize_signal_configs()
        self.active_signals = {}
        self.signal_history = []
        self.automation_enabled = False
        self.monitoring_task = None
        
    def _initialize_signal_configs(self) -> Dict[SignalType, SignalConfig]:
        """Initialize configuration for each signal type"""
        return {
            SignalType.S1: SignalConfig(SignalType.S1, "SELL_PUT", 10, 50, 100, True, 30),
            SignalType.S2: SignalConfig(SignalType.S2, "SELL_PUT", 10, 50, 100, True, 30),
            SignalType.S3: SignalConfig(SignalType.S3, "SELL_CALL", 10, 50, 100, True, 30),
            SignalType.S4: SignalConfig(SignalType.S4, "SELL_PUT", 10, 50, 100, True, 30),
            SignalType.S5: SignalConfig(SignalType.S5, "SELL_CALL", 10, 50, 100, True, 30),
            SignalType.S6: SignalConfig(SignalType.S6, "SELL_CALL", 10, 50, 100, True, 30),
            SignalType.S7: SignalConfig(SignalType.S7, "SELL_PUT", 10, 50, 100, True, 30),
            SignalType.S8: SignalConfig(SignalType.S8, "SELL_CALL", 10, 50, 100, True, 30),
        }
    
    async def start_automation(self):
        """Start strategy automation"""
        if self.automation_enabled:
            logger.info("Automation already running")
            return
        
        self.automation_enabled = True
        self.monitoring_task = asyncio.create_task(self._monitor_signals())
        logger.info("Strategy automation started")
    
    async def stop_automation(self):
        """Stop strategy automation"""
        self.automation_enabled = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Strategy automation stopped")
    
    async def _monitor_signals(self):
        """Monitor market for signal triggers"""
        while self.automation_enabled:
            try:
                # Check if market is open
                if not self._is_market_open():
                    await asyncio.sleep(60)  # Check every minute
                    continue
                
                # Check for signals
                signals = await self._check_for_signals()
                
                for signal in signals:
                    if signal.signal_type not in self.active_signals:
                        await self._process_signal(signal)
                
                # Monitor existing positions
                await self._monitor_positions()
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in signal monitoring: {e}")
                await asyncio.sleep(5)
    
    def _is_market_open(self) -> bool:
        """Check if market is open for trading"""
        now = datetime.now()
        market_open = time(9, 15)
        market_close = time(15, 30)
        
        # Check if weekday (Monday=0, Sunday=6)
        if now.weekday() > 4:  # Saturday or Sunday
            return False
        
        current_time = now.time()
        return market_open <= current_time <= market_close
    
    async def _check_for_signals(self) -> List[SignalTrigger]:
        """Check market data for signal triggers"""
        signals = []
        
        try:
            # Get market data
            if self.market_service:
                market_data = await self.market_service.get_all_market_data()
                spot_price = market_data.get('NIFTY', {}).get('ltp', 0)
                
                # Check each signal condition
                # S1: Bear Trap - Price dips below support then recovers
                if await self._check_s1_condition(market_data):
                    signals.append(SignalTrigger(
                        signal_type=SignalType.S1,
                        timestamp=datetime.now(),
                        spot_price=spot_price,
                        strike_price=self._get_atm_strike(spot_price),
                        confidence=0.8
                    ))
                
                # S2: Support Hold - Price holds above support
                if await self._check_s2_condition(market_data):
                    signals.append(SignalTrigger(
                        signal_type=SignalType.S2,
                        timestamp=datetime.now(),
                        spot_price=spot_price,
                        strike_price=self._get_atm_strike(spot_price),
                        confidence=0.75
                    ))
                
                # Add more signal checks for S3-S8...
                
        except Exception as e:
            logger.error(f"Error checking signals: {e}")
        
        return signals
    
    async def _check_s1_condition(self, market_data: Dict) -> bool:
        """Check for S1 Bear Trap signal"""
        # Implement S1 signal logic
        # For now, return False
        return False
    
    async def _check_s2_condition(self, market_data: Dict) -> bool:
        """Check for S2 Support Hold signal"""
        # Implement S2 signal logic
        return False
    
    def _get_atm_strike(self, spot_price: float) -> int:
        """Get At-The-Money strike price"""
        return int(round(spot_price / 50) * 50)
    
    async def _process_signal(self, signal: SignalTrigger):
        """Process a triggered signal and place trade"""
        try:
            config = self.signal_configs[signal.signal_type]
            
            # Determine option symbol
            strike = signal.strike_price
            option_type = "PE" if config.action == "SELL_PUT" else "CE"
            expiry = self._get_current_expiry()
            symbol = f"NIFTY{expiry}{strike}{option_type}"
            
            # Calculate quantities
            quantity = config.quantity_lots * 75  # 75 qty per lot for NIFTY
            
            # Get option price
            option_price = await self._get_option_price(symbol)
            
            # Calculate stop loss and target
            stop_loss = strike if option_type == "PE" else strike  # Main strike as SL
            target = option_price + config.target_points
            
            # Place main order
            if self.trading_service:
                from src.services.trading_execution_service import OrderRequest, OrderSide, OrderType, ProductType
                
                order_request = OrderRequest(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=quantity,
                    order_type=OrderType.LIMIT,
                    product_type=ProductType.OPTIONS,
                    price=option_price,
                    stop_loss=stop_loss,
                    target=target,
                    trailing_stop=config.trailing_stop
                )
                
                response = await self.trading_service.place_order(order_request)
                
                if response.status == 'SUCCESS':
                    signal.triggered = True
                    signal.order_id = response.order_id
                    
                    # Place hedge if enabled
                    if config.hedge_enabled:
                        await self.trading_service.place_hedge_order(
                            response.order_id,
                            config.hedge_percentage
                        )
                    
                    # Track active signal
                    self.active_signals[signal.signal_type] = {
                        'signal': signal,
                        'config': config,
                        'order_id': response.order_id,
                        'entry_time': datetime.now(),
                        'status': 'ACTIVE'
                    }
                    
                    logger.info(f"Signal {signal.signal_type.value} executed: {response.order_id}")
                
        except Exception as e:
            logger.error(f"Error processing signal {signal.signal_type}: {e}")
    
    def _get_current_expiry(self) -> str:
        """Get current weekly expiry date"""
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0 and today.hour >= 15:
            days_until_thursday = 7
        expiry = today + timedelta(days=days_until_thursday)
        return expiry.strftime("%d%b%y").upper()
    
    async def _get_option_price(self, symbol: str) -> float:
        """Get current option price"""
        try:
            if self.market_service:
                # Parse symbol to extract strike and option type
                # Expected format: NIFTY22DEC25000CE or NIFTY22DEC25000PE
                import re
                match = re.search(r'(\d+)(CE|PE)$', symbol)
                if match:
                    strike = int(match.group(1))
                    option_type = match.group(2)
                    
                    # Get option quote from market service
                    quote = await self.market_service.get_option_quote(strike, option_type)
                    if quote and 'ltp' in quote:
                        return float(quote['ltp'])
                
                # If market service has a direct method for symbol quotes
                if hasattr(self.market_service, 'get_quotes'):
                    quotes_data = await self.market_service.get_quotes(symbol)
                    if quotes_data and 'ltp' in quotes_data:
                        return float(quotes_data['ltp'])
            
            # Fallback to default if no market service or data unavailable
            logger.warning(f"Could not fetch real option price for {symbol}, using default")
            return 100.0
        except Exception as e:
            logger.error(f"Error fetching option price for {symbol}: {e}")
            return 100.0
    
    async def _monitor_positions(self):
        """Monitor active positions for exit conditions"""
        for signal_type, position_data in list(self.active_signals.items()):
            if position_data['status'] != 'ACTIVE':
                continue
            
            try:
                # Check if position hit stop loss or target
                # Check if signal reversal occurred
                # Check if end of day approaching
                
                # For now, just log
                elapsed = datetime.now() - position_data['entry_time']
                if elapsed.total_seconds() > 3600:  # 1 hour
                    logger.info(f"Position {signal_type.value} active for {elapsed}")
                
            except Exception as e:
                logger.error(f"Error monitoring position {signal_type}: {e}")
    
    def get_active_signals(self) -> Dict:
        """Get all active signals and positions"""
        return self.active_signals
    
    def get_signal_history(self) -> List:
        """Get historical signal triggers"""
        return self.signal_history
    
    def update_signal_config(self, signal_type: SignalType, config: SignalConfig):
        """Update configuration for a signal type"""
        self.signal_configs[signal_type] = config
        logger.info(f"Updated config for {signal_type.value}")
    
    async def backtest_signal(self, signal_type: SignalType, from_date: datetime, to_date: datetime) -> Dict:
        """Backtest a specific signal"""
        # Implement backtesting logic
        return {
            'signal': signal_type.value,
            'period': f"{from_date} to {to_date}",
            'trades': 0,
            'win_rate': 0,
            'total_pnl': 0
        }

# Singleton instance
_strategy_service = None

def get_strategy_service(trading_service=None, market_service=None):
    global _strategy_service
    if _strategy_service is None:
        _strategy_service = StrategyAutomationService(trading_service, market_service)
    return _strategy_service