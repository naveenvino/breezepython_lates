"""
Signal Types and Related Value Objects
Defines the 8 trading signals and related data structures
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum
from decimal import Decimal


class SignalType(Enum):
    """8 Trading signals from TradingView strategy"""
    S1 = "S1"  # Bear Trap (Bullish)
    S2 = "S2"  # Support Hold (Bullish) 
    S3 = "S3"  # Resistance Hold (Bearish)
    S4 = "S4"  # Bias Failure Bull (Bullish)
    S5 = "S5"  # Bias Failure Bear (Bearish)
    S6 = "S6"  # Weakness Confirmed (Bearish)
    S7 = "S7"  # Breakout Confirmed (Bullish)
    S8 = "S8"  # Breakdown Confirmed (Bearish)
    
    @property
    def is_bullish(self) -> bool:
        """Check if signal is bullish"""
        return self in [SignalType.S1, SignalType.S2, SignalType.S4, SignalType.S7]
    
    @property
    def option_type(self) -> str:
        """Get option type to sell for this signal"""
        return "PE" if self.is_bullish else "CE"


class TradeDirection(Enum):
    """Trade direction based on market bias"""
    BULLISH = 1
    BEARISH = -1
    NEUTRAL = 0


@dataclass
class WeeklyZones:
    """Weekly support and resistance zones"""
    # Resistance Zone
    upper_zone_top: float      # max(prevWeekHigh, prevMax4hBody)
    upper_zone_bottom: float   # min(prevWeekHigh, prevMax4hBody)
    
    # Support Zone
    lower_zone_top: float      # max(prevWeekLow, prevMin4hBody)
    lower_zone_bottom: float   # min(prevWeekLow, prevMin4hBody)
    
    # Margins for proximity checks (calculated dynamically)
    margin_high: float = 0.0
    margin_low: float = 0.0
    
    # Week data used for calculation
    prev_week_high: float = 0
    prev_week_low: float = 0
    prev_week_close: float = 0
    prev_max_4h_body: float = 0
    prev_min_4h_body: float = 0
    
    # Timestamp when zones were calculated
    calculation_time: Optional[datetime] = None
    
    def __post_init__(self):
        """Calculate margins after initialization"""
        # According to API guide:
        # marginHigh = max((upperZTop - upperZBottom) * 3, minTick * 5)
        # marginLow = max((lowerZTop - lowerZBottom) * 3, minTick * 5)
        min_tick = 0.05  # NIFTY minimum tick size
        
        upper_zone_range = self.upper_zone_top - self.upper_zone_bottom
        lower_zone_range = self.lower_zone_top - self.lower_zone_bottom
        
        self.margin_high = max(upper_zone_range * 3, min_tick * 5)
        self.margin_low = max(lower_zone_range * 3, min_tick * 5)
    
    def is_near_upper_zone(self, price: float) -> bool:
        """Check if price is near upper zone"""
        return abs(price - self.upper_zone_bottom) <= self.margin_high
    
    def is_near_lower_zone(self, price: float) -> bool:
        """Check if price is near lower zone"""
        return abs(price - self.lower_zone_bottom) <= self.margin_low


@dataclass
class WeeklyBias:
    """Weekly market bias calculation"""
    bias: TradeDirection
    distance_to_resistance: float
    distance_to_support: float
    strength: float = 0.0  # 0-1 strength indicator
    description: str = ""
    
    @property
    def is_bullish(self) -> bool:
        return self.bias == TradeDirection.BULLISH
    
    @property
    def is_bearish(self) -> bool:
        return self.bias == TradeDirection.BEARISH


@dataclass
class BarData:
    """OHLC data for a single bar"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    
    @property
    def body_top(self) -> float:
        """Top of candle body"""
        return max(self.open, self.close)
    
    @property
    def body_bottom(self) -> float:
        """Bottom of candle body"""
        return min(self.open, self.close)
    
    @property
    def range(self) -> float:
        """Candle range (high - low)"""
        return self.high - self.low
    
    @property
    def body_range(self) -> float:
        """Body range (open - close)"""
        return abs(self.open - self.close)
    
    @property
    def is_bullish(self) -> bool:
        """Check if candle is bullish"""
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        """Check if candle is bearish"""
        return self.close < self.open


@dataclass
class WeeklyContext:
    """Context for weekly signal evaluation"""
    # Current week zones and bias
    zones: WeeklyZones
    bias: WeeklyBias
    
    # First hour bar of the week
    first_hour_bar: Optional[BarData] = None
    
    # Tracking for signals
    signal_triggered_this_week: bool = False
    triggered_signal: Optional[SignalType] = None
    triggered_at: Optional[datetime] = None
    
    # State tracking for complex signals
    has_touched_upper_zone_this_week: bool = False
    has_touched_lower_zone_this_week: bool = False
    s4_breakout_candle_high: Optional[float] = None
    s8_breakdown_candle_low: Optional[float] = None
    
    # Running statistics for the week
    weekly_bars: List[BarData] = None
    weekly_max_high: float = 0.0
    weekly_min_low: float = float('inf')
    weekly_max_close: float = 0.0
    weekly_min_close: float = float('inf')
    
    def __post_init__(self):
        if self.weekly_bars is None:
            self.weekly_bars = []
    
    def update_weekly_stats(self, bar: BarData):
        """Update running statistics with new bar"""
        self.weekly_bars.append(bar)
        self.weekly_max_high = max(self.weekly_max_high, bar.high)
        self.weekly_min_low = min(self.weekly_min_low, bar.low)
        self.weekly_max_close = max(self.weekly_max_close, bar.close)
        self.weekly_min_close = min(self.weekly_min_close, bar.close)
        
        # Track zone touches
        if bar.high >= self.zones.upper_zone_bottom:
            self.has_touched_upper_zone_this_week = True
        if bar.low <= self.zones.lower_zone_top:
            self.has_touched_lower_zone_this_week = True
    
    def reset_for_new_week(self, new_zones: WeeklyZones, new_bias: WeeklyBias):
        """Reset context for a new week"""
        self.zones = new_zones
        self.bias = new_bias
        self.first_hour_bar = None
        self.signal_triggered_this_week = False
        self.triggered_signal = None
        self.triggered_at = None
        self.has_touched_upper_zone_this_week = False
        self.has_touched_lower_zone_this_week = False
        self.s4_breakout_candle_high = None
        self.s8_breakdown_candle_low = None
        self.weekly_bars = []
        self.weekly_max_high = 0.0
        self.weekly_min_low = float('inf')
        self.weekly_max_close = 0.0
        self.weekly_min_close = float('inf')


@dataclass
class SignalResult:
    """Result of signal evaluation"""
    is_triggered: bool
    signal_type: Optional[SignalType] = None
    option_type: Optional[str] = None  # CE or PE
    strike_price: Optional[float] = None
    stop_loss: Optional[float] = None
    direction: Optional[TradeDirection] = None
    entry_time: Optional[datetime] = None
    entry_price: Optional[float] = None
    confidence: float = 0.0
    reason: str = ""
    
    @classmethod
    def no_signal(cls):
        """Factory method for no signal"""
        return cls(is_triggered=False, reason="No signal conditions met")
    
    @classmethod
    def from_signal(
        cls,
        signal_type: SignalType,
        stop_loss: float,
        entry_time: datetime,
        entry_price: float,
        direction: Optional[TradeDirection] = None,
        confidence: float = 0.8
    ):
        """Create signal result from signal type"""
        # Use provided direction or infer from signal type
        if direction is None:
            direction = TradeDirection.BULLISH if signal_type.is_bullish else TradeDirection.BEARISH
            
        return cls(
            is_triggered=True,
            signal_type=signal_type,
            option_type=signal_type.option_type,
            # Round to nearest 50 with directional bias
            # Bullish (PE): round down, Bearish (CE): round up
            strike_price=(int(stop_loss / 50) * 50) if signal_type.is_bullish else (int((stop_loss + 49) / 50) * 50),
            stop_loss=stop_loss,
            direction=direction,
            entry_time=entry_time,
            entry_price=entry_price,
            confidence=confidence,
            reason=f"{signal_type.value} signal triggered"
        )