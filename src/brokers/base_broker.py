from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class ProductType(Enum):
    CNC = "CNC"  # Cash & Carry
    MIS = "MIS"  # Intraday
    NRML = "NRML"  # Normal

@dataclass
class Order:
    symbol: str
    quantity: int
    side: OrderSide
    order_type: OrderType
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    product_type: ProductType = ProductType.MIS
    tag: Optional[str] = None
    validity: str = "DAY"
    disclosed_quantity: int = 0
    
@dataclass
class Position:
    symbol: str
    quantity: int
    product_type: ProductType
    average_price: float
    last_price: float
    pnl: float
    unrealized_pnl: float
    realized_pnl: float
    
@dataclass
class Holdings:
    symbol: str
    quantity: int
    average_price: float
    last_price: float
    pnl: float
    product: str
    
@dataclass
class MarketQuote:
    symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    bid_quantity: int
    ask_quantity: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime

class BaseBroker(ABC):
    """Abstract base class for all broker implementations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_connected = False
        self._validate_config()
        
    @abstractmethod
    def _validate_config(self):
        """Validate broker-specific configuration"""
        pass
        
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to broker"""
        pass
        
    @abstractmethod
    def disconnect(self):
        """Disconnect from broker"""
        pass
        
    @abstractmethod
    def place_order(self, order: Order) -> Dict[str, Any]:
        """Place an order"""
        pass
        
    @abstractmethod
    def modify_order(self, order_id: str, order: Order) -> Dict[str, Any]:
        """Modify an existing order"""
        pass
        
    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order"""
        pass
        
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status of a specific order"""
        pass
        
    @abstractmethod
    def get_orders(self) -> List[Dict[str, Any]]:
        """Get all orders for the day"""
        pass
        
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get all open positions"""
        pass
        
    @abstractmethod
    def get_holdings(self) -> List[Holdings]:
        """Get holdings"""
        pass
        
    @abstractmethod
    def get_quote(self, symbol: str) -> MarketQuote:
        """Get market quote for a symbol"""
        pass
        
    @abstractmethod
    def get_historical_data(
        self, 
        symbol: str, 
        from_date: datetime, 
        to_date: datetime,
        interval: str = "5minute"
    ) -> List[Dict[str, Any]]:
        """Get historical data"""
        pass
        
    @abstractmethod
    def get_margin(self) -> Dict[str, Any]:
        """Get margin/funds information"""
        pass
        
    @abstractmethod
    def square_off_position(self, symbol: str, quantity: int = None) -> Dict[str, Any]:
        """Square off a position"""
        pass
        
    @abstractmethod
    def convert_position(
        self, 
        symbol: str, 
        quantity: int,
        from_product: ProductType,
        to_product: ProductType
    ) -> Dict[str, Any]:
        """Convert position from one product type to another"""
        pass
        
    def is_market_open(self) -> bool:
        """Check if market is open"""
        now = datetime.now()
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_open <= now <= market_close and now.weekday() < 5
        
    def validate_order(self, order: Order) -> tuple[bool, str]:
        """Basic order validation"""
        if order.quantity <= 0:
            return False, "Quantity must be positive"
            
        if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and not order.price:
            return False, f"{order.order_type.value} order requires price"
            
        if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and not order.trigger_price:
            return False, f"{order.order_type.value} order requires trigger price"
            
        return True, "Valid"