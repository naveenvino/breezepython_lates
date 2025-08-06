"""
Application Interfaces
Interfaces for application services
"""
from .idata_collector import IDataCollector
from .ibacktest_engine import IBacktestEngine
from .istrategy_manager import IStrategyManager
from .inotification_service import INotificationService, NotificationType, NotificationPriority

__all__ = [
    'IDataCollector',
    'IBacktestEngine',
    'IStrategyManager',
    'INotificationService',
    'NotificationType',
    'NotificationPriority'
]