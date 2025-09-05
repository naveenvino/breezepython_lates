"""
Multi-Broker Integration Service
Manages multiple broker connections with failover and load balancing
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import threading
from queue import Queue, PriorityQueue
import time

logger = logging.getLogger(__name__)

class BrokerType(Enum):
    ZERODHA = "zerodha"
    BREEZE = "breeze"
    ANGEL = "angel"
    FYERS = "fyers"
    UPSTOX = "upstox"

class OrderStatus(Enum):
    PENDING = "pending"
    PLACED = "placed"
    CONFIRMED = "confirmed"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"

class BrokerStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    MAINTENANCE = "maintenance"

@dataclass
class BrokerConfig:
    """Broker configuration"""
    broker_type: BrokerType
    api_key: str
    api_secret: str
    access_token: Optional[str] = None
    priority: int = 1  # Lower number = higher priority
    enabled: bool = True
    max_requests_per_second: int = 10
    max_orders_per_minute: int = 60
    cooldown_seconds: int = 60
    features: List[str] = field(default_factory=lambda: ["orders", "data", "websocket"])

@dataclass
class BrokerHealth:
    """Broker health metrics"""
    broker_type: BrokerType
    status: BrokerStatus
    last_successful_request: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    success_rate: float = 100.0
    avg_latency_ms: float = 0
    requests_today: int = 0
    orders_today: int = 0

@dataclass
class AdvancedOrder:
    """Advanced order with multiple execution strategies"""
    symbol: str
    quantity: int
    order_type: str  # LIMIT, MARKET, SL, etc.
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    
    # Advanced features
    iceberg_legs: int = 1  # Split into N legs
    iceberg_quantity_variance: float = 0.1  # 10% variance in leg quantities
    
    bracket_stop_loss: Optional[float] = None
    bracket_target: Optional[float] = None
    bracket_trailing_stop: Optional[float] = None
    
    time_in_force: str = "DAY"  # DAY, IOC, GTD
    validity_date: Optional[datetime] = None
    
    retry_count: int = 3
    retry_delay_seconds: int = 2
    
    preferred_broker: Optional[BrokerType] = None
    exclude_brokers: List[BrokerType] = field(default_factory=list)

class MultiBrokerService:
    """
    Manages multiple broker connections with intelligent routing
    """
    
    def __init__(self):
        self.brokers: Dict[BrokerType, BrokerConfig] = {}
        self.broker_health: Dict[BrokerType, BrokerHealth] = {}
        self.broker_clients: Dict[BrokerType, Any] = {}
        
        # Rate limiting
        self.request_queues: Dict[BrokerType, Queue] = {}
        self.rate_limiters: Dict[BrokerType, 'RateLimiter'] = {}
        
        # Order routing
        self.order_queue = PriorityQueue()
        self.pending_orders: Dict[str, AdvancedOrder] = {}
        self.order_history: List[Dict] = []
        
        # Performance metrics
        self.metrics = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'total_requests': 0,
            'broker_distribution': {}
        }
        
        # Initialize default brokers
        self._initialize_default_brokers()
        
        # Start background workers
        self._start_workers()
    
    def _initialize_default_brokers(self):
        """Initialize default broker configurations"""
        # Zerodha (Primary for orders)
        self.add_broker(BrokerConfig(
            broker_type=BrokerType.ZERODHA,
            api_key="",
            api_secret="",
            priority=1,
            max_requests_per_second=3,
            max_orders_per_minute=200,
            features=["orders", "positions", "data"]
        ))
        
        # Breeze (Primary for data)
        self.add_broker(BrokerConfig(
            broker_type=BrokerType.BREEZE,
            api_key="",
            api_secret="",
            priority=2,
            max_requests_per_second=10,
            max_orders_per_minute=60,
            features=["data", "websocket", "orders"]
        ))
    
    def add_broker(self, config: BrokerConfig) -> bool:
        """Add a new broker configuration"""
        try:
            self.brokers[config.broker_type] = config
            self.broker_health[config.broker_type] = BrokerHealth(
                broker_type=config.broker_type,
                status=BrokerStatus.DISCONNECTED
            )
            
            # Initialize rate limiter
            self.rate_limiters[config.broker_type] = RateLimiter(
                max_requests_per_second=config.max_requests_per_second,
                max_requests_per_minute=config.max_orders_per_minute
            )
            
            # Initialize request queue
            self.request_queues[config.broker_type] = Queue()
            
            logger.info(f"Added broker: {config.broker_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding broker: {e}")
            return False
    
    def connect_broker(self, broker_type: BrokerType) -> bool:
        """Connect to a specific broker"""
        try:
            config = self.brokers.get(broker_type)
            if not config:
                return False
            
            # Initialize broker client based on type
            if broker_type == BrokerType.ZERODHA:
                from src.infrastructure.brokers.kite.kite_client import get_kite_client
                client = get_kite_client()
            elif broker_type == BrokerType.BREEZE:
                from src.infrastructure.services.breeze_service import get_breeze_service
                client = get_breeze_service()
            else:
                logger.warning(f"Broker {broker_type.value} not implemented")
                return False
            
            self.broker_clients[broker_type] = client
            self.broker_health[broker_type].status = BrokerStatus.CONNECTED
            self.broker_health[broker_type].last_successful_request = datetime.now()
            
            logger.info(f"Connected to broker: {broker_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to {broker_type.value}: {e}")
            self.broker_health[broker_type].status = BrokerStatus.ERROR
            self.broker_health[broker_type].last_error = str(e)
            return False
    
    def get_best_broker(self, feature: str = "orders", exclude: List[BrokerType] = None) -> Optional[BrokerType]:
        """
        Get the best available broker for a specific feature
        
        Args:
            feature: Required feature (orders, data, websocket)
            exclude: List of brokers to exclude
        
        Returns:
            Best available broker or None
        """
        exclude = exclude or []
        available_brokers = []
        
        for broker_type, config in self.brokers.items():
            if broker_type in exclude:
                continue
            
            if not config.enabled:
                continue
            
            if feature not in config.features:
                continue
            
            health = self.broker_health[broker_type]
            if health.status != BrokerStatus.CONNECTED:
                continue
            
            # Check rate limits
            if self.rate_limiters[broker_type].is_limited():
                continue
            
            # Calculate score based on priority, health, and performance
            score = (
                config.priority * 100 +
                health.error_count * 10 -
                health.success_rate +
                health.avg_latency_ms / 100
            )
            
            available_brokers.append((broker_type, score))
        
        if not available_brokers:
            return None
        
        # Sort by score (lower is better)
        available_brokers.sort(key=lambda x: x[1])
        return available_brokers[0][0]
    
    async def place_advanced_order(self, order: AdvancedOrder) -> Tuple[bool, str, Dict]:
        """
        Place an advanced order with intelligent routing
        
        Returns:
            Tuple of (success, message, order_details)
        """
        order_id = f"MBO_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        try:
            # Select broker
            if order.preferred_broker and order.preferred_broker not in order.exclude_brokers:
                broker = order.preferred_broker
            else:
                broker = self.get_best_broker("orders", order.exclude_brokers)
            
            if not broker:
                return False, "No available broker", {}
            
            # Check if iceberg order
            if order.iceberg_legs > 1:
                return await self._place_iceberg_order(broker, order, order_id)
            
            # Check if bracket order
            if order.bracket_stop_loss or order.bracket_target:
                return await self._place_bracket_order(broker, order, order_id)
            
            # Regular order
            return await self._place_regular_order(broker, order, order_id)
            
        except Exception as e:
            logger.error(f"Error placing advanced order: {e}")
            return False, str(e), {}
    
    async def _place_iceberg_order(self, broker: BrokerType, order: AdvancedOrder, order_id: str) -> Tuple[bool, str, Dict]:
        """Place an iceberg order (split into multiple legs)"""
        try:
            total_quantity = order.quantity
            leg_quantity = total_quantity // order.iceberg_legs
            remaining = total_quantity % order.iceberg_legs
            
            legs_placed = []
            
            for i in range(order.iceberg_legs):
                # Add variance to leg quantity
                variance = int(leg_quantity * order.iceberg_quantity_variance)
                import random
                leg_qty = leg_quantity + random.randint(-variance, variance)
                
                # Ensure we don't exceed total
                if i == order.iceberg_legs - 1:
                    leg_qty = total_quantity - sum(legs_placed)
                
                # Place leg order with slight delay
                leg_order = AdvancedOrder(
                    symbol=order.symbol,
                    quantity=leg_qty,
                    order_type=order.order_type,
                    price=order.price,
                    trigger_price=order.trigger_price
                )
                
                success, msg, details = await self._place_regular_order(broker, leg_order, f"{order_id}_L{i}")
                
                if success:
                    legs_placed.append(leg_qty)
                    
                    # Add delay between legs
                    if i < order.iceberg_legs - 1:
                        await asyncio.sleep(random.uniform(1, 3))
                else:
                    logger.error(f"Failed to place iceberg leg {i}: {msg}")
            
            placed_quantity = sum(legs_placed)
            success = placed_quantity == total_quantity
            
            return success, f"Iceberg order: {placed_quantity}/{total_quantity} placed", {
                "order_id": order_id,
                "legs_placed": len(legs_placed),
                "total_quantity": placed_quantity
            }
            
        except Exception as e:
            logger.error(f"Error placing iceberg order: {e}")
            return False, str(e), {}
    
    async def _place_bracket_order(self, broker: BrokerType, order: AdvancedOrder, order_id: str) -> Tuple[bool, str, Dict]:
        """Place a bracket order with stop loss and target"""
        try:
            client = self.broker_clients.get(broker)
            if not client:
                return False, f"Broker {broker.value} not connected", {}
            
            # Place main order
            main_success, main_msg, main_details = await self._place_regular_order(
                broker, order, f"{order_id}_MAIN"
            )
            
            if not main_success:
                return False, f"Main order failed: {main_msg}", {}
            
            # Place stop loss order
            if order.bracket_stop_loss:
                sl_order = AdvancedOrder(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    order_type="SL",
                    trigger_price=order.bracket_stop_loss
                )
                
                sl_success, sl_msg, sl_details = await self._place_regular_order(
                    broker, sl_order, f"{order_id}_SL"
                )
                
                if not sl_success:
                    logger.error(f"Stop loss order failed: {sl_msg}")
            
            # Place target order
            if order.bracket_target:
                target_order = AdvancedOrder(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    order_type="LIMIT",
                    price=order.bracket_target
                )
                
                target_success, target_msg, target_details = await self._place_regular_order(
                    broker, target_order, f"{order_id}_TARGET"
                )
                
                if not target_success:
                    logger.error(f"Target order failed: {target_msg}")
            
            return True, "Bracket order placed", {
                "order_id": order_id,
                "main_order": main_details,
                "has_stop_loss": order.bracket_stop_loss is not None,
                "has_target": order.bracket_target is not None
            }
            
        except Exception as e:
            logger.error(f"Error placing bracket order: {e}")
            return False, str(e), {}
    
    async def _place_regular_order(self, broker: BrokerType, order: AdvancedOrder, order_id: str) -> Tuple[bool, str, Dict]:
        """Place a regular order through specified broker"""
        try:
            # Check rate limit
            if not self.rate_limiters[broker].allow_request():
                # Try fallback broker
                fallback = self.get_best_broker("orders", [broker])
                if fallback:
                    broker = fallback
                else:
                    return False, "Rate limited on all brokers", {}
            
            # Get broker client
            client = self.broker_clients.get(broker)
            if not client:
                return False, f"Broker {broker.value} not available", {}
            
            # Track request
            start_time = time.time()
            
            # Place order based on broker type
            if broker == BrokerType.ZERODHA:
                # Zerodha specific implementation
                result = await self._place_zerodha_order(client, order)
            elif broker == BrokerType.BREEZE:
                # Breeze specific implementation  
                result = await self._place_breeze_order(client, order)
            else:
                return False, f"Broker {broker.value} not implemented", {}
            
            # Update metrics
            latency_ms = (time.time() - start_time) * 1000
            self._update_broker_metrics(broker, True, latency_ms)
            
            return True, "Order placed successfully", {
                "order_id": order_id,
                "broker": broker.value,
                "latency_ms": latency_ms
            }
            
        except Exception as e:
            logger.error(f"Error placing regular order: {e}")
            self._update_broker_metrics(broker, False, 0)
            return False, str(e), {}
    
    async def _place_zerodha_order(self, client, order: AdvancedOrder) -> Dict:
        """Place order through Zerodha"""
        # Implementation would go here
        return {"status": "success"}
    
    async def _place_breeze_order(self, client, order: AdvancedOrder) -> Dict:
        """Place order through Breeze"""
        # Implementation would go here
        return {"status": "success"}
    
    def _update_broker_metrics(self, broker: BrokerType, success: bool, latency_ms: float):
        """Update broker health metrics"""
        health = self.broker_health[broker]
        
        if success:
            health.last_successful_request = datetime.now()
            health.error_count = 0
        else:
            health.error_count += 1
        
        # Update success rate (rolling average)
        health.success_rate = (health.success_rate * 0.9) + (100 if success else 0) * 0.1
        
        # Update latency (rolling average)
        if latency_ms > 0:
            health.avg_latency_ms = (health.avg_latency_ms * 0.9) + (latency_ms * 0.1)
        
        # Update counters
        health.requests_today += 1
        
        # Update distribution metrics
        if broker not in self.metrics['broker_distribution']:
            self.metrics['broker_distribution'][broker.value] = 0
        self.metrics['broker_distribution'][broker.value] += 1
    
    def get_broker_status(self) -> Dict[str, Any]:
        """Get status of all brokers"""
        status = {}
        
        for broker_type, health in self.broker_health.items():
            config = self.brokers[broker_type]
            
            status[broker_type.value] = {
                "status": health.status.value,
                "enabled": config.enabled,
                "priority": config.priority,
                "success_rate": f"{health.success_rate:.1f}%",
                "avg_latency_ms": f"{health.avg_latency_ms:.0f}",
                "error_count": health.error_count,
                "requests_today": health.requests_today,
                "features": config.features,
                "rate_limit": {
                    "current": self.rate_limiters[broker_type].current_requests,
                    "max_per_second": config.max_requests_per_second
                }
            }
        
        return status
    
    def _start_workers(self):
        """Start background worker threads"""
        # Start order processor
        threading.Thread(target=self._process_order_queue, daemon=True).start()
        
        # Start health monitor
        threading.Thread(target=self._monitor_broker_health, daemon=True).start()
    
    def _process_order_queue(self):
        """Process orders from queue"""
        while True:
            try:
                if not self.order_queue.empty():
                    priority, order = self.order_queue.get()
                    asyncio.run(self.place_advanced_order(order))
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing order queue: {e}")
    
    def _monitor_broker_health(self):
        """Monitor broker health and reconnect if needed"""
        while True:
            try:
                for broker_type, health in self.broker_health.items():
                    if health.status == BrokerStatus.DISCONNECTED:
                        # Try to reconnect
                        self.connect_broker(broker_type)
                    
                    elif health.status == BrokerStatus.ERROR and health.error_count > 5:
                        # Too many errors, mark as disconnected
                        health.status = BrokerStatus.DISCONNECTED
                    
                    elif health.status == BrokerStatus.RATE_LIMITED:
                        # Check if cooldown period has passed
                        if health.last_error:
                            last_error_time = datetime.fromisoformat(health.last_error)
                            if datetime.now() - last_error_time > timedelta(seconds=60):
                                health.status = BrokerStatus.CONNECTED
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring broker health: {e}")

class RateLimiter:
    """Rate limiter for API requests"""
    
    def __init__(self, max_requests_per_second: int = 10, max_requests_per_minute: int = 60):
        self.max_per_second = max_requests_per_second
        self.max_per_minute = max_requests_per_minute
        self.requests = []
        self.current_requests = 0
    
    def allow_request(self) -> bool:
        """Check if request is allowed"""
        now = time.time()
        
        # Remove old requests
        self.requests = [r for r in self.requests if now - r < 60]
        
        # Check per minute limit
        if len(self.requests) >= self.max_per_minute:
            return False
        
        # Check per second limit
        recent = [r for r in self.requests if now - r < 1]
        if len(recent) >= self.max_per_second:
            return False
        
        # Allow request
        self.requests.append(now)
        self.current_requests = len(self.requests)
        return True
    
    def is_limited(self) -> bool:
        """Check if currently rate limited"""
        return not self.allow_request()

# Singleton instance
_instance = None

def get_multi_broker_service() -> MultiBrokerService:
    """Get singleton instance"""
    global _instance
    if _instance is None:
        _instance = MultiBrokerService()
    return _instance