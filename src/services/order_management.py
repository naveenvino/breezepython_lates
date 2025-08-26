"""
Advanced Order Management Service
Handles bulk operations, modifications, and cancellations
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class OrderAction(Enum):
    """Order action types"""
    PLACE = "PLACE"
    MODIFY = "MODIFY"
    CANCEL = "CANCEL"
    SQUARE_OFF = "SQUARE_OFF"

class OrderStatus(Enum):
    """Order status types"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class OrderManagementService:
    """
    Comprehensive order management service
    """
    
    def __init__(self, breeze_session=None, kite_session=None):
        self.breeze = breeze_session
        self.kite = kite_session
        self.active_orders: Dict[str, Dict] = {}
        self.order_history: List[Dict] = []
    
    async def cancel_all_orders(self, product_type: Optional[str] = None) -> Dict:
        """
        Cancel all pending orders
        
        Args:
            product_type: Optional filter by product type (MIS, NRML, CNC)
        
        Returns:
            Summary of cancelled orders
        """
        try:
            cancelled = []
            failed = []
            
            # Get all pending orders
            pending_orders = await self.get_pending_orders()
            
            for order in pending_orders:
                # Filter by product type if specified
                if product_type and order.get('product') != product_type:
                    continue
                
                try:
                    # Cancel order based on broker
                    if order.get('broker') == 'breeze' and self.breeze:
                        result = self.breeze.cancel_order(
                            order_id=order['order_id'],
                            exchange_code=order.get('exchange', 'NFO')
                        )
                    elif order.get('broker') == 'kite' and self.kite:
                        result = self.kite.cancel_order(
                            variety=order.get('variety', 'regular'),
                            order_id=order['order_id']
                        )
                    else:
                        continue
                    
                    if result:
                        cancelled.append(order['order_id'])
                        logger.info(f"Cancelled order: {order['order_id']}")
                except Exception as e:
                    failed.append({'order_id': order['order_id'], 'error': str(e)})
                    logger.error(f"Failed to cancel order {order['order_id']}: {e}")
            
            return {
                'status': 'success',
                'cancelled_count': len(cancelled),
                'failed_count': len(failed),
                'cancelled_orders': cancelled,
                'failed_orders': failed,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def modify_bulk_orders(self, modifications: List[Dict]) -> Dict:
        """
        Modify multiple orders in bulk
        
        Args:
            modifications: List of order modifications
                [{
                    'order_id': 'xxx',
                    'quantity': 100,
                    'price': 150.5,
                    'trigger_price': 149.0
                }]
        
        Returns:
            Summary of modifications
        """
        try:
            modified = []
            failed = []
            
            for mod in modifications:
                try:
                    order_id = mod['order_id']
                    
                    # Get original order details
                    order = self.active_orders.get(order_id)
                    if not order:
                        failed.append({'order_id': order_id, 'error': 'Order not found'})
                        continue
                    
                    # Modify based on broker
                    if order.get('broker') == 'breeze' and self.breeze:
                        result = self.breeze.modify_order(
                            order_id=order_id,
                            quantity=mod.get('quantity', order['quantity']),
                            price=mod.get('price', order['price']),
                            trigger_price=mod.get('trigger_price')
                        )
                    elif order.get('broker') == 'kite' and self.kite:
                        result = self.kite.modify_order(
                            variety=order.get('variety', 'regular'),
                            order_id=order_id,
                            quantity=mod.get('quantity'),
                            price=mod.get('price'),
                            trigger_price=mod.get('trigger_price')
                        )
                    else:
                        continue
                    
                    if result:
                        modified.append(order_id)
                        # Update local cache
                        self.active_orders[order_id].update(mod)
                        logger.info(f"Modified order: {order_id}")
                    
                except Exception as e:
                    failed.append({'order_id': mod.get('order_id'), 'error': str(e)})
                    logger.error(f"Failed to modify order: {e}")
            
            return {
                'status': 'success',
                'modified_count': len(modified),
                'failed_count': len(failed),
                'modified_orders': modified,
                'failed_orders': failed,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error modifying bulk orders: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def square_off_all_positions(self, product_type: Optional[str] = None) -> Dict:
        """
        Square off all open positions
        
        Args:
            product_type: Optional filter by product type
        
        Returns:
            Summary of squared off positions
        """
        try:
            squared_off = []
            failed = []
            
            # Get all open positions
            positions = await self.get_open_positions()
            
            for position in positions:
                # Filter by product type if specified
                if product_type and position.get('product') != product_type:
                    continue
                
                try:
                    # Calculate square off quantity
                    qty = abs(position['quantity'])
                    transaction_type = 'BUY' if position['quantity'] < 0 else 'SELL'
                    
                    # Place square off order
                    if position.get('broker') == 'breeze' and self.breeze:
                        result = self.breeze.place_order(
                            stock_code=position['symbol'],
                            exchange_code=position.get('exchange', 'NFO'),
                            product=position.get('product', 'MIS'),
                            action=transaction_type,
                            order_type='MARKET',
                            quantity=qty,
                            price=0,
                            validity='DAY'
                        )
                    elif position.get('broker') == 'kite' and self.kite:
                        result = self.kite.place_order(
                            variety='regular',
                            exchange=position.get('exchange', 'NFO'),
                            tradingsymbol=position['symbol'],
                            transaction_type=transaction_type,
                            quantity=qty,
                            product=position.get('product', 'MIS'),
                            order_type='MARKET',
                            validity='DAY'
                        )
                    else:
                        continue
                    
                    if result:
                        squared_off.append({
                            'symbol': position['symbol'],
                            'quantity': qty,
                            'order_id': result.get('order_id')
                        })
                        logger.info(f"Squared off position: {position['symbol']}")
                    
                except Exception as e:
                    failed.append({'symbol': position['symbol'], 'error': str(e)})
                    logger.error(f"Failed to square off {position['symbol']}: {e}")
            
            return {
                'status': 'success',
                'squared_off_count': len(squared_off),
                'failed_count': len(failed),
                'squared_off_positions': squared_off,
                'failed_positions': failed,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error squaring off positions: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_pending_orders(self) -> List[Dict]:
        """Get all pending orders"""
        pending_orders = []
        
        try:
            # Get from Breeze
            if self.breeze:
                breeze_orders = self.breeze.get_order_list(exchange_code='NFO')
                if breeze_orders and breeze_orders.get('Success'):
                    for order in breeze_orders['Success']:
                        if order.get('status') in ['PENDING', 'OPEN']:
                            pending_orders.append({
                                'broker': 'breeze',
                                'order_id': order.get('order_id'),
                                'symbol': order.get('stock_code'),
                                'quantity': order.get('quantity'),
                                'price': order.get('price'),
                                'status': order.get('status'),
                                'product': order.get('product'),
                                'exchange': order.get('exchange_code')
                            })
            
            # Get from Kite
            if self.kite:
                kite_orders = self.kite.orders()
                for order in kite_orders:
                    if order['status'] in ['PENDING', 'OPEN', 'TRIGGER PENDING']:
                        pending_orders.append({
                            'broker': 'kite',
                            'order_id': order['order_id'],
                            'symbol': order['tradingsymbol'],
                            'quantity': order['quantity'],
                            'price': order['price'],
                            'status': order['status'],
                            'product': order['product'],
                            'exchange': order['exchange'],
                            'variety': order['variety']
                        })
        
        except Exception as e:
            logger.error(f"Error fetching pending orders: {e}")
        
        return pending_orders
    
    async def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        open_positions = []
        
        try:
            # Get from Breeze
            if self.breeze:
                breeze_positions = self.breeze.get_portfolio_positions()
                if breeze_positions and breeze_positions.get('Success'):
                    for pos in breeze_positions['Success']:
                        if pos.get('quantity', 0) != 0:
                            open_positions.append({
                                'broker': 'breeze',
                                'symbol': pos.get('stock_code'),
                                'quantity': pos.get('quantity'),
                                'avg_price': pos.get('average_price'),
                                'pnl': pos.get('profit_and_loss'),
                                'product': pos.get('product'),
                                'exchange': pos.get('exchange_code')
                            })
            
            # Get from Kite
            if self.kite:
                kite_positions = self.kite.positions()
                for pos in kite_positions.get('net', []):
                    if pos['quantity'] != 0:
                        open_positions.append({
                            'broker': 'kite',
                            'symbol': pos['tradingsymbol'],
                            'quantity': pos['quantity'],
                            'avg_price': pos['average_price'],
                            'pnl': pos['pnl'],
                            'product': pos['product'],
                            'exchange': pos['exchange']
                        })
        
        except Exception as e:
            logger.error(f"Error fetching open positions: {e}")
        
        return open_positions
    
    def get_order_history(self, limit: int = 100) -> List[Dict]:
        """Get order history"""
        return self.order_history[-limit:]


# Global instance
_order_manager: Optional[OrderManagementService] = None

def get_order_manager(breeze_session=None, kite_session=None) -> OrderManagementService:
    """Get or create order management service"""
    global _order_manager
    if _order_manager is None:
        _order_manager = OrderManagementService(breeze_session, kite_session)
    return _order_manager