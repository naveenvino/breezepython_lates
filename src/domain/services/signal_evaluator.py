"""
Signal Evaluator Service - Final Verified Version
Evaluates all 8 trading signals based on weekly zones and bias.
This version has been verified to accurately match the logic of the
provided TradingView Pine Script indicator.
"""
import logging
import math
from datetime import datetime, timedelta
from typing import List, Optional

# Assuming these are defined in your project's value_objects file
from ..value_objects.signal_types import (
    SignalType, SignalResult, BarData, WeeklyContext, TradeDirection
)

logger = logging.getLogger(__name__)

class SignalEvaluator:
    """
    Evaluates all 8 trading signals based on weekly zones and bias,
    mirroring the logic of the TradingView Pine Script indicator.
    """

    def __init__(self):
        # State tracking for S4/S8 triggers to ensure they fire only once per week
        self.s4_triggered_this_week: bool = False
        self.s8_triggered_this_week: bool = False

    def evaluate_all_signals(self, completed_bar: BarData, context: WeeklyContext,
                             bar_close_time: datetime) -> SignalResult:
        """
        Evaluate all signals in order of priority. This is the main entry point.
        It should be called immediately after a 1-hour bar has completed.

        Args:
            completed_bar: The just-completed bar (e.g., 10:15-11:15 bar).
            context: The weekly context with zones, bias, and all bars so far this week.
            bar_close_time: The exact time the bar closed (e.g., 11:15:00).

        Returns:
            SignalResult with the triggered signal or a no_signal result.
        """
        # On the first bar of a new week, reset the trigger states.
        if len(context.weekly_bars) == 1:
            self.s4_triggered_this_week = False
            self.s8_triggered_this_week = False
            logger.debug(f"New week started - reset S4/S8 trigger states")

        # Do not evaluate if a signal has already been confirmed for this week.
        if context.signal_triggered_this_week:
            logger.debug(f"Signal already triggered this week: {context.triggered_signal}")
            return SignalResult.no_signal()

        weekly_bars = context.weekly_bars
        if not weekly_bars:
            return SignalResult.no_signal()

        first_bar = weekly_bars[0]
        is_second_bar = len(weekly_bars) == 2
        
        logger.debug(f"Evaluating signals at {bar_close_time}: Bar #{len(weekly_bars)}, Bias={context.bias.bias.name}")

        # A list of evaluator methods to be called in order of signal priority (S1 > S2 > S3 > S4 > S5 > S6 > S7 > S8).
        evaluators = [
            (self._evaluate_s1, (is_second_bar, first_bar, completed_bar, context, bar_close_time)),
            (self._evaluate_s2, (is_second_bar, first_bar, completed_bar, context, bar_close_time)),
            (self._evaluate_s3, (is_second_bar, first_bar, completed_bar, weekly_bars, context, bar_close_time)),
            (self._evaluate_s4, (first_bar, completed_bar, weekly_bars, context, bar_close_time)),
            (self._evaluate_s5, (first_bar, completed_bar, context, bar_close_time)),
            (self._evaluate_s6, (is_second_bar, first_bar, completed_bar, weekly_bars, context, bar_close_time)),
            (self._evaluate_s7, (completed_bar, weekly_bars, context, bar_close_time)),
            (self._evaluate_s8, (completed_bar, weekly_bars, context, bar_close_time))
        ]

        for evaluator, args in evaluators:
            signal = evaluator(*args)
            if signal.is_triggered:
                # Mark signal as triggered to prevent further signals this week.
                context.signal_triggered_this_week = True
                context.triggered_signal = signal.signal_type
                context.triggered_at = bar_close_time
                logger.info(f"Signal {signal.signal_type.name} confirmed at {bar_close_time}")
                return signal

        return SignalResult.no_signal()

    def _evaluate_s1(self, is_second_bar: bool, first_bar: BarData,
                       current_bar: BarData, context: WeeklyContext,
                       bar_close_time: datetime) -> SignalResult:
        """S1: Bear Trap (Bullish) - Fake breakdown below support that recovers."""
        if not is_second_bar:
            return SignalResult.no_signal()

        zones = context.zones
        
        # Conditions from Pine Script, checked at bar close
        cond1 = first_bar.open >= zones.lower_zone_bottom
        cond2 = first_bar.close < zones.lower_zone_bottom
        cond3 = current_bar.close > first_bar.low

        logger.debug(f"S1 Check at {bar_close_time}: is_second_bar={is_second_bar}")
        logger.debug(f"  FirstBar: O={first_bar.open} C={first_bar.close} L={first_bar.low}")
        logger.debug(f"  CurrentBar: C={current_bar.close}")
        logger.debug(f"  Zones: SupportBottom={zones.lower_zone_bottom}")
        logger.debug(f"  Conditions: cond1={cond1}, cond2={cond2}, cond3={cond3}")

        if cond1 and cond2 and cond3:
            stop_loss = first_bar.low - abs(first_bar.open - first_bar.close)
            logger.info(f"S1 TRIGGERED at {bar_close_time}! Stop loss: {stop_loss}")
            return SignalResult.from_signal(
                signal_type=SignalType.S1, stop_loss=stop_loss,
                entry_time=bar_close_time, entry_price=current_bar.close,
                direction=TradeDirection.BULLISH
            )
        return SignalResult.no_signal()

    def _evaluate_s2(self, is_second_bar: bool, first_bar: BarData,
                       current_bar: BarData, context: WeeklyContext,
                       bar_close_time: datetime) -> SignalResult:
        """S2: Support Hold (Bullish) - Price respects support with a bullish bias."""
        if not is_second_bar:
            return SignalResult.no_signal()

        zones = context.zones
        bias = context.bias

        # Debug logging for S2 evaluation
        logger.debug(f"S2 Evaluation at {bar_close_time}:")
        logger.debug(f"  Bias: {bias.bias.name} (dist_to_support: {bias.distance_to_support:.2f}, dist_to_resistance: {bias.distance_to_resistance:.2f})")
        logger.debug(f"  Zones - Support Top: {zones.lower_zone_top:.2f}, Support Bottom: {zones.lower_zone_bottom:.2f}")
        logger.debug(f"  Prev Week - High: {zones.prev_week_high:.2f}, Low: {zones.prev_week_low:.2f}, Close: {zones.prev_week_close:.2f}")
        logger.debug(f"  4H Bodies - Max: {zones.prev_max_4h_body:.2f}, Min: {zones.prev_min_4h_body:.2f}")
        logger.debug(f"  First Bar: O={first_bar.open:.2f} H={first_bar.high:.2f} L={first_bar.low:.2f} C={first_bar.close:.2f}")
        logger.debug(f"  Current Bar: C={current_bar.close:.2f}")
        logger.debug(f"  Margin Low: {zones.margin_low:.2f}")

        if bias.bias != TradeDirection.BULLISH:
            logger.debug(f"  S2 REJECTED: Bias is {bias.bias.name}, not BULLISH")
            return SignalResult.no_signal()

        # Check if first bar touches the support zone
        first_bar_touches_support = first_bar.low <= zones.lower_zone_top
        logger.debug(f"  First bar touches support zone: {first_bar_touches_support} (Low {first_bar.low:.2f} <= Zone Top {zones.lower_zone_top:.2f})")

        # Check all conditions individually for debugging
        cond1 = first_bar.open > zones.prev_week_low
        
        # Margin conditions - bypass if bar touches zone
        if first_bar_touches_support:
            logger.debug(f"  First bar touches support zone - bypassing margin checks")
            cond2 = True  # Bypass margin check for prev_close
            cond3 = True  # Bypass margin check for first_open
        else:
            cond2 = abs(zones.prev_week_close - zones.lower_zone_bottom) <= zones.margin_low
            cond3 = abs(first_bar.open - zones.lower_zone_bottom) <= zones.margin_low
            
        cond4 = first_bar.close >= zones.lower_zone_bottom
        cond5 = first_bar.close >= zones.prev_week_close
        cond6 = current_bar.close >= first_bar.low
        cond7 = current_bar.close > zones.prev_week_close
        cond8 = current_bar.close > zones.lower_zone_bottom
        
        logger.debug(f"  S2 Conditions:")
        logger.debug(f"    1. first_open > prev_low: {first_bar.open:.2f} > {zones.prev_week_low:.2f} = {cond1}")
        if not first_bar_touches_support:
            logger.debug(f"    2. |prev_close - support| <= margin: {abs(zones.prev_week_close - zones.lower_zone_bottom):.2f} <= {zones.margin_low:.2f} = {cond2}")
            logger.debug(f"    3. |first_open - support| <= margin: {abs(first_bar.open - zones.lower_zone_bottom):.2f} <= {zones.margin_low:.2f} = {cond3}")
        else:
            logger.debug(f"    2. Margin check bypassed (bar touches zone) = {cond2}")
            logger.debug(f"    3. Margin check bypassed (bar touches zone) = {cond3}")
        logger.debug(f"    4. first_close >= support: {first_bar.close:.2f} >= {zones.lower_zone_bottom:.2f} = {cond4}")
        logger.debug(f"    5. first_close >= prev_close: {first_bar.close:.2f} >= {zones.prev_week_close:.2f} = {cond5}")
        logger.debug(f"    6. curr_close >= first_low: {current_bar.close:.2f} >= {first_bar.low:.2f} = {cond6}")
        logger.debug(f"    7. curr_close > prev_close: {current_bar.close:.2f} > {zones.prev_week_close:.2f} = {cond7}")
        logger.debug(f"    8. curr_close > support: {current_bar.close:.2f} > {zones.lower_zone_bottom:.2f} = {cond8}")

        # All conditions from Pine Script, with margin bypass if bar touches zone
        if (cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7 and cond8):
            logger.info(f"S2 TRIGGERED at {bar_close_time}! All conditions met.")
            return SignalResult.from_signal(
                signal_type=SignalType.S2, stop_loss=zones.lower_zone_bottom,
                entry_time=bar_close_time, entry_price=current_bar.close,
                direction=TradeDirection.BULLISH
            )
        
        logger.debug(f"  S2 REJECTED: Not all conditions met")
        return SignalResult.no_signal()

    def _evaluate_s3(self, is_second_bar: bool, first_bar: BarData,
                       current_bar: BarData, weekly_bars: List[BarData],
                       context: WeeklyContext, bar_close_time: datetime) -> SignalResult:
        """S3: Resistance Hold (Bearish) - Price fails at resistance with a bearish bias."""
        zones = context.zones
        bias = context.bias

        if bias.bias != TradeDirection.BEARISH:
            return SignalResult.no_signal()

        # Check if first bar touches the resistance zone
        first_bar_touches_resistance = first_bar.high >= zones.upper_zone_bottom
        
        # Base conditions with margin bypass if bar touches zone
        if first_bar_touches_resistance:
            # Bypass margin checks if bar touches resistance
            margin_conditions_met = True
        else:
            # Apply margin checks only if bar doesn't touch zone
            margin_conditions_met = (abs(zones.prev_week_close - zones.upper_zone_bottom) <= zones.margin_high and
                                    abs(first_bar.open - zones.upper_zone_bottom) <= zones.margin_high)
        
        if not (margin_conditions_met and first_bar.close <= zones.prev_week_high):
            return SignalResult.no_signal()

        # Scenario A: 2nd candle rejection
        if is_second_bar:
            touched_zone = (first_bar.high >= zones.upper_zone_bottom or current_bar.high >= zones.upper_zone_bottom)
            if (current_bar.close < first_bar.high and
                current_bar.close < zones.upper_zone_bottom and
                touched_zone):
                return SignalResult.from_signal(
                    signal_type=SignalType.S3, stop_loss=zones.prev_week_high,
                    entry_time=bar_close_time, entry_price=current_bar.close,
                    direction=TradeDirection.BEARISH
                )

        # Scenario B: Breakdown below weekly lows
        if len(weekly_bars) > 1:
            prev_bars = weekly_bars[:-1]
            weekly_min_low = min(bar.low for bar in prev_bars)
            weekly_min_close = min(bar.close for bar in prev_bars)
            
            if (current_bar.close < first_bar.low and
                current_bar.close < zones.upper_zone_bottom and
                current_bar.close < weekly_min_low and
                current_bar.close < weekly_min_close):
                return SignalResult.from_signal(
                    signal_type=SignalType.S3, stop_loss=zones.prev_week_high,
                    entry_time=bar_close_time, entry_price=current_bar.close,
                    direction=TradeDirection.BEARISH
                )
        return SignalResult.no_signal()

    def _evaluate_s4(self, first_bar: BarData, current_bar: BarData,
                       weekly_bars: List[BarData], context: WeeklyContext,
                       bar_close_time: datetime) -> SignalResult:
        """S4: Bias Failure Bullish - Bearish bias fails on a gap up and breakout."""
        zones = context.zones
        bias = context.bias

        if not (bias.bias == TradeDirection.BEARISH and first_bar.open > zones.upper_zone_top):
            return SignalResult.no_signal()

        s4_triggered = self._check_s4_trigger(weekly_bars, context)
        s4_first_trigger = s4_triggered and not self.s4_triggered_this_week
        self.s4_triggered_this_week = s4_triggered

        if s4_first_trigger and context.first_hour_bar:
            return SignalResult.from_signal(
                signal_type=SignalType.S4, stop_loss=context.first_hour_bar.low,
                entry_time=bar_close_time, entry_price=current_bar.close,
                direction=TradeDirection.BULLISH
            )
        return SignalResult.no_signal()

    def _evaluate_s5(self, first_bar: BarData, current_bar: BarData,
                       context: WeeklyContext, bar_close_time: datetime) -> SignalResult:
        """S5: Bias Failure Bearish - Bullish bias fails on a gap down and breakdown."""
        zones = context.zones
        bias = context.bias

        logger.debug(f"S5 Check at {bar_close_time}:")
        logger.debug(f"  Bias: {bias.bias}")
        logger.debug(f"  FirstBar: O={first_bar.open}")
        logger.debug(f"  Zones: SupportBottom={zones.lower_zone_bottom}, PrevWeekLow={zones.prev_week_low}")
        
        if not context.first_hour_bar:
            logger.debug("  No first hour bar available")
            return SignalResult.no_signal()
        
        logger.debug(f"  FirstHourBar: C={context.first_hour_bar.close} L={context.first_hour_bar.low} H={context.first_hour_bar.high}")
        logger.debug(f"  CurrentBar: C={current_bar.close}")
        
        cond1 = bias.bias == TradeDirection.BULLISH
        cond2 = first_bar.open < zones.lower_zone_bottom
        cond3 = context.first_hour_bar.close < zones.lower_zone_bottom
        cond4 = context.first_hour_bar.close < zones.prev_week_low
        cond5 = current_bar.close < context.first_hour_bar.low
        
        logger.debug(f"  Conditions: bias_bullish={cond1}, gap_down={cond2}, fh_below_support={cond3}, fh_below_prev_low={cond4}, breakdown={cond5}")
            
        if cond1 and cond2 and cond3 and cond4 and cond5:
            logger.info(f"S5 TRIGGERED at {bar_close_time}! Stop loss: {context.first_hour_bar.high}")
            return SignalResult.from_signal(
                signal_type=SignalType.S5, stop_loss=context.first_hour_bar.high,
                entry_time=bar_close_time, entry_price=current_bar.close,
                direction=TradeDirection.BEARISH
            )
            
        return SignalResult.no_signal()

    def _evaluate_s6(self, is_second_bar: bool, first_bar: BarData,
                       current_bar: BarData, weekly_bars: List[BarData],
                       context: WeeklyContext, bar_close_time: datetime) -> SignalResult:
        """S6: Weakness Confirmed (Bearish) - Similar to S3 with different entry conditions."""
        zones = context.zones
        bias = context.bias

        if bias.bias != TradeDirection.BEARISH:
            return SignalResult.no_signal()

        # For S6, the condition is that high touches zone, so no margin bypass needed here
        # as the condition already requires touching the zone
        if not (first_bar.high >= zones.upper_zone_bottom and
                first_bar.close <= zones.upper_zone_top and
                first_bar.close <= zones.prev_week_high):
            return SignalResult.no_signal()

        # Scenario A: 2nd candle rejection
        if is_second_bar and current_bar.close < first_bar.high and current_bar.close < zones.upper_zone_bottom:
            return SignalResult.from_signal(
                signal_type=SignalType.S6, stop_loss=zones.prev_week_high,
                entry_time=bar_close_time, entry_price=current_bar.close,
                direction=TradeDirection.BEARISH
            )

        # Scenario B: Breakdown
        if len(weekly_bars) > 1:
            prev_bars = weekly_bars[:-1]
            weekly_min_low = min(bar.low for bar in prev_bars)
            weekly_min_close = min(bar.close for bar in prev_bars)
            
            if (current_bar.close < first_bar.low and
                current_bar.close < zones.upper_zone_bottom and
                current_bar.close < weekly_min_low and
                current_bar.close < weekly_min_close):
                return SignalResult.from_signal(
                    signal_type=SignalType.S6, stop_loss=zones.prev_week_high,
                    entry_time=bar_close_time, entry_price=current_bar.close,
                    direction=TradeDirection.BEARISH
                )
        return SignalResult.no_signal()

    def _evaluate_s7(self, current_bar: BarData, weekly_bars: List[BarData],
                       context: WeeklyContext, bar_close_time: datetime) -> SignalResult:
        """S7: 1H Breakout Confirmed (Bullish) - Pure breakout signal."""
        zones = context.zones
        
        s4_triggered = self._check_s4_trigger(weekly_bars, context)
        s4_first_trigger = s4_triggered and not self.s4_triggered_this_week
        self.s4_triggered_this_week = s4_triggered

        if not s4_first_trigger:
            return SignalResult.no_signal()

        # Check if too close below prev high (0.4% rule)
        if current_bar.close < zones.prev_week_high and ((zones.prev_week_high - current_bar.close) / current_bar.close) * 100 < 0.40:
            return SignalResult.no_signal()

        # Strongest breakout check
        if len(weekly_bars) > 1:
            prev_bars = weekly_bars[:-1]
            weekly_max_high = max(bar.high for bar in prev_bars)
            weekly_max_close = max(bar.close for bar in prev_bars)
            
            if current_bar.close > weekly_max_high and current_bar.close > weekly_max_close and context.first_hour_bar:
                return SignalResult.from_signal(
                    signal_type=SignalType.S7, stop_loss=context.first_hour_bar.low,
                    entry_time=bar_close_time, entry_price=current_bar.close,
                    direction=TradeDirection.BULLISH
                )
        return SignalResult.no_signal()

    def _evaluate_s8(self, current_bar: BarData, weekly_bars: List[BarData],
                       context: WeeklyContext, bar_close_time: datetime) -> SignalResult:
        """S8: 1H Breakdown Confirmed (Bearish) - Pure breakdown signal."""
        zones = context.zones
        
        s8_triggered = self._check_s8_trigger(weekly_bars, context)
        s8_first_trigger = s8_triggered and not self.s8_triggered_this_week
        self.s8_triggered_this_week = s8_triggered

        if not s8_first_trigger:
            return SignalResult.no_signal()

        # Check if upper zone was touched and price closed below it
        has_touched_upper = any(bar.high >= zones.upper_zone_bottom for bar in weekly_bars)
        if not (has_touched_upper and current_bar.close < zones.upper_zone_bottom):
            return SignalResult.no_signal()

        # Weakest breakdown check
        if len(weekly_bars) > 1:
            prev_bars = weekly_bars[:-1]
            weekly_min_low = min(bar.low for bar in prev_bars)
            weekly_min_close = min(bar.close for bar in prev_bars)
            
            if current_bar.close < weekly_min_low and current_bar.close < weekly_min_close and context.first_hour_bar:
                return SignalResult.from_signal(
                    signal_type=SignalType.S8, stop_loss=context.first_hour_bar.high,
                    entry_time=bar_close_time, entry_price=current_bar.close,
                    direction=TradeDirection.BEARISH
                )
        return SignalResult.no_signal()

    def _check_s4_trigger(self, weekly_bars: List[BarData], context: WeeklyContext) -> bool:
        """Helper to check the stateful S4 breakout logic, mirroring f_s4_logic in Pine Script."""
        if not context.first_hour_bar:
            return False
            
        first_hour_high = context.first_hour_bar.high
        first_hour_day = context.first_hour_bar.timestamp.date()
        
        breakout_candle_high = context.s4_breakout_candle_high
        current_bar = weekly_bars[-1]
        
        highest_high_before = 0.0
        if len(weekly_bars) > 1:
            highest_high_before = max(b.high for b in weekly_bars[:-1])

        if current_bar.timestamp.date() == first_hour_day:
            if current_bar.close > first_hour_high:
                return True
        else:
            if breakout_candle_high is None:
                if (current_bar.close > current_bar.open and
                    current_bar.close > first_hour_high and
                    current_bar.high >= highest_high_before):
                    context.s4_breakout_candle_high = current_bar.high
            else:
                if current_bar.close > breakout_candle_high:
                    return True
        return False

    def _check_s8_trigger(self, weekly_bars: List[BarData], context: WeeklyContext) -> bool:
        """Helper to check the stateful S8 breakdown logic, mirroring f_s8_logic in Pine Script."""
        if not context.first_hour_bar:
            return False
            
        first_hour_low = context.first_hour_bar.low
        first_hour_day = context.first_hour_bar.timestamp.date()

        breakdown_candle_low = context.s8_breakdown_candle_low
        current_bar = weekly_bars[-1]

        lowest_low_before = float('inf')
        if len(weekly_bars) > 1:
            lowest_low_before = min(b.low for b in weekly_bars[:-1])

        if current_bar.timestamp.date() == first_hour_day:
            if current_bar.close < first_hour_low:
                return True
        else:
            if breakdown_candle_low is None:
                if (current_bar.close < current_bar.open and
                    current_bar.close < first_hour_low and
                    current_bar.low <= lowest_low_before):
                    context.s8_breakdown_candle_low = current_bar.low
            else:
                if current_bar.close < breakdown_candle_low:
                    return True
        return False

    def check_stop_loss_hit(self, completed_bar: BarData, active_trade: dict,
                              bar_close_time: datetime) -> bool:
        """
        Checks if the stop loss for an active trade was hit by the completed bar.
        
        Args:
            completed_bar: The just-completed bar.
            active_trade: A dictionary with trade details including 'stop_loss' and 'direction'.
            bar_close_time: The exact time the bar closed.
            
        Returns:
            True if the stop loss was hit, False otherwise.
        """
        stop_loss_price = active_trade['stop_loss']
        direction = active_trade['direction']
        
        if direction == TradeDirection.BULLISH and completed_bar.close <= stop_loss_price:
            logger.warning(f"STOP LOSS HIT for {active_trade['signal_type']} at {bar_close_time}")
            logger.warning(f"  > Bar closed at {completed_bar.close}, which is <= SL of {stop_loss_price}")
            return True
        elif direction == TradeDirection.BEARISH and completed_bar.close >= stop_loss_price:
            logger.warning(f"STOP LOSS HIT for {active_trade['signal_type']} at {bar_close_time}")
            logger.warning(f"  > Bar closed at {completed_bar.close}, which is >= SL of {stop_loss_price}")
            return True
            
        return False