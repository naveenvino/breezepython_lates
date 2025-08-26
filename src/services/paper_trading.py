"""
Paper Trading System
Simulates real trading without actual money for safe testing
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_MARKET = "STOP_LOSS_MARKET"

@dataclass
class PaperOrder:
    order_id: str
    symbol: str
    quantity: int
    order_type: OrderType
    side: str  # BUY or SELL
    price: Optional[float]
    stop_price: Optional[float]
    status: OrderStatus
    timestamp: datetime
    executed_price: Optional[float] = None
    executed_time: Optional[datetime] = None
    rejection_reason: Optional[str] = None

@dataclass
class PaperPosition:
    symbol: str
    quantity: int  # Positive for long, negative for short
    average_price: float
    current_price: float
    pnl: float
    unrealized_pnl: float
    realized_pnl: float

@dataclass
class PaperAccount:
    account_id: str
    initial_capital: float
    current_capital: float
    available_margin: float
    used_margin: float
    positions: Dict[str, PaperPosition]
    orders: List[PaperOrder]
    trades: List[Dict]
    created_at: datetime

class PaperTradingEngine:
    """Paper trading engine for simulation"""
    
    def __init__(self, initial_capital: float = 500000):
        self.account = PaperAccount(
            account_id=str(uuid.uuid4()),
            initial_capital=initial_capital,
            current_capital=initial_capital,
            available_margin=initial_capital,
            used_margin=0,
            positions={},
            orders=[],
            trades=[],
            created_at=datetime.now()
        )
        
        self.price_feed = {}  # Current market prices
        self.is_running = False
        self.execution_delay = 0.5  # Simulate execution delay
        
    async def start(self):
        """Start paper trading engine"""
        self.is_running = True
        logger.info(f"Paper trading started with capital: ₹{self.account.initial_capital:,.2f}")
        
        # Start background tasks
        asyncio.create_task(self._process_orders())
        asyncio.create_task(self._update_positions())
        
    async def stop(self):
        """Stop paper trading engine"""
        self.is_running = False
        logger.info("Paper trading stopped")
        
    async def place_order(self, symbol: str, quantity: int, order_type: str, 
                          side: str, price: Optional[float] = None,
                          stop_price: Optional[float] = None) -> Dict:
        """Place a paper order"""
        
        # Validate order
        validation = self._validate_order(symbol, quantity, order_type, side, price)
        if not validation['valid']:
            return {
                "status": "error",
                "message": validation['reason'],
                "order_id": None
            }
        
        # Create order
        order = PaperOrder(
            order_id=f"PAPER_{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            quantity=quantity,
            order_type=OrderType[order_type.upper()],
            side=side.upper(),
            price=price,
            stop_price=stop_price,
            status=OrderStatus.PENDING,
            timestamp=datetime.now()
        )
        
        self.account.orders.append(order)
        
        logger.info(f"Paper order placed: {order.order_id} - {side} {quantity} {symbol}")
        
        # Process market orders immediately
        if order.order_type == OrderType.MARKET:
            await self._execute_order(order)
        
        return {
            "status": "success",
            "message": "Order placed successfully",
            "order_id": order.order_id,
            "order": asdict(order)
        }
        
    def _validate_order(self, symbol: str, quantity: int, order_type: str, 
                        side: str, price: Optional[float]) -> Dict:
        """Validate order parameters"""
        
        # Check quantity
        if quantity <= 0:
            return {"valid": False, "reason": "Invalid quantity"}
        
        # Check margin
        required_margin = self._calculate_margin(symbol, quantity, price)
        if required_margin > self.account.available_margin:
            return {"valid": False, "reason": "Insufficient margin"}
        
        # Check position limits
        if len(self.account.positions) >= 10:
            return {"valid": False, "reason": "Maximum positions reached"}
        
        return {"valid": True}
        
    def _calculate_margin(self, symbol: str, quantity: int, 
                         price: Optional[float]) -> float:
        """Calculate required margin for order"""
        
        # Get current price
        current_price = price or self.price_feed.get(symbol, 100)
        
        # Simple margin calculation (10% for options)
        if "CE" in symbol or "PE" in symbol:
            margin_percent = 0.1
        else:
            margin_percent = 0.2
            
        return quantity * current_price * margin_percent
        
    async def _execute_order(self, order: PaperOrder):
        """Execute a paper order"""
        
        # Simulate execution delay
        await asyncio.sleep(self.execution_delay)
        
        # Get execution price
        current_price = self.price_feed.get(order.symbol, 100)
        
        if order.order_type == OrderType.MARKET:
            execution_price = current_price
        elif order.order_type == OrderType.LIMIT:
            if order.side == "BUY" and current_price <= order.price:
                execution_price = order.price
            elif order.side == "SELL" and current_price >= order.price:
                execution_price = order.price
            else:
                return  # Order not executable yet
        else:
            return  # Handle other order types
        
        # Update order
        order.status = OrderStatus.EXECUTED
        order.executed_price = execution_price
        order.executed_time = datetime.now()
        
        # Update position
        self._update_position(order)
        
        # Record trade
        trade = {
            "trade_id": f"TRADE_{uuid.uuid4().hex[:8]}",
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "price": execution_price,
            "timestamp": order.executed_time.isoformat(),
            "pnl": 0
        }
        
        self.account.trades.append(trade)
        
        logger.info(f"Order executed: {order.order_id} at ₹{execution_price:.2f}")
        
    def _update_position(self, order: PaperOrder):
        """Update position after order execution"""
        
        symbol = order.symbol
        
        if symbol not in self.account.positions:
            # New position
            self.account.positions[symbol] = PaperPosition(
                symbol=symbol,
                quantity=order.quantity if order.side == "BUY" else -order.quantity,
                average_price=order.executed_price,
                current_price=order.executed_price,
                pnl=0,
                unrealized_pnl=0,
                realized_pnl=0
            )
        else:
            # Update existing position
            position = self.account.positions[symbol]
            
            if order.side == "BUY":
                # Adding to position
                total_value = (position.quantity * position.average_price + 
                             order.quantity * order.executed_price)
                position.quantity += order.quantity
                position.average_price = total_value / position.quantity if position.quantity != 0 else 0
            else:
                # Reducing or reversing position
                if position.quantity > 0:
                    # Closing long position
                    realized_pnl = (order.executed_price - position.average_price) * min(order.quantity, position.quantity)
                    position.realized_pnl += realized_pnl
                    self.account.current_capital += realized_pnl
                    
                position.quantity -= order.quantity
                
                if position.quantity == 0:
                    # Position closed
                    del self.account.positions[symbol]
                elif position.quantity < 0:
                    # Position reversed
                    position.average_price = order.executed_price
                    
        # Update margin
        self._update_margin()
        
    def _update_margin(self):
        """Update margin calculations"""
        
        used_margin = 0
        for position in self.account.positions.values():
            used_margin += abs(position.quantity) * position.average_price * 0.1
            
        self.account.used_margin = used_margin
        self.account.available_margin = self.account.current_capital - used_margin
        
    async def _process_orders(self):
        """Process pending orders"""
        
        while self.is_running:
            try:
                for order in self.account.orders:
                    if order.status == OrderStatus.PENDING:
                        
                        # Check limit orders
                        if order.order_type == OrderType.LIMIT:
                            current_price = self.price_feed.get(order.symbol, 100)
                            
                            if order.side == "BUY" and current_price <= order.price:
                                await self._execute_order(order)
                            elif order.side == "SELL" and current_price >= order.price:
                                await self._execute_order(order)
                                
                        # Check stop orders
                        elif order.order_type == OrderType.STOP_LOSS:
                            current_price = self.price_feed.get(order.symbol, 100)
                            
                            if order.side == "SELL" and current_price <= order.stop_price:
                                await self._execute_order(order)
                            elif order.side == "BUY" and current_price >= order.stop_price:
                                await self._execute_order(order)
                                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing orders: {e}")
                await asyncio.sleep(5)
                
    async def _update_positions(self):
        """Update position P&L"""
        
        while self.is_running:
            try:
                total_pnl = 0
                
                for position in self.account.positions.values():
                    # Get current price
                    current_price = self.price_feed.get(position.symbol, position.average_price)
                    position.current_price = current_price
                    
                    # Calculate P&L
                    if position.quantity > 0:
                        position.unrealized_pnl = (current_price - position.average_price) * position.quantity
                    else:
                        position.unrealized_pnl = (position.average_price - current_price) * abs(position.quantity)
                        
                    position.pnl = position.unrealized_pnl + position.realized_pnl
                    total_pnl += position.pnl
                    
                # Update account capital
                self.account.current_capital = self.account.initial_capital + total_pnl
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error updating positions: {e}")
                await asyncio.sleep(10)
                
    def update_price(self, symbol: str, price: float):
        """Update market price for symbol"""
        self.price_feed[symbol] = price
        
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel a pending order"""
        
        for order in self.account.orders:
            if order.order_id == order_id and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                logger.info(f"Order cancelled: {order_id}")
                
                return {
                    "status": "success",
                    "message": "Order cancelled",
                    "order_id": order_id
                }
                
        return {
            "status": "error",
            "message": "Order not found or already executed",
            "order_id": order_id
        }
        
    def get_positions(self) -> List[Dict]:
        """Get all positions"""
        return [asdict(pos) for pos in self.account.positions.values()]
        
    def get_orders(self) -> List[Dict]:
        """Get all orders"""
        return [asdict(order) for order in self.account.orders]
        
    def get_trades(self) -> List[Dict]:
        """Get all trades"""
        return self.account.trades
        
    def get_account_summary(self) -> Dict:
        """Get account summary"""
        
        total_pnl = sum(pos.pnl for pos in self.account.positions.values())
        total_trades = len(self.account.trades)
        winning_trades = sum(1 for t in self.account.trades if t.get('pnl', 0) > 0)
        
        return {
            "account_id": self.account.account_id,
            "initial_capital": self.account.initial_capital,
            "current_capital": self.account.current_capital,
            "total_pnl": total_pnl,
            "pnl_percentage": (total_pnl / self.account.initial_capital * 100) if self.account.initial_capital > 0 else 0,
            "available_margin": self.account.available_margin,
            "used_margin": self.account.used_margin,
            "open_positions": len(self.account.positions),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            "created_at": self.account.created_at.isoformat()
        }
        
    def reset_account(self, initial_capital: Optional[float] = None):
        """Reset paper trading account"""
        
        capital = initial_capital or self.account.initial_capital
        
        self.account = PaperAccount(
            account_id=str(uuid.uuid4()),
            initial_capital=capital,
            current_capital=capital,
            available_margin=capital,
            used_margin=0,
            positions={},
            orders=[],
            trades=[],
            created_at=datetime.now()
        )
        
        logger.info(f"Paper trading account reset with capital: ₹{capital:,.2f}")
        
    def export_trades(self, filepath: str):
        """Export trades to JSON file"""
        
        data = {
            "account_summary": self.get_account_summary(),
            "positions": self.get_positions(),
            "orders": self.get_orders(),
            "trades": self.get_trades()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
            
        logger.info(f"Trades exported to {filepath}")

# Singleton instance
_paper_trading_engine = None

def get_paper_trading_engine(initial_capital: float = 500000) -> PaperTradingEngine:
    """Get or create paper trading engine instance"""
    global _paper_trading_engine
    if _paper_trading_engine is None:
        _paper_trading_engine = PaperTradingEngine(initial_capital)
    return _paper_trading_engine