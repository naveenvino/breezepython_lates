"""
Alert Notification Service
Handles Telegram, Email, and Push notifications for trading events
"""

import logging
import asyncio
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
import os

logger = logging.getLogger(__name__)

class AlertType(Enum):
    TRADE_ENTRY = "trade_entry"
    TRADE_EXIT = "trade_exit"
    STOP_LOSS = "stop_loss"
    RISK_WARNING = "risk_warning"
    DAILY_SUMMARY = "daily_summary"
    SYSTEM_ERROR = "system_error"
    POSITION_UPDATE = "position_update"
    MARKET_ALERT = "market_alert"

class AlertPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AlertConfig:
    """Alert configuration settings"""
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    email_enabled: bool = False
    email_smtp_server: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_from: str = ""
    email_password: str = ""
    email_to: List[str] = None
    
    webhook_enabled: bool = False
    webhook_url: str = ""
    
    sound_enabled: bool = True
    desktop_notifications: bool = True
    
    def __post_init__(self):
        if self.email_to is None:
            self.email_to = []

@dataclass
class Alert:
    """Alert message structure"""
    type: AlertType
    priority: AlertPriority
    title: str
    message: str
    data: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.data is None:
            self.data = {}

class AlertNotificationService:
    """
    Manages alert notifications across multiple channels
    """
    
    def __init__(self):
        self.config = AlertConfig()
        self.alert_history = []
        self.max_history = 100
        self.load_config()
        
        # Alert templates
        self.templates = {
            AlertType.TRADE_ENTRY: "🟢 *TRADE ENTRY*\n{signal} - {strike} {type}\nQuantity: {quantity}\nPrice: ₹{price}",
            AlertType.TRADE_EXIT: "🔴 *TRADE EXIT*\n{signal} - {strike} {type}\nP&L: ₹{pnl}\nReason: {reason}",
            AlertType.STOP_LOSS: "⛔ *STOP LOSS HIT*\n{strike} {type}\nLoss: ₹{loss}\nReason: {reason}",
            AlertType.RISK_WARNING: "⚠️ *RISK WARNING*\n{message}\nCurrent Risk Level: {risk_level}",
            AlertType.DAILY_SUMMARY: "📊 *DAILY SUMMARY*\nTotal P&L: ₹{total_pnl}\nTrades: {trade_count}\nWin Rate: {win_rate}%",
            AlertType.SYSTEM_ERROR: "🚨 *SYSTEM ERROR*\n{error_message}\nComponent: {component}",
            AlertType.POSITION_UPDATE: "📈 *POSITION UPDATE*\n{strike} {type}\nCurrent P&L: ₹{pnl}\nBreakeven: {breakeven}",
            AlertType.MARKET_ALERT: "📢 *MARKET ALERT*\nNIFTY: {spot_price}\n{message}"
        }
    
    def load_config(self):
        """Load configuration from file or environment"""
        config_file = "alert_config.json"
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    for key, value in config_data.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
                logger.info("Alert configuration loaded")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        # Override with environment variables if present
        if os.getenv('TELEGRAM_BOT_TOKEN'):
            self.config.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            self.config.telegram_enabled = True
        
        if os.getenv('TELEGRAM_CHAT_ID'):
            self.config.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    def save_config(self):
        """Save current configuration"""
        try:
            config_dict = asdict(self.config)
            # Don't save sensitive data
            config_dict.pop('email_password', None)
            config_dict.pop('telegram_bot_token', None)
            
            with open("alert_config.json", 'w') as f:
                json.dump(config_dict, f, indent=2)
            logger.info("Alert configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    async def send_alert(self, alert: Alert) -> bool:
        """
        Send alert through all enabled channels
        
        Returns:
            Success status
        """
        success = True
        
        # Add to history
        self._add_to_history(alert)
        
        # Format message
        message = self._format_message(alert)
        
        # Send through enabled channels
        tasks = []
        
        if self.config.telegram_enabled:
            tasks.append(self._send_telegram(alert.title, message, alert.priority))
        
        if self.config.email_enabled and alert.priority in [AlertPriority.HIGH, AlertPriority.CRITICAL]:
            tasks.append(self._send_email(alert.title, message, alert.priority))
        
        if self.config.webhook_enabled:
            tasks.append(self._send_webhook(alert))
        
        # Execute all tasks
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Alert send error: {result}")
                    success = False
        
        return success
    
    async def _send_telegram(self, title: str, message: str, priority: AlertPriority) -> bool:
        """Send Telegram notification"""
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
            
            # Add priority emoji
            priority_emoji = {
                AlertPriority.LOW: "ℹ️",
                AlertPriority.MEDIUM: "📌",
                AlertPriority.HIGH: "⚠️",
                AlertPriority.CRITICAL: "🚨"
            }
            
            full_message = f"{priority_emoji.get(priority, '')} {title}\n\n{message}"
            
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": full_message,
                "parse_mode": "Markdown"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Telegram alert sent: {title}")
                        return True
                    else:
                        logger.error(f"Telegram send failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False
    
    async def _send_email(self, subject: str, body: str, priority: AlertPriority) -> bool:
        """Send email notification"""
        if not self.config.email_enabled or not self.config.email_to:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.email_from
            msg['To'] = ', '.join(self.config.email_to)
            msg['Subject'] = f"[{priority.value.upper()}] {subject}"
            
            # Add priority header for email clients
            if priority == AlertPriority.CRITICAL:
                msg['X-Priority'] = '1'
            elif priority == AlertPriority.HIGH:
                msg['X-Priority'] = '2'
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.config.email_smtp_server, self.config.email_smtp_port) as server:
                server.starttls()
                server.login(self.config.email_from, self.config.email_password)
                server.send_message(msg)
            
            logger.info(f"Email alert sent: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False
    
    async def _send_webhook(self, alert: Alert) -> bool:
        """Send webhook notification"""
        if not self.config.webhook_enabled or not self.config.webhook_url:
            return False
        
        try:
            payload = {
                "type": alert.type.value,
                "priority": alert.priority.value,
                "title": alert.title,
                "message": alert.message,
                "data": alert.data,
                "timestamp": alert.timestamp.isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.webhook_url, json=payload) as response:
                    if response.status in [200, 201, 204]:
                        logger.info(f"Webhook alert sent: {alert.title}")
                        return True
                    else:
                        logger.error(f"Webhook send failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Webhook send error: {e}")
            return False
    
    def _format_message(self, alert: Alert) -> str:
        """Format alert message using template"""
        template = self.templates.get(alert.type, "{message}")
        
        try:
            # Merge alert data for formatting
            format_data = {**alert.data, "message": alert.message}
            return template.format(**format_data)
        except Exception as e:
            logger.error(f"Message format error: {e}")
            return alert.message
    
    def _add_to_history(self, alert: Alert):
        """Add alert to history"""
        self.alert_history.append({
            "type": alert.type.value,
            "priority": alert.priority.value,
            "title": alert.title,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat()
        })
        
        # Limit history size
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
    
    async def send_trade_entry(self, signal: str, strike: int, option_type: str, quantity: int, price: float):
        """Send trade entry alert"""
        alert = Alert(
            type=AlertType.TRADE_ENTRY,
            priority=AlertPriority.HIGH,
            title="New Trade Entry",
            message=f"Entered {signal} trade",
            data={
                "signal": signal,
                "strike": strike,
                "type": option_type,
                "quantity": quantity,
                "price": price
            }
        )
        await self.send_alert(alert)
    
    def send_trade_exit(self, signal: str, strike: int, option_type: str, pnl: float, reason: str):
        """Send trade exit alert"""
        priority = AlertPriority.HIGH if pnl < 0 else AlertPriority.MEDIUM
        
        alert = Alert(
            type=AlertType.TRADE_EXIT,
            priority=priority,
            title="Trade Exit",
            message=f"Exited {signal} trade",
            data={
                "signal": signal,
                "strike": strike,
                "type": option_type,
                "pnl": pnl,
                "reason": reason
            }
        )
        asyncio.create_task(self.send_alert(alert))
    
    def send_stop_loss(self, strike: int, option_type: str, loss: float, reason: str):
        """Send stop loss alert"""
        alert = Alert(
            type=AlertType.STOP_LOSS,
            priority=AlertPriority.CRITICAL,
            title="Stop Loss Triggered",
            message=f"Stop loss hit for {strike} {option_type}",
            data={
                "strike": strike,
                "type": option_type,
                "loss": abs(loss),
                "reason": reason
            }
        )
        asyncio.create_task(self.send_alert(alert))
    
    def send_risk_warning(self, message: str, risk_level: str):
        """Send risk warning alert"""
        priority = AlertPriority.CRITICAL if risk_level == "HIGH" else AlertPriority.HIGH
        
        alert = Alert(
            type=AlertType.RISK_WARNING,
            priority=priority,
            title="Risk Warning",
            message=message,
            data={
                "risk_level": risk_level
            }
        )
        asyncio.create_task(self.send_alert(alert))
    
    def send_daily_summary(self, total_pnl: float, trade_count: int, win_rate: float):
        """Send daily summary alert"""
        alert = Alert(
            type=AlertType.DAILY_SUMMARY,
            priority=AlertPriority.MEDIUM,
            title="Daily Trading Summary",
            message="End of day summary",
            data={
                "total_pnl": total_pnl,
                "trade_count": trade_count,
                "win_rate": win_rate
            }
        )
        asyncio.create_task(self.send_alert(alert))
    
    def send_system_error(self, error_message: str, component: str):
        """Send system error alert"""
        alert = Alert(
            type=AlertType.SYSTEM_ERROR,
            priority=AlertPriority.CRITICAL,
            title="System Error",
            message="System error detected",
            data={
                "error_message": error_message,
                "component": component
            }
        )
        asyncio.create_task(self.send_alert(alert))
    
    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent alert history"""
        return self.alert_history[-limit:]
    
    async def send_telegram_alert(self, alert: Alert) -> bool:
        """Public method to send telegram alert"""
        return await self._send_telegram(alert.title, self._format_message(alert), alert.priority)
    
    def send_email_alert(self, alert: Alert) -> bool:
        """Public method to send email alert (sync wrapper for async)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._send_email(alert.title, self._format_message(alert), alert.priority))
        finally:
            loop.close()
    
    def update_config(self, config_updates: Dict[str, Any]):
        """Update alert configuration"""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self.save_config()
        logger.info(f"Alert config updated: {list(config_updates.keys())}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration (without sensitive data)"""
        config_dict = asdict(self.config)
        # Hide sensitive data
        if config_dict.get('telegram_bot_token'):
            config_dict['telegram_bot_token'] = '***' + config_dict['telegram_bot_token'][-4:]
        if config_dict.get('email_password'):
            config_dict['email_password'] = '***'
        return config_dict
    
    async def test_desktop(self) -> bool:
        """Test desktop notifications (always available)"""
        try:
            logger.info("Desktop notifications available (console output)")
            return True
        except Exception as e:
            logger.error(f"Desktop test error: {e}")
            return False

# Singleton instance
_instance = None

def get_alert_service() -> AlertNotificationService:
    """Get singleton instance of alert service"""
    global _instance
    if _instance is None:
        _instance = AlertNotificationService()
    return _instance