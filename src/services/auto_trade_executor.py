"""
Auto Trade Executor Service
Handles automated trade execution with real broker integration and risk management
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, time
from enum import Enum
import json
import os

from kiteconnect import KiteConnect
from breeze_connect import BreezeConnect

logger = logging.getLogger(__name__)

class TradeMode(Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"
    BACKTEST = "BACKTEST"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"

class AutoTradeExecutor:
    """Handles automated trade execution with comprehensive risk management"""
    
    def __init__(self):
        self.kite = None
        self.breeze = None
        self.mode = TradeMode.PAPER
        self.enabled = False
        
        # Load configuration from database
        self._load_config_from_db()
        
        # Session tracking
        self.daily_pnl = 0
        self.open_positions = []
        self.orders_today = []
        self.last_trade_time = None
        
        # Load saved state
        self.load_state()
        
        # Set up stop loss callback
        self._setup_stop_loss_callback()
        
    def _load_config_from_db(self):
        """Load configuration from database"""
        try:
            from src.services.trade_config_service import get_trade_config_service
            
            service = get_trade_config_service()
            config = service.load_trade_config(user_id='default', config_name='default')
            
            if config:
                # Risk parameters
                self.max_positions = config.get('max_positions', 5)
                self.max_loss_per_trade = config.get('max_loss_per_trade', 20000)
                self.max_daily_loss = config.get('daily_loss_limit', 50000)
                self.max_capital_per_trade = 100000  # Fixed for now
                self.position_size_pct = 0.1  # Fixed for now
                
                # Trading parameters
                self.lot_size = 75  # NIFTY lot size - fixed
                self.default_lots = config.get('num_lots', 10)
                self.entry_timing = config.get('entry_timing', 'immediate')  # immediate or delayed
                self.use_hedging = config.get('hedge_enabled', True)
                self.hedge_distance = config.get('hedge_offset', 200)
                self.hedge_percentage = config.get('hedge_percent', 30.0)
                self.hedge_method = config.get('hedge_method', 'percentage')
                
                # Stop loss parameters
                self.profit_lock_enabled = config.get('profit_lock_enabled', False)
                self.profit_target = config.get('profit_target', 10.0)
                self.profit_lock = config.get('profit_lock', 5.0)
                self.trailing_stop_enabled = config.get('trailing_stop_enabled', False)
                self.trail_percent = config.get('trail_percent', 1.0)
                
                # Active signals
                self.active_signals = config.get('active_signals', [])
                
                logger.info("Loaded config from DB", extra={
                "config": {
                    "lots": self.default_lots,
                    "hedge_enabled": self.use_hedging,
                    "hedge_method": self.hedge_method,
                    "active_signals": self.active_signals,
                    "max_positions": self.max_positions,
                    "daily_loss_limit": self.max_daily_loss
                }
            })
            else:
                # Use defaults if no config found
                self._set_default_config()
                
        except Exception as e:
            logger.error(f"Error loading config from DB: {e}")
            self._set_default_config()
            
    def _set_default_config(self):
        """Set default configuration"""
        # Risk parameters
        self.max_positions = 5
        self.max_loss_per_trade = 20000
        self.max_daily_loss = 50000
        self.max_capital_per_trade = 100000
        self.position_size_pct = 0.1
        
        # Trading parameters
        self.lot_size = 75
        self.default_lots = 10
        self.entry_timing = 'immediate'  # immediate or delayed
        self.use_hedging = True
        self.hedge_distance = 200
        self.hedge_percentage = 30.0
        self.hedge_method = 'percentage'
        
        # Stop loss parameters
        self.profit_lock_enabled = False
        self.profit_target = 10.0
        self.profit_lock = 5.0
        self.trailing_stop_enabled = False
        self.trail_percent = 1.0
        
        # Active signals
        self.active_signals = []
        
    def reload_config(self):
        """Reload configuration from database - call this when settings change"""
        self._load_config_from_db()
        logger.info("Configuration reloaded from database")
        
    def _setup_stop_loss_callback(self):
        """Set up callback for stop loss triggers"""
        try:
            from src.services.live_stoploss_monitor import get_live_stoploss_monitor
            from src.services.hybrid_data_manager import LivePosition
            
            monitor = get_live_stoploss_monitor()
            
            def on_stop_loss_triggered(position: LivePosition, stop_type, reason: str):
                """Handle stop loss trigger"""
                logger.warning("STOP LOSS TRIGGERED", extra={
                "position_id": position.id,
                "stop_type": stop_type.value,
                "reason": reason,
                "strike": position.main_strike,
                "type": position.main_type
            })
                
                # Find and close the position
                for pos in self.open_positions:
                    if pos.get('id') == position.id:
                        # Execute square off
                        self.close_position(pos, f"Stop loss: {reason}")
                        break
            
            monitor.on_stop_loss_triggered = on_stop_loss_triggered
            logger.info("Stop loss callback registered")
            
        except Exception as e:
            logger.error(f"Error setting up stop loss callback: {e}")
        
    def initialize_brokers(self):
        """Initialize broker connections"""
        try:
            # Initialize Zerodha Kite
            api_key = os.getenv('KITE_API_KEY')
            api_secret = os.getenv('KITE_API_SECRET')
            access_token = self.get_kite_access_token()
            
            if api_key and access_token:
                self.kite = KiteConnect(api_key=api_key)
                self.kite.set_access_token(access_token)
                
                # Verify connection
                profile = self.kite.profile()
                logger.info(f"Connected to Kite as {profile.get('user_name')}")
            else:
                logger.warning("Kite credentials not configured")
                
            # Initialize Breeze for market data
            breeze_key = os.getenv('BREEZE_API_KEY')
            breeze_secret = os.getenv('BREEZE_API_SECRET')
            breeze_session = os.getenv('BREEZE_API_SESSION')
            
            if breeze_key and breeze_secret and breeze_session:
                self.breeze = BreezeConnect(api_key=breeze_key)
                self.breeze.generate_session(
                    api_secret=breeze_secret,
                    session_token=breeze_session
                )
                logger.info("Connected to Breeze for market data")
            else:
                logger.warning("Breeze credentials not configured")
                
        except Exception as e:
            logger.error(f"Error initializing brokers: {e}")
            
    def get_kite_access_token(self) -> Optional[str]:
        """Get saved Kite access token"""
        try:
            token_file = 'logs/kite_auth_cache.json'
            if os.path.exists(token_file):
                with open(token_file, 'r') as f:
                    data = json.load(f)
                    return data.get('access_token')
        except Exception as e:
            logger.error(f"Error reading access token: {e}")
        return None
        
    def validate_trade_signal(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate if trade signal should be executed"""
        
        # Check if auto trade is enabled
        if not self.enabled:
            return False, "Auto trade is disabled"
            
        # Check if signal is in active signals list
        signal_name = signal.get('signal_name', '')
        if self.active_signals and signal_name not in self.active_signals:
            return False, f"Signal {signal_name} is not in active signals list"
            
        # Check market hours (9:15 AM to 3:30 PM)
        now = datetime.now()
        market_open = time(9, 15)
        market_close = time(15, 30)
        
        if not (market_open <= now.time() <= market_close):
            return False, "Outside market hours"
            
        # Check if it's a trading day (Mon-Fri)
        if now.weekday() > 4:
            return False, "Market closed (weekend)"
            
        # Check position limits
        if len(self.open_positions) >= self.max_positions:
            return False, f"Max positions ({self.max_positions}) reached"
            
        # Check daily loss limit
        if self.daily_pnl <= -self.max_daily_loss:
            return False, f"Daily loss limit reached ({self.max_daily_loss})"
            
        # Validate signal data
        required_fields = ['type', 'strike', 'action', 'signal_name']
        for field in required_fields:
            if field not in signal:
                return False, f"Missing required field: {field}"
                
        # Check duplicate signals (avoid re-entering same position)
        for pos in self.open_positions:
            if (pos.get('strike') == signal['strike'] and 
                pos.get('type') == signal['type']):
                return False, "Position already exists for this strike"
                
        return True, "Signal validated"
        
    def calculate_position_size(self, signal: Dict[str, Any]) -> int:
        """Calculate appropriate position size based on risk management"""
        
        # Get account capital
        capital = self.get_available_capital()
        
        # Calculate position size based on percentage
        position_value = capital * self.position_size_pct
        
        # Get option price
        option_price = self.get_option_price(
            signal['strike'], 
            signal['type']
        )
        
        if option_price > 0:
            # Calculate lots based on capital allocation
            lots = int(position_value / (option_price * self.lot_size))
            
            # Apply min/max constraints
            lots = max(1, min(lots, self.default_lots))
        else:
            lots = self.default_lots
            
        return lots
        
    def get_available_capital(self) -> float:
        """Get available trading capital"""
        if self.mode == TradeMode.PAPER:
            return 500000  # 5 lakh for paper trading
            
        try:
            if self.kite:
                margins = self.kite.margins()
                return margins['equity']['available']['live_balance']
        except Exception as e:
            logger.error(f"Error fetching capital: {e}")
            
        return 0
        
    def get_option_price(self, strike: int, option_type: str) -> float:
        """Get current option price"""
        try:
            symbol = f"NIFTY{strike}{option_type}"
            
            if self.mode == TradeMode.PAPER:
                # Return mock price for paper trading
                return 150.0
                
            if self.kite:
                quote = self.kite.quote(f"NFO:{symbol}")
                return quote.get(f"NFO:{symbol}", {}).get('last_price', 0)
                
        except Exception as e:
            logger.error(f"Error fetching option price: {e}")
            
        return 0
        
    def execute_trade(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Execute trade based on signal"""
        
        # Validate signal
        is_valid, message = self.validate_trade_signal(signal)
        if not is_valid:
            return {
                "success": False,
                "message": message
            }
            
        # Check entry timing
        if self.entry_timing == 'delayed':
            # For delayed entry, wait for second candle after signal
            logger.info(f"Entry timing is 'delayed' - will enter on second candle after signal")
            # In production, this would check if we're on the second candle
            # For now, we'll just log it
            signal['entry_note'] = 'Entry on second candle (11:15 AM typical)'
        else:
            logger.info(f"Entry timing is 'immediate' - entering now")
            signal['entry_note'] = 'Immediate entry'
            
        try:
            # Calculate position size
            lots = self.calculate_position_size(signal)
            quantity = lots * self.lot_size
            
            # Prepare order details
            main_order = {
                "symbol": f"NIFTY{signal['strike']}{signal['type']}",
                "quantity": quantity,
                "transaction_type": "SELL",  # Selling options
                "order_type": OrderType.MARKET.value,
                "product": "MIS",  # Intraday
                "strike": signal['strike'],
                "option_type": signal['type']
            }
            
            # Execute based on mode
            if self.mode == TradeMode.PAPER:
                result = self.execute_paper_trade(main_order, signal)
            else:
                result = self.execute_live_trade(main_order, signal)
                
            # Handle hedging if enabled
            if result['success'] and self.use_hedging:
                hedge_result = self.place_hedge_order(signal, lots)
                result['hedge'] = hedge_result
                
            # Update position tracking
            if result['success']:
                self.track_position(result, signal)
                
            return result
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return {
                "success": False,
                "message": str(e)
            }
            
    def execute_paper_trade(self, order: Dict, signal: Dict) -> Dict[str, Any]:
        """Execute paper trade"""
        
        # Generate mock order ID
        order_id = f"PAPER_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Get mock price
        price = self.get_option_price(order['strike'], order['option_type'])
        
        # Create position record
        position = {
            "order_id": order_id,
            "symbol": order['symbol'],
            "quantity": order['quantity'],
            "transaction_type": order['transaction_type'],
            "price": price,
            "timestamp": datetime.now().isoformat(),
            "signal": signal['signal_name'],
            "mode": "PAPER"
        }
        
        # Add to open positions
        self.open_positions.append(position)
        self.orders_today.append(position)
        
        # Save state
        self.save_state()
        
        logger.info("Paper trade executed", extra={
            "trade": {
                "order_id": order_id,
                "symbol": order['symbol'],
                "quantity": order['quantity'],
                "price": price,
                "signal": signal['signal_name'],
                "mode": "PAPER"
            }
        })
        
        return {
            "success": True,
            "order_id": order_id,
            "position": position,
            "message": "Paper trade executed successfully"
        }
        
    def execute_live_trade(self, order: Dict, signal: Dict) -> Dict[str, Any]:
        """Execute live trade through Kite"""
        
        if not self.kite:
            return {
                "success": False,
                "message": "Kite not connected"
            }
            
        try:
            # Map to Kite order format
            kite_order = {
                "tradingsymbol": order['symbol'],
                "exchange": "NFO",
                "transaction_type": KiteConnect.TRANSACTION_TYPE_SELL if order['transaction_type'] == "SELL" else KiteConnect.TRANSACTION_TYPE_BUY,
                "quantity": order['quantity'],
                "order_type": KiteConnect.ORDER_TYPE_MARKET,
                "product": KiteConnect.PRODUCT_MIS,
                "validity": KiteConnect.VALIDITY_DAY
            }
            
            # Place order
            order_id = self.kite.place_order(**kite_order)
            
            # Get order details
            order_details = self.kite.order_history(order_id)[-1]
            
            # Create position record
            position = {
                "order_id": str(order_id),
                "symbol": order['symbol'],
                "quantity": order['quantity'],
                "transaction_type": order['transaction_type'],
                "price": order_details.get('average_price', 0),
                "status": order_details.get('status'),
                "timestamp": datetime.now().isoformat(),
                "signal": signal['signal_name'],
                "mode": "LIVE"
            }
            
            # Add to tracking
            self.open_positions.append(position)
            self.orders_today.append(position)
            
            # Save state
            self.save_state()
            
            logger.info("Live trade executed", extra={
                "trade": {
                    "order_id": str(order_id),
                    "symbol": order['symbol'],
                    "quantity": order['quantity'],
                    "price": order_details.get('average_price', 0),
                    "signal": signal['signal_name'],
                    "mode": "LIVE",
                    "status": order_details.get('status')
                }
            })
            
            return {
                "success": True,
                "order_id": str(order_id),
                "position": position,
                "message": "Live trade executed successfully"
            }
            
        except Exception as e:
            logger.error(f"Error placing live order: {e}")
            return {
                "success": False,
                "message": str(e)
            }
            
    def place_hedge_order(self, signal: Dict, lots: int) -> Dict[str, Any]:
        """Place hedge order for protection"""
        
        # Calculate hedge strike
        hedge_strike = signal['strike']
        if signal['type'] == 'PE':
            hedge_strike -= self.hedge_distance
        else:
            hedge_strike += self.hedge_distance
            
        # Prepare hedge order
        hedge_order = {
            "symbol": f"NIFTY{hedge_strike}{signal['type']}",
            "quantity": lots * self.lot_size,
            "transaction_type": "BUY",  # Buying for hedge
            "order_type": OrderType.MARKET.value,
            "product": "MIS",
            "strike": hedge_strike,
            "option_type": signal['type']
        }
        
        # Execute hedge
        if self.mode == TradeMode.PAPER:
            return self.execute_paper_trade(hedge_order, signal)
        else:
            return self.execute_live_trade(hedge_order, signal)
            
    def track_position(self, result: Dict, signal: Dict):
        """Track position for monitoring and stop loss"""
        
        # Add to stop loss monitor if profit lock or trailing stop enabled
        if self.profit_lock_enabled or self.trailing_stop_enabled:
            try:
                from src.services.hybrid_data_manager import get_hybrid_data_manager, LivePosition
                from datetime import datetime
                
                data_manager = get_hybrid_data_manager()
                
                # Create LivePosition object
                position = LivePosition(
                    id=result['order_id'],
                    entry_time=datetime.now(),
                    signal_type=signal.get('signal_name', 'Unknown'),
                    main_strike=signal.get('strike', 0),
                    main_type=signal.get('type', 'PE'),
                    main_quantity=result.get('position', {}).get('quantity', 0),
                    main_entry_price=result.get('position', {}).get('price', 0),
                    hedge_strike=signal.get('hedge_strike', 0),
                    hedge_type=signal.get('type', 'PE'),
                    hedge_quantity=result.get('hedge', {}).get('quantity', 0) if result.get('hedge') else 0,
                    hedge_entry_price=result.get('hedge', {}).get('price', 0) if result.get('hedge') else 0,
                    status='active'
                )
                
                # Add to data manager for stop loss monitoring
                data_manager.add_position(position)
                logger.info(f"Position {position.id} added to stop loss monitor")
                
                # Configure stop loss rules
                from src.services.live_stoploss_monitor import get_live_stoploss_monitor, StopLossType
                monitor = get_live_stoploss_monitor()
                
                # Enable profit lock if configured
                if self.profit_lock_enabled:
                    for rule in monitor.stop_loss_rules:
                        if rule.type == StopLossType.PROFIT_LOCK:
                            rule.enabled = True
                            rule.params['target_percent'] = self.profit_target
                            rule.params['lock_percent'] = self.profit_lock
                            logger.info(f"Profit lock enabled: {self.profit_target}% target, {self.profit_lock}% lock")
                
                # Enable trailing stop if configured
                if self.trailing_stop_enabled:
                    for rule in monitor.stop_loss_rules:
                        if rule.type == StopLossType.TRAILING:
                            rule.enabled = True
                            rule.params['trail_percent'] = self.trail_percent
                            logger.info(f"Trailing stop enabled: {self.trail_percent}% trail")
                            
            except Exception as e:
                logger.error(f"Error adding position to stop loss monitor: {e}")
        
        position_data = {
            "id": result['order_id'],
            "signal": signal,
            "entry_time": datetime.now().isoformat(),
            "entry_price": result['position']['price'],
            "quantity": result['position']['quantity'],
            "stop_loss": signal['strike'],  # ATM strike as SL
            "target": None,
            "status": "OPEN",
            "pnl": 0
        }
        
        # Save to tracking file
        self.save_position_data(position_data)
        
    def monitor_positions(self):
        """Monitor open positions for stop loss and targets"""
        
        for position in self.open_positions:
            if position.get('status') == 'OPEN':
                # Check stop loss
                current_price = self.get_option_price(
                    position['strike'], 
                    position['option_type']
                )
                
                # Calculate P&L
                if position['transaction_type'] == 'SELL':
                    pnl = (position['price'] - current_price) * position['quantity']
                else:
                    pnl = (current_price - position['price']) * position['quantity']
                    
                position['pnl'] = pnl
                
                # Check stop loss breach
                if pnl <= -self.max_loss_per_trade:
                    self.close_position(position, "Stop loss hit")
                    
    def close_position(self, position: Dict, reason: str):
        """Close an open position"""
        
        try:
            # Reverse the position
            close_order = {
                "symbol": position['symbol'],
                "quantity": position['quantity'],
                "transaction_type": "BUY" if position['transaction_type'] == "SELL" else "SELL",
                "order_type": OrderType.MARKET.value,
                "product": "MIS"
            }
            
            # Execute close order
            if self.mode == TradeMode.PAPER:
                logger.info("Paper position closed", extra={
                    "position": {
                        "symbol": position['symbol'],
                        "reason": reason,
                        "pnl": position.get('pnl', 0),
                        "mode": "PAPER"
                    }
                })
            else:
                if self.kite:
                    self.kite.place_order(
                        tradingsymbol=close_order['symbol'],
                        exchange="NFO",
                        transaction_type=KiteConnect.TRANSACTION_TYPE_BUY if close_order['transaction_type'] == "BUY" else KiteConnect.TRANSACTION_TYPE_SELL,
                        quantity=close_order['quantity'],
                        order_type=KiteConnect.ORDER_TYPE_MARKET,
                        product=KiteConnect.PRODUCT_MIS
                    )
                    
            # Update position status
            position['status'] = 'CLOSED'
            position['close_reason'] = reason
            position['close_time'] = datetime.now().isoformat()
            
            # Update daily P&L
            self.daily_pnl += position.get('pnl', 0)
            
            # Save state
            self.save_state()
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            
    def enable_auto_trade(self):
        """Enable auto trading"""
        self.enabled = True
        self.save_state()
        logger.info("Auto trading enabled")
        
    def disable_auto_trade(self):
        """Disable auto trading"""
        self.enabled = False
        self.save_state()
        logger.info("Auto trading disabled")
        
    def set_mode(self, mode: str):
        """Set trading mode"""
        try:
            self.mode = TradeMode[mode.upper()]
            self.save_state()
            logger.info(f"Trading mode set to {self.mode.value}")
        except KeyError:
            logger.error(f"Invalid mode: {mode}")
            
    def get_status(self) -> Dict[str, Any]:
        """Get current auto trade status"""
        return {
            "enabled": self.enabled,
            "mode": self.mode.value,
            "open_positions": len(self.open_positions),
            "daily_pnl": self.daily_pnl,
            "orders_today": len(self.orders_today),
            "max_positions": self.max_positions,
            "connected": {
                "kite": self.kite is not None,
                "breeze": self.breeze is not None
            }
        }
        
    def save_state(self):
        """Save current state to file"""
        state = {
            "enabled": self.enabled,
            "mode": self.mode.value,
            "daily_pnl": self.daily_pnl,
            "open_positions": self.open_positions,
            "orders_today": self.orders_today,
            "last_updated": datetime.now().isoformat()
        }
        
        try:
            with open('auto_trade_state.json', 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
            
    def load_state(self):
        """Load saved state"""
        try:
            if os.path.exists('auto_trade_state.json'):
                with open('auto_trade_state.json', 'r') as f:
                    state = json.load(f)
                    
                # Reset daily data if new day
                last_updated = datetime.fromisoformat(state.get('last_updated', datetime.now().isoformat()))
                if last_updated.date() < datetime.now().date():
                    self.daily_pnl = 0
                    self.orders_today = []
                else:
                    self.daily_pnl = state.get('daily_pnl', 0)
                    self.orders_today = state.get('orders_today', [])
                    
                self.enabled = state.get('enabled', False)
                self.mode = TradeMode[state.get('mode', 'PAPER')]
                self.open_positions = state.get('open_positions', [])
                
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            
    def save_position_data(self, position: Dict):
        """Save position data for analysis"""
        try:
            filename = f"positions_{datetime.now().strftime('%Y%m%d')}.json"
            positions = []
            
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    positions = json.load(f)
                    
            positions.append(position)
            
            with open(filename, 'w') as f:
                json.dump(positions, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving position data: {e}")

# Singleton instance
_auto_trade_executor = None

def get_auto_trade_executor() -> AutoTradeExecutor:
    """Get singleton auto trade executor instance"""
    global _auto_trade_executor
    if _auto_trade_executor is None:
        _auto_trade_executor = AutoTradeExecutor()
        _auto_trade_executor.initialize_brokers()
    return _auto_trade_executor