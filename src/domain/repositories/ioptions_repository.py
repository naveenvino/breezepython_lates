"""
Options Repository Interface
Defines the contract for options data persistence
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from ..entities.option import Option, OptionType
from ..entities.market_data import MarketData, TimeInterval
from ..value_objects.strike_price import StrikePrice


class IOptionsRepository(ABC):
    """Interface for options repository"""
    
    @abstractmethod
    async def save_option(self, option: Option) -> Option:
        """Save an option"""
        pass
    
    @abstractmethod
    async def save_options_bulk(self, options: List[Option]) -> int:
        """Save multiple options"""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[Option]:
        """Get option by ID"""
        pass
    
    @abstractmethod
    async def get_by_trading_symbol(self, trading_symbol: str) -> Optional[Option]:
        """Get option by trading symbol"""
        pass
    
    @abstractmethod
    async def get_options_by_expiry(
        self,
        underlying: str,
        expiry_date: date,
        option_type: Optional[OptionType] = None
    ) -> List[Option]:
        """Get all options for a specific expiry"""
        pass
    
    @abstractmethod
    async def get_option_chain(
        self,
        underlying: str,
        expiry_date: date,
        min_strike: Optional[Decimal] = None,
        max_strike: Optional[Decimal] = None
    ) -> Dict[Decimal, Dict[str, Option]]:
        """Get option chain for an expiry"""
        pass
    
    @abstractmethod
    async def get_available_expiries(
        self,
        underlying: str,
        after_date: Optional[date] = None
    ) -> List[date]:
        """Get available expiry dates"""
        pass
    
    @abstractmethod
    async def get_available_strikes(
        self,
        underlying: str,
        expiry_date: date,
        option_type: Optional[OptionType] = None
    ) -> List[Decimal]:
        """Get available strikes for an expiry"""
        pass
    
    @abstractmethod
    async def get_atm_options(
        self,
        underlying: str,
        expiry_date: date,
        spot_price: Decimal,
        num_strikes: int = 1
    ) -> List[Option]:
        """Get ATM options"""
        pass
    
    @abstractmethod
    async def update_market_data(
        self,
        trading_symbol: str,
        last_price: Decimal,
        volume: Optional[int] = None,
        open_interest: Optional[int] = None,
        bid: Optional[Decimal] = None,
        ask: Optional[Decimal] = None
    ) -> bool:
        """Update market data for an option"""
        pass
    
    @abstractmethod
    async def update_greeks(
        self,
        trading_symbol: str,
        delta: Optional[Decimal] = None,
        gamma: Optional[Decimal] = None,
        theta: Optional[Decimal] = None,
        vega: Optional[Decimal] = None,
        iv: Optional[Decimal] = None
    ) -> bool:
        """Update Greeks for an option"""
        pass


class IOptionsHistoricalDataRepository(ABC):
    """Interface for options historical data repository"""
    
    @abstractmethod
    async def save_historical_data(
        self,
        trading_symbol: str,
        market_data: MarketData
    ) -> bool:
        """Save historical data for an option"""
        pass
    
    @abstractmethod
    async def save_historical_data_bulk(
        self,
        data: List[Dict[str, Any]]
    ) -> int:
        """Save bulk historical data"""
        pass
    
    @abstractmethod
    async def get_historical_data(
        self,
        trading_symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: TimeInterval = TimeInterval.ONE_DAY
    ) -> List[MarketData]:
        """Get historical data for an option"""
        pass
    
    @abstractmethod
    async def get_historical_data_by_strike(
        self,
        underlying: str,
        strike: Decimal,
        option_type: OptionType,
        expiry_date: date,
        start_date: datetime,
        end_date: datetime,
        interval: TimeInterval = TimeInterval.ONE_DAY
    ) -> List[MarketData]:
        """Get historical data by strike details"""
        pass
    
    @abstractmethod
    async def get_option_chain_snapshot(
        self,
        underlying: str,
        expiry_date: date,
        timestamp: datetime
    ) -> Dict[Decimal, Dict[str, MarketData]]:
        """Get option chain snapshot at specific time"""
        pass
    
    @abstractmethod
    async def exists(
        self,
        trading_symbol: str,
        timestamp: datetime,
        interval: TimeInterval
    ) -> bool:
        """Check if historical data exists"""
        pass
    
    @abstractmethod
    async def get_data_coverage(
        self,
        trading_symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get data coverage statistics"""
        pass
    
    @abstractmethod
    async def delete_historical_data(
        self,
        trading_symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """Delete historical data"""
        pass