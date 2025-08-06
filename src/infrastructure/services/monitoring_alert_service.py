"""
Monitoring and Alert Service
Handles real-time monitoring and alert notifications for live trading
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Callable
from datetime import datetime, time
from enum import Enum
import json
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class AlertType(Enum):
    TRADE_EXECUTED = "TRADE_EXECUTED"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    POSITION_SQUARED_OFF = "POSITION_SQUARED_OFF"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    CONNECTION_LOST = "CONNECTION_LOST"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    ORDER_REJECTED = "ORDER_REJECTED"
    EXPIRY_SQUARE_OFF = "EXPIRY_SQUARE_OFF"
    SYSTEM_ERROR = "SYSTEM_ERROR"

class MonitoringAlertService:
    """
    Service for monitoring trading system and sending alerts
    """
    
    def __init__(self):
        # Email configuration
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_email = os.getenv('ALERT_EMAIL')
        
        # Alert configuration
        self.alert_callbacks = {
            AlertType.STOP_LOSS_HIT: [],
            AlertType.DAILY_LOSS_LIMIT: [],
            AlertType.CONNECTION_LOST: [],
            AlertType.SYSTEM_ERROR: []
        }
        
        # Monitoring thresholds
        self.thresholds = {
            'max_daily_loss': 50000,
            'max_trade_loss': 25000,
            'min_margin_percent': 20,
            'max_position_time_hours': 6
        }
        
        # Alert history
        self.alert_history = []
        
    def send_alert(self, alert_type: AlertType, level: AlertLevel, 
                  title: str, message: str, data: Optional[Dict] = None):
        """
        Send alert through configured channels
        
        Args:
            alert_type: Type of alert
            level: Severity level
            title: Alert title
            message: Alert message
            data: Additional data
        """
        alert = {
            'type': alert_type.value,
            'level': level.value,
            'title': title,
            'message': message,
            'data': data or {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Log the alert
        self._log_alert(alert)
        
        # Store in history
        self.alert_history.append(alert)
        
        # Send email for critical alerts
        if level == AlertLevel.CRITICAL:
            self._send_email_alert(alert)
        
        # Execute callbacks
        if alert_type in self.alert_callbacks:
            for callback in self.alert_callbacks[alert_type]:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
    
    def _log_alert(self, alert: Dict):
        """Log alert based on level"""
        if alert['level'] == AlertLevel.INFO.value:
            logger.info(f"ALERT: {alert['title']} - {alert['message']}")
        elif alert['level'] == AlertLevel.WARNING.value:
            logger.warning(f"ALERT: {alert['title']} - {alert['message']}")
        else:
            logger.critical(f"ALERT: {alert['title']} - {alert['message']}")
    
    def _send_email_alert(self, alert: Dict):
        """Send email alert"""
        if not all([self.smtp_username, self.smtp_password, self.alert_email]):
            logger.warning("Email configuration incomplete, skipping email alert")
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = self.alert_email
            msg['Subject'] = f"[{alert['level']}] Trading Alert: {alert['title']}"
            
            # Create email body
            body = f"""
Trading System Alert

Type: {alert['type']}
Level: {alert['level']}
Time: {alert['timestamp']}

{alert['message']}

Additional Data:
{json.dumps(alert['data'], indent=2)}

---
This is an automated alert from your trading system.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email alert sent to {self.alert_email}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def add_alert_callback(self, alert_type: AlertType, callback: Callable):
        """Add callback for specific alert type"""
        if alert_type in self.alert_callbacks:
            self.alert_callbacks[alert_type].append(callback)
    
    def monitor_position_health(self, positions: List[Dict]) -> List[Dict]:
        """
        Monitor position health and generate alerts
        
        Args:
            positions: List of current positions
            
        Returns:
            List of health issues found
        """
        issues = []
        total_pnl = sum(pos.get('pnl', 0) for pos in positions)
        
        # Check daily loss limit
        if total_pnl < -self.thresholds['max_daily_loss']:
            self.send_alert(
                AlertType.DAILY_LOSS_LIMIT,
                AlertLevel.CRITICAL,
                "Daily Loss Limit Exceeded",
                f"Total P&L: {total_pnl}. Limit: -{self.thresholds['max_daily_loss']}",
                {'total_pnl': total_pnl, 'limit': self.thresholds['max_daily_loss']}
            )
            issues.append({
                'type': 'daily_loss_limit',
                'severity': 'critical',
                'message': f"Daily loss limit exceeded: {total_pnl}"
            })
        
        # Check individual position losses
        for position in positions:
            pnl = position.get('pnl', 0)
            if pnl < -self.thresholds['max_trade_loss']:
                self.send_alert(
                    AlertType.STOP_LOSS_HIT,
                    AlertLevel.WARNING,
                    f"Large Loss on {position.get('symbol', 'Unknown')}",
                    f"Position P&L: {pnl}. Threshold: -{self.thresholds['max_trade_loss']}",
                    {'position': position}
                )
                issues.append({
                    'type': 'position_loss',
                    'severity': 'warning',
                    'symbol': position.get('symbol'),
                    'pnl': pnl
                })
        
        return issues
    
    def monitor_system_health(self, system_status: Dict) -> List[Dict]:
        """
        Monitor overall system health
        
        Args:
            system_status: Current system status
            
        Returns:
            List of system issues
        """
        issues = []
        
        # Check connection status
        if not system_status.get('kite_connected', False):
            self.send_alert(
                AlertType.CONNECTION_LOST,
                AlertLevel.CRITICAL,
                "Kite Connection Lost",
                "Lost connection to Kite API. Trading halted.",
                system_status
            )
            issues.append({
                'type': 'connection_lost',
                'severity': 'critical',
                'service': 'kite'
            })
        
        # Check authentication
        if not system_status.get('authenticated', False):
            self.send_alert(
                AlertType.AUTHENTICATION_FAILED,
                AlertLevel.CRITICAL,
                "Authentication Failed",
                "Kite authentication failed. Please re-authenticate.",
                system_status
            )
            issues.append({
                'type': 'auth_failed',
                'severity': 'critical'
            })
        
        # Check margin
        margin_percent = system_status.get('available_margin_percent', 100)
        if margin_percent < self.thresholds['min_margin_percent']:
            self.send_alert(
                AlertType.WARNING,
                AlertLevel.WARNING,
                "Low Margin",
                f"Available margin: {margin_percent}%. Minimum: {self.thresholds['min_margin_percent']}%",
                {'margin_percent': margin_percent}
            )
            issues.append({
                'type': 'low_margin',
                'severity': 'warning',
                'margin_percent': margin_percent
            })
        
        return issues
    
    def check_market_hours(self) -> bool:
        """Check if market is open"""
        now = datetime.now()
        
        # Market hours
        market_open = time(9, 15)
        market_close = time(15, 30)
        
        # Check weekday
        if now.weekday() > 4:  # Weekend
            return False
        
        # Check time
        current_time = now.time()
        return market_open <= current_time <= market_close
    
    def check_expiry_day_alerts(self) -> Optional[Dict]:
        """Check for expiry day specific alerts"""
        now = datetime.now()
        
        # Check if Thursday (expiry day)
        if now.weekday() == 3:
            current_time = now.time()
            
            # Alert 30 minutes before square-off
            if current_time >= time(14, 45) and current_time < time(14, 50):
                return {
                    'type': 'expiry_warning',
                    'message': 'Expiry day square-off in 30 minutes',
                    'time_remaining': '30 minutes'
                }
            
            # Alert 15 minutes before square-off
            elif current_time >= time(15, 0) and current_time < time(15, 5):
                return {
                    'type': 'expiry_urgent',
                    'message': 'Expiry day square-off in 15 minutes',
                    'time_remaining': '15 minutes'
                }
        
        return None
    
    def get_alert_summary(self, hours: int = 24) -> Dict:
        """Get summary of alerts in last N hours"""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        
        recent_alerts = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert['timestamp']).timestamp() > cutoff_time
        ]
        
        summary = {
            'total_alerts': len(recent_alerts),
            'by_level': {},
            'by_type': {},
            'critical_alerts': []
        }
        
        for alert in recent_alerts:
            # Count by level
            level = alert['level']
            summary['by_level'][level] = summary['by_level'].get(level, 0) + 1
            
            # Count by type
            alert_type = alert['type']
            summary['by_type'][alert_type] = summary['by_type'].get(alert_type, 0) + 1
            
            # Collect critical alerts
            if alert['level'] == AlertLevel.CRITICAL.value:
                summary['critical_alerts'].append({
                    'title': alert['title'],
                    'message': alert['message'],
                    'timestamp': alert['timestamp']
                })
        
        return summary
    
    def update_threshold(self, key: str, value: float):
        """Update monitoring threshold"""
        if key in self.thresholds:
            self.thresholds[key] = value
            logger.info(f"Updated threshold {key} to {value}")
    
    def clear_alert_history(self, older_than_hours: int = 24):
        """Clear old alerts from history"""
        cutoff_time = datetime.now().timestamp() - (older_than_hours * 3600)
        
        self.alert_history = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert['timestamp']).timestamp() > cutoff_time
        ]
        
        logger.info(f"Cleared alerts older than {older_than_hours} hours")