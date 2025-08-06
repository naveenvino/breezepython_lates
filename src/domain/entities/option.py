"""
Option Entity - Represents an options contract
"""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
from .base import Entity


class OptionType(Enum):
    """Option type enumeration"""
    CALL = "CE"
    PUT = "PE"


class Option(Entity):
    """Option entity representing an options contract"""
    
    def __init__(
        self,
        id: Optional[str] = None,
        underlying: str = None,
        strike_price: Decimal = None,
        expiry_date: date = None,
        option_type: OptionType = None,
        lot_size: int = 50  # Default NIFTY lot size
    ):
        super().__init__(id)
        self._underlying = underlying
        self._strike_price = strike_price
        self._expiry_date = expiry_date
        self._option_type = option_type
        self._lot_size = lot_size
        
        # Market data
        self._last_price: Optional[Decimal] = None
        self._bid_price: Optional[Decimal] = None
        self._ask_price: Optional[Decimal] = None
        self._volume: Optional[int] = None
        self._open_interest: Optional[int] = None
        
        # Greeks
        self._delta: Optional[Decimal] = None
        self._gamma: Optional[Decimal] = None
        self._theta: Optional[Decimal] = None
        self._vega: Optional[Decimal] = None
        self._iv: Optional[Decimal] = None  # Implied Volatility
    
    @property
    def underlying(self) -> str:
        return self._underlying
    
    @property
    def strike_price(self) -> Decimal:
        return self._strike_price
    
    @property
    def expiry_date(self) -> date:
        return self._expiry_date
    
    @property
    def option_type(self) -> OptionType:
        return self._option_type
    
    @property
    def lot_size(self) -> int:
        return self._lot_size
    
    @property
    def last_price(self) -> Optional[Decimal]:
        return self._last_price
    
    @property
    def bid_price(self) -> Optional[Decimal]:
        return self._bid_price
    
    @property
    def ask_price(self) -> Optional[Decimal]:
        return self._ask_price
    
    @property
    def volume(self) -> Optional[int]:
        return self._volume
    
    @property
    def open_interest(self) -> Optional[int]:
        return self._open_interest
    
    @property
    def iv(self) -> Optional[Decimal]:
        return self._iv
    
    @property
    def trading_symbol(self) -> str:
        """Generate trading symbol for the option"""
        expiry_str = self._expiry_date.strftime('%y%b%d').upper()
        return f"{self._underlying}{expiry_str}{int(self._strike_price)}{self._option_type.value}"
    
    @property
    def is_call(self) -> bool:
        """Check if this is a call option"""
        return self._option_type == OptionType.CALL
    
    @property
    def is_put(self) -> bool:
        """Check if this is a put option"""
        return self._option_type == OptionType.PUT
    
    @property
    def days_to_expiry(self) -> int:
        """Calculate days remaining to expiry"""
        if self._expiry_date:
            return (self._expiry_date - date.today()).days
        return 0
    
    @property
    def is_expired(self) -> bool:
        """Check if option has expired"""
        return self.days_to_expiry < 0
    
    @property
    def is_weekly(self) -> bool:
        """Check if this is a weekly option (expires on Thursday)"""
        return self._expiry_date.weekday() == 3  # Thursday
    
    @property
    def is_monthly(self) -> bool:
        """Check if this is a monthly option (last Thursday of month)"""
        if not self.is_weekly:
            return False
        
        # Check if this Thursday is the last Thursday of the month
        next_week = self._expiry_date + datetime.timedelta(days=7)
        return next_week.month != self._expiry_date.month
    
    @property
    def bid_ask_spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread"""
        if self._bid_price and self._ask_price:
            return self._ask_price - self._bid_price
        return None
    
    @property
    def mid_price(self) -> Optional[Decimal]:
        """Calculate mid price between bid and ask"""
        if self._bid_price and self._ask_price:
            return (self._bid_price + self._ask_price) / 2
        return self._last_price
    
    def update_market_data(
        self,
        last_price: Optional[Decimal] = None,
        bid_price: Optional[Decimal] = None,
        ask_price: Optional[Decimal] = None,
        volume: Optional[int] = None,
        open_interest: Optional[int] = None
    ) -> 'Option':
        """Update market data for the option"""
        if last_price is not None:
            self._last_price = last_price
        if bid_price is not None:
            self._bid_price = bid_price
        if ask_price is not None:
            self._ask_price = ask_price
        if volume is not None:
            self._volume = volume
        if open_interest is not None:
            self._open_interest = open_interest
        
        self.mark_updated()
        return self
    
    def update_greeks(
        self,
        delta: Optional[Decimal] = None,
        gamma: Optional[Decimal] = None,
        theta: Optional[Decimal] = None,
        vega: Optional[Decimal] = None,
        iv: Optional[Decimal] = None
    ) -> 'Option':
        """Update option Greeks"""
        if delta is not None:
            self._delta = delta
        if gamma is not None:
            self._gamma = gamma
        if theta is not None:
            self._theta = theta
        if vega is not None:
            self._vega = vega
        if iv is not None:
            self._iv = iv
        
        self.mark_updated()
        return self
    
    def calculate_intrinsic_value(self, spot_price: Decimal) -> Decimal:
        """Calculate intrinsic value of the option"""
        if self.is_call:
            return max(spot_price - self._strike_price, Decimal('0'))
        else:  # PUT
            return max(self._strike_price - spot_price, Decimal('0'))
    
    def calculate_time_value(self, spot_price: Decimal) -> Optional[Decimal]:
        """Calculate time value of the option"""
        if self._last_price is None:
            return None
        
        intrinsic_value = self.calculate_intrinsic_value(spot_price)
        return self._last_price - intrinsic_value
    
    def is_itm(self, spot_price: Decimal) -> bool:
        """Check if option is In-The-Money"""
        if self.is_call:
            return spot_price > self._strike_price
        else:  # PUT
            return spot_price < self._strike_price
    
    def is_otm(self, spot_price: Decimal) -> bool:
        """Check if option is Out-of-The-Money"""
        return not self.is_itm(spot_price) and not self.is_atm(spot_price)
    
    def is_atm(self, spot_price: Decimal, threshold: Decimal = Decimal('0.5')) -> bool:
        """Check if option is At-The-Money"""
        percentage_diff = abs((spot_price - self._strike_price) / spot_price) * 100
        return percentage_diff <= threshold
    
    def moneyness(self, spot_price: Decimal) -> Decimal:
        """Calculate moneyness of the option"""
        return spot_price / self._strike_price
    
    def to_dict(self) -> dict:
        """Convert option to dictionary"""
        return {
            'id': self.id,
            'underlying': self._underlying,
            'strike_price': float(self._strike_price) if self._strike_price else None,
            'expiry_date': self._expiry_date.isoformat() if self._expiry_date else None,
            'option_type': self._option_type.value if self._option_type else None,
            'lot_size': self._lot_size,
            'trading_symbol': self.trading_symbol,
            'last_price': float(self._last_price) if self._last_price else None,
            'bid_price': float(self._bid_price) if self._bid_price else None,
            'ask_price': float(self._ask_price) if self._ask_price else None,
            'volume': self._volume,
            'open_interest': self._open_interest,
            'bid_ask_spread': float(self.bid_ask_spread) if self.bid_ask_spread else None,
            'mid_price': float(self.mid_price) if self.mid_price else None,
            'days_to_expiry': self.days_to_expiry,
            'is_weekly': self.is_weekly,
            'is_monthly': self.is_monthly,
            'greeks': {
                'delta': float(self._delta) if self._delta else None,
                'gamma': float(self._gamma) if self._gamma else None,
                'theta': float(self._theta) if self._theta else None,
                'vega': float(self._vega) if self._vega else None,
                'iv': float(self._iv) if self._iv else None
            },
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }