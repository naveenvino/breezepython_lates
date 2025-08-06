"""
Notification Service Interface
Application interface for sending notifications
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    """Notification types"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class INotificationService(ABC):
    """Interface for notification service"""
    
    @abstractmethod
    async def send_notification(
        self,
        recipient: str,
        subject: str,
        message: str,
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Send a single notification"""
        pass
    
    @abstractmethod
    async def send_bulk_notifications(
        self,
        recipients: List[str],
        subject: str,
        message: str,
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """Send notifications to multiple recipients"""
        pass
    
    @abstractmethod
    async def send_trade_alert(
        self,
        trade_data: Dict[str, Any],
        recipients: List[str],
        channels: List[NotificationType]
    ) -> List[str]:
        """Send trade execution alert"""
        pass
    
    @abstractmethod
    async def send_risk_alert(
        self,
        risk_data: Dict[str, Any],
        recipients: List[str],
        priority: NotificationPriority = NotificationPriority.HIGH
    ) -> List[str]:
        """Send risk management alert"""
        pass
    
    @abstractmethod
    async def send_market_alert(
        self,
        market_data: Dict[str, Any],
        condition: str,
        recipients: List[str]
    ) -> List[str]:
        """Send market condition alert"""
        pass
    
    @abstractmethod
    async def send_system_alert(
        self,
        system_event: str,
        details: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.HIGH
    ) -> str:
        """Send system event alert"""
        pass
    
    @abstractmethod
    async def schedule_notification(
        self,
        recipient: str,
        subject: str,
        message: str,
        notification_type: NotificationType,
        scheduled_time: datetime,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Schedule a notification for future delivery"""
        pass
    
    @abstractmethod
    async def cancel_scheduled_notification(
        self,
        notification_id: str
    ) -> bool:
        """Cancel a scheduled notification"""
        pass
    
    @abstractmethod
    async def get_notification_status(
        self,
        notification_id: str
    ) -> Dict[str, Any]:
        """Get status of a notification"""
        pass
    
    @abstractmethod
    async def get_notification_history(
        self,
        recipient: Optional[str] = None,
        notification_type: Optional[NotificationType] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get notification history"""
        pass
    
    @abstractmethod
    async def update_notification_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """Update user notification preferences"""
        pass
    
    @abstractmethod
    async def get_notification_preferences(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Get user notification preferences"""
        pass
    
    @abstractmethod
    async def create_notification_template(
        self,
        template_name: str,
        template_type: NotificationType,
        subject_template: str,
        body_template: str,
        variables: List[str]
    ) -> str:
        """Create a notification template"""
        pass
    
    @abstractmethod
    async def send_templated_notification(
        self,
        recipient: str,
        template_name: str,
        variables: Dict[str, Any],
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.MEDIUM
    ) -> str:
        """Send notification using template"""
        pass