"""
Integrated Trading Engine
Connects signal detection, paper trading, and trade journaling into a unified system
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

# Import all components
from src.services.signal_monitor import SignalMonitor, SignalType
from src.services.paper_trading import get_paper_trading_engine, PaperOrder
from src.services.trade_journal_service import get_trade_journal_service, Trade
from src.services.api_cache_manager import get_cache_manager, SmartDataProvider

logger = logging.getLogger(__name__)

@dataclass
class TradingConfig:
    """Trading configuration parameters"""
    enable_auto_trading: bool = True
    enable_paper_trading: bool = True
    enable_live_trading: bool = False
    max_positions: int = 5
    max_risk_per_trade: float = 0.02  # 2% risk per trade
    default_quantity: int = 100
    stop_loss_percent: float = 0.02  # 2% stop loss
    target_percent: float = 0.03  # 3% target
    enable_hedging: bool = True
    hedge_offset: int = 200  # Points away for hedge

class IntegratedTradingEngine:
    """Main trading engine that orchestrates all components"""
    
    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self.signal_monitor = SignalMonitor()
        self.paper_trading = get_paper_trading_engine()
        self.trade_journal = get_trade_journal_service()
        self.cache_manager = get_cache_manager()
        self.data_provider = SmartDataProvider(self.cache_manager)
        
        self.is_running = False
        self.active_trades = {}  # Map signal to trade
        self.signal_queue = asyncio.Queue()
        
    async def start(self):
        """Start the integrated trading engine"""
        if self.is_running:
            logger.warning("Trading engine already running")
            return
            
        self.is_running = True
        logger.info("Starting Integrated Trading Engine")
        
        # Start paper trading engine
        await self.paper_trading.start()
        
        # Start background tasks
        tasks = [
            self._signal_processor(),
            self._position_manager(),
            self._risk_monitor(),
            self._performance_tracker()
        ]
        
        # Start signal monitoring with callback
        self.signal_monitor.signal_callback = self._on_signal_detected
        tasks.append(self.signal_monitor.start_monitoring())
        
        await asyncio.gather(*tasks)
        
    async def stop(self):
        """Stop the trading engine"""
        self.is_running = False
        await self.signal_monitor.stop_monitoring()
        await self.paper_trading.stop()
        logger.info("Trading Engine stopped")
        
    async def _on_signal_detected(self, signal: Dict):
        """Callback when signal is detected"""
        await self.signal_queue.put(signal)
        
    async def _signal_processor(self):
        """Process detected signals and create trades"""
        while self.is_running:
            try:
                # Get signal from queue
                signal = await asyncio.wait_for(
                    self.signal_queue.get(),
                    timeout=1.0
                )
                
                logger.info(f"Processing signal: {signal}")
                
                # Check if we should trade
                if not self._should_trade(signal):
                    continue
                    
                # Record signal in journal
                await self._record_signal(signal)
                
                # Create trade based on signal
                trade_params = self._prepare_trade(signal)
                
                if trade_params:
                    # Execute trade in paper trading
                    if self.config.enable_paper_trading:
                        await self._execute_paper_trade(trade_params)
                        
                    # Execute live trade if enabled
                    if self.config.enable_live_trading:
                        await self._execute_live_trade(trade_params)
                        
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing signal: {e}")
                await asyncio.sleep(1)
                
    def _should_trade(self, signal: Dict) -> bool:
        """Determine if we should act on this signal"""
        
        # Check if auto trading is enabled
        if not self.config.enable_auto_trading:
            return False
            
        # Check max positions
        if len(self.active_trades) >= self.config.max_positions:
            logger.info(f"Max positions reached ({self.config.max_positions})")
            return False
            
        # Check if we already have a trade for this signal
        signal_type = signal.get('type')
        if signal_type in self.active_trades:
            logger.info(f"Already have active trade for signal {signal_type}")
            return False
            
        # Check signal confidence
        confidence = signal.get('confidence', 0)
        if confidence < 0.6:  # Minimum 60% confidence
            logger.info(f"Signal confidence too low: {confidence}")
            return False
            
        # Check market hours (9:15 AM to 3:30 PM)
        now = datetime.now()
        market_open = now.replace(hour=9, minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)
        
        if not (market_open <= now <= market_close):
            logger.info("Outside market hours")
            return False
            
        return True
        
    def _prepare_trade(self, signal: Dict) -> Optional[Dict]:
        """Prepare trade parameters based on signal"""
        
        signal_type = signal.get('type')
        spot_price = signal.get('spot_price', 0)
        
        if not signal_type or not spot_price:
            return None
            
        # Determine trade direction based on signal
        trade_direction = self._get_trade_direction(signal_type)
        
        # Calculate strike price (ATM for now)
        strike = round(spot_price / 100) * 100
        
        # Determine option type
        if trade_direction == 'BULLISH':
            option_type = 'PE'  # Sell PUT for bullish signals
            symbol = f"NIFTY{strike}PE"
        else:
            option_type = 'CE'  # Sell CALL for bearish signals
            symbol = f"NIFTY{strike}CE"
            
        # Calculate entry, stop loss, and target
        entry_price = signal.get('option_price', 100)  # Get from market data
        stop_loss = entry_price * (1 + self.config.stop_loss_percent)
        target = entry_price * (1 - self.config.target_percent)
        
        trade_params = {
            'signal_type': signal_type,
            'symbol': symbol,
            'strike': strike,
            'option_type': option_type,
            'side': 'SELL',  # We're selling options
            'quantity': self.config.default_quantity,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'target': target,
            'spot_price': spot_price,
            'confidence': signal.get('confidence', 0.5),
            'reason': signal.get('reason', '')
        }
        
        # Add hedge if enabled
        if self.config.enable_hedging:
            hedge_strike = strike + self.config.hedge_offset if option_type == 'CE' else strike - self.config.hedge_offset
            trade_params['hedge'] = {
                'symbol': f"NIFTY{hedge_strike}{option_type}",
                'strike': hedge_strike,
                'side': 'BUY',
                'quantity': self.config.default_quantity
            }
            
        return trade_params
        
    def _get_trade_direction(self, signal_type: str) -> str:
        """Get trade direction from signal type"""
        
        bullish_signals = ['S1', 'S2', 'S4', 'S7']  # Bear trap, Support hold, Bias failure bull, Breakout
        bearish_signals = ['S3', 'S5', 'S6', 'S8']  # Resistance hold, Bias failure bear, Weakness, Breakdown
        
        if signal_type in bullish_signals:
            return 'BULLISH'
        elif signal_type in bearish_signals:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
            
    async def _execute_paper_trade(self, trade_params: Dict):
        """Execute trade in paper trading system"""
        try:
            # Place main order
            main_order = await self.paper_trading.place_order(
                symbol=trade_params['symbol'],
                quantity=trade_params['quantity'],
                order_type='MARKET',
                side=trade_params['side'],
                price=trade_params['entry_price']
            )
            
            if main_order['status'] == 'success':
                order_id = main_order['order_id']
                
                # Record in trade journal
                trade = Trade(
                    trade_id=order_id,
                    symbol=trade_params['symbol'],
                    trade_type=trade_params['side'],
                    quantity=trade_params['quantity'],
                    entry_price=trade_params['entry_price'],
                    strategy_name="Integrated Signal Trading",
                    signal_type=trade_params['signal_type'],
                    notes=f"Auto-traded from signal with {trade_params['confidence']:.1%} confidence"
                )
                
                journal_result = self.trade_journal.record_trade_entry(trade)
                
                # Store active trade
                self.active_trades[trade_params['signal_type']] = {
                    'paper_order_id': order_id,
                    'journal_trade_id': journal_result.get('trade_id'),
                    'params': trade_params,
                    'entry_time': datetime.now(),
                    'status': 'OPEN'
                }
                
                # Place hedge order if configured
                if 'hedge' in trade_params:
                    hedge = trade_params['hedge']
                    hedge_order = await self.paper_trading.place_order(
                        symbol=hedge['symbol'],
                        quantity=hedge['quantity'],
                        order_type='MARKET',
                        side=hedge['side']
                    )
                    
                    self.active_trades[trade_params['signal_type']]['hedge_order_id'] = hedge_order.get('order_id')
                    
                logger.info(f"Paper trade executed: {order_id} for signal {trade_params['signal_type']}")
                
        except Exception as e:
            logger.error(f"Error executing paper trade: {e}")
            
    async def _execute_live_trade(self, trade_params: Dict):
        """Execute live trade (placeholder for actual broker integration)"""
        logger.info(f"Live trading not implemented yet. Would execute: {trade_params}")
        # TODO: Integrate with actual broker API
        pass
        
    async def _position_manager(self):
        """Manage open positions - check stops and targets"""
        while self.is_running:
            try:
                for signal_type, trade_info in list(self.active_trades.items()):
                    if trade_info['status'] != 'OPEN':
                        continue
                        
                    params = trade_info['params']
                    symbol = params['symbol']
                    
                    # Get current price
                    current_price = self.paper_trading.price_feed.get(symbol, params['entry_price'])
                    
                    # Check stop loss
                    if params['side'] == 'SELL' and current_price >= params['stop_loss']:
                        await self._close_trade(signal_type, current_price, "Stop Loss Hit")
                        
                    # Check target
                    elif params['side'] == 'SELL' and current_price <= params['target']:
                        await self._close_trade(signal_type, current_price, "Target Reached")
                        
                    # Check time-based exit (3:15 PM square off)
                    elif datetime.now().hour == 15 and datetime.now().minute >= 15:
                        await self._close_trade(signal_type, current_price, "EOD Square Off")
                        
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in position manager: {e}")
                await asyncio.sleep(10)
                
    async def _close_trade(self, signal_type: str, exit_price: float, reason: str):
        """Close an active trade"""
        try:
            trade_info = self.active_trades.get(signal_type)
            if not trade_info:
                return
                
            # Close in paper trading
            if trade_info.get('paper_order_id'):
                # Place opposite order to close
                params = trade_info['params']
                close_side = 'BUY' if params['side'] == 'SELL' else 'SELL'
                
                close_order = await self.paper_trading.place_order(
                    symbol=params['symbol'],
                    quantity=params['quantity'],
                    order_type='MARKET',
                    side=close_side,
                    price=exit_price
                )
                
                # Close hedge if exists
                if trade_info.get('hedge_order_id'):
                    hedge = params.get('hedge')
                    if hedge:
                        hedge_close_side = 'SELL' if hedge['side'] == 'BUY' else 'BUY'
                        await self.paper_trading.place_order(
                            symbol=hedge['symbol'],
                            quantity=hedge['quantity'],
                            order_type='MARKET',
                            side=hedge_close_side
                        )
                        
            # Record exit in journal
            if trade_info.get('journal_trade_id'):
                self.trade_journal.record_trade_exit(
                    trade_id=trade_info['journal_trade_id'],
                    exit_price=exit_price,
                    commission=40,  # Default commission
                    notes=reason
                )
                
            # Update trade status
            trade_info['status'] = 'CLOSED'
            trade_info['exit_time'] = datetime.now()
            trade_info['exit_reason'] = reason
            
            # Calculate P&L
            params = trade_info['params']
            if params['side'] == 'SELL':
                pnl = (params['entry_price'] - exit_price) * params['quantity']
            else:
                pnl = (exit_price - params['entry_price']) * params['quantity']
                
            logger.info(f"Trade closed for {signal_type}: P&L = ₹{pnl:.2f}, Reason: {reason}")
            
            # Remove from active trades
            del self.active_trades[signal_type]
            
        except Exception as e:
            logger.error(f"Error closing trade: {e}")
            
    async def _risk_monitor(self):
        """Monitor portfolio risk metrics"""
        while self.is_running:
            try:
                # Calculate current portfolio metrics
                total_exposure = 0
                total_pnl = 0
                open_positions = len(self.active_trades)
                
                for trade_info in self.active_trades.values():
                    if trade_info['status'] == 'OPEN':
                        params = trade_info['params']
                        exposure = params['quantity'] * params['entry_price']
                        total_exposure += exposure
                        
                        # Get current P&L from paper trading
                        positions = self.paper_trading.get_positions()
                        for pos in positions:
                            if pos['symbol'] == params['symbol']:
                                total_pnl += pos['pnl']
                                
                # Calculate risk metrics
                portfolio_value = self.paper_trading.account.current_capital
                
                if portfolio_value > 0:
                    risk_metrics = {
                        'portfolio_value': portfolio_value,
                        'total_exposure': total_exposure,
                        'exposure_percent': (total_exposure / portfolio_value) * 100,
                        'total_pnl': total_pnl,
                        'pnl_percent': (total_pnl / portfolio_value) * 100,
                        'open_positions': open_positions,
                        'max_positions': self.config.max_positions
                    }
                    
                    # Log risk metrics
                    logger.info(f"Risk Metrics: Exposure={risk_metrics['exposure_percent']:.1f}%, P&L={total_pnl:.2f}")
                    
                    # Store in journal
                    if abs(total_pnl) > 0:  # Only store if there's actual P&L
                        self.trade_journal.calculate_risk_metrics(portfolio_value)
                        
                    # Check risk limits
                    if risk_metrics['exposure_percent'] > 50:  # 50% exposure limit
                        logger.warning("High exposure warning! Consider reducing positions")
                        
                    if risk_metrics['pnl_percent'] < -5:  # 5% drawdown limit
                        logger.warning("Drawdown limit approaching! Consider stopping trading")
                        # Could implement auto-stop here
                        
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in risk monitor: {e}")
                await asyncio.sleep(60)
                
    async def _performance_tracker(self):
        """Track and log performance metrics"""
        while self.is_running:
            try:
                # Get performance from paper trading
                paper_summary = self.paper_trading.get_account_summary()
                
                # Get performance from journal
                journal_summary = self.trade_journal.get_performance_summary()
                
                # Combine metrics
                performance = {
                    'timestamp': datetime.now().isoformat(),
                    'paper_trading': {
                        'capital': paper_summary['current_capital'],
                        'pnl': paper_summary['total_pnl'],
                        'win_rate': paper_summary['win_rate'],
                        'open_positions': paper_summary['open_positions']
                    },
                    'journal': {
                        'total_trades': journal_summary.get('total_trades', 0),
                        'win_rate': journal_summary.get('win_rate', 0),
                        'avg_pnl': journal_summary.get('avg_pnl', 0),
                        'best_trade': journal_summary.get('best_trade', 0),
                        'worst_trade': journal_summary.get('worst_trade', 0)
                    }
                }
                
                # Log performance
                logger.info(f"Performance Update: P&L={performance['paper_trading']['pnl']:.2f}, "
                          f"Win Rate={performance['paper_trading']['win_rate']:.1f}%")
                
                # Could send alerts or notifications here
                if performance['paper_trading']['pnl'] > 10000:
                    logger.info("Great performance! P&L exceeds ₹10,000")
                    
                await asyncio.sleep(300)  # Update every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in performance tracker: {e}")
                await asyncio.sleep(300)
                
    async def _record_signal(self, signal: Dict):
        """Record signal in journal"""
        try:
            self.trade_journal.record_signal(
                signal_type=signal.get('type', 'Unknown'),
                spot_price=signal.get('spot_price', 0),
                strike_price=signal.get('strike_price'),
                option_type=signal.get('option_type'),
                confidence=signal.get('confidence', 0.5),
                reason=signal.get('reason', '')
            )
        except Exception as e:
            logger.error(f"Error recording signal: {e}")
            
    def get_status(self) -> Dict:
        """Get current engine status"""
        return {
            'is_running': self.is_running,
            'config': {
                'auto_trading': self.config.enable_auto_trading,
                'paper_trading': self.config.enable_paper_trading,
                'live_trading': self.config.enable_live_trading,
                'max_positions': self.config.max_positions
            },
            'active_trades': len(self.active_trades),
            'trades': [
                {
                    'signal': signal,
                    'symbol': info['params']['symbol'],
                    'status': info['status'],
                    'entry_time': info['entry_time'].isoformat() if info.get('entry_time') else None
                }
                for signal, info in self.active_trades.items()
            ],
            'paper_trading': self.paper_trading.get_account_summary() if self.paper_trading else {},
            'signals_in_queue': self.signal_queue.qsize()
        }
        
    async def manual_signal(self, signal_type: str, spot_price: float, confidence: float = 0.7):
        """Manually trigger a signal for testing"""
        signal = {
            'type': signal_type,
            'spot_price': spot_price,
            'confidence': confidence,
            'reason': 'Manual trigger',
            'timestamp': datetime.now().isoformat()
        }
        
        await self.signal_queue.put(signal)
        logger.info(f"Manual signal queued: {signal_type}")
        
    def update_config(self, **kwargs):
        """Update configuration dynamically"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Config updated: {key} = {value}")
                
# Singleton instance
_trading_engine = None

def get_trading_engine(config: Optional[TradingConfig] = None) -> IntegratedTradingEngine:
    """Get or create trading engine instance"""
    global _trading_engine
    if _trading_engine is None:
        _trading_engine = IntegratedTradingEngine(config)
    return _trading_engine