"""
Strike Price Value Object
Represents and validates option strike prices
"""
from decimal import Decimal
from typing import List, Optional
from ..entities.base import ValueObject


class StrikePrice(ValueObject):
    """Value object representing an option strike price"""
    
    def __init__(self, price: float, underlying: str = "NIFTY"):
        if price <= 0:
            raise ValueError("Strike price must be positive")
        
        self._price = Decimal(str(price))
        self._underlying = underlying.upper()
        self._interval = self._get_strike_interval()
        
        # Validate strike price is at correct interval
        if not self._is_valid_strike():
            raise ValueError(
                f"Strike price {price} is not valid for {underlying}. "
                f"Must be at {self._interval} point intervals"
            )
    
    def _get_strike_interval(self) -> int:
        """Get the strike interval for the underlying"""
        intervals = {
            "NIFTY": 50,
            "BANKNIFTY": 100,
            "FINNIFTY": 50,
            "MIDCPNIFTY": 25
        }
        return intervals.get(self._underlying, 50)
    
    def _is_valid_strike(self) -> bool:
        """Check if the strike price is at valid interval"""
        return self._price % self._interval == 0
    
    @property
    def price(self) -> Decimal:
        """Get the strike price"""
        return self._price
    
    @property
    def underlying(self) -> str:
        """Get the underlying instrument"""
        return self._underlying
    
    @property
    def interval(self) -> int:
        """Get the strike interval"""
        return self._interval
    
    def __float__(self) -> float:
        """Convert to float"""
        return float(self._price)
    
    def __int__(self) -> int:
        """Convert to int"""
        return int(self._price)
    
    def distance_from(self, spot_price: float) -> Decimal:
        """Calculate distance from spot price"""
        return abs(self._price - Decimal(str(spot_price)))
    
    def percentage_from(self, spot_price: float) -> Decimal:
        """Calculate percentage distance from spot price"""
        spot = Decimal(str(spot_price))
        if spot == 0:
            return Decimal('0')
        return (self.distance_from(spot_price) / spot) * 100
    
    def is_itm_call(self, spot_price: float) -> bool:
        """Check if this strike is ITM for a call option"""
        return Decimal(str(spot_price)) > self._price
    
    def is_itm_put(self, spot_price: float) -> bool:
        """Check if this strike is ITM for a put option"""
        return Decimal(str(spot_price)) < self._price
    
    def is_otm_call(self, spot_price: float) -> bool:
        """Check if this strike is OTM for a call option"""
        return Decimal(str(spot_price)) < self._price
    
    def is_otm_put(self, spot_price: float) -> bool:
        """Check if this strike is OTM for a put option"""
        return Decimal(str(spot_price)) > self._price
    
    def is_atm(self, spot_price: float, threshold_percent: float = 0.5) -> bool:
        """Check if this strike is ATM within threshold"""
        return self.percentage_from(spot_price) <= Decimal(str(threshold_percent))
    
    def next_strike(self) -> 'StrikePrice':
        """Get the next higher strike"""
        return StrikePrice(float(self._price + self._interval), self._underlying)
    
    def previous_strike(self) -> 'StrikePrice':
        """Get the previous lower strike"""
        new_price = self._price - self._interval
        if new_price <= 0:
            raise ValueError("Previous strike would be negative")
        return StrikePrice(float(new_price), self._underlying)
    
    @staticmethod
    def get_atm_strike(spot_price: float, underlying: str = "NIFTY") -> 'StrikePrice':
        """Get the ATM strike for a given spot price"""
        interval = StrikePrice._get_interval_for_underlying(underlying)
        atm_price = round(spot_price / interval) * interval
        return StrikePrice(atm_price, underlying)
    
    @staticmethod
    def _get_interval_for_underlying(underlying: str) -> int:
        """Static method to get interval for underlying"""
        intervals = {
            "NIFTY": 50,
            "BANKNIFTY": 100,
            "FINNIFTY": 50,
            "MIDCPNIFTY": 25
        }
        return intervals.get(underlying.upper(), 50)
    
    @staticmethod
    def get_strikes_around_spot(
        spot_price: float,
        num_strikes: int = 10,
        underlying: str = "NIFTY"
    ) -> List['StrikePrice']:
        """Get strikes around spot price"""
        atm_strike = StrikePrice.get_atm_strike(spot_price, underlying)
        strikes = []
        
        # Add strikes below ATM
        current = atm_strike
        for _ in range(num_strikes // 2):
            try:
                current = current.previous_strike()
                strikes.insert(0, current)
            except ValueError:
                break
        
        # Add ATM
        strikes.append(atm_strike)
        
        # Add strikes above ATM
        current = atm_strike
        for _ in range(num_strikes // 2):
            current = current.next_strike()
            strikes.append(current)
        
        return strikes
    
    @staticmethod
    def get_strikes_in_range(
        min_strike: float,
        max_strike: float,
        underlying: str = "NIFTY"
    ) -> List['StrikePrice']:
        """Get all valid strikes in a range"""
        interval = StrikePrice._get_interval_for_underlying(underlying)
        
        # Round to nearest valid strikes
        start = (int(min_strike) // interval) * interval
        if start < min_strike:
            start += interval
        
        end = (int(max_strike) // interval) * interval
        if end > max_strike:
            end -= interval
        
        strikes = []
        current = start
        while current <= end:
            strikes.append(StrikePrice(current, underlying))
            current += interval
        
        return strikes
    
    def __str__(self) -> str:
        return str(int(self._price))
    
    def __repr__(self) -> str:
        return f"StrikePrice({self._price}, '{self._underlying}')"
    
    def __lt__(self, other):
        if isinstance(other, StrikePrice):
            return self._price < other._price
        return self._price < other
    
    def __le__(self, other):
        if isinstance(other, StrikePrice):
            return self._price <= other._price
        return self._price <= other
    
    def __gt__(self, other):
        if isinstance(other, StrikePrice):
            return self._price > other._price
        return self._price > other
    
    def __ge__(self, other):
        if isinstance(other, StrikePrice):
            return self._price >= other._price
        return self._price >= other
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'price': float(self._price),
            'underlying': self._underlying,
            'interval': self._interval
        }