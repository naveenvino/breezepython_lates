"""
Smart Order Routing Service
Intelligently routes orders for best execution
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
from enum import Enum

logger = logging.getLogger(__name__)

class ExecutionStrategy(Enum):
    """Order execution strategies"""
    IMMEDIATE = "IMMEDIATE"
    ICEBERG = "ICEBERG"
    TWAP = "TWAP"  # Time-Weighted Average Price
    VWAP = "VWAP"  # Volume-Weighted Average Price
    LIMIT_CHASE = "LIMIT_CHASE"
    ADAPTIVE = "ADAPTIVE"

class SmartOrderRouter:
    """
    Intelligent order routing for optimal execution
    """
    
    def __init__(self, breeze_session=None, kite_session=None):
        self.breeze = breeze_session
        self.kite = kite_session
        
        # Execution parameters
        self.slippage_tolerance = 0.5  # % slippage tolerance
        self.max_order_size = 1000  # Maximum single order size
        self.iceberg_reveal_qty = 100  # Iceberg reveal quantity
        self.chase_ticks = 5  # Number of ticks to chase for limit orders
        
    async def route_order(self, order_params: Dict, strategy: ExecutionStrategy = ExecutionStrategy.IMMEDIATE) -> Dict:
        """
        Route order using specified execution strategy
        
        Args:
            order_params: Order parameters
            strategy: Execution strategy to use
        
        Returns:
            Execution result
        """
        try:
            # Validate order parameters
            validation = self._validate_order(order_params)
            if not validation['valid']:
                return {
                    'status': 'error',
                    'message': validation['message'],
                    'timestamp': datetime.now().isoformat()
                }
            
            # Route based on strategy
            if strategy == ExecutionStrategy.IMMEDIATE:
                return await self._execute_immediate(order_params)
            elif strategy == ExecutionStrategy.ICEBERG:
                return await self._execute_iceberg(order_params)
            elif strategy == ExecutionStrategy.TWAP:
                return await self._execute_twap(order_params)
            elif strategy == ExecutionStrategy.VWAP:
                return await self._execute_vwap(order_params)
            elif strategy == ExecutionStrategy.LIMIT_CHASE:
                return await self._execute_limit_chase(order_params)
            elif strategy == ExecutionStrategy.ADAPTIVE:
                return await self._execute_adaptive(order_params)
            else:
                return await self._execute_immediate(order_params)
                
        except Exception as e:
            logger.error(f"Smart order routing error: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _validate_order(self, order_params: Dict) -> Dict:
        """Validate order parameters"""
        required_fields = ['symbol', 'quantity', 'transaction_type']
        
        for field in required_fields:
            if field not in order_params:
                return {
                    'valid': False,
                    'message': f"Missing required field: {field}"
                }
        
        # Validate quantity
        if order_params['quantity'] <= 0:
            return {
                'valid': False,
                'message': "Quantity must be positive"
            }
        
        # Validate transaction type
        if order_params['transaction_type'] not in ['BUY', 'SELL']:
            return {
                'valid': False,
                'message': "Invalid transaction type"
            }
        
        return {'valid': True}
    
    async def _execute_immediate(self, order_params: Dict) -> Dict:
        """Execute order immediately at market"""
        try:
            # Choose broker based on availability and preference
            broker = self._select_broker(order_params)
            
            if broker == 'breeze' and self.breeze:
                result = self.breeze.place_order(
                    stock_code=order_params['symbol'],
                    exchange_code=order_params.get('exchange', 'NFO'),
                    product=order_params.get('product', 'MIS'),
                    action=order_params['transaction_type'],
                    order_type='MARKET',
                    quantity=order_params['quantity'],
                    price=0,
                    validity='DAY'
                )
            elif broker == 'kite' and self.kite:
                result = self.kite.place_order(
                    variety='regular',
                    exchange=order_params.get('exchange', 'NFO'),
                    tradingsymbol=order_params['symbol'],
                    transaction_type=order_params['transaction_type'],
                    quantity=order_params['quantity'],
                    product=order_params.get('product', 'MIS'),
                    order_type='MARKET',
                    validity='DAY'
                )
            else:
                return {
                    'status': 'error',
                    'message': 'No broker available',
                    'timestamp': datetime.now().isoformat()
                }
            
            return {
                'status': 'success',
                'strategy': 'IMMEDIATE',
                'order_id': result.get('order_id'),
                'broker': broker,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Immediate execution error: {e}")
            raise
    
    async def _execute_iceberg(self, order_params: Dict) -> Dict:
        """Execute large order as iceberg (hidden quantity)"""
        try:
            total_qty = order_params['quantity']
            reveal_qty = min(self.iceberg_reveal_qty, total_qty)
            executed_qty = 0
            order_ids = []
            
            while executed_qty < total_qty:
                # Calculate current slice
                current_qty = min(reveal_qty, total_qty - executed_qty)
                
                # Place order slice
                slice_params = order_params.copy()
                slice_params['quantity'] = current_qty
                
                result = await self._execute_immediate(slice_params)
                
                if result['status'] == 'success':
                    order_ids.append(result['order_id'])
                    executed_qty += current_qty
                    
                    # Wait before next slice (to avoid market impact)
                    import asyncio
                    await asyncio.sleep(2)
                else:
                    break
            
            return {
                'status': 'success',
                'strategy': 'ICEBERG',
                'total_quantity': total_qty,
                'executed_quantity': executed_qty,
                'slices': len(order_ids),
                'order_ids': order_ids,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Iceberg execution error: {e}")
            raise
    
    async def _execute_twap(self, order_params: Dict) -> Dict:
        """Execute order using Time-Weighted Average Price strategy"""
        try:
            import asyncio
            total_qty = order_params['quantity']
            duration_minutes = order_params.get('duration', 30)  # Default 30 minutes
            slices = min(duration_minutes // 5, 10)  # 5-minute intervals, max 10 slices
            
            slice_qty = total_qty // slices
            remainder = total_qty % slices
            
            executed_qty = 0
            order_ids = []
            prices = []
            
            for i in range(slices):
                # Calculate current slice quantity
                current_qty = slice_qty
                if i == slices - 1:  # Add remainder to last slice
                    current_qty += remainder
                
                # Place order slice
                slice_params = order_params.copy()
                slice_params['quantity'] = current_qty
                
                result = await self._execute_immediate(slice_params)
                
                if result['status'] == 'success':
                    order_ids.append(result['order_id'])
                    executed_qty += current_qty
                    
                    # Track execution price (would need to fetch from order status)
                    prices.append(order_params.get('price', 0))
                    
                    # Wait for next interval
                    if i < slices - 1:
                        await asyncio.sleep(300)  # 5 minutes
                else:
                    break
            
            avg_price = sum(prices) / len(prices) if prices else 0
            
            return {
                'status': 'success',
                'strategy': 'TWAP',
                'total_quantity': total_qty,
                'executed_quantity': executed_qty,
                'slices': len(order_ids),
                'average_price': avg_price,
                'order_ids': order_ids,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"TWAP execution error: {e}")
            raise
    
    async def _execute_vwap(self, order_params: Dict) -> Dict:
        """Execute order using Volume-Weighted Average Price strategy"""
        # Similar to TWAP but weighted by market volume
        # This would require real-time volume data
        return await self._execute_twap(order_params)  # Simplified for now
    
    async def _execute_limit_chase(self, order_params: Dict) -> Dict:
        """Execute limit order with price chasing"""
        try:
            # Start with limit order at specified price
            order_params['order_type'] = 'LIMIT'
            attempts = 0
            max_attempts = self.chase_ticks
            
            while attempts < max_attempts:
                result = await self._execute_immediate(order_params)
                
                if result['status'] == 'success':
                    # Check order status after short delay
                    import asyncio
                    await asyncio.sleep(2)
                    
                    # Would need to check actual order status here
                    # For now, assume success
                    return {
                        'status': 'success',
                        'strategy': 'LIMIT_CHASE',
                        'order_id': result['order_id'],
                        'attempts': attempts + 1,
                        'final_price': order_params.get('price'),
                        'timestamp': datetime.now().isoformat()
                    }
                
                # Adjust price for next attempt (chase the market)
                if order_params['transaction_type'] == 'BUY':
                    order_params['price'] *= 1.001  # Increase by 0.1%
                else:
                    order_params['price'] *= 0.999  # Decrease by 0.1%
                
                attempts += 1
            
            # If all attempts failed, execute at market
            order_params['order_type'] = 'MARKET'
            return await self._execute_immediate(order_params)
            
        except Exception as e:
            logger.error(f"Limit chase execution error: {e}")
            raise
    
    async def _execute_adaptive(self, order_params: Dict) -> Dict:
        """Adaptive execution based on market conditions"""
        try:
            # Analyze market conditions
            market_conditions = self._analyze_market_conditions(order_params['symbol'])
            
            # Choose strategy based on conditions
            if market_conditions['volatility'] > 2.0:
                # High volatility - use iceberg
                return await self._execute_iceberg(order_params)
            elif market_conditions['liquidity'] < 1000:
                # Low liquidity - use TWAP
                return await self._execute_twap(order_params)
            elif market_conditions['spread'] > 1.0:
                # Wide spread - use limit chase
                return await self._execute_limit_chase(order_params)
            else:
                # Normal conditions - immediate execution
                return await self._execute_immediate(order_params)
                
        except Exception as e:
            logger.error(f"Adaptive execution error: {e}")
            raise
    
    def _select_broker(self, order_params: Dict) -> str:
        """Select best broker for order execution"""
        # Simple selection logic - can be enhanced
        if self.breeze:
            return 'breeze'
        elif self.kite:
            return 'kite'
        else:
            return None
    
    def _analyze_market_conditions(self, symbol: str) -> Dict:
        """Analyze current market conditions for symbol"""
        # Simplified market analysis
        # In production, would fetch real market data
        return {
            'volatility': 1.5,  # Implied volatility
            'liquidity': 5000,  # Average volume
            'spread': 0.5,  # Bid-ask spread percentage
            'trend': 'neutral'  # Market trend
        }


class BasketOrderService:
    """
    Service for executing basket orders (multiple orders as a group)
    """
    
    def __init__(self, smart_router: SmartOrderRouter):
        self.router = smart_router
        self.baskets: Dict[str, Dict] = {}
    
    async def create_basket(self, basket_name: str, orders: List[Dict]) -> Dict:
        """
        Create a basket of orders
        
        Args:
            basket_name: Name of the basket
            orders: List of order parameters
        
        Returns:
            Basket creation result
        """
        try:
            basket_id = f"BASKET_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            self.baskets[basket_id] = {
                'name': basket_name,
                'orders': orders,
                'created': datetime.now().isoformat(),
                'status': 'CREATED',
                'executed_orders': []
            }
            
            return {
                'status': 'success',
                'basket_id': basket_id,
                'basket_name': basket_name,
                'order_count': len(orders),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Basket creation error: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def execute_basket(self, basket_id: str, strategy: ExecutionStrategy = ExecutionStrategy.IMMEDIATE) -> Dict:
        """
        Execute all orders in a basket
        
        Args:
            basket_id: ID of the basket to execute
            strategy: Execution strategy for all orders
        
        Returns:
            Basket execution result
        """
        try:
            if basket_id not in self.baskets:
                return {
                    'status': 'error',
                    'message': 'Basket not found',
                    'timestamp': datetime.now().isoformat()
                }
            
            basket = self.baskets[basket_id]
            basket['status'] = 'EXECUTING'
            
            successful = []
            failed = []
            
            for order in basket['orders']:
                try:
                    result = await self.router.route_order(order, strategy)
                    
                    if result['status'] == 'success':
                        successful.append({
                            'symbol': order['symbol'],
                            'quantity': order['quantity'],
                            'order_id': result.get('order_id')
                        })
                    else:
                        failed.append({
                            'symbol': order['symbol'],
                            'error': result.get('message')
                        })
                    
                except Exception as e:
                    failed.append({
                        'symbol': order.get('symbol'),
                        'error': str(e)
                    })
            
            basket['status'] = 'EXECUTED'
            basket['executed_orders'] = successful
            
            return {
                'status': 'success',
                'basket_id': basket_id,
                'total_orders': len(basket['orders']),
                'successful': len(successful),
                'failed': len(failed),
                'execution_details': {
                    'successful_orders': successful,
                    'failed_orders': failed
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Basket execution error: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_basket_status(self, basket_id: str) -> Dict:
        """Get status of a basket"""
        if basket_id in self.baskets:
            return self.baskets[basket_id]
        return None


# Global instances
_smart_router: Optional[SmartOrderRouter] = None
_basket_service: Optional[BasketOrderService] = None

def get_smart_router(breeze_session=None, kite_session=None) -> SmartOrderRouter:
    """Get or create smart order router"""
    global _smart_router
    if _smart_router is None:
        _smart_router = SmartOrderRouter(breeze_session, kite_session)
    return _smart_router

def get_basket_service() -> BasketOrderService:
    """Get or create basket order service"""
    global _basket_service
    if _basket_service is None:
        router = get_smart_router()
        _basket_service = BasketOrderService(router)
    return _basket_service