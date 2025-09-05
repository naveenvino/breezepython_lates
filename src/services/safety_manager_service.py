"""
Safety Manager Service - Critical safety features for trading system
"""

import logging
import asyncio
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import pyodbc
import hashlib

logger = logging.getLogger(__name__)

class SafetyStatus(Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"
    HALTED = "HALTED"

@dataclass
class SafetyConfig:
    """Safety configuration parameters"""
    # Kill switch
    enable_kill_switch: bool = True
    kill_switch_active: bool = False
    
    # Circuit breakers
    max_daily_loss: float = 50000
    max_position_loss: float = 15000
    max_consecutive_losses: int = 3
    circuit_breaker_cooldown: int = 300  # seconds
    
    # Order validation
    max_order_value: float = 500000
    max_position_size: int = 20  # lots
    min_order_interval: int = 2  # seconds between orders
    
    # Duplicate prevention
    duplicate_check_window: int = 10  # seconds
    
    # Network monitoring
    max_network_retries: int = 3
    network_timeout: int = 30  # seconds
    heartbeat_interval: int = 60  # seconds
    
    # System limits
    max_orders_per_minute: int = 10
    max_api_calls_per_second: int = 5
    emergency_contact: str = ""  # Phone/Email for alerts

class SafetyManagerService:
    """Comprehensive safety management for trading system"""
    
    def __init__(self, trading_service=None, risk_service=None):
        self.trading_service = trading_service
        self.risk_service = risk_service
        self.config = SafetyConfig()
        self.status = SafetyStatus.NORMAL
        
        # Tracking
        self.last_order_time = None
        self.recent_orders = []
        self.consecutive_losses = 0
        self.circuit_breaker_triggered = False
        self.circuit_breaker_time = None
        self.emergency_stop_active = False
        
        # Order tracking for duplicate prevention
        self.order_hashes = {}
        
        # Network monitoring
        self.last_heartbeat = datetime.now()
        self.network_failures = 0
        
        # Statistics
        self.orders_this_minute = 0
        self.api_calls_this_second = 0
        self.daily_loss = 0
        
        # Database connection
        self.conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=(localdb)\\mssqllocaldb;"
            "DATABASE=KiteConnectApi;"
            "Trusted_Connection=yes;"
        )
        
        # Start monitoring
        self.monitoring_task = None
    
    async def start_monitoring(self):
        """Start safety monitoring"""
        if self.monitoring_task:
            return
        
        self.monitoring_task = asyncio.create_task(self._safety_monitor())
        logger.info("Safety monitoring started")
    
    async def stop_monitoring(self):
        """Stop safety monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Safety monitoring stopped")
    
    async def _safety_monitor(self):
        """Main safety monitoring loop"""
        while True:
            try:
                # Check kill switch
                if self.config.kill_switch_active:
                    await self.trigger_emergency_stop("Kill switch activated")
                
                # Check circuit breaker cooldown
                if self.circuit_breaker_triggered:
                    if datetime.now() - self.circuit_breaker_time > timedelta(seconds=self.config.circuit_breaker_cooldown):
                        self.circuit_breaker_triggered = False
                        self.status = SafetyStatus.NORMAL
                        logger.info("Circuit breaker reset")
                
                # Check heartbeat
                if datetime.now() - self.last_heartbeat > timedelta(seconds=self.config.heartbeat_interval * 2):
                    await self.handle_network_failure("Heartbeat timeout")
                
                # Reset per-minute counters
                if datetime.now().second == 0:
                    self.orders_this_minute = 0
                
                # Clean old order hashes (older than duplicate window)
                cutoff_time = datetime.now() - timedelta(seconds=self.config.duplicate_check_window)
                self.order_hashes = {
                    k: v for k, v in self.order_hashes.items()
                    if v > cutoff_time
                }
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Safety monitor error: {e}")
                await asyncio.sleep(5)
    
    async def validate_order(self, order_data: Dict) -> tuple[bool, str]:
        """
        Validate order before execution
        Returns: (is_valid, message)
        """
        try:
            # Check emergency stop
            if self.emergency_stop_active:
                return False, "Emergency stop is active"
            
            # Check kill switch
            if self.config.kill_switch_active:
                return False, "Kill switch is active"
            
            # Check circuit breaker
            if self.circuit_breaker_triggered:
                return False, "Circuit breaker is active"
            
            # Check order frequency
            if self.last_order_time:
                time_since_last = (datetime.now() - self.last_order_time).total_seconds()
                if time_since_last < self.config.min_order_interval:
                    return False, f"Order too frequent (min interval: {self.config.min_order_interval}s)"
            
            # Check duplicate order
            order_hash = self._generate_order_hash(order_data)
            if order_hash in self.order_hashes:
                return False, "Duplicate order detected"
            
            # Check order value
            quantity = order_data.get('quantity', 0)
            price = order_data.get('price', 100)
            order_value = quantity * price
            
            if order_value > self.config.max_order_value:
                return False, f"Order value exceeds limit: {order_value} > {self.config.max_order_value}"
            
            # Check position size
            lots = quantity / 75  # Convert to lots for NIFTY
            if lots > self.config.max_position_size:
                return False, f"Position size exceeds limit: {lots} > {self.config.max_position_size}"
            
            # Check orders per minute
            if self.orders_this_minute >= self.config.max_orders_per_minute:
                return False, "Max orders per minute exceeded"
            
            # Check daily loss limit
            if self.daily_loss >= self.config.max_daily_loss:
                await self.trigger_circuit_breaker("Daily loss limit exceeded")
                return False, "Daily loss limit exceeded"
            
            # All checks passed
            self._record_order(order_hash)
            return True, "Order validated"
            
        except Exception as e:
            logger.error(f"Order validation error: {e}")
            return False, f"Validation error: {e}"
    
    def _generate_order_hash(self, order_data: Dict) -> str:
        """Generate unique hash for order to detect duplicates"""
        key_fields = [
            str(order_data.get('symbol', '')),
            str(order_data.get('side', '')),
            str(order_data.get('quantity', '')),
            str(order_data.get('price', '')),
            str(order_data.get('order_type', ''))
        ]
        
        order_string = '|'.join(key_fields)
        return hashlib.md5(order_string.encode()).hexdigest()
    
    def _record_order(self, order_hash: str):
        """Record order for tracking"""
        self.order_hashes[order_hash] = datetime.now()
        self.last_order_time = datetime.now()
        self.orders_this_minute += 1
        
        # Add to recent orders
        self.recent_orders.append(datetime.now())
        # Keep only last 100 orders
        if len(self.recent_orders) > 100:
            self.recent_orders = self.recent_orders[-100:]
    
    async def trigger_kill_switch(self, reason: str = "Manual trigger"):
        """Activate kill switch - stops all trading immediately"""
        logger.critical(f"KILL SWITCH ACTIVATED: {reason}")
        
        self.config.kill_switch_active = True
        self.status = SafetyStatus.HALTED
        
        # Close all positions
        if self.trading_service:
            await self.trading_service.square_off_all()
        
        # Cancel all pending orders
        await self._cancel_all_pending_orders()
        
        # Log to database
        self._log_safety_event("KILL_SWITCH", reason)
        
        # Send emergency notification
        await self._send_emergency_notification(f"Kill switch activated: {reason}")
    
    async def release_kill_switch(self):
        """Release kill switch"""
        self.config.kill_switch_active = False
        self.status = SafetyStatus.NORMAL
        logger.info("Kill switch released")
        self._log_safety_event("KILL_SWITCH_RELEASED", "Manual release")
    
    async def trigger_circuit_breaker(self, reason: str):
        """Trigger circuit breaker - temporary trading halt"""
        logger.warning(f"Circuit breaker triggered: {reason}")
        
        self.circuit_breaker_triggered = True
        self.circuit_breaker_time = datetime.now()
        self.status = SafetyStatus.CRITICAL
        
        # Cancel pending orders
        await self._cancel_all_pending_orders()
        
        # Log event
        self._log_safety_event("CIRCUIT_BREAKER", reason)
        
        # Notification
        await self._send_emergency_notification(f"Circuit breaker: {reason}")
    
    async def trigger_emergency_stop(self, reason: str):
        """Emergency stop - immediate halt of all operations"""
        logger.critical(f"EMERGENCY STOP: {reason}")
        
        self.emergency_stop_active = True
        self.status = SafetyStatus.EMERGENCY
        
        # Square off all positions
        if self.trading_service:
            await self.trading_service.square_off_all()
        
        # Cancel all orders
        await self._cancel_all_pending_orders()
        
        # Log event
        self._log_safety_event("EMERGENCY_STOP", reason)
        
        # Send emergency notification
        await self._send_emergency_notification(f"EMERGENCY STOP: {reason}")
    
    async def handle_network_failure(self, error: str):
        """Handle network failure"""
        self.network_failures += 1
        
        if self.network_failures >= self.config.max_network_retries:
            await self.trigger_circuit_breaker(f"Network failure: {error}")
        else:
            logger.warning(f"Network issue ({self.network_failures}/{self.config.max_network_retries}): {error}")
    
    def record_trade_result(self, pnl: float):
        """Record trade result for monitoring"""
        if pnl < 0:
            self.consecutive_losses += 1
            self.daily_loss += abs(pnl)
            
            # Check consecutive losses
            if self.consecutive_losses >= self.config.max_consecutive_losses:
                asyncio.create_task(
                    self.trigger_circuit_breaker(f"Consecutive losses: {self.consecutive_losses}")
                )
            
            # Check position loss
            if abs(pnl) >= self.config.max_position_loss:
                asyncio.create_task(
                    self.trigger_circuit_breaker(f"Position loss exceeded: {abs(pnl)}")
                )
        else:
            self.consecutive_losses = 0  # Reset on profit
    
    async def _cancel_all_pending_orders(self):
        """Cancel all pending orders"""
        try:
            if self.trading_service:
                orders = await self.trading_service.get_order_list()
                
                for order in orders:
                    if order.get('status') in ['OPEN', 'PENDING']:
                        await self.trading_service.cancel_order(order['order_id'])
                
                logger.info(f"Cancelled {len(orders)} pending orders")
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
    
    def _log_safety_event(self, event_type: str, message: str):
        """Log safety event to database"""
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO TradingLogs (log_type, message, details)
                VALUES (?, ?, ?)
            """, (
                f"SAFETY_{event_type}",
                message,
                json.dumps({
                    'status': self.status.value,
                    'daily_loss': self.daily_loss,
                    'consecutive_losses': self.consecutive_losses,
                    'network_failures': self.network_failures
                })
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging safety event: {e}")
    
    async def _send_emergency_notification(self, message: str):
        """Send emergency notification"""
        # Implement email/SMS notification here
        logger.critical(f"EMERGENCY NOTIFICATION: {message}")
        
        # For now, just log
        if self.config.emergency_contact:
            logger.info(f"Would send to: {self.config.emergency_contact}")
    
    def update_heartbeat(self):
        """Update heartbeat timestamp"""
        self.last_heartbeat = datetime.now()
    
    def get_safety_status(self) -> Dict:
        """Get current safety status"""
        return {
            'status': self.status.value,
            'kill_switch': self.config.kill_switch_active,
            'circuit_breaker': self.circuit_breaker_triggered,
            'emergency_stop': self.emergency_stop_active,
            'daily_loss': self.daily_loss,
            'consecutive_losses': self.consecutive_losses,
            'network_failures': self.network_failures,
            'orders_this_minute': self.orders_this_minute,
            'last_heartbeat': self.last_heartbeat.isoformat()
        }
    
    def reset_daily_counters(self):
        """Reset daily counters (call at start of trading day)"""
        self.daily_loss = 0
        self.consecutive_losses = 0
        logger.info("Daily safety counters reset")
    
    def update_config(self, config_updates: Dict):
        """Update safety configuration"""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        logger.info(f"Safety config updated: {config_updates}")

# Singleton instance
_safety_manager = None

def get_safety_manager(trading_service=None, risk_service=None):
    global _safety_manager
    if _safety_manager is None:
        _safety_manager = SafetyManagerService(trading_service, risk_service)
    return _safety_manager