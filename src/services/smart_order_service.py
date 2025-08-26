from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
import math
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class OrderExecutionStrategy(Enum):
    IMMEDIATE = "immediate"
    TWAP = "twap"  # Time-Weighted Average Price
    VWAP = "vwap"  # Volume-Weighted Average Price
    ICEBERG = "iceberg"
    SLICE = "slice"

@dataclass
class SmartOrder:
    symbol: str
    quantity: int
    side: str  # BUY or SELL
    order_type: str  # MARKET, LIMIT, SL, SL-M
    product_type: str  # MIS, CNC, NRML
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    disclosed_quantity: Optional[int] = None
    validity: str = "DAY"
    tag: Optional[str] = None
    
@dataclass
class BasketOrder:
    orders: List[SmartOrder]
    execution_strategy: OrderExecutionStrategy = OrderExecutionStrategy.IMMEDIATE
    name: Optional[str] = None
    
@dataclass
class SplitOrderConfig:
    max_quantity_per_order: int
    time_interval_seconds: int = 0
    price_range_percent: float = 0.0
    randomize_quantity: bool = False
    
@dataclass
class IcebergOrderConfig:
    visible_quantity: int
    total_quantity: int
    price_levels: Optional[List[float]] = None
    refresh_interval_seconds: int = 30

class SmartOrderService:
    def __init__(self, broker_client):
        self.broker = broker_client
        self.active_orders = {}
        self.basket_executions = {}
        
    async def place_basket_order(
        self,
        basket: BasketOrder,
        parallel: bool = False
    ) -> Dict[str, Any]:
        """
        Execute multiple orders as a basket
        
        Args:
            basket: BasketOrder containing list of orders
            parallel: Execute orders in parallel (faster) or sequential (safer)
        
        Returns:
            Dictionary with execution results for each order
        """
        basket_id = f"BASKET_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.basket_executions[basket_id] = {
            "status": "INITIATED",
            "orders": [],
            "start_time": datetime.now()
        }
        
        results = {
            "basket_id": basket_id,
            "total_orders": len(basket.orders),
            "successful": 0,
            "failed": 0,
            "orders": []
        }
        
        try:
            if parallel:
                # Execute all orders simultaneously
                tasks = [
                    self._place_single_order(order, basket_id)
                    for order in basket.orders
                ]
                order_results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Execute orders one by one
                order_results = []
                for order in basket.orders:
                    result = await self._place_single_order(order, basket_id)
                    order_results.append(result)
                    
                    # Small delay between orders to avoid rate limiting
                    if len(basket.orders) > 1:
                        await asyncio.sleep(0.1)
            
            # Process results
            for i, result in enumerate(order_results):
                if isinstance(result, Exception):
                    results["failed"] += 1
                    results["orders"].append({
                        "index": i,
                        "symbol": basket.orders[i].symbol,
                        "status": "FAILED",
                        "error": str(result)
                    })
                else:
                    if result.get("status") == "success":
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                    results["orders"].append(result)
            
            self.basket_executions[basket_id]["status"] = "COMPLETED"
            self.basket_executions[basket_id]["end_time"] = datetime.now()
            
        except Exception as e:
            logger.error(f"Basket order execution failed: {e}")
            self.basket_executions[basket_id]["status"] = "FAILED"
            self.basket_executions[basket_id]["error"] = str(e)
            results["error"] = str(e)
        
        return results
    
    async def place_split_order(
        self,
        order: SmartOrder,
        config: SplitOrderConfig
    ) -> Dict[str, Any]:
        """
        Split a large order into smaller chunks
        
        Args:
            order: The original order to split
            config: Configuration for splitting
        
        Returns:
            Dictionary with execution results for all split orders
        """
        total_quantity = order.quantity
        max_per_order = config.max_quantity_per_order
        
        # Calculate number of orders needed
        num_orders = math.ceil(total_quantity / max_per_order)
        
        results = {
            "original_quantity": total_quantity,
            "num_splits": num_orders,
            "orders": [],
            "successful": 0,
            "failed": 0
        }
        
        remaining_quantity = total_quantity
        base_price = order.price or 0
        
        for i in range(num_orders):
            # Calculate quantity for this order
            if config.randomize_quantity and i < num_orders - 1:
                # Random quantity between 50% and 100% of max
                current_quantity = min(
                    remaining_quantity,
                    int(max_per_order * (0.5 + 0.5 * asyncio.get_event_loop().time() % 1))
                )
            else:
                current_quantity = min(remaining_quantity, max_per_order)
            
            # Create split order
            split_order = SmartOrder(
                symbol=order.symbol,
                quantity=current_quantity,
                side=order.side,
                order_type=order.order_type,
                product_type=order.product_type,
                price=self._calculate_split_price(base_price, i, config),
                trigger_price=order.trigger_price,
                disclosed_quantity=order.disclosed_quantity,
                validity=order.validity,
                tag=f"{order.tag or 'SPLIT'}_{i+1}_{num_orders}"
            )
            
            # Place the order
            try:
                result = await self._place_single_order(split_order, f"SPLIT_{i}")
                
                if result.get("status") == "success":
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    
                results["orders"].append(result)
                
            except Exception as e:
                logger.error(f"Split order {i+1} failed: {e}")
                results["failed"] += 1
                results["orders"].append({
                    "index": i,
                    "status": "FAILED",
                    "error": str(e)
                })
            
            remaining_quantity -= current_quantity
            
            # Wait between orders if configured
            if config.time_interval_seconds > 0 and i < num_orders - 1:
                await asyncio.sleep(config.time_interval_seconds)
        
        return results
    
    async def place_iceberg_order(
        self,
        order: SmartOrder,
        config: IcebergOrderConfig
    ) -> Dict[str, Any]:
        """
        Place an iceberg order that shows only a portion of the total quantity
        
        Args:
            order: The original order
            config: Iceberg configuration
        
        Returns:
            Dictionary with iceberg order management details
        """
        iceberg_id = f"ICEBERG_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        self.active_orders[iceberg_id] = {
            "type": "ICEBERG",
            "total_quantity": config.total_quantity,
            "visible_quantity": config.visible_quantity,
            "filled_quantity": 0,
            "active": True,
            "orders": []
        }
        
        results = {
            "iceberg_id": iceberg_id,
            "total_quantity": config.total_quantity,
            "visible_quantity": config.visible_quantity,
            "status": "ACTIVE",
            "orders_placed": 0
        }
        
        remaining_quantity = config.total_quantity
        
        while remaining_quantity > 0 and self.active_orders[iceberg_id]["active"]:
            # Calculate current slice quantity
            current_quantity = min(remaining_quantity, config.visible_quantity)
            
            # Create visible order
            visible_order = SmartOrder(
                symbol=order.symbol,
                quantity=current_quantity,
                side=order.side,
                order_type=order.order_type,
                product_type=order.product_type,
                price=order.price,
                trigger_price=order.trigger_price,
                disclosed_quantity=current_quantity,  # Show full quantity of this slice
                validity=order.validity,
                tag=f"ICEBERG_{iceberg_id}"
            )
            
            try:
                # Place the visible order
                result = await self._place_single_order(visible_order, iceberg_id)
                
                if result.get("status") == "success":
                    results["orders_placed"] += 1
                    self.active_orders[iceberg_id]["orders"].append(result.get("order_id"))
                    
                    # Monitor this order for completion
                    await self._monitor_iceberg_slice(
                        result.get("order_id"),
                        iceberg_id,
                        config.refresh_interval_seconds
                    )
                    
                    remaining_quantity -= current_quantity
                    self.active_orders[iceberg_id]["filled_quantity"] += current_quantity
                else:
                    logger.error(f"Iceberg slice failed: {result}")
                    break
                    
            except Exception as e:
                logger.error(f"Iceberg order failed: {e}")
                results["status"] = "FAILED"
                results["error"] = str(e)
                break
        
        if remaining_quantity == 0:
            results["status"] = "COMPLETED"
        
        return results
    
    async def place_bracket_order(
        self,
        entry_order: SmartOrder,
        stop_loss_points: float,
        target_points: float,
        trailing_stop_loss: bool = False
    ) -> Dict[str, Any]:
        """
        Place a bracket order with automatic stop loss and target
        
        Args:
            entry_order: The main entry order
            stop_loss_points: Points for stop loss from entry
            target_points: Points for target from entry
            trailing_stop_loss: Enable trailing stop loss
        
        Returns:
            Dictionary with bracket order details
        """
        results = {
            "bracket_id": f"BRACKET_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "entry_order": None,
            "stop_loss_order": None,
            "target_order": None,
            "status": "PENDING"
        }
        
        try:
            # Place entry order first
            entry_result = await self._place_single_order(entry_order, results["bracket_id"])
            
            if entry_result.get("status") != "success":
                results["status"] = "FAILED"
                results["error"] = "Entry order failed"
                return results
            
            results["entry_order"] = entry_result
            entry_price = entry_result.get("price", entry_order.price)
            
            # Calculate stop loss and target prices
            if entry_order.side == "BUY":
                sl_price = entry_price - stop_loss_points
                target_price = entry_price + target_points
            else:
                sl_price = entry_price + stop_loss_points
                target_price = entry_price - target_points
            
            # Create stop loss order
            sl_order = SmartOrder(
                symbol=entry_order.symbol,
                quantity=entry_order.quantity,
                side="SELL" if entry_order.side == "BUY" else "BUY",
                order_type="SL",
                product_type=entry_order.product_type,
                trigger_price=sl_price,
                price=sl_price - 0.5 if entry_order.side == "BUY" else sl_price + 0.5,
                validity=entry_order.validity,
                tag=f"SL_{results['bracket_id']}"
            )
            
            # Create target order
            target_order = SmartOrder(
                symbol=entry_order.symbol,
                quantity=entry_order.quantity,
                side="SELL" if entry_order.side == "BUY" else "BUY",
                order_type="LIMIT",
                product_type=entry_order.product_type,
                price=target_price,
                validity=entry_order.validity,
                tag=f"TARGET_{results['bracket_id']}"
            )
            
            # Place both orders
            sl_result = await self._place_single_order(sl_order, results["bracket_id"])
            target_result = await self._place_single_order(target_order, results["bracket_id"])
            
            results["stop_loss_order"] = sl_result
            results["target_order"] = target_result
            
            if trailing_stop_loss:
                # Start monitoring for trailing stop loss
                asyncio.create_task(
                    self._manage_trailing_stop_loss(
                        results["bracket_id"],
                        entry_order.symbol,
                        entry_price,
                        stop_loss_points,
                        entry_order.side
                    )
                )
            
            results["status"] = "ACTIVE"
            
        except Exception as e:
            logger.error(f"Bracket order failed: {e}")
            results["status"] = "FAILED"
            results["error"] = str(e)
        
        return results
    
    async def _place_single_order(
        self,
        order: SmartOrder,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Place a single order through the broker"""
        try:
            # Convert SmartOrder to broker format
            broker_order = {
                "symbol": order.symbol,
                "quantity": order.quantity,
                "side": order.side,
                "order_type": order.order_type,
                "product_type": order.product_type,
                "price": order.price,
                "trigger_price": order.trigger_price,
                "disclosed_quantity": order.disclosed_quantity,
                "validity": order.validity,
                "tag": order.tag
            }
            
            # Remove None values
            broker_order = {k: v for k, v in broker_order.items() if v is not None}
            
            # Place order through broker
            result = await self.broker.place_order(**broker_order)
            
            # Add parent reference if applicable
            if parent_id:
                result["parent_id"] = parent_id
            
            return result
            
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "symbol": order.symbol,
                "quantity": order.quantity
            }
    
    def _calculate_split_price(
        self,
        base_price: float,
        index: int,
        config: SplitOrderConfig
    ) -> Optional[float]:
        """Calculate price for split order based on configuration"""
        if not base_price or config.price_range_percent == 0:
            return base_price
        
        # Add small price variation to avoid detection
        variation = (config.price_range_percent / 100) * base_price
        offset = (index % 3 - 1) * variation / 3  # -1/3, 0, +1/3 of variation
        
        return round(base_price + offset, 2)
    
    async def _monitor_iceberg_slice(
        self,
        order_id: str,
        iceberg_id: str,
        refresh_interval: int
    ):
        """Monitor an iceberg order slice for completion"""
        await asyncio.sleep(refresh_interval)
        # This would check order status and place next slice if filled
        # Implementation depends on broker API capabilities
    
    async def _manage_trailing_stop_loss(
        self,
        bracket_id: str,
        symbol: str,
        entry_price: float,
        stop_loss_points: float,
        side: str
    ):
        """Manage trailing stop loss for bracket order"""
        # This would monitor price and adjust stop loss
        # Implementation depends on real-time price feed
        pass
    
    def cancel_smart_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an active smart order"""
        if order_id in self.active_orders:
            self.active_orders[order_id]["active"] = False
            return {"status": "success", "message": f"Order {order_id} cancelled"}
        return {"status": "error", "message": "Order not found"}
    
    def get_basket_status(self, basket_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a basket order execution"""
        return self.basket_executions.get(basket_id)