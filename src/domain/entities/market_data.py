"""
Market Data Entity - Represents market data for instruments
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any
from .base import Entity


class TimeInterval(Enum):
    """Time interval enumeration"""
    ONE_MINUTE = "1minute"
    FIVE_MINUTE = "5minute"
    FIFTEEN_MINUTE = "15minute"
    THIRTY_MINUTE = "30minute"
    ONE_HOUR = "1hour"
    ONE_DAY = "1day"
    ONE_WEEK = "1week"
    ONE_MONTH = "1month"


class MarketData(Entity):
    """Market data entity representing price and volume information"""
    
    def __init__(
        self,
        id: Optional[str] = None,
        symbol: str = None,
        timestamp: datetime = None,
        interval: TimeInterval = TimeInterval.ONE_MINUTE
    ):
        super().__init__(id)
        self._symbol = symbol
        self._timestamp = timestamp
        self._interval = interval
        
        # OHLC data
        self._open: Optional[Decimal] = None
        self._high: Optional[Decimal] = None
        self._low: Optional[Decimal] = None
        self._close: Optional[Decimal] = None
        
        # Volume data
        self._volume: Optional[int] = None
        self._open_interest: Optional[int] = None
        
        # Additional market data
        self._bid: Optional[Decimal] = None
        self._ask: Optional[Decimal] = None
        self._last_traded_price: Optional[Decimal] = None
        self._previous_close: Optional[Decimal] = None
        
        # Calculated fields
        self._vwap: Optional[Decimal] = None  # Volume Weighted Average Price
        self._turnover: Optional[Decimal] = None
        self._trades_count: Optional[int] = None
    
    @property
    def symbol(self) -> str:
        return self._symbol
    
    @property
    def timestamp(self) -> datetime:
        return self._timestamp
    
    @property
    def interval(self) -> TimeInterval:
        return self._interval
    
    @property
    def open(self) -> Optional[Decimal]:
        return self._open
    
    @property
    def high(self) -> Optional[Decimal]:
        return self._high
    
    @property
    def low(self) -> Optional[Decimal]:
        return self._low
    
    @property
    def close(self) -> Optional[Decimal]:
        return self._close
    
    @property
    def volume(self) -> Optional[int]:
        return self._volume
    
    @property
    def open_interest(self) -> Optional[int]:
        return self._open_interest
    
    @property
    def bid(self) -> Optional[Decimal]:
        return self._bid
    
    @property
    def ask(self) -> Optional[Decimal]:
        return self._ask
    
    @property
    def vwap(self) -> Optional[Decimal]:
        return self._vwap
    
    @property
    def change(self) -> Optional[Decimal]:
        """Calculate absolute change from previous close"""
        if self._close and self._previous_close:
            return self._close - self._previous_close
        return None
    
    @property
    def change_percentage(self) -> Optional[Decimal]:
        """Calculate percentage change from previous close"""
        if self._close and self._previous_close and self._previous_close != 0:
            return ((self._close - self._previous_close) / self._previous_close) * 100
        return None
    
    @property
    def range(self) -> Optional[Decimal]:
        """Calculate range (high - low)"""
        if self._high and self._low:
            return self._high - self._low
        return None
    
    @property
    def typical_price(self) -> Optional[Decimal]:
        """Calculate typical price (HLC/3)"""
        if all([self._high, self._low, self._close]):
            return (self._high + self._low + self._close) / 3
        return None
    
    @property
    def true_range(self) -> Optional[Decimal]:
        """Calculate true range for ATR calculations"""
        if not all([self._high, self._low]):
            return None
        
        high_low = self._high - self._low
        
        if self._previous_close:
            high_close = abs(self._high - self._previous_close)
            low_close = abs(self._low - self._previous_close)
            return max(high_low, high_close, low_close)
        
        return high_low
    
    @property
    def is_bullish_candle(self) -> bool:
        """Check if this is a bullish candle"""
        if self._open and self._close:
            return self._close > self._open
        return False
    
    @property
    def is_bearish_candle(self) -> bool:
        """Check if this is a bearish candle"""
        if self._open and self._close:
            return self._close < self._open
        return False
    
    @property
    def is_doji(self, threshold: Decimal = Decimal('0.1')) -> bool:
        """Check if this is a doji candle"""
        if self._open and self._close and self._high and self._low:
            body = abs(self._close - self._open)
            range_val = self._high - self._low
            if range_val > 0:
                return (body / range_val) < threshold
        return False
    
    def set_ohlc(self, open: Decimal, high: Decimal, low: Decimal, close: Decimal) -> 'MarketData':
        """Set OHLC values"""
        self._open = open
        self._high = high
        self._low = low
        self._close = close
        self.mark_updated()
        return self
    
    def set_volume_data(self, volume: int, open_interest: Optional[int] = None) -> 'MarketData':
        """Set volume data"""
        self._volume = volume
        if open_interest is not None:
            self._open_interest = open_interest
        self.mark_updated()
        return self
    
    def set_market_depth(self, bid: Decimal, ask: Decimal) -> 'MarketData':
        """Set market depth (bid/ask)"""
        self._bid = bid
        self._ask = ask
        self.mark_updated()
        return self
    
    def set_additional_data(
        self,
        vwap: Optional[Decimal] = None,
        turnover: Optional[Decimal] = None,
        trades_count: Optional[int] = None,
        previous_close: Optional[Decimal] = None
    ) -> 'MarketData':
        """Set additional market data"""
        if vwap is not None:
            self._vwap = vwap
        if turnover is not None:
            self._turnover = turnover
        if trades_count is not None:
            self._trades_count = trades_count
        if previous_close is not None:
            self._previous_close = previous_close
        self.mark_updated()
        return self
    
    def merge_with(self, other: 'MarketData') -> 'MarketData':
        """Merge with another market data (for aggregation)"""
        if self._symbol != other._symbol:
            raise ValueError("Cannot merge data from different symbols")
        
        # For aggregation, we need to recalculate OHLC
        new_data = MarketData(
            symbol=self._symbol,
            timestamp=max(self._timestamp, other._timestamp),
            interval=self._interval
        )
        
        # Calculate aggregated OHLC
        if all([self._open, other._open, self._high, other._high, 
                self._low, other._low, self._close, other._close]):
            new_data.set_ohlc(
                open=self._open if self._timestamp < other._timestamp else other._open,
                high=max(self._high, other._high),
                low=min(self._low, other._low),
                close=other._close if other._timestamp > self._timestamp else self._close
            )
        
        # Aggregate volume
        if self._volume and other._volume:
            new_data._volume = self._volume + other._volume
        
        return new_data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert market data to dictionary"""
        return {
            'id': self.id,
            'symbol': self._symbol,
            'timestamp': self._timestamp.isoformat() if self._timestamp else None,
            'interval': self._interval.value if self._interval else None,
            'open': float(self._open) if self._open else None,
            'high': float(self._high) if self._high else None,
            'low': float(self._low) if self._low else None,
            'close': float(self._close) if self._close else None,
            'volume': self._volume,
            'open_interest': self._open_interest,
            'bid': float(self._bid) if self._bid else None,
            'ask': float(self._ask) if self._ask else None,
            'vwap': float(self._vwap) if self._vwap else None,
            'change': float(self.change) if self.change else None,
            'change_percentage': float(self.change_percentage) if self.change_percentage else None,
            'typical_price': float(self.typical_price) if self.typical_price else None,
            'is_bullish': self.is_bullish_candle,
            'is_bearish': self.is_bearish_candle,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Quote(Entity):
    """Real-time quote data"""
    
    def __init__(
        self,
        id: Optional[str] = None,
        symbol: str = None,
        timestamp: datetime = None
    ):
        super().__init__(id)
        self._symbol = symbol
        self._timestamp = timestamp
        
        # Price data
        self._last_price: Optional[Decimal] = None
        self._bid: Optional[Decimal] = None
        self._ask: Optional[Decimal] = None
        self._bid_size: Optional[int] = None
        self._ask_size: Optional[int] = None
        
        # Day statistics
        self._open: Optional[Decimal] = None
        self._high: Optional[Decimal] = None
        self._low: Optional[Decimal] = None
        self._close: Optional[Decimal] = None
        self._previous_close: Optional[Decimal] = None
        
        # Volume statistics
        self._volume: Optional[int] = None
        self._average_volume: Optional[int] = None
        self._open_interest: Optional[int] = None
    
    @property
    def symbol(self) -> str:
        return self._symbol
    
    @property
    def last_price(self) -> Optional[Decimal]:
        return self._last_price
    
    @property
    def bid(self) -> Optional[Decimal]:
        return self._bid
    
    @property
    def ask(self) -> Optional[Decimal]:
        return self._ask
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread"""
        if self._bid and self._ask:
            return self._ask - self._bid
        return None
    
    @property
    def spread_percentage(self) -> Optional[Decimal]:
        """Calculate bid-ask spread as percentage"""
        if self._bid and self._ask and self._last_price and self._last_price > 0:
            return (self.spread / self._last_price) * 100
        return None
    
    def update_quote(
        self,
        last_price: Decimal,
        bid: Optional[Decimal] = None,
        ask: Optional[Decimal] = None,
        bid_size: Optional[int] = None,
        ask_size: Optional[int] = None,
        volume: Optional[int] = None
    ) -> 'Quote':
        """Update quote data"""
        self._last_price = last_price
        self._timestamp = datetime.utcnow()
        
        if bid is not None:
            self._bid = bid
        if ask is not None:
            self._ask = ask
        if bid_size is not None:
            self._bid_size = bid_size
        if ask_size is not None:
            self._ask_size = ask_size
        if volume is not None:
            self._volume = volume
        
        self.mark_updated()
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert quote to dictionary"""
        return {
            'id': self.id,
            'symbol': self._symbol,
            'timestamp': self._timestamp.isoformat() if self._timestamp else None,
            'last_price': float(self._last_price) if self._last_price else None,
            'bid': float(self._bid) if self._bid else None,
            'ask': float(self._ask) if self._ask else None,
            'bid_size': self._bid_size,
            'ask_size': self._ask_size,
            'spread': float(self.spread) if self.spread else None,
            'spread_percentage': float(self.spread_percentage) if self.spread_percentage else None,
            'volume': self._volume,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }