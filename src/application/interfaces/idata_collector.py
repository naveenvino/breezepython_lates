"""
Data Collector Interface
Application interface for data collection services
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import date, datetime


class IDataCollector(ABC):
    """Interface for data collection service"""
    
    @abstractmethod
    async def collect_index_data(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        interval: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Collect index/NIFTY data"""
        pass
    
    @abstractmethod
    async def collect_options_data(
        self,
        underlying: str,
        expiry_date: date,
        strikes: List[int],
        from_date: date,
        to_date: date,
        interval: str,
        option_types: List[str] = ["CE", "PE"],
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Collect options data for multiple strikes"""
        pass
    
    @abstractmethod
    async def collect_options_data_parallel(
        self,
        underlying: str,
        expiry_date: date,
        strikes: List[int],
        from_date: date,
        to_date: date,
        interval: str,
        option_types: List[str] = ["CE", "PE"],
        max_workers: int = 5,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Collect options data in parallel"""
        pass
    
    @abstractmethod
    async def collect_option_chain(
        self,
        symbol: str,
        expiry_date: Optional[date] = None,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """Collect complete option chain"""
        pass
    
    @abstractmethod
    async def collect_real_time_quotes(
        self,
        symbols: List[str]
    ) -> Dict[str, Any]:
        """Collect real-time quotes for symbols"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to data source"""
        pass