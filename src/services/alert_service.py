"""
Alert and Notification Service
"""

from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

class AlertType(Enum):
    PRICE = "PRICE"
    SIGNAL = "SIGNAL"
    PNL = "PNL"
    RISK = "RISK"
    POSITION = "POSITION"
    SYSTEM = "SYSTEM"

class AlertPriority(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class Alert:
    alert_id: str
    alert_type: AlertType
    priority: AlertPriority
    title: str
    message: str
    condition: Dict
    created_at: datetime
    triggered_at: Optional[datetime] = None
    triggered: bool = False
    active: bool = True
    data: Optional[Dict] = None

class AlertService:
    def __init__(self):
        self.alerts = {}
        self.alert_history = []
        self.alert_callbacks = []
        self.monitoring_task = None
        self.is_monitoring = False
        
    async def create_alert(self, 
                          alert_type: AlertType,
                          title: str,
                          message: str,
                          condition: Dict,
                          priority: AlertPriority = AlertPriority.MEDIUM) -> str:
        """Create a new alert"""
        alert_id = f"ALERT_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            priority=priority,
            title=title,
            message=message,
            condition=condition,
            created_at=datetime.now()
        )
        
        self.alerts[alert_id] = alert
        logger.info(f"Alert created: {alert_id} - {title}")
        
        return alert_id
    
    async def create_price_alert(self, symbol: str, price: float, condition: str = "above") -> str:
        """Create a price alert"""
        return await self.create_alert(
            alert_type=AlertType.PRICE,
            title=f"{symbol} Price Alert",
            message=f"{symbol} price {condition} {price}",
            condition={
                "symbol": symbol,
                "price": price,
                "condition": condition
            }
        )
    
    async def create_signal_alert(self, signal_type: str) -> str:
        """Create a signal alert"""
        return await self.create_alert(
            alert_type=AlertType.SIGNAL,
            title=f"Signal Alert: {signal_type}",
            message=f"Signal {signal_type} has been triggered",
            condition={
                "signal_type": signal_type
            },
            priority=AlertPriority.HIGH
        )
    
    async def create_pnl_alert(self, threshold: float, alert_type: str = "profit") -> str:
        """Create P&L alert"""
        return await self.create_alert(
            alert_type=AlertType.PNL,
            title=f"P&L Alert",
            message=f"P&L {alert_type} threshold reached: ₹{threshold}",
            condition={
                "threshold": threshold,
                "type": alert_type
            }
        )
    
    async def create_risk_alert(self, metric: str, threshold: float) -> str:
        """Create risk management alert"""
        return await self.create_alert(
            alert_type=AlertType.RISK,
            title=f"Risk Alert: {metric}",
            message=f"Risk metric {metric} exceeded threshold: {threshold}",
            condition={
                "metric": metric,
                "threshold": threshold
            },
            priority=AlertPriority.CRITICAL
        )
    
    async def start_monitoring(self):
        """Start alert monitoring"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitor_alerts())
        logger.info("Alert monitoring started")
    
    async def stop_monitoring(self):
        """Stop alert monitoring"""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Alert monitoring stopped")
    
    async def _monitor_alerts(self):
        """Monitor and trigger alerts"""
        while self.is_monitoring:
            try:
                for alert_id, alert in list(self.alerts.items()):
                    if not alert.active or alert.triggered:
                        continue
                    
                    if await self._check_alert_condition(alert):
                        await self._trigger_alert(alert)
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Error monitoring alerts: {e}")
                await asyncio.sleep(1)
    
    async def _check_alert_condition(self, alert: Alert) -> bool:
        """Check if alert condition is met"""
        try:
            if alert.alert_type == AlertType.PRICE:
                return await self._check_price_condition(alert.condition)
            elif alert.alert_type == AlertType.SIGNAL:
                return await self._check_signal_condition(alert.condition)
            elif alert.alert_type == AlertType.PNL:
                return await self._check_pnl_condition(alert.condition)
            elif alert.alert_type == AlertType.RISK:
                return await self._check_risk_condition(alert.condition)
            
        except Exception as e:
            logger.error(f"Error checking alert condition: {e}")
        
        return False
    
    async def _check_price_condition(self, condition: Dict) -> bool:
        """Check price alert condition"""
        # Get current price from market service
        # For now, return False
        return False
    
    async def _check_signal_condition(self, condition: Dict) -> bool:
        """Check signal alert condition"""
        # Check if signal has been triggered
        return False
    
    async def _check_pnl_condition(self, condition: Dict) -> bool:
        """Check P&L alert condition"""
        # Get current P&L from trading service
        return False
    
    async def _check_risk_condition(self, condition: Dict) -> bool:
        """Check risk alert condition"""
        # Get risk metrics
        return False
    
    async def _trigger_alert(self, alert: Alert):
        """Trigger an alert"""
        alert.triggered = True
        alert.triggered_at = datetime.now()
        
        # Add to history
        self.alert_history.append({
            'alert': alert,
            'triggered_at': alert.triggered_at
        })
        
        # Call registered callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
        
        # Log alert
        self._log_alert(alert)
        
        # Send notifications
        await self._send_notifications(alert)
    
    def _log_alert(self, alert: Alert):
        """Log alert to file"""
        log_entry = {
            'alert_id': alert.alert_id,
            'type': alert.alert_type.value,
            'priority': alert.priority.value,
            'title': alert.title,
            'message': alert.message,
            'triggered_at': alert.triggered_at.isoformat() if alert.triggered_at else None
        }
        
        logger.warning(f"ALERT TRIGGERED: {alert.title} - {alert.message}")
        
        # Save to file
        try:
            with open('alerts.log', 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Error logging alert: {e}")
    
    async def _send_notifications(self, alert: Alert):
        """Send alert notifications"""
        # Implement email, SMS, push notifications
        # For now, just log
        if alert.priority in [AlertPriority.HIGH, AlertPriority.CRITICAL]:
            logger.critical(f"HIGH PRIORITY ALERT: {alert.title}")
    
    def register_callback(self, callback: Callable):
        """Register a callback for alert triggers"""
        self.alert_callbacks.append(callback)
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return [alert for alert in self.alerts.values() if alert.active and not alert.triggered]
    
    def get_triggered_alerts(self) -> List[Alert]:
        """Get all triggered alerts"""
        return [alert for alert in self.alerts.values() if alert.triggered]
    
    def delete_alert(self, alert_id: str):
        """Delete an alert"""
        if alert_id in self.alerts:
            self.alerts[alert_id].active = False
            logger.info(f"Alert deleted: {alert_id}")
    
    def clear_triggered_alerts(self):
        """Clear all triggered alerts"""
        for alert_id in list(self.alerts.keys()):
            if self.alerts[alert_id].triggered:
                del self.alerts[alert_id]
    
    def get_alert_stats(self) -> Dict:
        """Get alert statistics"""
        active = len(self.get_active_alerts())
        triggered = len(self.get_triggered_alerts())
        total = len(self.alerts)
        
        by_type = {}
        by_priority = {}
        
        for alert in self.alerts.values():
            # By type
            alert_type = alert.alert_type.value
            by_type[alert_type] = by_type.get(alert_type, 0) + 1
            
            # By priority
            priority = alert.priority.value
            by_priority[priority] = by_priority.get(priority, 0) + 1
        
        return {
            'total': total,
            'active': active,
            'triggered': triggered,
            'by_type': by_type,
            'by_priority': by_priority
        }

# Singleton instance
_alert_service = None

def get_alert_service():
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service