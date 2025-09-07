"""
Production monitoring and alerting system
"""
import os
import time
import logging
import threading
import smtplib
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from dataclasses import dataclass
from enum import Enum
import psutil
import requests
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """Types of metrics to monitor"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMING = "timing"

@dataclass
class Alert:
    """Alert data structure"""
    name: str
    severity: AlertSeverity
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None

@dataclass
class Metric:
    """Metric data structure"""
    name: str
    value: float
    metric_type: MetricType
    tags: Dict[str, str]
    timestamp: datetime

class MonitoringSystem:
    """Comprehensive monitoring and alerting system"""
    
    def __init__(self):
        self.metrics: Dict[str, List[Metric]] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_handlers: List[Callable[[Alert], None]] = []
        self.thresholds: Dict[str, Dict[str, Any]] = {}
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._lock = threading.Lock()
        
        # Configuration from environment
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_email = os.getenv('ALERT_EMAIL')
        
        # Setup default thresholds
        self._setup_default_thresholds()
        
        # Setup default alert handlers
        self._setup_alert_handlers()
        
        logger.info("Monitoring system initialized")
    
    def _setup_default_thresholds(self):
        """Setup default monitoring thresholds"""
        self.thresholds = {
            'cpu_usage': {
                'warning': 70.0,
                'critical': 90.0
            },
            'memory_usage': {
                'warning': 80.0,
                'critical': 95.0
            },
            'disk_usage': {
                'warning': 85.0,
                'critical': 95.0
            },
            'api_response_time': {
                'warning': 2000.0,  # milliseconds
                'critical': 5000.0
            },
            'database_connections': {
                'warning': 80.0,  # percentage of pool
                'critical': 95.0
            },
            'error_rate': {
                'warning': 5.0,  # percentage
                'critical': 10.0
            },
            'daily_loss': {
                'warning': 0.7,  # 70% of limit
                'critical': 0.9   # 90% of limit
            }
        }
    
    def _setup_alert_handlers(self):
        """Setup default alert handlers"""
        if self.smtp_username and self.alert_email:
            self.alert_handlers.append(self._email_alert_handler)
        
        # Always add console logging
        self.alert_handlers.append(self._console_alert_handler)
        
        # Add file logging
        self.alert_handlers.append(self._file_alert_handler)
    
    def record_metric(self, name: str, value: float, 
                     metric_type: MetricType = MetricType.GAUGE,
                     tags: Dict[str, str] = None):
        """Record a metric value"""
        metric = Metric(
            name=name,
            value=value,
            metric_type=metric_type,
            tags=tags or {},
            timestamp=datetime.utcnow()
        )
        
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = []
            
            self.metrics[name].append(metric)
            
            # Keep only last 1000 points per metric
            if len(self.metrics[name]) > 1000:
                self.metrics[name] = self.metrics[name][-1000:]
        
        # Check thresholds
        self._check_threshold(name, value, tags or {})
    
    def increment_counter(self, name: str, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        current_value = self._get_current_metric_value(name) + 1
        self.record_metric(name, current_value, MetricType.COUNTER, tags)
    
    def record_timing(self, name: str, duration_ms: float, tags: Dict[str, str] = None):
        """Record a timing metric"""
        self.record_metric(name, duration_ms, MetricType.TIMING, tags)
    
    def _get_current_metric_value(self, name: str) -> float:
        """Get current value of a metric"""
        with self._lock:
            if name not in self.metrics or not self.metrics[name]:
                return 0.0
            return self.metrics[name][-1].value
    
    def _check_threshold(self, metric_name: str, value: float, tags: Dict[str, str]):
        """Check if metric value crosses threshold"""
        if metric_name not in self.thresholds:
            return
        
        thresholds = self.thresholds[metric_name]
        alert_key = f"{metric_name}_{hash(frozenset(tags.items()))}"
        
        # Check critical threshold
        if 'critical' in thresholds and value >= thresholds['critical']:
            if alert_key not in self.active_alerts:
                alert = Alert(
                    name=f"{metric_name}_critical",
                    severity=AlertSeverity.CRITICAL,
                    message=f"{metric_name} reached critical level: {value}",
                    details={
                        'metric': metric_name,
                        'value': value,
                        'threshold': thresholds['critical'],
                        'tags': tags
                    },
                    timestamp=datetime.utcnow()
                )
                self._trigger_alert(alert_key, alert)
        
        # Check warning threshold
        elif 'warning' in thresholds and value >= thresholds['warning']:
            warning_key = f"{alert_key}_warning"
            if warning_key not in self.active_alerts:
                alert = Alert(
                    name=f"{metric_name}_warning",
                    severity=AlertSeverity.WARNING,
                    message=f"{metric_name} reached warning level: {value}",
                    details={
                        'metric': metric_name,
                        'value': value,
                        'threshold': thresholds['warning'],
                        'tags': tags
                    },
                    timestamp=datetime.utcnow()
                )
                self._trigger_alert(warning_key, alert)
        
        # Check if alert should be resolved
        else:
            self._resolve_alert(alert_key)
            self._resolve_alert(f"{alert_key}_warning")
    
    def _trigger_alert(self, alert_key: str, alert: Alert):
        """Trigger an alert"""
        with self._lock:
            self.active_alerts[alert_key] = alert
        
        logger.error(f"ALERT TRIGGERED: {alert.name} - {alert.message}")
        
        # Send to all alert handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    def _resolve_alert(self, alert_key: str):
        """Resolve an active alert"""
        with self._lock:
            if alert_key in self.active_alerts:
                alert = self.active_alerts[alert_key]
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                
                logger.info(f"ALERT RESOLVED: {alert.name}")
                
                # Remove from active alerts
                del self.active_alerts[alert_key]
    
    def _console_alert_handler(self, alert: Alert):
        """Console alert handler"""
        severity_colors = {
            AlertSeverity.INFO: '\033[94m',      # Blue
            AlertSeverity.WARNING: '\033[93m',   # Yellow
            AlertSeverity.ERROR: '\033[91m',     # Red
            AlertSeverity.CRITICAL: '\033[95m'   # Magenta
        }
        color = severity_colors.get(alert.severity, '')
        reset = '\033[0m'
        
        print(f"{color}[{alert.severity.value.upper()}] {alert.message}{reset}")
    
    def _file_alert_handler(self, alert: Alert):
        """File alert handler"""
        try:
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            
            alert_file = logs_dir / "alerts.log"
            
            with open(alert_file, 'a') as f:
                f.write(f"{alert.timestamp.isoformat()} [{alert.severity.value.upper()}] "
                       f"{alert.name}: {alert.message}\n")
                if alert.details:
                    f.write(f"Details: {json.dumps(alert.details, default=str)}\n")
                f.write("-" * 80 + "\n")
                
        except Exception as e:
            logger.error(f"Failed to write alert to file: {e}")
    
    def _email_alert_handler(self, alert: Alert):
        """Email alert handler"""
        if not self.smtp_username or not self.alert_email:
            return
        
        try:
            msg = MimeMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = self.alert_email
            msg['Subject'] = f"[{alert.severity.value.upper()}] Trading System Alert: {alert.name}"
            
            body = f"""
Trading System Alert

Alert: {alert.name}
Severity: {alert.severity.value.upper()}
Time: {alert.timestamp.isoformat()}
Message: {alert.message}

Details:
{json.dumps(alert.details, indent=2, default=str)}

This is an automated alert from the BreezeConnect Trading System.
"""
            
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Alert email sent for {alert.name}")
            
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self._monitoring_thread.daemon = True
        self._monitoring_thread.start()
        
        logger.info("Monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self._stop_monitoring.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info("Monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while not self._stop_monitoring.wait(30):  # Check every 30 seconds
            try:
                self._collect_system_metrics()
                self._collect_application_metrics()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    def _collect_system_metrics(self):
        """Collect system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric("cpu_usage", cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.record_metric("memory_usage", memory.percent)
            self.record_metric("memory_available", memory.available / (1024**3))  # GB
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.record_metric("disk_usage", disk_percent)
            self.record_metric("disk_free", disk.free / (1024**3))  # GB
            
            # Network I/O
            net_io = psutil.net_io_counters()
            self.record_metric("network_bytes_sent", net_io.bytes_sent, MetricType.COUNTER)
            self.record_metric("network_bytes_recv", net_io.bytes_recv, MetricType.COUNTER)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    def _collect_application_metrics(self):
        """Collect application-specific metrics"""
        try:
            # Database health check
            from src.infrastructure.database.connection_pool import health_check_databases
            db_health = health_check_databases()
            
            if db_health.get("healthy"):
                self.record_metric("database_healthy", 1.0)
            else:
                self.record_metric("database_healthy", 0.0)
            
            # Risk manager metrics
            from src.core.risk_manager import get_risk_manager
            risk_manager = get_risk_manager()
            risk_status = risk_manager.get_risk_status()
            
            # Position metrics
            self.record_metric("active_positions", risk_status["positions"]["count"])
            self.record_metric("position_utilization", risk_status["positions"]["utilization"])
            
            # Exposure metrics
            self.record_metric("total_exposure", risk_status["exposure"]["current"])
            self.record_metric("exposure_utilization", risk_status["exposure"]["utilization"])
            
            # Daily P&L metrics
            self.record_metric("daily_pnl", risk_status["daily_pnl"]["current"])
            if risk_status["daily_pnl"]["current"] < 0:
                daily_loss_ratio = risk_status["daily_pnl"]["utilization"] / 100
                self.record_metric("daily_loss_ratio", daily_loss_ratio)
            
            # Circuit breaker status
            active_breakers = sum(1 for cb in risk_status["circuit_breakers"].values() 
                                if cb["triggered"])
            self.record_metric("active_circuit_breakers", active_breakers)
            
        except Exception as e:
            logger.error(f"Failed to collect application metrics: {e}")
    
    def get_metrics(self, metric_name: str = None, 
                   since: datetime = None, 
                   limit: int = 100) -> List[Metric]:
        """Get collected metrics"""
        with self._lock:
            if metric_name:
                metrics = self.metrics.get(metric_name, [])
            else:
                metrics = []
                for metric_list in self.metrics.values():
                    metrics.extend(metric_list)
            
            # Filter by time if specified
            if since:
                metrics = [m for m in metrics if m.timestamp >= since]
            
            # Sort by timestamp and limit
            metrics.sort(key=lambda x: x.timestamp, reverse=True)
            return metrics[:limit]
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        with self._lock:
            return list(self.active_alerts.values())
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics"""
        with self._lock:
            summary = {}
            
            for metric_name, metric_list in self.metrics.items():
                if metric_list:
                    latest = metric_list[-1]
                    summary[metric_name] = {
                        'current_value': latest.value,
                        'timestamp': latest.timestamp.isoformat(),
                        'data_points': len(metric_list)
                    }
            
            return {
                'metrics': summary,
                'active_alerts': len(self.active_alerts),
                'generated_at': datetime.utcnow().isoformat()
            }
    
    def create_custom_alert(self, name: str, condition: Callable[[], bool], 
                          message: str, severity: AlertSeverity = AlertSeverity.WARNING,
                          check_interval: int = 60):
        """Create a custom alert with a condition function"""
        def check_condition():
            while not self._stop_monitoring.wait(check_interval):
                try:
                    if condition():
                        alert = Alert(
                            name=name,
                            severity=severity,
                            message=message,
                            details={'type': 'custom'},
                            timestamp=datetime.utcnow()
                        )
                        self._trigger_alert(f"custom_{name}", alert)
                    else:
                        self._resolve_alert(f"custom_{name}")
                except Exception as e:
                    logger.error(f"Custom alert condition check failed: {e}")
        
        thread = threading.Thread(target=check_condition)
        thread.daemon = True
        thread.start()

# Global monitoring instance
_monitoring_system: Optional[MonitoringSystem] = None

def get_monitoring_system() -> MonitoringSystem:
    """Get global monitoring system instance"""
    global _monitoring_system
    if _monitoring_system is None:
        _monitoring_system = MonitoringSystem()
    return _monitoring_system

# Convenience functions for common operations
def record_api_request(endpoint: str, method: str, status_code: int, response_time_ms: float):
    """Record API request metrics"""
    monitoring = get_monitoring_system()
    
    tags = {
        'endpoint': endpoint,
        'method': method,
        'status': str(status_code // 100) + 'xx'
    }
    
    monitoring.increment_counter("api_requests_total", tags)
    monitoring.record_timing("api_response_time", response_time_ms, tags)
    
    if status_code >= 400:
        monitoring.increment_counter("api_errors_total", tags)

def record_trade_event(event_type: str, symbol: str, success: bool = True):
    """Record trading event metrics"""
    monitoring = get_monitoring_system()
    
    tags = {
        'event_type': event_type,
        'symbol': symbol,
        'success': str(success).lower()
    }
    
    monitoring.increment_counter("trade_events_total", tags)
    
    if not success:
        monitoring.increment_counter("trade_errors_total", tags)