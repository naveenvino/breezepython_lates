"""
Order Reconciliation Service
Ensures system state matches broker state and handles order failures
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    PENDING = "pending"
    PLACED = "placed"
    EXECUTED = "executed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed"
    MISMATCH = "mismatch"

class ReconciliationAction(Enum):
    RETRY = "retry"
    CANCEL = "cancel"
    ALERT = "alert"
    SYNC = "sync"
    NONE = "none"

@dataclass
class OrderDiscrepancy:
    order_id: str
    internal_status: OrderStatus
    broker_status: str
    detected_at: datetime
    action_taken: ReconciliationAction
    resolution: Optional[str] = None

class OrderReconciliationService:
    """
    Handles order state reconciliation between internal system and broker
    """
    
    def __init__(self, broker_client, alert_service, db_service):
        self.broker_client = broker_client
        self.alert_service = alert_service
        self.db_service = db_service
        self.pending_orders = {}
        self.failed_orders = {}
        self.discrepancies = []
        self.reconciliation_running = False
        self.max_retry_attempts = 3
        self.reconciliation_interval = 30  # seconds
        
    async def start_reconciliation_loop(self):
        """Start continuous reconciliation loop"""
        self.reconciliation_running = True
        while self.reconciliation_running:
            try:
                await self.reconcile_all_orders()
                await asyncio.sleep(self.reconciliation_interval)
            except Exception as e:
                logger.error(f"Reconciliation loop error: {e}")
                await asyncio.sleep(5)
    
    async def reconcile_all_orders(self) -> Dict[str, Any]:
        """
        Reconcile all active orders with broker state
        
        Returns:
            Reconciliation report
        """
        logger.info("Starting order reconciliation...")
        
        report = {
            "timestamp": datetime.now(),
            "orders_checked": 0,
            "discrepancies_found": 0,
            "auto_fixed": 0,
            "manual_intervention_needed": 0,
            "details": []
        }
        
        try:
            # Get internal active orders
            internal_orders = await self.db_service.get_active_orders()
            report["orders_checked"] = len(internal_orders)
            
            # Get broker orders
            broker_orders = await self.broker_client.get_orders()
            broker_orders_dict = {o["order_id"]: o for o in broker_orders}
            
            # Check each internal order
            for internal_order in internal_orders:
                discrepancy = await self._check_order_discrepancy(
                    internal_order, 
                    broker_orders_dict.get(internal_order["order_id"])
                )
                
                if discrepancy:
                    report["discrepancies_found"] += 1
                    action_result = await self._handle_discrepancy(discrepancy)
                    
                    if action_result["auto_resolved"]:
                        report["auto_fixed"] += 1
                    else:
                        report["manual_intervention_needed"] += 1
                    
                    report["details"].append({
                        "order_id": discrepancy.order_id,
                        "issue": discrepancy.internal_status.value,
                        "action": discrepancy.action_taken.value,
                        "resolution": action_result
                    })
            
            # Check for broker orders not in internal system
            for broker_order_id, broker_order in broker_orders_dict.items():
                if broker_order_id not in [o["order_id"] for o in internal_orders]:
                    # Order exists at broker but not in our system
                    logger.warning(f"Unknown order found at broker: {broker_order_id}")
                    await self._handle_unknown_broker_order(broker_order)
                    report["discrepancies_found"] += 1
            
            # Log summary
            if report["discrepancies_found"] > 0:
                logger.warning(
                    f"Reconciliation found {report['discrepancies_found']} discrepancies, "
                    f"auto-fixed {report['auto_fixed']}, "
                    f"manual needed for {report['manual_intervention_needed']}"
                )
            
            return report
            
        except Exception as e:
            logger.error(f"Error during reconciliation: {e}")
            report["error"] = str(e)
            await self._send_critical_alert(f"Reconciliation failed: {e}")
            return report
    
    async def _check_order_discrepancy(
        self, 
        internal_order: Dict, 
        broker_order: Optional[Dict]
    ) -> Optional[OrderDiscrepancy]:
        """Check for discrepancies between internal and broker order state"""
        
        order_id = internal_order["order_id"]
        internal_status = OrderStatus(internal_order["status"])
        
        # Case 1: Order not found at broker
        if not broker_order:
            if internal_status in [OrderStatus.PLACED, OrderStatus.EXECUTED]:
                return OrderDiscrepancy(
                    order_id=order_id,
                    internal_status=internal_status,
                    broker_status="NOT_FOUND",
                    detected_at=datetime.now(),
                    action_taken=ReconciliationAction.ALERT
                )
            return None
        
        # Case 2: Status mismatch
        broker_status = broker_order["status"].upper()
        
        # Map broker status to internal status
        status_mapping = {
            "COMPLETE": OrderStatus.EXECUTED,
            "OPEN": OrderStatus.PLACED,
            "PENDING": OrderStatus.PENDING,
            "REJECTED": OrderStatus.REJECTED,
            "CANCELLED": OrderStatus.CANCELLED,
            "TRIGGER_PENDING": OrderStatus.PENDING
        }
        
        mapped_broker_status = status_mapping.get(broker_status, OrderStatus.FAILED)
        
        if internal_status != mapped_broker_status:
            # Significant mismatch
            if internal_status == OrderStatus.EXECUTED and mapped_broker_status == OrderStatus.REJECTED:
                # Critical: We think it's executed but broker rejected it
                return OrderDiscrepancy(
                    order_id=order_id,
                    internal_status=internal_status,
                    broker_status=broker_status,
                    detected_at=datetime.now(),
                    action_taken=ReconciliationAction.ALERT
                )
            
            # Update internal state to match broker
            return OrderDiscrepancy(
                order_id=order_id,
                internal_status=internal_status,
                broker_status=broker_status,
                detected_at=datetime.now(),
                action_taken=ReconciliationAction.SYNC
            )
        
        # Case 3: Check execution price mismatch
        if mapped_broker_status == OrderStatus.EXECUTED:
            internal_price = internal_order.get("execution_price", 0)
            broker_price = broker_order.get("average_price", 0)
            
            if abs(internal_price - broker_price) > 0.01:  # Price mismatch
                return OrderDiscrepancy(
                    order_id=order_id,
                    internal_status=internal_status,
                    broker_status=f"PRICE_MISMATCH ({broker_price})",
                    detected_at=datetime.now(),
                    action_taken=ReconciliationAction.SYNC
                )
        
        return None
    
    async def _handle_discrepancy(self, discrepancy: OrderDiscrepancy) -> Dict:
        """Handle detected discrepancy"""
        
        result = {
            "auto_resolved": False,
            "action": discrepancy.action_taken.value,
            "details": ""
        }
        
        try:
            if discrepancy.action_taken == ReconciliationAction.SYNC:
                # Update internal state to match broker
                await self.db_service.update_order_status(
                    discrepancy.order_id,
                    discrepancy.broker_status
                )
                result["auto_resolved"] = True
                result["details"] = f"Synced status to {discrepancy.broker_status}"
                
            elif discrepancy.action_taken == ReconciliationAction.RETRY:
                # Retry order placement
                if discrepancy.order_id not in self.failed_orders:
                    self.failed_orders[discrepancy.order_id] = 0
                
                if self.failed_orders[discrepancy.order_id] < self.max_retry_attempts:
                    await self._retry_order(discrepancy.order_id)
                    self.failed_orders[discrepancy.order_id] += 1
                    result["details"] = f"Retrying order (attempt {self.failed_orders[discrepancy.order_id]})"
                else:
                    await self._send_critical_alert(
                        f"Order {discrepancy.order_id} failed after {self.max_retry_attempts} retries"
                    )
                    result["details"] = "Max retries exceeded, alert sent"
                    
            elif discrepancy.action_taken == ReconciliationAction.ALERT:
                # Send immediate alert
                await self._send_critical_alert(
                    f"Critical discrepancy: Order {discrepancy.order_id} - "
                    f"Internal: {discrepancy.internal_status.value}, "
                    f"Broker: {discrepancy.broker_status}"
                )
                result["details"] = "Critical alert sent"
                
            elif discrepancy.action_taken == ReconciliationAction.CANCEL:
                # Cancel the order
                await self.broker_client.cancel_order(discrepancy.order_id)
                await self.db_service.update_order_status(
                    discrepancy.order_id,
                    OrderStatus.CANCELLED.value
                )
                result["auto_resolved"] = True
                result["details"] = "Order cancelled"
            
            # Store discrepancy for audit
            self.discrepancies.append(discrepancy)
            
        except Exception as e:
            logger.error(f"Error handling discrepancy for {discrepancy.order_id}: {e}")
            result["details"] = f"Error: {str(e)}"
        
        return result
    
    async def _handle_unknown_broker_order(self, broker_order: Dict):
        """Handle orders that exist at broker but not in our system"""
        
        logger.warning(f"Unknown broker order: {broker_order}")
        
        # Import the order into our system
        await self.db_service.import_broker_order({
            "order_id": broker_order["order_id"],
            "symbol": broker_order.get("tradingsymbol"),
            "quantity": broker_order.get("quantity"),
            "price": broker_order.get("average_price", 0),
            "status": broker_order["status"],
            "order_type": broker_order.get("order_type"),
            "imported_at": datetime.now(),
            "source": "reconciliation"
        })
        
        # Alert about the unknown order
        await self.alert_service.send_alert(
            level="warning",
            title="Unknown Order Detected",
            message=f"Order {broker_order['order_id']} found at broker but not in system",
            data=broker_order
        )
    
    async def _retry_order(self, order_id: str):
        """Retry a failed order"""
        
        order = await self.db_service.get_order(order_id)
        if not order:
            logger.error(f"Cannot retry order {order_id}: Not found")
            return
        
        try:
            # Place new order with same parameters
            new_order = await self.broker_client.place_order({
                "symbol": order["symbol"],
                "quantity": order["quantity"],
                "order_type": order["order_type"],
                "price": order.get("limit_price"),
                "trigger_price": order.get("trigger_price"),
                "tag": f"RETRY_{order_id}"
            })
            
            # Update order mapping
            await self.db_service.link_retry_order(order_id, new_order["order_id"])
            
            logger.info(f"Successfully retried order {order_id} as {new_order['order_id']}")
            
        except Exception as e:
            logger.error(f"Failed to retry order {order_id}: {e}")
    
    async def _send_critical_alert(self, message: str):
        """Send critical alert through all channels"""
        
        await self.alert_service.send_alert(
            level="critical",
            title="Order Reconciliation Alert",
            message=message,
            channels=["telegram", "email", "sms"]
        )
    
    async def handle_order_rejection(self, order: Dict, rejection_reason: str):
        """
        Handle order rejection from broker
        
        Args:
            order: Order details
            rejection_reason: Reason for rejection from broker
        """
        
        logger.error(f"Order rejected: {order['order_id']} - {rejection_reason}")
        
        # Parse rejection reason
        reason_lower = rejection_reason.lower()
        
        if "margin" in reason_lower or "insufficient" in reason_lower:
            # Margin issue - don't retry
            await self.alert_service.send_alert(
                level="critical",
                title="Order Rejected - Insufficient Margin",
                message=f"Order {order['order_id']} rejected due to insufficient margin",
                data={"order": order, "reason": rejection_reason}
            )
            await self.db_service.update_order_status(
                order["order_id"],
                OrderStatus.REJECTED.value,
                {"rejection_reason": rejection_reason}
            )
            
        elif "price" in reason_lower or "circuit" in reason_lower:
            # Price issue - may retry with updated price
            if order.get("retry_count", 0) < 2:
                # Get fresh price and retry
                await self._retry_with_fresh_price(order)
            else:
                await self.alert_service.send_alert(
                    level="critical",
                    title="Order Rejected - Price Issue",
                    message=f"Order {order['order_id']} rejected due to price issue",
                    data={"order": order, "reason": rejection_reason}
                )
                
        elif "market closed" in reason_lower or "after market" in reason_lower:
            # Market timing issue
            await self.db_service.queue_order_for_next_session(order)
            await self.alert_service.send_alert(
                level="warning",
                title="Order Queued",
                message=f"Order {order['order_id']} queued for next market session",
                data=order
            )
            
        else:
            # Unknown rejection - alert and mark failed
            await self.alert_service.send_alert(
                level="critical",
                title="Order Rejected - Unknown Reason",
                message=f"Order {order['order_id']} rejected: {rejection_reason}",
                data={"order": order, "reason": rejection_reason}
            )
            await self.db_service.update_order_status(
                order["order_id"],
                OrderStatus.FAILED.value,
                {"rejection_reason": rejection_reason}
            )
    
    async def _retry_with_fresh_price(self, order: Dict):
        """Retry order with fresh market price"""
        
        try:
            # Get fresh price
            fresh_price = await self.broker_client.get_ltp(order["symbol"])
            
            # Apply small buffer for market orders
            if order["order_type"] == "MARKET":
                buffer = fresh_price * 0.001  # 0.1% buffer
                fresh_price = fresh_price + buffer if order["transaction_type"] == "BUY" else fresh_price - buffer
            
            # Update order price
            order["price"] = fresh_price
            order["retry_count"] = order.get("retry_count", 0) + 1
            
            # Retry order
            await self._retry_order(order["order_id"])
            
        except Exception as e:
            logger.error(f"Failed to retry with fresh price: {e}")
    
    def get_reconciliation_stats(self) -> Dict:
        """Get reconciliation statistics"""
        
        recent_discrepancies = [d for d in self.discrepancies 
                               if d.detected_at > datetime.now() - timedelta(hours=24)]
        
        return {
            "total_discrepancies_24h": len(recent_discrepancies),
            "auto_resolved": sum(1 for d in recent_discrepancies 
                               if d.resolution and "auto" in d.resolution.lower()),
            "pending_manual": sum(1 for d in recent_discrepancies 
                                if not d.resolution),
            "failed_orders": len(self.failed_orders),
            "last_reconciliation": max(d.detected_at for d in self.discrepancies) 
                                  if self.discrepancies else None
        }
    
    async def stop(self):
        """Stop reconciliation loop"""
        self.reconciliation_running = False

# Usage
async def setup_reconciliation(broker_client, alert_service, db_service):
    """Setup and start reconciliation service"""
    
    service = OrderReconciliationService(broker_client, alert_service, db_service)
    
    # Start reconciliation loop in background
    asyncio.create_task(service.start_reconciliation_loop())
    
    return service