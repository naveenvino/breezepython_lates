"""
Market Data Repository Interface
Defines the contract for market data persistence
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from ..entities.market_data import MarketData, Quote, TimeInterval
from ..value_objects.trading_symbol import TradingSymbol


class IMarketDataRepository(ABC):
    """Interface for market data repository"""
    
    @abstractmethod
    async def save_market_data(self, market_data: MarketData) -> MarketData:
        """Save market data"""
        pass
    
    @abstractmethod
    async def save_market_data_bulk(self, market_data_list: List[MarketData]) -> int:
        """Save multiple market data records"""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[MarketData]:
        """Get market data by ID"""
        pass
    
    @abstractmethod
    async def get_latest(self, symbol: str) -> Optional[MarketData]:
        """Get latest market data for a symbol"""
        pass
    
    @abstractmethod
    async def get_by_symbol_and_date_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: Optional[TimeInterval] = None
    ) -> List[MarketData]:
        """Get market data for a symbol within date range"""
        pass
    
    @abstractmethod
    async def get_by_symbols_and_date(
        self,
        symbols: List[str],
        date: date,
        interval: Optional[TimeInterval] = None
    ) -> Dict[str, List[MarketData]]:
        """Get market data for multiple symbols on a specific date"""
        pass
    
    @abstractmethod
    async def exists(
        self,
        symbol: str,
        timestamp: datetime,
        interval: TimeInterval
    ) -> bool:
        """Check if market data exists"""
        pass
    
    @abstractmethod
    async def delete_by_symbol_and_date_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """Delete market data within date range"""
        pass
    
    @abstractmethod
    async def get_unique_symbols(self) -> List[str]:
        """Get all unique symbols in the repository"""
        pass
    
    @abstractmethod
    async def get_date_range_for_symbol(self, symbol: str) -> Optional[Dict[str, datetime]]:
        """Get the earliest and latest dates for a symbol"""
        pass
    
    @abstractmethod
    async def get_missing_dates(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: TimeInterval
    ) -> List[date]:
        """Get dates with missing data"""
        pass
    
    @abstractmethod
    async def get_data_statistics(self, symbol: str) -> Dict[str, Any]:
        """Get statistics about the data for a symbol"""
        pass


class IQuoteRepository(ABC):
    """Interface for real-time quote repository"""
    
    @abstractmethod
    async def save_quote(self, quote: Quote) -> Quote:
        """Save a quote"""
        pass
    
    @abstractmethod
    async def get_latest_quote(self, symbol: str) -> Optional[Quote]:
        """Get the latest quote for a symbol"""
        pass
    
    @abstractmethod
    async def get_quotes_by_symbols(self, symbols: List[str]) -> Dict[str, Quote]:
        """Get latest quotes for multiple symbols"""
        pass
    
    @abstractmethod
    async def get_quote_history(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[Quote]:
        """Get quote history for a symbol"""
        pass