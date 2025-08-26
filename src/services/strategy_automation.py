"""
Strategy Automation Service
Automates trading strategies based on signals and rules
"""

import logging
import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, time
from enum import Enum
import json

logger = logging.getLogger(__name__)

class StrategyStatus(Enum):
    """Strategy status"""
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"

class TradingSignal(Enum):
    """Trading signal types"""
    S1 = "S1"  # Bear Trap (Bullish)
    S2 = "S2"  # Support Hold (Bullish)
    S3 = "S3"  # Resistance Hold (Bearish)
    S4 = "S4"  # Bias Failure Bull (Bullish)
    S5 = "S5"  # Bias Failure Bear (Bearish)
    S6 = "S6"  # Weakness Confirmed (Bearish)
    S7 = "S7"  # Breakout Confirmed (Bullish)
    S8 = "S8"  # Breakdown Confirmed (Bearish)

class AutomatedStrategy:
    """
    Base class for automated trading strategies
    """
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
        self.status = StrategyStatus.INACTIVE
        self.positions: List[Dict] = []
        self.pnl = 0.0
        self.trades_count = 0
        self.win_rate = 0.0
        self.last_signal_time = None
        self.created_at = datetime.now()
    
    async def evaluate(self, market_data: Dict) -> Optional[Dict]:
        """
        Evaluate strategy conditions and return trading action
        Override in derived classes
        """
        raise NotImplementedError
    
    async def on_position_update(self, position: Dict):
        """Handle position updates"""
        pass
    
    async def on_order_update(self, order: Dict):
        """Handle order updates"""
        pass
    
    def get_stats(self) -> Dict:
        """Get strategy statistics"""
        return {
            'name': self.name,
            'status': self.status.value,
            'positions': len(self.positions),
            'pnl': self.pnl,
            'trades': self.trades_count,
            'win_rate': self.win_rate,
            'last_signal': self.last_signal_time.isoformat() if self.last_signal_time else None,
            'running_since': self.created_at.isoformat()
        }


class SignalBasedStrategy(AutomatedStrategy):
    """
    Strategy based on S1-S8 signals
    """
    
    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.active_signals = config.get('signals', ['S1', 'S2', 'S3', 'S4'])
        self.lots_per_trade = config.get('lots_per_trade', 10)
        self.stop_loss_percent = config.get('stop_loss_percent', 2.0)
        self.target_percent = config.get('target_percent', 3.0)
        self.max_positions = config.get('max_positions', 3)
    
    async def evaluate(self, market_data: Dict) -> Optional[Dict]:
        """Evaluate signals and generate trading action"""
        try:
            # Check if we have room for more positions
            if len(self.positions) >= self.max_positions:
                return None
            
            # Check for signals in market data
            signal = market_data.get('signal')
            if not signal or signal not in self.active_signals:
                return None
            
            # Determine action based on signal
            if signal in ['S1', 'S2', 'S4', 'S7']:
                # Bullish signals - Sell PUT
                action = {
                    'action': 'SELL',
                    'option_type': 'PUT',
                    'strike': self._calculate_strike(market_data['spot_price'], 'PUT'),
                    'quantity': self.lots_per_trade * 75,  # NIFTY lot size
                    'signal': signal,
                    'stop_loss': market_data['spot_price'] * (1 - self.stop_loss_percent / 100),
                    'target': market_data['spot_price'] * (1 + self.target_percent / 100)
                }
            else:
                # Bearish signals - Sell CALL
                action = {
                    'action': 'SELL',
                    'option_type': 'CALL',
                    'strike': self._calculate_strike(market_data['spot_price'], 'CALL'),
                    'quantity': self.lots_per_trade * 75,
                    'signal': signal,
                    'stop_loss': market_data['spot_price'] * (1 + self.stop_loss_percent / 100),
                    'target': market_data['spot_price'] * (1 - self.target_percent / 100)
                }
            
            self.last_signal_time = datetime.now()
            return action
            
        except Exception as e:
            logger.error(f"Strategy evaluation error: {e}")
            return None
    
    def _calculate_strike(self, spot_price: float, option_type: str) -> int:
        """Calculate strike price based on spot price"""
        atm_strike = round(spot_price / 50) * 50
        
        if option_type == 'PUT':
            # For PUT, go slightly OTM
            return atm_strike - 50
        else:
            # For CALL, go slightly OTM
            return atm_strike + 50


class MomentumStrategy(AutomatedStrategy):
    """
    Momentum-based automated strategy
    """
    
    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.momentum_period = config.get('momentum_period', 20)
        self.entry_threshold = config.get('entry_threshold', 2.0)
        self.exit_threshold = config.get('exit_threshold', -1.0)
    
    async def evaluate(self, market_data: Dict) -> Optional[Dict]:
        """Evaluate momentum and generate trading action"""
        try:
            # Calculate momentum
            momentum = market_data.get('momentum', 0)
            
            if momentum > self.entry_threshold and len(self.positions) == 0:
                # Strong upward momentum - Buy CALL
                return {
                    'action': 'BUY',
                    'option_type': 'CALL',
                    'strike': round(market_data['spot_price'] / 50) * 50,
                    'quantity': 75,
                    'reason': f'Momentum {momentum:.2f} > {self.entry_threshold}'
                }
            elif momentum < self.exit_threshold and len(self.positions) > 0:
                # Momentum reversal - Exit positions
                return {
                    'action': 'EXIT_ALL',
                    'reason': f'Momentum {momentum:.2f} < {self.exit_threshold}'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Momentum strategy error: {e}")
            return None


class StrategyAutomationService:
    """
    Service for managing and executing automated strategies
    """
    
    def __init__(self, order_service=None):
        self.order_service = order_service
        self.strategies: Dict[str, AutomatedStrategy] = {}
        self.running = False
        self.execution_task = None
    
    def create_strategy(self, strategy_type: str, name: str, config: Dict) -> Dict:
        """Create a new automated strategy"""
        try:
            strategy_id = f"STRAT_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            if strategy_type == 'SIGNAL_BASED':
                strategy = SignalBasedStrategy(name, config)
            elif strategy_type == 'MOMENTUM':
                strategy = MomentumStrategy(name, config)
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown strategy type: {strategy_type}'
                }
            
            self.strategies[strategy_id] = strategy
            
            return {
                'status': 'success',
                'strategy_id': strategy_id,
                'name': name,
                'type': strategy_type,
                'config': config,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Strategy creation error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def start_strategy(self, strategy_id: str) -> Dict:
        """Start an automated strategy"""
        try:
            if strategy_id not in self.strategies:
                return {
                    'status': 'error',
                    'message': 'Strategy not found'
                }
            
            strategy = self.strategies[strategy_id]
            strategy.status = StrategyStatus.ACTIVE
            
            logger.info(f"Started strategy: {strategy_id}")
            
            return {
                'status': 'success',
                'strategy_id': strategy_id,
                'message': 'Strategy activated',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Strategy start error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def stop_strategy(self, strategy_id: str, close_positions: bool = False) -> Dict:
        """Stop an automated strategy"""
        try:
            if strategy_id not in self.strategies:
                return {
                    'status': 'error',
                    'message': 'Strategy not found'
                }
            
            strategy = self.strategies[strategy_id]
            strategy.status = StrategyStatus.STOPPED
            
            # Close positions if requested
            if close_positions and strategy.positions:
                for position in strategy.positions:
                    # Close position through order service
                    if self.order_service:
                        await self.order_service.close_position(position)
                
                strategy.positions = []
            
            logger.info(f"Stopped strategy: {strategy_id}")
            
            return {
                'status': 'success',
                'strategy_id': strategy_id,
                'positions_closed': close_positions,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Strategy stop error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def execute_strategies(self, market_data: Dict):
        """Execute all active strategies with current market data"""
        try:
            for strategy_id, strategy in self.strategies.items():
                if strategy.status != StrategyStatus.ACTIVE:
                    continue
                
                # Evaluate strategy
                action = await strategy.evaluate(market_data)
                
                if action:
                    # Execute the action
                    await self._execute_action(strategy_id, action)
            
        except Exception as e:
            logger.error(f"Strategy execution error: {e}")
    
    async def _execute_action(self, strategy_id: str, action: Dict):
        """Execute a trading action from a strategy"""
        try:
            strategy = self.strategies[strategy_id]
            
            logger.info(f"Executing action for {strategy_id}: {action}")
            
            if action.get('action') == 'EXIT_ALL':
                # Close all positions
                for position in strategy.positions:
                    if self.order_service:
                        await self.order_service.close_position(position)
                strategy.positions = []
            else:
                # Place new order
                if self.order_service:
                    order_result = await self.order_service.place_order(action)
                    
                    if order_result.get('status') == 'success':
                        # Track position
                        strategy.positions.append({
                            'order_id': order_result.get('order_id'),
                            'symbol': action.get('symbol'),
                            'quantity': action.get('quantity'),
                            'entry_time': datetime.now().isoformat()
                        })
                        strategy.trades_count += 1
            
        except Exception as e:
            logger.error(f"Action execution error: {e}")
    
    def get_all_strategies(self) -> List[Dict]:
        """Get all strategies and their status"""
        return [
            {
                'id': strategy_id,
                **strategy.get_stats()
            }
            for strategy_id, strategy in self.strategies.items()
        ]
    
    def get_strategy_performance(self, strategy_id: str) -> Dict:
        """Get detailed performance metrics for a strategy"""
        if strategy_id not in self.strategies:
            return None
        
        strategy = self.strategies[strategy_id]
        return {
            'strategy_id': strategy_id,
            'name': strategy.name,
            'performance': {
                'total_pnl': strategy.pnl,
                'trades': strategy.trades_count,
                'win_rate': strategy.win_rate,
                'active_positions': len(strategy.positions),
                'avg_trade_pnl': strategy.pnl / strategy.trades_count if strategy.trades_count > 0 else 0
            },
            'config': strategy.config,
            'status': strategy.status.value,
            'timestamp': datetime.now().isoformat()
        }
    
    async def start_automation(self):
        """Start the automation service"""
        self.running = True
        self.execution_task = asyncio.create_task(self._automation_loop())
        logger.info("Strategy automation service started")
    
    async def stop_automation(self):
        """Stop the automation service"""
        self.running = False
        if self.execution_task:
            self.execution_task.cancel()
        logger.info("Strategy automation service stopped")
    
    async def _automation_loop(self):
        """Main automation loop"""
        while self.running:
            try:
                # Fetch current market data
                market_data = await self._fetch_market_data()
                
                # Execute strategies
                await self.execute_strategies(market_data)
                
                # Wait before next iteration
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Automation loop error: {e}")
                await asyncio.sleep(10)
    
    async def _fetch_market_data(self) -> Dict:
        """Fetch current market data"""
        # This would fetch real market data
        # For now, return sample data
        return {
            'spot_price': 25000,
            'timestamp': datetime.now().isoformat()
        }


# Global instance
_automation_service: Optional[StrategyAutomationService] = None

def get_automation_service(order_service=None) -> StrategyAutomationService:
    """Get or create strategy automation service"""
    global _automation_service
    if _automation_service is None:
        _automation_service = StrategyAutomationService(order_service)
    return _automation_service