"""
Kite Order Service
Handles order placement, modification, and management for NIFTY options
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date, time
from enum import Enum

logger = logging.getLogger(__name__)

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"

class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"

class Product(Enum):
    MIS = "MIS"      # Intraday
    NRML = "NRML"    # Normal (for F&O)
    CNC = "CNC"      # Cash and carry (for equity)

class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    TRIGGER_PENDING = "TRIGGER PENDING"

class KiteOrderService:
    """
    Service for placing and managing orders on Kite Connect
    """
    
    def __init__(self, kite_client):
        self.kite_client = kite_client
        self.exchange = "NFO"  # National Futures & Options
        self.lot_size = 75     # NIFTY lot size
        self.num_lots = 10     # Default number of lots to trade
        
    def place_option_order(self, 
                          symbol: str,
                          transaction_type: TransactionType,
                          quantity: int,
                          order_type: OrderType = OrderType.MARKET,
                          price: Optional[float] = None,
                          trigger_price: Optional[float] = None,
                          tag: Optional[str] = None) -> str:
        """
        Place an option order
        
        Args:
            symbol: Option symbol (e.g., NIFTY24DEC1925000CE)
            transaction_type: BUY or SELL
            quantity: Number of shares (lots * lot_size)
            order_type: MARKET, LIMIT, etc.
            price: Limit price (required for LIMIT orders)
            trigger_price: Trigger price (required for SL orders)
            tag: Optional tag for tracking
            
        Returns:
            order_id: Kite order ID
        """
        try:
            order_params = {
                "tradingsymbol": symbol,
                "exchange": self.exchange,
                "transaction_type": transaction_type.value,
                "quantity": quantity,
                "order_type": order_type.value,
                "product": Product.NRML.value,
                "variety": "regular",
                "validity": "DAY"
            }
            
            if order_type == OrderType.LIMIT and price is not None:
                order_params["price"] = price
            
            if order_type in [OrderType.SL, OrderType.SL_M] and trigger_price is not None:
                order_params["trigger_price"] = trigger_price
                if order_type == OrderType.SL and price is not None:
                    order_params["price"] = price
            
            if tag:
                order_params["tag"] = tag[:20]  # Kite allows max 20 chars
            
            order_id = self.kite_client.place_order(**order_params)
            logger.info(f"Order placed: {symbol} {transaction_type.value} {quantity} @ {order_type.value}")
            return order_id
            
        except Exception as e:
            logger.error(f"Order placement failed for {symbol}: {e}")
            raise
    
    def place_option_spread(self,
                           main_symbol: str,
                           hedge_symbol: str,
                           quantity: int = None,
                           tag: Optional[str] = None) -> Tuple[str, str]:
        """
        Place option spread (main position SELL, hedge position BUY)
        
        Args:
            main_symbol: Main option symbol to SELL
            hedge_symbol: Hedge option symbol to BUY
            quantity: Number of shares (defaults to num_lots * lot_size)
            tag: Optional tag for tracking
            
        Returns:
            Tuple of (main_order_id, hedge_order_id)
        """
        if quantity is None:
            quantity = self.num_lots * self.lot_size
        
        try:
            # Place main position (SELL)
            main_order_id = self.place_option_order(
                symbol=main_symbol,
                transaction_type=TransactionType.SELL,
                quantity=quantity,
                order_type=OrderType.MARKET,
                tag=f"{tag}_MAIN" if tag else "MAIN"
            )
            
            # Place hedge position (BUY)
            hedge_order_id = self.place_option_order(
                symbol=hedge_symbol,
                transaction_type=TransactionType.BUY,
                quantity=quantity,
                order_type=OrderType.MARKET,
                tag=f"{tag}_HEDGE" if tag else "HEDGE"
            )
            
            logger.info(f"Spread placed: SELL {main_symbol}, BUY {hedge_symbol}")
            return main_order_id, hedge_order_id
            
        except Exception as e:
            logger.error(f"Spread order placement failed: {e}")
            # TODO: Handle partial fills - cancel the successful leg if one fails
            raise
    
    def square_off_position(self, symbol: str, quantity: int, is_buy_position: bool) -> str:
        """
        Square off an existing position
        
        Args:
            symbol: Option symbol
            quantity: Quantity to square off
            is_buy_position: True if current position is BUY (will SELL to square off)
            
        Returns:
            order_id: Square off order ID
        """
        transaction_type = TransactionType.SELL if is_buy_position else TransactionType.BUY
        
        return self.place_option_order(
            symbol=symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=OrderType.MARKET,
            tag="SQUARE_OFF"
        )
    
    def square_off_all_positions(self) -> List[str]:
        """
        Square off all open positions
        Typically used at 3:15 PM on expiry day
        
        Returns:
            List of square off order IDs
        """
        try:
            positions = self.kite_client.get_positions()
            net_positions = positions.get('net', [])
            
            order_ids = []
            
            for position in net_positions:
                if position['exchange'] == self.exchange and position['quantity'] != 0:
                    symbol = position['tradingsymbol']
                    quantity = abs(position['quantity'])
                    is_buy = position['quantity'] > 0
                    
                    try:
                        order_id = self.square_off_position(symbol, quantity, is_buy)
                        order_ids.append(order_id)
                        logger.info(f"Squared off: {symbol} qty: {quantity}")
                    except Exception as e:
                        logger.error(f"Failed to square off {symbol}: {e}")
            
            return order_ids
            
        except Exception as e:
            logger.error(f"Failed to square off all positions: {e}")
            raise
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get current status of an order"""
        try:
            order_history = self.kite_client.get_order_history(order_id)
            if order_history:
                return order_history[-1]  # Latest status
            return {}
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            raise
    
    def is_order_complete(self, order_id: str) -> bool:
        """Check if an order is complete"""
        status = self.get_order_status(order_id)
        return status.get('status') == OrderStatus.COMPLETE.value
    
    def cancel_pending_orders(self) -> List[str]:
        """Cancel all pending orders"""
        try:
            orders = self.kite_client.get_orders()
            cancelled_ids = []
            
            for order in orders:
                if order['status'] in [OrderStatus.PENDING.value, OrderStatus.OPEN.value]:
                    try:
                        self.kite_client.cancel_order(order['order_id'], order['variety'])
                        cancelled_ids.append(order['order_id'])
                        logger.info(f"Cancelled order: {order['order_id']}")
                    except Exception as e:
                        logger.error(f"Failed to cancel order {order['order_id']}: {e}")
            
            return cancelled_ids
            
        except Exception as e:
            logger.error(f"Failed to cancel pending orders: {e}")
            raise
    
    def check_and_square_off_expiry(self) -> List[str]:
        """
        Check if it's expiry day and time to square off (3:15 PM)
        Returns list of order IDs if positions were squared off
        """
        current_time = datetime.now()
        
        # Check if today is Thursday (expiry day)
        if current_time.weekday() == 3:  # Thursday
            # Check if it's 3:15 PM or later
            if current_time.time() >= time(15, 15):
                logger.info("Expiry day square-off triggered at 3:15 PM")
                return self.square_off_all_positions()
        
        return []
    
    def get_position_pnl(self) -> Dict[str, float]:
        """Get current P&L for all positions"""
        try:
            positions = self.kite_client.get_positions()
            
            total_pnl = 0.0
            realized_pnl = 0.0
            unrealized_pnl = 0.0
            position_details = {}
            
            # Calculate realized P&L from day positions (closed)
            for position in positions.get('day', []):
                if position['quantity'] == 0 and position.get('pnl', 0) != 0:
                    realized_pnl += position.get('pnl', 0.0)
            
            # Calculate unrealized P&L from net positions (open)
            for position in positions.get('net', []):
                if position['quantity'] != 0:
                    pnl = position.get('pnl', 0.0)
                    unrealized_pnl += pnl
                    position_details[position['tradingsymbol']] = pnl
            
            total_pnl = realized_pnl + unrealized_pnl
            
            return {
                'total_pnl': total_pnl,
                'realized_pnl': realized_pnl,
                'unrealized_pnl': unrealized_pnl,
                'positions': position_details
            }
            
        except Exception as e:
            logger.error(f"Failed to get position P&L: {e}")
            raise