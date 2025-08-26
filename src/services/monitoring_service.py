"""
Real-time Monitoring and Alerting Service
Tracks system health, performance metrics, and sends alerts
"""

import logging
import asyncio
import smtplib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict
import psutil
from collections import deque
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    SYSTEM = "system"
    TRADING = "trading"
    API = "api"
    DATABASE = "database"
    PERFORMANCE = "performance"

@dataclass
class Alert:
    level: AlertLevel
    metric_type: MetricType
    title: str
    message: str
    timestamp: datetime
    data: Optional[Dict] = None
    resolved: bool = False
    alert_id: Optional[str] = None

@dataclass
class MetricThreshold:
    name: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    alert_level: AlertLevel = AlertLevel.WARNING
    cooldown_minutes: int = 5

@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, float]
    process_count: int
    timestamp: datetime

class MonitoringService:
    """Service for monitoring system health and sending alerts"""
    
    def __init__(self):
        self.is_running = False
        self.monitoring_thread = None
        self.alerts_queue = deque(maxlen=1000)
        self.metrics_history = deque(maxlen=1000)
        self.last_alert_times = {}
        
        # Alert configurations
        self.email_config = self._load_email_config()
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        self.sms_config = self._load_sms_config()
        
        # Metric thresholds
        self.thresholds = self._initialize_thresholds()
        
        # Performance metrics
        self.api_metrics = {
            "total_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0,
            "active_connections": 0
        }
        
        self.trading_metrics = {
            "active_positions": 0,
            "total_pnl": 0,
            "risk_level": "low",
            "signals_processed": 0,
            "trades_executed": 0,
            "errors_count": 0
        }
        
        # Alert channels
        self.alert_channels = {
            "email": self.email_config.get("enabled", False),
            "webhook": bool(self.webhook_url),
            "sms": self.sms_config.get("enabled", False),
            "dashboard": True
        }
        
    def _load_email_config(self) -> Dict:
        """Load email configuration from environment"""
        return {
            "enabled": os.getenv("EMAIL_ALERTS_ENABLED", "false").lower() == "true",
            "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "smtp_username": os.getenv("SMTP_USERNAME"),
            "smtp_password": os.getenv("SMTP_PASSWORD"),
            "from_email": os.getenv("ALERT_FROM_EMAIL"),
            "to_emails": os.getenv("ALERT_TO_EMAILS", "").split(",")
        }
        
    def _load_sms_config(self) -> Dict:
        """Load SMS configuration from environment"""
        return {
            "enabled": os.getenv("SMS_ALERTS_ENABLED", "false").lower() == "true",
            "api_key": os.getenv("SMS_API_KEY"),
            "from_number": os.getenv("SMS_FROM_NUMBER"),
            "to_numbers": os.getenv("SMS_TO_NUMBERS", "").split(",")
        }
        
    def _initialize_thresholds(self) -> Dict[str, MetricThreshold]:
        """Initialize metric thresholds for alerts"""
        return {
            "cpu_usage": MetricThreshold(
                name="CPU Usage",
                max_value=80,
                alert_level=AlertLevel.WARNING,
                cooldown_minutes=5
            ),
            "memory_usage": MetricThreshold(
                name="Memory Usage",
                max_value=85,
                alert_level=AlertLevel.WARNING,
                cooldown_minutes=5
            ),
            "disk_usage": MetricThreshold(
                name="Disk Usage",
                max_value=90,
                alert_level=AlertLevel.ERROR,
                cooldown_minutes=30
            ),
            "api_error_rate": MetricThreshold(
                name="API Error Rate",
                max_value=10,  # percentage
                alert_level=AlertLevel.WARNING,
                cooldown_minutes=10
            ),
            "response_time": MetricThreshold(
                name="API Response Time",
                max_value=2000,  # milliseconds
                alert_level=AlertLevel.WARNING,
                cooldown_minutes=5
            ),
            "trade_loss": MetricThreshold(
                name="Trading Loss",
                min_value=-50000,  # Max loss in rupees
                alert_level=AlertLevel.ERROR,
                cooldown_minutes=15
            ),
            "position_risk": MetricThreshold(
                name="Position Risk",
                max_value=5,  # Max positions
                alert_level=AlertLevel.WARNING,
                cooldown_minutes=10
            )
        }
        
    def start(self):
        """Start monitoring service"""
        if self.is_running:
            return
            
        self.is_running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        logger.info("Monitoring service started")
        
    def stop(self):
        """Stop monitoring service"""
        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Monitoring service stopped")
        
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                # Collect system metrics
                system_metrics = self._collect_system_metrics()
                self.metrics_history.append(system_metrics)
                
                # Check thresholds
                self._check_system_thresholds(system_metrics)
                self._check_api_thresholds()
                self._check_trading_thresholds()
                
                # Sleep for monitoring interval
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
                
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Network I/O
            net_io = psutil.net_io_counters()
            network_io = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            }
            
            # Process count
            process_count = len(psutil.pids())
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                network_io=network_io,
                process_count=process_count,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(0, 0, 0, {}, 0, datetime.now())
            
    def _check_system_thresholds(self, metrics: SystemMetrics):
        """Check system metrics against thresholds"""
        # Check CPU usage
        if metrics.cpu_percent > self.thresholds["cpu_usage"].max_value:
            self._create_alert(
                level=self.thresholds["cpu_usage"].alert_level,
                metric_type=MetricType.SYSTEM,
                title="High CPU Usage",
                message=f"CPU usage is at {metrics.cpu_percent:.1f}%",
                data={"cpu_percent": metrics.cpu_percent}
            )
            
        # Check memory usage
        if metrics.memory_percent > self.thresholds["memory_usage"].max_value:
            self._create_alert(
                level=self.thresholds["memory_usage"].alert_level,
                metric_type=MetricType.SYSTEM,
                title="High Memory Usage",
                message=f"Memory usage is at {metrics.memory_percent:.1f}%",
                data={"memory_percent": metrics.memory_percent}
            )
            
        # Check disk usage
        if metrics.disk_percent > self.thresholds["disk_usage"].max_value:
            self._create_alert(
                level=self.thresholds["disk_usage"].alert_level,
                metric_type=MetricType.SYSTEM,
                title="High Disk Usage",
                message=f"Disk usage is at {metrics.disk_percent:.1f}%",
                data={"disk_percent": metrics.disk_percent}
            )
            
    def _check_api_thresholds(self):
        """Check API metrics against thresholds"""
        if self.api_metrics["total_requests"] > 0:
            error_rate = (self.api_metrics["failed_requests"] / 
                         self.api_metrics["total_requests"]) * 100
                         
            if error_rate > self.thresholds["api_error_rate"].max_value:
                self._create_alert(
                    level=self.thresholds["api_error_rate"].alert_level,
                    metric_type=MetricType.API,
                    title="High API Error Rate",
                    message=f"API error rate is {error_rate:.1f}%",
                    data={"error_rate": error_rate}
                )
                
        if self.api_metrics["average_response_time"] > self.thresholds["response_time"].max_value:
            self._create_alert(
                level=self.thresholds["response_time"].alert_level,
                metric_type=MetricType.API,
                title="Slow API Response",
                message=f"Average response time is {self.api_metrics['average_response_time']:.0f}ms",
                data={"response_time": self.api_metrics["average_response_time"]}
            )
            
    def _check_trading_thresholds(self):
        """Check trading metrics against thresholds"""
        # Check trading loss
        if self.trading_metrics["total_pnl"] < self.thresholds["trade_loss"].min_value:
            self._create_alert(
                level=self.thresholds["trade_loss"].alert_level,
                metric_type=MetricType.TRADING,
                title="Significant Trading Loss",
                message=f"Total P&L is ₹{self.trading_metrics['total_pnl']:,.2f}",
                data={"total_pnl": self.trading_metrics["total_pnl"]}
            )
            
        # Check position risk
        if self.trading_metrics["active_positions"] > self.thresholds["position_risk"].max_value:
            self._create_alert(
                level=self.thresholds["position_risk"].alert_level,
                metric_type=MetricType.TRADING,
                title="High Position Risk",
                message=f"Active positions: {self.trading_metrics['active_positions']}",
                data={"active_positions": self.trading_metrics["active_positions"]}
            )
            
    def _create_alert(self, level: AlertLevel, metric_type: MetricType,
                     title: str, message: str, data: Optional[Dict] = None):
        """Create and send alert"""
        # Check cooldown
        alert_key = f"{metric_type.value}:{title}"
        if alert_key in self.last_alert_times:
            last_alert = self.last_alert_times[alert_key]
            cooldown_minutes = 5  # Default cooldown
            
            # Get specific cooldown if available
            for threshold in self.thresholds.values():
                if threshold.name in title:
                    cooldown_minutes = threshold.cooldown_minutes
                    break
                    
            if (datetime.now() - last_alert).total_seconds() < cooldown_minutes * 60:
                return  # Skip alert due to cooldown
                
        # Create alert
        alert = Alert(
            level=level,
            metric_type=metric_type,
            title=title,
            message=message,
            timestamp=datetime.now(),
            data=data,
            alert_id=f"{alert_key}:{datetime.now().timestamp()}"
        )
        
        # Add to queue
        self.alerts_queue.append(alert)
        
        # Update last alert time
        self.last_alert_times[alert_key] = datetime.now()
        
        # Send alert through channels
        self._send_alert(alert)
        
    def _send_alert(self, alert: Alert):
        """Send alert through configured channels"""
        try:
            # Log alert
            log_message = f"[{alert.level.value.upper()}] {alert.title}: {alert.message}"
            if alert.level == AlertLevel.CRITICAL:
                logger.critical(log_message)
            elif alert.level == AlertLevel.ERROR:
                logger.error(log_message)
            elif alert.level == AlertLevel.WARNING:
                logger.warning(log_message)
            else:
                logger.info(log_message)
                
            # Send email alert
            if self.alert_channels["email"] and alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
                self._send_email_alert(alert)
                
            # Send webhook alert
            if self.alert_channels["webhook"]:
                self._send_webhook_alert(alert)
                
            # Send SMS for critical alerts
            if self.alert_channels["sms"] and alert.level == AlertLevel.CRITICAL:
                self._send_sms_alert(alert)
                
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            
    def _send_email_alert(self, alert: Alert):
        """Send alert via email"""
        try:
            if not self.email_config["smtp_username"] or not self.email_config["smtp_password"]:
                return
                
            msg = MIMEMultipart()
            msg['From'] = self.email_config["from_email"]
            msg['To'] = ", ".join(self.email_config["to_emails"])
            msg['Subject'] = f"[{alert.level.value.upper()}] Trading System Alert: {alert.title}"
            
            body = f"""
Trading System Alert
====================
Level: {alert.level.value.upper()}
Type: {alert.metric_type.value}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{alert.message}

Data: {json.dumps(alert.data, indent=2) if alert.data else 'N/A'}

---
This is an automated alert from your trading system.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.email_config["smtp_server"], self.email_config["smtp_port"]) as server:
                server.starttls()
                server.login(self.email_config["smtp_username"], self.email_config["smtp_password"])
                server.send_message(msg)
                
            logger.info(f"Email alert sent: {alert.title}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            
    def _send_webhook_alert(self, alert: Alert):
        """Send alert via webhook"""
        try:
            import requests
            
            payload = {
                "level": alert.level.value,
                "type": alert.metric_type.value,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "data": alert.data
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            
            logger.info(f"Webhook alert sent: {alert.title}")
            
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            
    def _send_sms_alert(self, alert: Alert):
        """Send alert via SMS"""
        try:
            # This would integrate with an SMS service like Twilio
            # For now, just log the attempt
            logger.info(f"SMS alert would be sent: {alert.title}")
            
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")
            
    def update_api_metrics(self, request_time: float, success: bool):
        """Update API metrics"""
        self.api_metrics["total_requests"] += 1
        if not success:
            self.api_metrics["failed_requests"] += 1
            
        # Update average response time
        if self.api_metrics["average_response_time"] == 0:
            self.api_metrics["average_response_time"] = request_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.api_metrics["average_response_time"] = (
                alpha * request_time + 
                (1 - alpha) * self.api_metrics["average_response_time"]
            )
            
    def update_trading_metrics(self, metrics: Dict[str, Any]):
        """Update trading metrics"""
        self.trading_metrics.update(metrics)
        
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        # Get latest system metrics
        latest_metrics = None
        if self.metrics_history:
            latest_metrics = self.metrics_history[-1]
            
        return {
            "monitoring_active": self.is_running,
            "system_metrics": asdict(latest_metrics) if latest_metrics else None,
            "api_metrics": self.api_metrics,
            "trading_metrics": self.trading_metrics,
            "active_alerts": len([a for a in self.alerts_queue if not a.resolved]),
            "total_alerts": len(self.alerts_queue),
            "alert_channels": self.alert_channels
        }
        
    def get_alerts(self, limit: int = 50, 
                  level: Optional[AlertLevel] = None,
                  metric_type: Optional[MetricType] = None) -> List[Dict]:
        """Get recent alerts"""
        alerts = list(self.alerts_queue)
        
        # Filter by level
        if level:
            alerts = [a for a in alerts if a.level == level]
            
        # Filter by type
        if metric_type:
            alerts = [a for a in alerts if a.metric_type == metric_type]
            
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Limit results
        alerts = alerts[:limit]
        
        return [asdict(a) for a in alerts]
        
    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved"""
        for alert in self.alerts_queue:
            if alert.alert_id == alert_id:
                alert.resolved = True
                return True
        return False
        
    def get_metrics_history(self, minutes: int = 60) -> List[Dict]:
        """Get metrics history for specified time period"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        metrics = [asdict(m) for m in self.metrics_history 
                  if m.timestamp > cutoff_time]
        
        return metrics
        
    def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        checks = {
            "monitoring_service": self.is_running,
            "alerts_queue": len(self.alerts_queue) < 900,  # Not near limit
            "email_configured": bool(self.email_config["smtp_username"]),
            "webhook_configured": bool(self.webhook_url)
        }
        
        health_status = "healthy" if all(checks.values()) else "degraded"
        
        return {
            "status": health_status,
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
_monitoring_service = None

def get_monitoring_service() -> MonitoringService:
    """Get or create monitoring service instance"""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service