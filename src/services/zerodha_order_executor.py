"""
Zerodha Order Execution Service
Handles real order placement through Kite Connect API
"""

import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import os
from dotenv import load_dotenv

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None
    logging.warning("KiteConnect not installed. Run: pip install kiteconnect")

load_dotenv()
logger = logging.getLogger(__name__)

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"

class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    TRIGGER_PENDING = "TRIGGER PENDING"

@dataclass
class OrderRequest:
    """Order request parameters"""
    symbol: str  # e.g., "NIFTY24DEC25000PE"
    exchange: str = "NFO"
    transaction_type: str = "SELL"  # SELL for option writing
    quantity: int = 75  # 1 lot = 75
    order_type: OrderType = OrderType.MARKET
    product: str = "MIS"  # MIS for intraday, NRML for carry forward
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    tag: Optional[str] = None

@dataclass
class OrderResponse:
    """Order placement response"""
    order_id: str
    status: str
    message: str
    average_price: Optional[float] = None
    quantity_filled: Optional[int] = None
    timestamp: Optional[datetime] = None

class ZerodhaOrderExecutor:
    """
    Executes orders through Zerodha Kite Connect API
    """
    
    def __init__(self):
        self.kite = None
        self.is_connected = False
        
        # Load credentials
        self.api_key = os.getenv('KITE_API_KEY')
        self.api_secret = os.getenv('KITE_API_SECRET')
        self.access_token = None
        
        # Order tracking
        self.pending_orders: Dict[str, OrderRequest] = {}
        self.executed_orders: Dict[str, OrderResponse] = {}
        
        # Trading parameters
        self.max_orders_per_minute = 10
        self.last_order_time = None
        self.order_count = 0
        
        # Initialize connection
        self._initialize_kite()
    
    def _initialize_kite(self):
        """Initialize Kite Connect"""
        try:
            if not self.api_key:
                logger.warning("Kite API key not found in environment")
                return False
            
            if KiteConnect is None:
                logger.error("KiteConnect library not installed")
                return False
            
            self.kite = KiteConnect(api_key=self.api_key)
            
            # Try to load saved access token
            self._load_access_token()
            
            if self.access_token:
                self.kite.set_access_token(self.access_token)
                self.is_connected = True
                logger.info("Kite Connect initialized with saved credentials")
            else:
                logger.warning("No credentials found. Authentication required.")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Kite Connect: {e}")
            return False
    
    def _load_access_token(self):
        """Load saved access token from file"""
        try:
            token_file = "logs/kite_access_token.txt"
            if os.path.exists(token_file):
                with open(token_file, 'r') as f:
                    self.access_token = f.read().strip()
                    logger.info("Loaded credentials from secure storage")
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
    
    def _save_access_token(self, token: str):
        """Save access token to file"""
        try:
            os.makedirs("logs", exist_ok=True)
            with open("logs/kite_access_token.txt", 'w') as f:
                f.write(token)
            logger.info("Saved credentials to secure storage")
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
    
    def authenticate(self, request_token: str) -> bool:
        """
        Authenticate with Kite Connect using request token
        
        Args:
            request_token: Token from Kite login redirect
            
        Returns:
            True if authentication successful
        """
        try:
            if not self.kite:
                self._initialize_kite()
            
            # Generate access token
            data = self.kite.generate_session(
                request_token=request_token,
                api_secret=self.api_secret
            )
            
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            self.is_connected = True
            
            # Save token for future use
            self._save_access_token(self.access_token)
            
            logger.info(f"Authentication successful. User: {data.get('user_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def get_login_url(self) -> str:
        """Get Kite login URL"""
        if self.kite:
            return self.kite.login_url()
        return f"https://kite.zerodha.com/connect/login?api_key={self.api_key}"
    
    def place_order(self, request: OrderRequest) -> OrderResponse:
        """
        Place an order through Kite Connect
        
        Args:
            request: Order request parameters
            
        Returns:
            OrderResponse with order details
        """
        try:
            if not self.is_connected:
                return OrderResponse(
                    order_id="",
                    status="FAILED",
                    message="Not connected to Kite. Please authenticate first."
                )
            
            # Rate limiting
            if not self._check_rate_limit():
                return OrderResponse(
                    order_id="",
                    status="FAILED",
                    message="Rate limit exceeded. Please wait."
                )
            
            # Prepare order parameters
            order_params = {
                "tradingsymbol": request.symbol,
                "exchange": request.exchange,
                "transaction_type": request.transaction_type,
                "quantity": request.quantity,
                "order_type": request.order_type.value,
                "product": request.product,
                "validity": "DAY"
            }
            
            # Add price for limit orders
            if request.order_type == OrderType.LIMIT:
                order_params["price"] = request.price
            elif request.order_type in [OrderType.SL, OrderType.SL_M]:
                order_params["trigger_price"] = request.trigger_price
                if request.order_type == OrderType.SL:
                    order_params["price"] = request.price
            
            # Add tag if provided
            if request.tag:
                order_params["tag"] = request.tag
            
            # Place order
            order_id = self.kite.place_order(**order_params)
            
            # Track order
            self.pending_orders[order_id] = request
            
            logger.info(f"Order placed successfully: {order_id} for {request.symbol}")
            
            return OrderResponse(
                order_id=str(order_id),
                status="PENDING",
                message="Order placed successfully",
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return OrderResponse(
                order_id="",
                status="FAILED",
                message=str(e)
            )
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            if not self.is_connected:
                logger.error("Not connected to Kite")
                return False
            
            self.kite.cancel_order(
                variety="regular",
                order_id=order_id
            )
            
            logger.info(f"Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get order status"""
        try:
            if not self.is_connected:
                return None
            
            orders = self.kite.orders()
            for order in orders:
                if str(order['order_id']) == order_id:
                    return {
                        'order_id': order['order_id'],
                        'status': order['status'],
                        'average_price': order.get('average_price', 0),
                        'filled_quantity': order.get('filled_quantity', 0),
                        'pending_quantity': order.get('pending_quantity', 0),
                        'message': order.get('status_message', '')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching order status: {e}")
            return None
    
    def get_positions(self) -> List[Dict]:
        """Get all positions"""
        try:
            if not self.is_connected:
                return []
            
            positions = self.kite.positions()
            return positions.get('net', [])
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def square_off_position(self, symbol: str, quantity: int) -> OrderResponse:
        """Square off a position"""
        try:
            # For squaring off, reverse the transaction type
            positions = self.get_positions()
            
            for pos in positions:
                if pos['tradingsymbol'] == symbol:
                    # Determine transaction type for square off
                    if pos['quantity'] > 0:
                        transaction_type = "SELL"
                    else:
                        transaction_type = "BUY"
                        quantity = abs(quantity)
                    
                    # Place square off order
                    request = OrderRequest(
                        symbol=symbol,
                        exchange="NFO",
                        transaction_type=transaction_type,
                        quantity=quantity,
                        order_type=OrderType.MARKET,
                        product=pos['product'],
                        tag="SQUARE_OFF"
                    )
                    
                    return self.place_order(request)
            
            return OrderResponse(
                order_id="",
                status="FAILED",
                message=f"Position not found for {symbol}"
            )
            
        except Exception as e:
            logger.error(f"Square off failed: {e}")
            return OrderResponse(
                order_id="",
                status="FAILED",
                message=str(e)
            )
    
    def get_margins(self) -> Dict:
        """Get account margins"""
        try:
            if not self.is_connected:
                return {}
            
            margins = self.kite.margins()
            return margins.get('equity', {})
            
        except Exception as e:
            logger.error(f"Error fetching margins: {e}")
            return {}
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        now = datetime.now()
        
        if self.last_order_time:
            time_diff = (now - self.last_order_time).total_seconds()
            if time_diff < 60:  # Within last minute
                if self.order_count >= self.max_orders_per_minute:
                    logger.warning("Rate limit reached")
                    return False
            else:
                # Reset counter
                self.order_count = 0
        
        self.last_order_time = now
        self.order_count += 1
        return True
    
    def create_option_symbol(self, strike: int, option_type: str, expiry: str = None) -> str:
        """
        Create option symbol for Zerodha
        
        Args:
            strike: Strike price
            option_type: 'CE' or 'PE'
            expiry: Expiry date (optional, defaults to current week)
            
        Returns:
            Symbol like "NIFTY24DEC25000PE"
        """
        if not expiry:
            # Get current weekly expiry (Tuesday)
            today = datetime.now()
            days_ahead = 1 - today.weekday()  # Tuesday is 1
            if days_ahead <= 0:
                days_ahead += 7
            expiry_date = today + timedelta(days=days_ahead)
        else:
            expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        
        # Format: NIFTY24DEC25000PE
        month = expiry_date.strftime('%b').upper()
        year = expiry_date.strftime('%y')
        
        symbol = f"NIFTY{year}{month}{strike}{option_type}"
        return symbol

# Singleton instance
_instance = None

def get_zerodha_executor() -> ZerodhaOrderExecutor:
    """Get singleton instance of Zerodha executor"""
    global _instance
    if _instance is None:
        _instance = ZerodhaOrderExecutor()
    return _instance