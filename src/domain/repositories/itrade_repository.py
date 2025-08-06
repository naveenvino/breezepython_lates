"""
Trade Repository Interface
Domain repository interface for trade persistence
"""
from abc import abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from .irepository import IRepository
from ..entities.trade import Trade, TradeStatus


class ITradeRepository(IRepository[Trade]):
    """Repository interface for trade entities"""
    
    @abstractmethod
    async def get_active_trades(self) -> List[Trade]:
        """Get all active/open trades"""
        pass
    
    @abstractmethod
    async def get_active_trade_by_symbol(self, symbol: str) -> Optional[Trade]:
        """Get active trade for a specific symbol"""
        pass
    
    @abstractmethod
    async def get_trades_by_date_range(
        self,
        from_date: datetime,
        to_date: datetime
    ) -> List[Trade]:
        """Get trades within a date range"""
        pass
    
    @abstractmethod
    async def get_trades_by_status(self, status: TradeStatus) -> List[Trade]:
        """Get trades by status"""
        pass
    
    @abstractmethod
    async def get_trade_statistics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get trade statistics for a period"""
        pass
    
    @abstractmethod
    async def add_trade_log(
        self,
        trade_id: str,
        action: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a log entry for a trade"""
        pass