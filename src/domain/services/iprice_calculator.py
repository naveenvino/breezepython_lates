"""
Price Calculator Service Interface
Domain service for price calculations
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime, date
from ..entities.option import Option
from ..entities.market_data import MarketData


class IPriceCalculator(ABC):
    """Interface for price calculation service"""
    
    @abstractmethod
    def calculate_option_price(
        self,
        spot_price: Decimal,
        strike_price: Decimal,
        time_to_expiry: float,
        volatility: Decimal,
        risk_free_rate: Decimal,
        is_call: bool,
        dividend_yield: Decimal = Decimal('0')
    ) -> Decimal:
        """Calculate theoretical option price using pricing model"""
        pass
    
    @abstractmethod
    def calculate_implied_volatility(
        self,
        option_price: Decimal,
        spot_price: Decimal,
        strike_price: Decimal,
        time_to_expiry: float,
        risk_free_rate: Decimal,
        is_call: bool,
        dividend_yield: Decimal = Decimal('0')
    ) -> Optional[Decimal]:
        """Calculate implied volatility from option price"""
        pass
    
    @abstractmethod
    def calculate_greeks(
        self,
        spot_price: Decimal,
        strike_price: Decimal,
        time_to_expiry: float,
        volatility: Decimal,
        risk_free_rate: Decimal,
        is_call: bool,
        dividend_yield: Decimal = Decimal('0')
    ) -> Dict[str, Decimal]:
        """Calculate option Greeks (delta, gamma, theta, vega, rho)"""
        pass
    
    @abstractmethod
    def calculate_intrinsic_value(
        self,
        spot_price: Decimal,
        strike_price: Decimal,
        is_call: bool
    ) -> Decimal:
        """Calculate intrinsic value of option"""
        pass
    
    @abstractmethod
    def calculate_time_value(
        self,
        option_price: Decimal,
        spot_price: Decimal,
        strike_price: Decimal,
        is_call: bool
    ) -> Decimal:
        """Calculate time value of option"""
        pass
    
    @abstractmethod
    def calculate_breakeven_price(
        self,
        strike_price: Decimal,
        premium: Decimal,
        is_call: bool,
        lot_size: int = 1
    ) -> Decimal:
        """Calculate breakeven price for option position"""
        pass
    
    @abstractmethod
    def calculate_payoff(
        self,
        spot_price: Decimal,
        strike_price: Decimal,
        premium: Decimal,
        is_call: bool,
        is_long: bool,
        quantity: int = 1
    ) -> Decimal:
        """Calculate payoff at expiry"""
        pass
    
    @abstractmethod
    def calculate_profit_loss(
        self,
        entry_price: Decimal,
        exit_price: Decimal,
        quantity: int,
        is_long: bool = True
    ) -> Dict[str, Decimal]:
        """Calculate profit/loss for a position"""
        pass
    
    @abstractmethod
    def calculate_margin_requirement(
        self,
        option: Option,
        spot_price: Decimal,
        quantity: int,
        is_short: bool = False
    ) -> Decimal:
        """Calculate margin requirement for option position"""
        pass