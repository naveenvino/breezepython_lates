"""
Live Trading Engine with Paper Trading Mode
Handles real and simulated trading with safety checks
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json
import os
from decimal import Decimal
import asyncio
import pandas as pd
import numpy as np

from breeze_connect import BreezeConnect
from kiteconnect import KiteConnect

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"


class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    TRIGGER_PENDING = "TRIGGER_PENDING"


class Position:
    """Represents a trading position"""
    
    def __init__(
        self,
        signal_type: str,
        strike_price: int,
        option_type: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        target: Optional[float] = None
    ):
        self.id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{signal_type}_{strike_price}"
        self.signal_type = signal_type
        self.strike_price = strike_price
        self.option_type = option_type  # CE or PE
        self.quantity = quantity
        self.entry_price = entry_price
        self.entry_time = datetime.now()
        self.stop_loss = stop_loss
        self.target = target
        self.current_price = entry_price
        self.exit_price = None
        self.exit_time = None
        self.status = OrderStatus.OPEN
        self.pnl = 0.0
        self.order_id = None
        self.exit_reason = None
        
    def update_price(self, current_price: float):
        """Update current price and calculate P&L"""
        self.current_price = current_price
        # For selling options, profit when price decreases
        self.pnl = (self.entry_price - current_price) * self.quantity
        
    def close_position(self, exit_price: float, reason: str = "Manual"):
        """Close the position"""
        self.exit_price = exit_price
        self.exit_time = datetime.now()
        self.status = OrderStatus.COMPLETE
        self.exit_reason = reason
        self.pnl = (self.entry_price - exit_price) * self.quantity
        
    def to_dict(self) -> Dict:
        """Convert position to dictionary"""
        return {
            'id': self.id,
            'signal_type': self.signal_type,
            'strike_price': self.strike_price,
            'option_type': self.option_type,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat(),
            'stop_loss': self.stop_loss,
            'target': self.target,
            'current_price': self.current_price,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'status': self.status.value,
            'pnl': self.pnl,
            'order_id': self.order_id,
            'exit_reason': self.exit_reason
        }


class LiveTradingEngine:
    """Main trading engine with paper and live modes"""
    
    def __init__(
        self,
        mode: TradingMode = TradingMode.PAPER,
        capital: float = 500000,
        max_positions: int = 3,
        lots_per_trade: int = 10,
        stop_loss_percent: float = 2.0
    ):
        self.mode = mode
        self.capital = capital
        self.available_capital = capital
        self.max_positions = max_positions
        self.lots_per_trade = lots_per_trade
        self.lot_size = 75  # NIFTY lot size
        self.stop_loss_percent = stop_loss_percent
        
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.active_signals: List[str] = []
        self.is_trading = False
        self.is_paused = False
        
        # Broker connections
        self.breeze = None
        self.kite = None
        self.primary_broker = "breeze"  # or "kite"
        
        # Paper trading data
        self.paper_trades = []
        self.paper_balance = capital
        
        # Safety checks
        self.max_loss_per_day = capital * 0.02  # 2% of capital
        self.max_trades_per_day = 20
        self.today_trades = 0
        self.today_pnl = 0.0
        
        logger.info(f"Trading engine initialized in {mode.value} mode")
        
    def connect_brokers(self):
        """Connect to broker APIs"""
        if self.mode == TradingMode.PAPER:
            logger.info("Paper trading mode - no broker connection needed")
            return True
            
        try:
            # Connect to Breeze
            if os.getenv('BREEZE_API_KEY'):
                self.breeze = BreezeConnect(api_key=os.getenv('BREEZE_API_KEY'))
                self.breeze.generate_session(
                    api_secret=os.getenv('BREEZE_API_SECRET'),
                    session_token=os.getenv('BREEZE_API_SESSION')
                )
                logger.info("Connected to Breeze API")
                
            # Connect to Kite
            if os.getenv('KITE_API_KEY'):
                self.kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
                self.kite.set_access_token(os.getenv('KITE_ACCESS_TOKEN'))
                logger.info("Connected to Kite API")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to brokers: {e}")
            return False
    
    def start_trading(self, signals: List[str]):
        """Start live trading with selected signals"""
        if self.is_trading:
            return {"status": "error", "message": "Trading already active"}
            
        # Safety checks
        if not self._perform_safety_checks():
            return {"status": "error", "message": "Safety checks failed"}
            
        self.active_signals = signals
        self.is_trading = True
        self.is_paused = False
        
        logger.info(f"Started trading with signals: {signals}")
        
        return {
            "status": "success",
            "message": f"Trading started in {self.mode.value} mode",
            "mode": self.mode.value,
            "signals": signals
        }
    
    def pause_trading(self):
        """Pause trading (no new positions)"""
        self.is_paused = not self.is_paused
        status = "paused" if self.is_paused else "resumed"
        logger.info(f"Trading {status}")
        return {"status": "success", "paused": self.is_paused}
    
    def stop_trading(self, close_all: bool = False):
        """Stop trading and optionally close all positions"""
        self.is_trading = False
        self.is_paused = False
        
        if close_all:
            for position_id, position in list(self.positions.items()):
                self.close_position(position_id, "Trading Stopped")
                
        logger.info("Trading stopped")
        return {"status": "success", "positions_closed": close_all}
    
    def place_order(
        self,
        signal_type: str,
        strike_price: int,
        option_type: str,
        action: str = "SELL",
        weeks_ahead: int = 0,
        use_monthly: bool = False
    ) -> Dict[str, Any]:
        """Place an order (real or paper)
        
        Args:
            signal_type: Signal type (S1, S2, etc.)
            strike_price: Strike price
            option_type: CE or PE
            action: BUY or SELL
            weeks_ahead: 0 for current week, 1 for next week, etc.
            use_monthly: True for monthly expiry
        """
        
        # Check if we can place more orders
        if len(self.positions) >= self.max_positions:
            return {"status": "error", "message": "Max positions reached"}
            
        # Check daily limits
        if self.today_trades >= self.max_trades_per_day:
            return {"status": "error", "message": "Daily trade limit reached"}
            
        quantity = self.lots_per_trade * self.lot_size
        
        # Get current option price
        option_price = self._get_option_price(strike_price, option_type)
        if not option_price:
            return {"status": "error", "message": "Could not fetch option price"}
            
        # Calculate stop loss
        stop_loss = strike_price  # ATM stop loss
        
        # Paper trading
        if self.mode == TradingMode.PAPER:
            position = Position(
                signal_type=signal_type,
                strike_price=strike_price,
                option_type=option_type,
                quantity=quantity,
                entry_price=option_price,
                stop_loss=stop_loss
            )
            
            position.order_id = f"PAPER_{len(self.paper_trades) + 1}"
            self.positions[position.id] = position
            self.paper_trades.append(position.to_dict())
            self.today_trades += 1
            
            logger.info(f"Paper trade placed: {position.id}")
            
            return {
                "status": "success",
                "order_id": position.order_id,
                "position": position.to_dict()
            }
            
        # Live trading
        else:
            try:
                order_response = self._place_real_order(
                    strike_price, option_type, quantity, action, option_price,
                    weeks_ahead=weeks_ahead, use_monthly=use_monthly
                )
                
                if order_response['status'] == 'success':
                    position = Position(
                        signal_type=signal_type,
                        strike_price=strike_price,
                        option_type=option_type,
                        quantity=quantity,
                        entry_price=option_price,
                        stop_loss=stop_loss
                    )
                    
                    position.order_id = order_response['order_id']
                    self.positions[position.id] = position
                    self.today_trades += 1
                    
                    logger.info(f"Live order placed: {order_response['order_id']}")
                    
                    return {
                        "status": "success",
                        "order_id": order_response['order_id'],
                        "position": position.to_dict()
                    }
                else:
                    return order_response
                    
            except Exception as e:
                logger.error(f"Failed to place live order: {e}")
                return {"status": "error", "message": str(e)}
    
    def _place_real_order(
        self,
        strike_price: int,
        option_type: str,
        quantity: int,
        action: str,
        limit_price: float,
        weeks_ahead: int = 0,
        use_monthly: bool = False
    ) -> Dict[str, Any]:
        """Place real order with broker"""
        
        # Determine expiry based on parameters
        expiry = self._get_current_expiry(weeks_ahead=weeks_ahead, use_monthly=use_monthly)
        
        # Breeze order
        if self.primary_broker == "breeze" and self.breeze:
            try:
                order = self.breeze.place_order(
                    stock_code="NIFTY",
                    exchange_code="NFO",
                    product="options",
                    action=action.lower(),
                    order_type="limit",
                    quantity=quantity,
                    price=limit_price,
                    validity="day",
                    strike_price=strike_price,
                    expiry_date=expiry,
                    right=option_type.lower()
                )
                
                return {
                    "status": "success",
                    "order_id": order['Success']['order_id']
                }
                
            except Exception as e:
                logger.error(f"Breeze order failed: {e}")
                
                # Fallback to Kite
                if self.kite:
                    return self._place_kite_order(
                        strike_price, option_type, quantity, action, limit_price, expiry
                    )
                    
                return {"status": "error", "message": str(e)}
                
        # Kite order
        elif self.kite:
            return self._place_kite_order(
                strike_price, option_type, quantity, action, limit_price, expiry
            )
            
        return {"status": "error", "message": "No broker connected"}
    
    def _place_kite_order(
        self,
        strike_price: int,
        option_type: str,
        quantity: int,
        action: str,
        limit_price: float,
        expiry: str
    ) -> Dict[str, Any]:
        """Place order with Kite"""
        try:
            # Format symbol for Kite: NIFTY + YY + MONTH + STRIKE + TYPE
            # expiry is already in format "25AUG" from _get_current_expiry()
            symbol = f"NIFTY{expiry}{strike_price}{option_type}"
            
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                tradingsymbol=symbol,
                transaction_type=self.kite.TRANSACTION_TYPE_SELL if action == "SELL" else self.kite.TRANSACTION_TYPE_BUY,
                quantity=quantity,
                product=self.kite.PRODUCT_MIS,  # Intraday
                order_type=self.kite.ORDER_TYPE_LIMIT,
                price=limit_price,
                validity=self.kite.VALIDITY_DAY
            )
            
            return {
                "status": "success",
                "order_id": order_id
            }
            
        except Exception as e:
            logger.error(f"Kite order failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def close_position(self, position_id: str, reason: str = "Manual") -> Dict[str, Any]:
        """Close a position"""
        if position_id not in self.positions:
            return {"status": "error", "message": "Position not found"}
            
        position = self.positions[position_id]
        
        # Get current price for exit
        exit_price = self._get_option_price(position.strike_price, position.option_type)
        if not exit_price:
            exit_price = position.current_price  # Use last known price
            
        # Paper trading
        if self.mode == TradingMode.PAPER:
            position.close_position(exit_price, reason)
            self.closed_positions.append(position)
            self.today_pnl += position.pnl
            self.paper_balance += position.pnl
            del self.positions[position_id]
            
            logger.info(f"Paper position closed: {position_id}, PnL: {position.pnl}")
            
            return {
                "status": "success",
                "position": position.to_dict(),
                "pnl": position.pnl
            }
            
        # Live trading
        else:
            try:
                # Place exit order (BUY to close SHORT position)
                exit_response = self._place_real_order(
                    position.strike_price,
                    position.option_type,
                    position.quantity,
                    "BUY",
                    exit_price
                )
                
                if exit_response['status'] == 'success':
                    position.close_position(exit_price, reason)
                    self.closed_positions.append(position)
                    self.today_pnl += position.pnl
                    del self.positions[position_id]
                    
                    logger.info(f"Live position closed: {position_id}, PnL: {position.pnl}")
                    
                    return {
                        "status": "success",
                        "position": position.to_dict(),
                        "pnl": position.pnl
                    }
                else:
                    return exit_response
                    
            except Exception as e:
                logger.error(f"Failed to close position: {e}")
                return {"status": "error", "message": str(e)}
    
    def update_positions(self):
        """Update all position prices and check stop losses"""
        positions_to_close = []
        
        for position_id, position in self.positions.items():
            # Get current price
            current_price = self._get_option_price(
                position.strike_price,
                position.option_type
            )
            
            if current_price:
                position.update_price(current_price)
                
                # Check stop loss (for selling options, loss when price increases)
                if current_price >= position.entry_price * (1 + self.stop_loss_percent / 100):
                    positions_to_close.append((position_id, "Stop Loss Hit"))
                    
                # Check target if set
                elif position.target and current_price <= position.target:
                    positions_to_close.append((position_id, "Target Reached"))
        
        # Close positions that hit stop loss or target
        for position_id, reason in positions_to_close:
            self.close_position(position_id, reason)
            
        return {
            "positions_updated": len(self.positions),
            "positions_closed": len(positions_to_close)
        }
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions"""
        return [pos.to_dict() for pos in self.positions.values()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics"""
        open_pnl = sum(pos.pnl for pos in self.positions.values())
        closed_pnl = sum(pos.pnl for pos in self.closed_positions)
        total_pnl = open_pnl + closed_pnl
        
        total_trades = len(self.closed_positions)
        winning_trades = len([p for p in self.closed_positions if p.pnl > 0])
        
        return {
            "mode": self.mode.value,
            "is_trading": self.is_trading,
            "is_paused": self.is_paused,
            "capital": self.capital,
            "available_capital": self.available_capital if self.mode == TradingMode.LIVE else self.paper_balance,
            "open_positions": len(self.positions),
            "total_trades_today": self.today_trades,
            "open_pnl": open_pnl,
            "closed_pnl": closed_pnl,
            "total_pnl": total_pnl,
            "today_pnl": self.today_pnl,
            "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            "max_positions": self.max_positions,
            "active_signals": self.active_signals
        }
    
    def _perform_safety_checks(self) -> bool:
        """Perform safety checks before trading"""
        checks = []
        
        # Check 1: Market hours (9:15 AM to 3:30 PM)
        now = datetime.now()
        market_open = now.replace(hour=9, minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)
        
        # Allow paper trading outside market hours for testing
        if self.mode == TradingMode.PAPER:
            checks.append(("market_hours", True, "Paper trading - market hours check bypassed"))
        elif not (market_open <= now <= market_close):
            logger.warning("Market is closed")
            checks.append(("market_hours", False, "Market is closed"))
        else:
            checks.append(("market_hours", True, "Market is open"))
            
        # Check 2: Daily loss limit
        if abs(self.today_pnl) > self.max_loss_per_day:
            logger.warning("Daily loss limit reached")
            checks.append(("loss_limit", False, f"Daily loss limit reached: {self.today_pnl}"))
        else:
            checks.append(("loss_limit", True, "Within loss limits"))
            
        # Check 3: Broker connection (for live trading)
        if self.mode == TradingMode.LIVE:
            if not (self.breeze or self.kite):
                logger.warning("No broker connected")
                checks.append(("broker", False, "No broker connected"))
            else:
                checks.append(("broker", True, "Broker connected"))
                
        # Check 4: Capital availability
        required_margin = self.lots_per_trade * self.lot_size * 100  # Approximate margin
        if self.available_capital < required_margin:
            logger.warning("Insufficient capital")
            checks.append(("capital", False, "Insufficient capital"))
        else:
            checks.append(("capital", True, "Sufficient capital"))
            
        # Log all checks
        for check_name, passed, message in checks:
            if passed:
                logger.info(f"Safety check '{check_name}': PASSED - {message}")
            else:
                logger.error(f"Safety check '{check_name}': FAILED - {message}")
                
        # Return True only if all checks pass
        return all(passed for _, passed, _ in checks)
    
    def _get_option_price(self, strike_price: int, option_type: str) -> Optional[float]:
        """Get current option price"""
        if self.mode == TradingMode.PAPER:
            # Simulate option price for paper trading
            base_price = 150
            volatility = np.random.uniform(0.9, 1.1)
            return round(base_price * volatility, 2)
            
        try:
            # Try to get from Breeze
            if self.breeze:
                quote = self.breeze.get_option_chain_quotes(
                    stock_code="NIFTY",
                    exchange_code="NFO",
                    strike_price=strike_price,
                    expiry_date=self._get_current_expiry()
                )
                
                if option_type == "CE":
                    return float(quote['Success'][0]['call_ltp'])
                else:
                    return float(quote['Success'][0]['put_ltp'])
                    
            # Try Kite
            elif self.kite:
                symbol = f"NIFTY{self._get_current_expiry()}{strike_price}{option_type}"
                quote = self.kite.ltp([f"NFO:{symbol}"])
                return float(quote[f"NFO:{symbol}"]['last_price'])
                
        except Exception as e:
            logger.error(f"Failed to get option price: {e}")
            
        return None
    
    def _get_current_expiry(self, weeks_ahead: int = 0, use_monthly: bool = False) -> str:
        """
        Get expiry date in Kite format
        
        Args:
            weeks_ahead: 0 for current week, 1 for next week, etc.
            use_monthly: True for monthly expiry (last Tuesday of month)
        
        Returns:
            Expiry in format "25AUG" for Kite
        """
        today = datetime.now()
        
        if use_monthly:
            # Get last Tuesday of current/next month
            if today.day > 25:  # Likely past monthly expiry
                # Move to next month
                if today.month == 12:
                    target_month = 1
                    target_year = today.year + 1
                else:
                    target_month = today.month + 1
                    target_year = today.year
            else:
                target_month = today.month
                target_year = today.year
            
            # Find last Tuesday of target month
            import calendar
            last_day = calendar.monthrange(target_year, target_month)[1]
            last_date = datetime(target_year, target_month, last_day)
            
            # Find last Tuesday
            while last_date.weekday() != 3:  # 3 is Tuesday
                last_date -= timedelta(days=1)
            
            expiry = last_date
        else:
            # Weekly expiry (Tuesday)
            days_until_tuesday = (1 - today.weekday()) % 7
            if days_until_tuesday == 0 and today.hour >= 15:  # After 3 PM on Tuesday
                days_until_tuesday = 7
            
            # Add additional weeks if specified
            days_to_add = days_until_tuesday + (weeks_ahead * 7)
            expiry = today + timedelta(days=days_to_add)
        
        # Format for Kite: YY + MONTH (e.g., "25AUG" for August 2025)
        return expiry.strftime("%y%b").upper()  # Format: 25AUG
    
    def emergency_stop(self) -> Dict[str, Any]:
        """Emergency stop - close all positions immediately"""
        logger.warning("EMERGENCY STOP ACTIVATED")
        
        positions_closed = []
        for position_id in list(self.positions.keys()):
            result = self.close_position(position_id, "Emergency Stop")
            positions_closed.append(result)
            
        self.stop_trading()
        
        return {
            "status": "success",
            "message": "Emergency stop executed",
            "positions_closed": len(positions_closed),
            "total_pnl": self.today_pnl
        }


# Global trading engine instance
_trading_engine = None


def get_trading_engine(mode: str = "paper") -> LiveTradingEngine:
    """Get or create trading engine instance"""
    global _trading_engine
    
    if _trading_engine is None:
        trading_mode = TradingMode.PAPER if mode == "paper" else TradingMode.LIVE
        _trading_engine = LiveTradingEngine(mode=trading_mode)
        _trading_engine.connect_brokers()
        
    return _trading_engine


def reset_trading_engine():
    """Reset trading engine"""
    global _trading_engine
    if _trading_engine:
        _trading_engine.stop_trading(close_all=True)
        _trading_engine = None