"""
Live Order Executor Service
Handles order execution with smart routing, basket orders, and iceberg orders
Following the strategy:
- Hedge-first entry for margin benefit
- Main-first exit for margin release
- Iceberg orders for quantities exceeding NSE freeze limit
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"

@dataclass
class OptionOrder:
    symbol: str
    strike: int
    option_type: str  # CE or PE
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    tag: Optional[str] = None

@dataclass
class BasketOrder:
    main_order: OptionOrder
    hedge_order: OptionOrder
    signal_id: str
    entry_time: datetime

class LiveOrderExecutor:
    """
    Executes orders for live trading with proper sequencing and margin management
    """
    
    def __init__(self, kite_client):
        self.kite = kite_client
        self.exchange = "NFO"
        self.lot_size = 75  # NIFTY lot size as of Aug 2025
        self.freeze_quantity = 1800  # NSE freeze limit for NIFTY as of Aug 2025
        self.active_positions = {}
        self.order_history = []
        
    def execute_basket_order(self, basket: BasketOrder) -> Dict[str, Any]:
        """
        Execute basket order with hedge-first entry for margin benefit
        
        Args:
            basket: BasketOrder containing main and hedge orders
            
        Returns:
            Execution result with order IDs
        """
        try:
            result = {
                'signal_id': basket.signal_id,
                'entry_time': basket.entry_time.isoformat(),
                'hedge_order_ids': [],
                'main_order_ids': [],
                'status': 'PENDING',
                'error': None
            }
            
            # Step 1: Place HEDGE order first (BUY) for margin benefit
            hedge_symbol = self._format_symbol(
                basket.hedge_order.strike,
                basket.hedge_order.option_type,
                self._get_current_expiry()
            )
            
            hedge_order_ids = self._execute_with_iceberg(
                symbol=hedge_symbol,
                side=OrderSide.BUY,
                quantity=basket.hedge_order.quantity,
                tag=f"{basket.signal_id}_HEDGE"
            )
            
            if not hedge_order_ids:
                result['status'] = 'FAILED'
                result['error'] = 'Hedge order placement failed'
                return result
                
            result['hedge_order_ids'] = hedge_order_ids
            logger.info(f"Hedge order placed: {hedge_symbol} BUY {basket.hedge_order.quantity}")
            
            # Step 2: Place MAIN order (SELL) after hedge is in place
            main_symbol = self._format_symbol(
                basket.main_order.strike,
                basket.main_order.option_type,
                self._get_current_expiry()
            )
            
            main_order_ids = self._execute_with_iceberg(
                symbol=main_symbol,
                side=OrderSide.SELL,
                quantity=basket.main_order.quantity,
                tag=f"{basket.signal_id}_MAIN"
            )
            
            if not main_order_ids:
                # Rollback hedge order if main fails
                logger.error("Main order failed, rolling back hedge order")
                self._cancel_orders(hedge_order_ids)
                result['status'] = 'FAILED'
                result['error'] = 'Main order placement failed, hedge rolled back'
                return result
                
            result['main_order_ids'] = main_order_ids
            result['status'] = 'EXECUTED'
            
            # Store position for tracking
            self.active_positions[basket.signal_id] = {
                'main_symbol': main_symbol,
                'hedge_symbol': hedge_symbol,
                'main_strike': basket.main_order.strike,
                'hedge_strike': basket.hedge_order.strike,
                'option_type': basket.main_order.option_type,
                'quantity': basket.main_order.quantity,
                'entry_time': basket.entry_time,
                'main_orders': main_order_ids,
                'hedge_orders': hedge_order_ids,
                'status': 'ACTIVE'
            }
            
            logger.info(f"Basket order executed successfully for signal {basket.signal_id}")
            return result
            
        except Exception as e:
            logger.error(f"Basket order execution failed: {e}")
            return {
                'signal_id': basket.signal_id,
                'status': 'FAILED',
                'error': str(e)
            }
    
    def exit_basket_position(self, signal_id: str) -> Dict[str, Any]:
        """
        Exit basket position with main-first exit for margin release
        
        Args:
            signal_id: Signal ID of the position to exit
            
        Returns:
            Exit result with order IDs
        """
        try:
            if signal_id not in self.active_positions:
                return {
                    'signal_id': signal_id,
                    'status': 'ERROR',
                    'error': 'Position not found'
                }
            
            position = self.active_positions[signal_id]
            result = {
                'signal_id': signal_id,
                'exit_time': datetime.now().isoformat(),
                'main_exit_ids': [],
                'hedge_exit_ids': [],
                'status': 'PENDING',
                'error': None
            }
            
            # Step 1: Exit MAIN position first (BUY back the SELL) for margin release
            main_exit_ids = self._execute_with_iceberg(
                symbol=position['main_symbol'],
                side=OrderSide.BUY,  # Buy back the sold option
                quantity=position['quantity'],
                tag=f"{signal_id}_MAIN_EXIT"
            )
            
            if not main_exit_ids:
                result['status'] = 'FAILED'
                result['error'] = 'Main position exit failed'
                return result
                
            result['main_exit_ids'] = main_exit_ids
            logger.info(f"Main position exited: {position['main_symbol']} BUY {position['quantity']}")
            
            # Step 2: Exit HEDGE position (SELL the BUY)
            hedge_exit_ids = self._execute_with_iceberg(
                symbol=position['hedge_symbol'],
                side=OrderSide.SELL,  # Sell the bought hedge
                quantity=position['quantity'],
                tag=f"{signal_id}_HEDGE_EXIT"
            )
            
            if not hedge_exit_ids:
                logger.warning(f"Hedge exit failed for {signal_id}, position may be partially closed")
                result['status'] = 'PARTIAL'
                result['error'] = 'Hedge exit failed, main position closed'
            else:
                result['hedge_exit_ids'] = hedge_exit_ids
                result['status'] = 'EXITED'
                logger.info(f"Hedge position exited: {position['hedge_symbol']} SELL {position['quantity']}")
            
            # Update position status
            position['status'] = 'EXITED'
            position['exit_time'] = datetime.now()
            position['exit_orders'] = {
                'main': main_exit_ids,
                'hedge': hedge_exit_ids
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Position exit failed for {signal_id}: {e}")
            return {
                'signal_id': signal_id,
                'status': 'FAILED',
                'error': str(e)
            }
    
    def _execute_with_iceberg(self, symbol: str, side: OrderSide, quantity: int, tag: str) -> List[str]:
        """
        Execute order with iceberg logic if quantity exceeds freeze limit
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Total quantity to execute
            tag: Order tag
            
        Returns:
            List of order IDs
        """
        order_ids = []
        
        try:
            # Check if iceberg is needed
            if quantity <= self.freeze_quantity:
                # Single order
                order_id = self._place_single_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    tag=tag
                )
                if order_id:
                    order_ids.append(order_id)
            else:
                # Split into multiple orders (iceberg)
                num_orders = math.ceil(quantity / self.freeze_quantity)
                remaining = quantity
                
                logger.info(f"Executing iceberg order: {quantity} contracts in {num_orders} slices")
                
                for i in range(num_orders):
                    slice_qty = min(remaining, self.freeze_quantity)
                    
                    order_id = self._place_single_order(
                        symbol=symbol,
                        side=side,
                        quantity=slice_qty,
                        tag=f"{tag}_SLICE_{i+1}"
                    )
                    
                    if order_id:
                        order_ids.append(order_id)
                        remaining -= slice_qty
                        logger.info(f"Iceberg slice {i+1}/{num_orders}: {slice_qty} contracts, order ID: {order_id}")
                    else:
                        logger.error(f"Iceberg slice {i+1} failed for {symbol}")
                        # Cancel previous orders on failure
                        if order_ids:
                            self._cancel_orders(order_ids)
                        return []
                
                logger.info(f"Iceberg order completed: {symbol} {side.value} {quantity} in {num_orders} slices")
            
            return order_ids
            
        except Exception as e:
            logger.error(f"Iceberg execution failed: {e}")
            if order_ids:
                self._cancel_orders(order_ids)
            return []
    
    def _place_single_order(self, symbol: str, side: OrderSide, quantity: int, tag: str) -> Optional[str]:
        """
        Place a single order through Kite
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Order quantity
            tag: Order tag
            
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            order_params = {
                "tradingsymbol": symbol,
                "exchange": self.exchange,
                "transaction_type": side.value,
                "quantity": quantity,
                "order_type": OrderType.MARKET.value,
                "product": "NRML",  # Normal for F&O
                "variety": "regular",
                "validity": "DAY",
                "tag": tag[:20]  # Kite allows max 20 chars
            }
            
            order_id = self.kite.place_order(**order_params)
            
            # Store in history
            self.order_history.append({
                'order_id': order_id,
                'symbol': symbol,
                'side': side.value,
                'quantity': quantity,
                'tag': tag,
                'timestamp': datetime.now()
            })
            
            logger.info(f"Order placed: {order_id} - {symbol} {side.value} {quantity}")
            return order_id
            
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return None
    
    def _cancel_orders(self, order_ids: List[str]):
        """Cancel multiple orders"""
        for order_id in order_ids:
            try:
                self.kite.cancel_order(order_id, variety="regular")
                logger.info(f"Cancelled order: {order_id}")
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {e}")
    
    def _format_symbol(self, strike: int, option_type: str, expiry: str) -> str:
        """
        Format option symbol for Kite
        Example: NIFTY24DEC1925000CE or NIFTY2482925000CE
        """
        # Convert expiry from YYYY-MM-DD to required format
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        
        # Format: NIFTY + YY + MMM + Strike + CE/PE for monthly
        # Format: NIFTY + YY + D + M + Strike + CE/PE for weekly
        year = expiry_date.strftime('%y')  # 24
        
        # Check if it's weekly or monthly expiry
        # Monthly expiry is the last Tuesday of the month
        import calendar
        month_cal = calendar.monthcalendar(expiry_date.year, expiry_date.month)
        
        # Find last Tuesday
        thursdays = []
        for week in month_cal:
            if week[3] != 0:  # Tuesday is index 3
                thursdays.append(week[3])
        
        last_thursday = thursdays[-1]
        
        if expiry_date.day == last_thursday:
            # Monthly expiry
            month = expiry_date.strftime('%b').upper()  # DEC
            symbol = f"NIFTY{year}{month}{strike}{option_type}"
        else:
            # Weekly expiry - use numeric format
            # Format: NIFTY + YY + M + DD (e.g., NIFTY24829 for Aug 29, 2024)
            month_num = expiry_date.month  # 8 for August
            day = expiry_date.day  # 29
            
            # For weekly: NIFTY + YY + M + DD + Strike + CE/PE
            # Example: NIFTY2482925000CE (2024 Aug 29, 25000 CE)
            symbol = f"NIFTY{year}{month_num}{day:02d}{strike}{option_type}"
        
        return symbol
    
    def _get_current_expiry(self) -> str:
        """Get current week expiry date in YYYY-MM-DD format"""
        today = datetime.now()
        days_until_tuesday = (1 - today.weekday()) % 7
        
        # If today is Tuesday after 3:30 PM, get next Tuesday
        if days_until_tuesday == 0:
            if today.hour >= 15 and today.minute >= 30:
                days_until_tuesday = 7
        
        expiry = today + timedelta(days=days_until_tuesday)
        return expiry.strftime('%Y-%m-%d')
    
    def get_active_positions(self) -> Dict[str, Any]:
        """Get all active positions"""
        active = {}
        for signal_id, position in self.active_positions.items():
            if position['status'] == 'ACTIVE':
                active[signal_id] = position
        return active
    
    def get_margin_requirement(self, main_strike: int, hedge_strike: int, 
                              option_type: str, quantity: int) -> float:
        """
        Calculate margin requirement for a spread position
        
        Args:
            main_strike: Strike price of main (sell) leg  
            hedge_strike: Strike price of hedge (buy) leg
            option_type: CE or PE
            quantity: Number of contracts
            
        Returns:
            Estimated margin requirement
        """
        try:
            # For a spread position, margin = spread width * quantity * lot_size
            spread_width = abs(main_strike - hedge_strike)
            
            # Convert to rupees (each point = ₹75 for NIFTY with lot size 75)
            max_loss = spread_width * quantity * self.lot_size
            
            # Add buffer for execution and volatility
            margin_buffer = 1.15  # 15% buffer
            
            estimated_margin = max_loss * margin_buffer
            
            logger.info(f"Margin for {option_type} spread {main_strike}/{hedge_strike} x {quantity}: ₹{estimated_margin:,.2f}")
            return estimated_margin
            
        except Exception as e:
            logger.error(f"Margin calculation failed: {e}")
            # Return conservative estimate
            return 150000.0  # ₹1.5 lakh as fallback
    
    def check_margin_available(self, required_margin: float) -> bool:
        """
        Check if sufficient margin is available
        
        Args:
            required_margin: Margin required for the trade
            
        Returns:
            True if margin available, False otherwise
        """
        try:
            # Get account margins from Kite
            margins = self.kite.margins()
            
            # Check equity segment margins (includes F&O)
            equity_margin = margins.get('equity', {})
            available = equity_margin.get('available', {}).get('live_balance', 0)
            
            logger.info(f"Available margin: ₹{available:,.2f}, Required: ₹{required_margin:,.2f}")
            
            return available >= required_margin
            
        except Exception as e:
            logger.error(f"Margin check failed: {e}")
            return False
    
    def calculate_strike_for_signal(self, spot_price: float, signal_type: str) -> Tuple[int, str]:
        """
        Calculate main strike and option type based on signal
        
        Args:
            spot_price: Current NIFTY spot price
            signal_type: Signal type (S1-S8)
            
        Returns:
            Tuple of (strike_price, option_type)
        """
        # Bearish signals sell CALL, Bullish signals sell PUT
        bearish_signals = ['S3', 'S5', 'S6', 'S8']
        
        if signal_type in bearish_signals:
            # Bearish - Sell CALL
            # Round UP to next 50 strike (ceil)
            strike = math.ceil(spot_price / 50) * 50
            option_type = "CE"
        else:
            # Bullish - Sell PUT  
            # Round DOWN to previous 50 strike (floor)
            strike = math.floor(spot_price / 50) * 50
            option_type = "PE"
        
        logger.info(f"Signal {signal_type}: Spot {spot_price:.2f} -> Strike {strike} {option_type}")
        return strike, option_type
    
    def create_basket_from_signal(self, signal_type: str, spot_price: float, 
                                 quantity: int, signal_id: str) -> BasketOrder:
        """
        Create a basket order from signal parameters
        
        Args:
            signal_type: Signal type (S1-S8)
            spot_price: Current NIFTY spot price
            quantity: Number of contracts
            signal_id: Unique signal identifier
            
        Returns:
            BasketOrder object ready for execution
        """
        # Calculate main strike and option type
        main_strike, option_type = self.calculate_strike_for_signal(spot_price, signal_type)
        
        # Calculate hedge strike (200 points away)
        if option_type == "CE":
            hedge_strike = main_strike + 200  # Further OTM for CALL hedge
        else:
            hedge_strike = main_strike - 200  # Further OTM for PUT hedge
        
        # Create main order (SELL)
        main_order = OptionOrder(
            symbol="NIFTY",
            strike=main_strike,
            option_type=option_type,
            side=OrderSide.SELL,
            quantity=quantity,
            tag=f"{signal_id}_MAIN"
        )
        
        # Create hedge order (BUY)
        hedge_order = OptionOrder(
            symbol="NIFTY",
            strike=hedge_strike,
            option_type=option_type,
            side=OrderSide.BUY,
            quantity=quantity,
            tag=f"{signal_id}_HEDGE"
        )
        
        return BasketOrder(
            main_order=main_order,
            hedge_order=hedge_order,
            signal_id=signal_id,
            entry_time=datetime.now()
        )
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status of a specific order"""
        try:
            order_history = self.kite.order_history(order_id)
            if order_history:
                return order_history[-1]  # Latest status
            return {}
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return {}
    
    def check_market_protection(self, symbol: str, side: OrderSide, price: float) -> bool:
        """
        Check if order price is within 2% protection band
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            price: Order price
            
        Returns:
            True if within protection band, False otherwise
        """
        try:
            # Get current market price
            quote = self.kite.quote([f"{self.exchange}:{symbol}"])
            if not quote:
                return True  # Allow if can't verify
            
            ltp = quote[f"{self.exchange}:{symbol}"]["last_price"]
            
            # Calculate 2% band
            upper_limit = ltp * 1.02
            lower_limit = ltp * 0.98
            
            # Check if price is within band
            if lower_limit <= price <= upper_limit:
                return True
            else:
                logger.warning(f"Price {price} outside 2% band [{lower_limit:.2f}, {upper_limit:.2f}] for LTP {ltp}")
                return False
                
        except Exception as e:
            logger.error(f"Market protection check failed: {e}")
            return True  # Allow on error