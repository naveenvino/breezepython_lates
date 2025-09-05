"""
Trading Execution Service - Complete trading functionality
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_MARKET = "SL-M"

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class ProductType(Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    OPTIONS = "OPTIONS"

@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    product_type: ProductType
    price: float = 0
    trigger_price: float = 0
    stop_loss: float = 0
    target: float = 0
    trailing_stop: float = 0
    is_hedge: bool = False
    parent_order_id: Optional[str] = None

@dataclass
class OrderResponse:
    order_id: str
    status: str
    message: str
    timestamp: datetime
    details: Dict

class TradingExecutionService:
    def __init__(self, breeze_client=None):
        self.breeze = breeze_client
        self.active_orders = {}
        self.positions = {}
        self.stop_losses = {}
        self.targets = {}
        self.paper_trading = False
        self.paper_positions = {}
        self.paper_balance = 500000  # 5 lakh paper money
        
    async def place_order(self, request: OrderRequest) -> OrderResponse:
        """Place a new order"""
        try:
            if self.paper_trading:
                return await self._place_paper_order(request)
            
            # Real order placement
            order_data = {
                "stock_code": request.symbol,
                "exchange_code": "NSE",
                "product": request.product_type.value,
                "action": request.side.value,
                "order_type": request.order_type.value,
                "quantity": str(request.quantity),
                "price": str(request.price) if request.price > 0 else "",
                "validity": "DAY",
                "stoploss": str(request.stop_loss) if request.stop_loss > 0 else "",
                "target": str(request.target) if request.target > 0 else ""
            }
            
            if self.breeze:
                response = self.breeze.place_order(**order_data)
                
                if response.get('Status') == 200:
                    order_id = response['Success']['order_id']
                    
                    # Track order
                    self.active_orders[order_id] = {
                        'request': request,
                        'status': 'OPEN',
                        'timestamp': datetime.now()
                    }
                    
                    # Set up stop loss and target if specified
                    if request.stop_loss > 0:
                        await self.set_stop_loss(order_id, request.stop_loss, request.trailing_stop)
                    
                    if request.target > 0:
                        await self.set_target(order_id, request.target)
                    
                    return OrderResponse(
                        order_id=order_id,
                        status='SUCCESS',
                        message='Order placed successfully',
                        timestamp=datetime.now(),
                        details=response['Success']
                    )
            
            return OrderResponse(
                order_id='',
                status='FAILED',
                message='Breeze client not initialized',
                timestamp=datetime.now(),
                details={}
            )
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return OrderResponse(
                order_id='',
                status='ERROR',
                message=str(e),
                timestamp=datetime.now(),
                details={}
            )
    
    async def _place_paper_order(self, request: OrderRequest) -> OrderResponse:
        """Place paper trading order"""
        order_id = f"PAPER_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Simulate order execution
        execution_price = request.price if request.price > 0 else self._get_market_price(request.symbol)
        order_value = execution_price * request.quantity
        
        if request.side == OrderSide.BUY:
            if order_value > self.paper_balance:
                return OrderResponse(
                    order_id='',
                    status='REJECTED',
                    message='Insufficient paper balance',
                    timestamp=datetime.now(),
                    details={'required': order_value, 'available': self.paper_balance}
                )
            
            self.paper_balance -= order_value
            
        # Track paper position
        position_key = f"{request.symbol}_{request.product_type.value}"
        if position_key not in self.paper_positions:
            self.paper_positions[position_key] = {
                'symbol': request.symbol,
                'quantity': 0,
                'avg_price': 0,
                'pnl': 0
            }
        
        pos = self.paper_positions[position_key]
        if request.side == OrderSide.BUY:
            new_qty = pos['quantity'] + request.quantity
            pos['avg_price'] = ((pos['avg_price'] * pos['quantity']) + (execution_price * request.quantity)) / new_qty
            pos['quantity'] = new_qty
        else:
            pos['quantity'] -= request.quantity
            realized_pnl = (execution_price - pos['avg_price']) * request.quantity
            pos['pnl'] += realized_pnl
            self.paper_balance += execution_price * request.quantity
        
        return OrderResponse(
            order_id=order_id,
            status='SUCCESS',
            message='Paper order executed',
            timestamp=datetime.now(),
            details={
                'execution_price': execution_price,
                'order_value': order_value,
                'paper_balance': self.paper_balance
            }
        )
    
    def _get_market_price(self, symbol: str) -> float:
        """Get current market price for paper trading"""
        try:
            # Import here to avoid circular imports
            from src.services.live_market_service import get_market_service
            
            # Get market service instance
            market_service = get_market_service()
            
            # Check if it's an index symbol or option
            if symbol in ['NIFTY', 'BANKNIFTY', 'INDIAVIX']:
                # For index symbols, get spot price
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, create a new task
                    spot_data = asyncio.create_task(market_service.get_spot_price(symbol))
                    # Use a timeout to avoid blocking
                    try:
                        result = asyncio.wait_for(spot_data, timeout=5.0)
                        spot_data = result
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout fetching spot price for {symbol}, using fallback")
                        return 100.0
                else:
                    spot_data = loop.run_until_complete(market_service.get_spot_price(symbol))
                
                if spot_data and 'ltp' in spot_data:
                    return float(spot_data['ltp'])
            else:
                # For options, parse symbol and get option quote
                import re
                match = re.search(r'(\d+)(CE|PE)$', symbol)
                if match:
                    strike = int(match.group(1))
                    option_type = match.group(2)
                    
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        quote_task = asyncio.create_task(market_service.get_option_quote(strike, option_type))
                        try:
                            quote = asyncio.wait_for(quote_task, timeout=5.0)
                        except asyncio.TimeoutError:
                            logger.warning(f"Timeout fetching option price for {symbol}, using fallback")
                            return 100.0
                    else:
                        quote = loop.run_until_complete(market_service.get_option_quote(strike, option_type))
                    
                    if quote and 'ltp' in quote:
                        return float(quote['ltp'])
            
            # Fallback to default price
            logger.warning(f"Could not fetch real market price for {symbol}, using default")
            return 100.0
            
        except Exception as e:
            logger.error(f"Error fetching market price for {symbol}: {e}")
            return 100.0
    
    async def set_stop_loss(self, order_id: str, stop_loss: float, trailing: float = 0):
        """Set or update stop loss for a position"""
        self.stop_losses[order_id] = {
            'price': stop_loss,
            'trailing': trailing,
            'initial': stop_loss,
            'last_updated': datetime.now()
        }
        
        if trailing > 0:
            # Start trailing stop loss monitoring
            asyncio.create_task(self._monitor_trailing_stop(order_id))
    
    async def set_target(self, order_id: str, target: float):
        """Set profit target for a position"""
        self.targets[order_id] = {
            'price': target,
            'created': datetime.now()
        }
    
    async def _monitor_trailing_stop(self, order_id: str):
        """Monitor and update trailing stop loss"""
        while order_id in self.stop_losses and self.stop_losses[order_id]['trailing'] > 0:
            try:
                # Get current price
                current_price = await self._get_current_price(order_id)
                sl_data = self.stop_losses[order_id]
                
                # Update trailing stop if price moved favorably
                new_stop = current_price - sl_data['trailing']
                if new_stop > sl_data['price']:
                    sl_data['price'] = new_stop
                    sl_data['last_updated'] = datetime.now()
                    logger.info(f"Trailing stop updated for {order_id}: {new_stop}")
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring trailing stop: {e}")
                await asyncio.sleep(5)
    
    async def _get_current_price(self, order_id: str) -> float:
        """Get current price for the symbol in the order"""
        try:
            if order_id in self.active_orders:
                symbol = self.active_orders[order_id]['request'].symbol
                
                # Import here to avoid circular imports
                from src.services.live_market_service import get_market_service
                
                # Get market service instance
                market_service = get_market_service()
                
                # Check if it's an index symbol or option
                if symbol in ['NIFTY', 'BANKNIFTY', 'INDIAVIX']:
                    # For index symbols, get spot price
                    spot_data = await market_service.get_spot_price(symbol)
                    if spot_data and 'ltp' in spot_data:
                        return float(spot_data['ltp'])
                else:
                    # For options, parse symbol and get option quote
                    import re
                    match = re.search(r'(\d+)(CE|PE)$', symbol)
                    if match:
                        strike = int(match.group(1))
                        option_type = match.group(2)
                        
                        quote = await market_service.get_option_quote(strike, option_type)
                        if quote and 'ltp' in quote:
                            return float(quote['ltp'])
                
                # Fallback to default
                logger.warning(f"Could not fetch real current price for {symbol}, using default")
                return 100.0
            
            return 0
        except Exception as e:
            logger.error(f"Error fetching current price for order {order_id}: {e}")
            return 100.0
    
    async def modify_order(self, order_id: str, modifications: Dict) -> OrderResponse:
        """Modify an existing order"""
        try:
            if self.paper_trading:
                # Paper trading modification
                if order_id in self.active_orders:
                    self.active_orders[order_id]['request'].__dict__.update(modifications)
                    return OrderResponse(
                        order_id=order_id,
                        status='SUCCESS',
                        message='Paper order modified',
                        timestamp=datetime.now(),
                        details=modifications
                    )
            
            # Real order modification
            if self.breeze:
                response = self.breeze.modify_order(
                    order_id=order_id,
                    **modifications
                )
                
                if response.get('Status') == 200:
                    return OrderResponse(
                        order_id=order_id,
                        status='SUCCESS',
                        message='Order modified successfully',
                        timestamp=datetime.now(),
                        details=response['Success']
                    )
            
            return OrderResponse(
                order_id=order_id,
                status='FAILED',
                message='Failed to modify order',
                timestamp=datetime.now(),
                details={}
            )
            
        except Exception as e:
            logger.error(f"Error modifying order: {e}")
            return OrderResponse(
                order_id=order_id,
                status='ERROR',
                message=str(e),
                timestamp=datetime.now(),
                details={}
            )
    
    async def cancel_order(self, order_id: str) -> OrderResponse:
        """Cancel an existing order"""
        try:
            if self.paper_trading:
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                    return OrderResponse(
                        order_id=order_id,
                        status='SUCCESS',
                        message='Paper order cancelled',
                        timestamp=datetime.now(),
                        details={}
                    )
            
            # Real order cancellation
            if self.breeze:
                response = self.breeze.cancel_order(
                    exchange_code="NSE",
                    order_id=order_id
                )
                
                if response.get('Status') == 200:
                    if order_id in self.active_orders:
                        self.active_orders[order_id]['status'] = 'CANCELLED'
                    
                    return OrderResponse(
                        order_id=order_id,
                        status='SUCCESS',
                        message='Order cancelled successfully',
                        timestamp=datetime.now(),
                        details=response['Success']
                    )
            
            return OrderResponse(
                order_id=order_id,
                status='FAILED',
                message='Failed to cancel order',
                timestamp=datetime.now(),
                details={}
            )
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return OrderResponse(
                order_id=order_id,
                status='ERROR',
                message=str(e),
                timestamp=datetime.now(),
                details={}
            )
    
    async def place_hedge_order(self, main_order_id: str, hedge_percentage: float = 30) -> OrderResponse:
        """Place a hedge order based on main position"""
        if main_order_id not in self.active_orders:
            return OrderResponse(
                order_id='',
                status='FAILED',
                message='Main order not found',
                timestamp=datetime.now(),
                details={}
            )
        
        main_order = self.active_orders[main_order_id]['request']
        
        # Calculate hedge quantity (30% of main position)
        hedge_quantity = int(main_order.quantity * (hedge_percentage / 100))
        
        # Create hedge order (opposite side, different strike)
        hedge_request = OrderRequest(
            symbol=self._get_hedge_symbol(main_order.symbol),
            side=OrderSide.BUY if main_order.side == OrderSide.SELL else OrderSide.SELL,
            quantity=hedge_quantity,
            order_type=OrderType.MARKET,
            product_type=main_order.product_type,
            is_hedge=True,
            parent_order_id=main_order_id
        )
        
        return await self.place_order(hedge_request)
    
    def _get_hedge_symbol(self, main_symbol: str) -> str:
        """Get hedge symbol (different strike)"""
        # Logic to determine hedge strike (e.g., 200 points away)
        # For now, return modified symbol
        return f"{main_symbol}_HEDGE"
    
    def toggle_paper_trading(self, enabled: bool):
        """Toggle paper trading mode"""
        self.paper_trading = enabled
        if enabled:
            logger.info("Paper trading mode enabled")
        else:
            logger.info("Live trading mode enabled")
    
    def get_paper_positions(self) -> Dict:
        """Get all paper trading positions"""
        total_pnl = sum(pos['pnl'] for pos in self.paper_positions.values())
        return {
            'positions': self.paper_positions,
            'balance': self.paper_balance,
            'total_pnl': total_pnl,
            'is_paper': True
        }
    
    async def square_off_all(self) -> List[OrderResponse]:
        """Square off all open positions"""
        responses = []
        
        for position_id, position in self.positions.items():
            # Place opposite order to square off
            square_off_request = OrderRequest(
                symbol=position['symbol'],
                side=OrderSide.SELL if position['side'] == 'BUY' else OrderSide.BUY,
                quantity=position['quantity'],
                order_type=OrderType.MARKET,
                product_type=ProductType.INTRADAY
            )
            
            response = await self.place_order(square_off_request)
            responses.append(response)
        
        return responses

# Singleton instance
_trading_service = None

def get_trading_service(breeze_client=None):
    global _trading_service
    if _trading_service is None:
        _trading_service = TradingExecutionService(breeze_client)
    return _trading_service