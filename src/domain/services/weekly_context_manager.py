"""
Weekly Context Manager
Manages weekly zones, bias calculation, and context for signal evaluation
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import pandas as pd
import pytz

from ..value_objects.signal_types import (
    WeeklyZones, WeeklyBias, WeeklyContext, BarData, TradeDirection
)
from ...infrastructure.database.models import NiftyIndexData
from ...utils.timezone_utils import (
    utc_to_ist, ist_to_utc, get_market_open_utc, 
    is_market_hours_utc, format_ist_time
)


logger = logging.getLogger(__name__)


class WeeklyContextManager:
    """Manages weekly context for signal evaluation"""
    
    def __init__(self):
        self.current_context: Optional[WeeklyContext] = None
        self.current_week_start: Optional[datetime] = None
    
    def get_week_start(self, date: datetime) -> datetime:
        """Get Sunday 9:15 AM IST for the week containing the date (matching TradingView/SP logic)"""
        # Get current day of week (Monday=0, Sunday=6)
        current_weekday = date.weekday()
        
        # Calculate days to subtract to get to previous Sunday
        # If Sunday (6), days_to_subtract = 0
        # If Monday (0), days_to_subtract = 1
        # If Tuesday (1), days_to_subtract = 2, etc.
        days_to_subtract = (current_weekday + 1) % 7
        
        # Get Sunday of current week
        sunday = date - timedelta(days=days_to_subtract)
        
        # Return Sunday 9:15 AM IST
        return sunday.replace(hour=9, minute=15, second=0, microsecond=0)
    
    def is_new_week(self, timestamp: datetime) -> bool:
        """Check if timestamp is in a new week"""
        week_start = self.get_week_start(timestamp)
        return self.current_week_start != week_start
    
    def calculate_weekly_zones(self, prev_week_data: List[NiftyIndexData]) -> WeeklyZones:
        """
        Calculate support and resistance zones from previous week data
        
        Args:
            prev_week_data: Previous week's hourly data
            
        Returns:
            WeeklyZones object
        """
        if not prev_week_data:
            raise ValueError("No previous week data available")
        
        # Convert to pandas for easier calculation
        df = pd.DataFrame([{
            'timestamp': d.timestamp,
            'open': float(d.open),
            'high': float(d.high),
            'low': float(d.low),
            'close': float(d.close)
        } for d in prev_week_data])
        
        # Previous week high/low/close
        prev_week_high = df['high'].max()
        prev_week_low = df['low'].min()
        prev_week_close = df['close'].iloc[-1]
        
        # Calculate 4-hour body extremes
        # Since we have hourly data from 5-min aggregation, 
        # we need to group into 4-hour blocks
        
        # Create 4-hour groups (0-3, 4-7, 8-11, 12-15, 16-19, 20-23)
        df['4h_group'] = (df['timestamp'].dt.hour // 4) * 4
        df['date'] = df['timestamp'].dt.date
        df['4h_key'] = df['date'].astype(str) + '_' + df['4h_group'].astype(str)
        
        # For each 4-hour group, find the body extremes
        four_hour_bodies = []
        for group_key, group_df in df.groupby('4h_key'):
            if len(group_df) > 0:
                # Get OHLC for this 4-hour period
                group_open = group_df.iloc[0]['open']
                group_close = group_df.iloc[-1]['close']
                
                # Body top and bottom for this 4-hour candle
                body_top = max(group_open, group_close)
                body_bottom = min(group_open, group_close)
                
                four_hour_bodies.append({
                    'body_top': body_top,
                    'body_bottom': body_bottom
                })
        
        # Get max/min body levels across all 4-hour candles
        if four_hour_bodies:
            prev_max_4h_body = max(b['body_top'] for b in four_hour_bodies)
            prev_min_4h_body = min(b['body_bottom'] for b in four_hour_bodies)
        else:
            # Fallback to hourly data if grouping fails
            df['body_top'] = df[['open', 'close']].max(axis=1)
            df['body_bottom'] = df[['open', 'close']].min(axis=1)
            prev_max_4h_body = df['body_top'].max()
            prev_min_4h_body = df['body_bottom'].min()
        
        # Calculate zones
        zones = WeeklyZones(
            upper_zone_top=max(prev_week_high, prev_max_4h_body),
            upper_zone_bottom=min(prev_week_high, prev_max_4h_body),
            lower_zone_top=max(prev_week_low, prev_min_4h_body),
            lower_zone_bottom=min(prev_week_low, prev_min_4h_body),
            prev_week_high=prev_week_high,
            prev_week_low=prev_week_low,
            prev_week_close=prev_week_close,
            prev_max_4h_body=prev_max_4h_body,
            prev_min_4h_body=prev_min_4h_body,
            calculation_time=datetime.now()
        )
        
        logger.info(f"Calculated weekly zones - Upper: {zones.upper_zone_bottom:.2f}-{zones.upper_zone_top:.2f}, "
                   f"Lower: {zones.lower_zone_bottom:.2f}-{zones.lower_zone_top:.2f}")
        
        return zones
    
    def calculate_weekly_bias(self, zones: WeeklyZones, current_price: float) -> WeeklyBias:
        """
        Calculate weekly market bias based on zones and current price
        
        Args:
            zones: Weekly support/resistance zones
            current_price: Current market price
            
        Returns:
            WeeklyBias object
        """
        # Calculate distances according to signal logic
        # Distance from previous week close to 4H bodies
        distance_to_resistance = abs(zones.prev_week_close - zones.prev_max_4h_body)
        distance_to_support = abs(zones.prev_week_close - zones.prev_min_4h_body)
        
        # Determine bias based on which is closer
        if distance_to_support < distance_to_resistance:
            # Closer to support - BULLISH
            bias = TradeDirection.BULLISH
            strength = 1.0
            description = "Bullish - Closer to support"
        elif distance_to_resistance < distance_to_support:
            # Closer to resistance - BEARISH
            bias = TradeDirection.BEARISH
            strength = 1.0
            description = "Bearish - Closer to resistance"
        else:
            # Equal distance - NEUTRAL
            bias = TradeDirection.NEUTRAL
            strength = 0.0
            description = "Neutral - Equal distance"
        
        weekly_bias = WeeklyBias(
            bias=bias,
            distance_to_resistance=distance_to_resistance,
            distance_to_support=distance_to_support,
            strength=strength,
            description=description
        )
        
        logger.info(f"Calculated weekly bias: {description} (dist to resistance: {distance_to_resistance:.2f}, dist to support: {distance_to_support:.2f})")
        
        return weekly_bias
    
    def update_context(self, current_bar: BarData, prev_week_data: List[NiftyIndexData]) -> WeeklyContext:
        """
        Update weekly context with new bar
        
        Args:
            current_bar: Current hourly bar
            prev_week_data: Previous week's data for zone calculation
            
        Returns:
            Updated WeeklyContext
        """
        # Check if new week
        if self.is_new_week(current_bar.timestamp) or self.current_context is None:
            # Calculate new zones and bias
            zones = self.calculate_weekly_zones(prev_week_data)
            bias = self.calculate_weekly_bias(zones, current_bar.close)
            
            # Create new context or reset existing
            if self.current_context is None:
                self.current_context = WeeklyContext(zones=zones, bias=bias)
            else:
                self.current_context.reset_for_new_week(zones, bias)
            
            self.current_week_start = self.get_week_start(current_bar.timestamp)
            logger.info(f"Started new week context at {self.current_week_start}")
        
        # Update context with current bar
        self.current_context.update_weekly_stats(current_bar)
        
        # Set first hour bar if not set
        if self.current_context.first_hour_bar is None:
            # Set the first bar of the week as the first hour bar
            # This handles cases where Monday data might be missing
            if len(self.current_context.weekly_bars) == 1:
                # This is the first bar we've seen this week
                self.current_context.first_hour_bar = current_bar
                logger.info(f"Set first hour bar: O={current_bar.open} H={current_bar.high} L={current_bar.low} C={current_bar.close} at {current_bar.timestamp}")
        
        return self.current_context
    
    def get_previous_week_data(
        self, 
        current_date: datetime,
        nifty_data: List[NiftyIndexData]
    ) -> List[NiftyIndexData]:
        """
        Get previous week's data from the dataset
        
        Args:
            current_date: Current date
            nifty_data: Full dataset of NIFTY data
            
        Returns:
            List of previous week's data
        """
        # Get current week start
        current_week_start = self.get_week_start(current_date)
        
        # Previous week is 7 days before
        prev_week_start = current_week_start - timedelta(days=7)
        # Previous week ends on Friday 15:30
        # With Sunday as week start, Friday is 5 days later
        friday = prev_week_start + timedelta(days=5)  # Sunday + 5 = Friday
        prev_week_end = friday.replace(hour=15, minute=30, second=0)
        
        # Filter data for previous week
        prev_week_data = [
            d for d in nifty_data
            if prev_week_start <= d.timestamp <= prev_week_end
        ]
        
        return prev_week_data
    
    def create_bar_from_nifty_data(self, data: NiftyIndexData) -> BarData:
        """Convert NiftyIndexData to BarData"""
        return BarData(
            timestamp=data.timestamp,
            open=float(data.open),
            high=float(data.high),
            low=float(data.low),
            close=float(data.close),
            volume=data.volume
        )
    
    def is_market_hours(self, timestamp: datetime) -> bool:
        """Check if timestamp is during market hours (IST)"""
        # Market hours: Monday-Friday, 9:15 AM - 3:30 PM IST
        if timestamp.weekday() >= 5:  # Saturday or Sunday
            return False
        
        time = timestamp.time()
        market_open = datetime.strptime("09:15", "%H:%M").time()
        market_close = datetime.strptime("15:30", "%H:%M").time()
        
        return market_open <= time <= market_close
    
    def get_next_expiry(self, date: datetime) -> datetime:
        """Get next Thursday expiry from given date"""
        # NIFTY weekly expiry is on Thursday
        days_ahead = 3 - date.weekday()  # Thursday is 3
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        expiry = date + timedelta(days=days_ahead)
        return expiry.replace(hour=15, minute=30, second=0, microsecond=0)
    
    def get_expiry_for_week(self, week_start: datetime) -> datetime:
        """Get expiry date for a given week (Thursday 3:30 PM)"""
        # Week starts on Sunday, expiry is on Thursday
        expiry = week_start + timedelta(days=4)  # Sunday + 4 = Thursday
        return expiry.replace(hour=15, minute=30, second=0, microsecond=0)