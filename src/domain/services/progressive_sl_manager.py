"""
Progressive Stop-Loss Manager
Manages P&L-based progressive stop-loss for option positions
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SLStage(Enum):
    """Stop-loss progression stages"""
    INITIAL = "INITIAL"
    HALF = "HALF"
    BREAKEVEN = "BREAKEVEN"
    PROFIT_LOCK = "PROFIT_LOCK"


@dataclass
class PositionData:
    """Data for a single option position"""
    position_type: str  # MAIN or HEDGE
    strike_price: int
    option_type: str  # CE or PE
    entry_price: float
    quantity: int  # Negative for sold options


class ProgressiveSLManager:
    """
    Manages P&L-based progressive stop-loss for option positions.
    Tracks both index-based and P&L-based stop-losses.
    """
    
    def __init__(
        self,
        initial_sl_per_lot: float = 6000,
        lots: int = 10,
        profit_trigger_percent: float = 40,
        day2_sl_factor: float = 0.5,
        day4_profit_lock_percent: float = 5
    ):
        """
        Initialize the Progressive Stop-Loss Manager
        
        Args:
            initial_sl_per_lot: Initial stop-loss amount per lot (default 6000)
            lots: Number of lots being traded
            profit_trigger_percent: Profit percentage to trigger breakeven (default 40%)
            day2_sl_factor: Factor to reduce SL on day 2 (default 0.5 = 50%)
            day4_profit_lock_percent: Minimum profit to lock on day 4 (default 5%)
        """
        self.initial_sl_per_lot = initial_sl_per_lot
        self.lots = lots
        self.initial_sl_total = -abs(initial_sl_per_lot * lots)  # e.g., -60,000 for 10 lots
        self.current_sl = self.initial_sl_total
        self.sl_stage = SLStage.INITIAL
        
        # Configuration
        self.profit_trigger_percent = profit_trigger_percent
        self.day2_sl_factor = day2_sl_factor
        self.day4_profit_lock_percent = day4_profit_lock_percent
        
        # Tracking
        self.sl_history = []
        self.last_update_time = None
        self.max_profit_seen = 0
        
        logger.info(f"Initialized ProgressiveSLManager with initial SL: {self.initial_sl_total}")
    
    def calculate_position_pnl(
        self,
        positions: List[PositionData],
        current_prices: Dict[Tuple[int, str], float],
        commission_per_lot: float = 40
    ) -> float:
        """
        Calculate current P&L for all positions
        
        Args:
            positions: List of position data
            current_prices: Dict mapping (strike, option_type) to current price
            commission_per_lot: Commission per lot
            
        Returns:
            Net P&L after commissions
        """
        total_pnl = 0
        
        for position in positions:
            key = (position.strike_price, position.option_type)
            current_price = current_prices.get(key)
            
            if current_price is None:
                logger.warning(f"No price available for {position.strike_price} {position.option_type}")
                continue
            
            if position.position_type == "MAIN":
                # Main position (SOLD option) - profit when price decreases
                position_pnl = (position.entry_price - current_price) * abs(position.quantity)
            else:  # HEDGE
                # Hedge position (BOUGHT option) - profit when price increases
                position_pnl = (current_price - position.entry_price) * abs(position.quantity)
            
            total_pnl += position_pnl
            
            logger.debug(
                f"{position.position_type} {position.strike_price}{position.option_type}: "
                f"Entry={position.entry_price:.2f}, Current={current_price:.2f}, "
                f"PnL={position_pnl:.2f}"
            )
        
        # Subtract commissions (entry + potential exit)
        total_commission = commission_per_lot * self.lots * 2
        net_pnl = total_pnl - total_commission
        
        # Track maximum profit seen
        if net_pnl > self.max_profit_seen:
            self.max_profit_seen = net_pnl
        
        return net_pnl
    
    def calculate_max_profit_receivable(
        self,
        main_entry_price: float,
        hedge_entry_price: float,
        quantity: int,
        commission_per_lot: float = 40
    ) -> float:
        """
        Calculate maximum profit receivable from the position
        
        Args:
            main_entry_price: Entry price of main (sold) option
            hedge_entry_price: Entry price of hedge (bought) option
            quantity: Total quantity
            commission_per_lot: Commission per lot
            
        Returns:
            Maximum profit receivable
        """
        net_premium_received = (main_entry_price - hedge_entry_price) * abs(quantity)
        total_commission = commission_per_lot * self.lots * 2
        max_profit = net_premium_received - total_commission
        
        logger.info(f"Max profit receivable: {max_profit:.2f}")
        return max_profit
    
    def update_stop_loss(
        self,
        current_pnl: float,
        max_profit_receivable: float,
        days_elapsed: int,
        current_time: datetime
    ) -> Optional[str]:
        """
        Update stop-loss based on progressive rules
        
        Args:
            current_pnl: Current P&L of the position
            max_profit_receivable: Maximum possible profit
            days_elapsed: Trading days since entry
            current_time: Current timestamp
            
        Returns:
            Update reason if SL was updated, None otherwise
        """
        old_sl = self.current_sl
        old_stage = self.sl_stage
        update_reason = None
        
        # Rule 1: 40% profit trigger (can happen anytime)
        if current_pnl >= (max_profit_receivable * self.profit_trigger_percent / 100):
            if self.sl_stage not in [SLStage.BREAKEVEN, SLStage.PROFIT_LOCK]:
                self.current_sl = 0  # Move to breakeven
                self.sl_stage = SLStage.BREAKEVEN
                update_reason = f"{self.profit_trigger_percent}% Profit Trigger - Moved to Breakeven"
        
        # Time-based rules (only if not already triggered by profit)
        if update_reason is None:
            # Rule 2: Day 2 at 1 PM - Move to 50% of initial
            if days_elapsed == 2 and current_time.hour >= 13:
                if self.sl_stage == SLStage.INITIAL:
                    self.current_sl = self.initial_sl_total * self.day2_sl_factor
                    self.sl_stage = SLStage.HALF
                    update_reason = f"Day 2 @ 1PM - SL moved to {self.day2_sl_factor*100}%"
            
            # Rule 3: Day 3 - Move to breakeven
            elif days_elapsed == 3:
                if self.sl_stage in [SLStage.INITIAL, SLStage.HALF]:
                    self.current_sl = 0
                    self.sl_stage = SLStage.BREAKEVEN
                    update_reason = "Day 3 - Moved to Breakeven"
            
            # Rule 4: Day 4 - Lock minimum profit
            elif days_elapsed >= 4:
                if self.sl_stage != SLStage.PROFIT_LOCK:
                    min_profit = max_profit_receivable * self.day4_profit_lock_percent / 100
                    self.current_sl = min_profit
                    self.sl_stage = SLStage.PROFIT_LOCK
                    update_reason = f"Day 4 - Locked {self.day4_profit_lock_percent}% Profit"
        
        # Log update if SL changed
        if update_reason:
            self.sl_history.append({
                "time": current_time,
                "old_sl": old_sl,
                "new_sl": self.current_sl,
                "old_stage": old_stage.value,
                "new_stage": self.sl_stage.value,
                "current_pnl": current_pnl,
                "reason": update_reason
            })
            self.last_update_time = current_time
            
            logger.info(
                f"SL Updated: {old_sl:.0f} -> {self.current_sl:.0f} | "
                f"Stage: {old_stage.value} -> {self.sl_stage.value} | "
                f"Reason: {update_reason}"
            )
        
        return update_reason
    
    def check_stop_loss_hit(self, current_pnl: float) -> Tuple[bool, Optional[str]]:
        """
        Check if current P&L has hit the stop-loss
        
        Args:
            current_pnl: Current P&L of the position
            
        Returns:
            Tuple of (is_hit, reason)
        """
        if current_pnl <= self.current_sl:
            reason = f"P&L SL Hit: {current_pnl:.0f} <= {self.current_sl:.0f} ({self.sl_stage.value})"
            return True, reason
        return False, None
    
    def get_sl_summary(self) -> Dict:
        """
        Get summary of stop-loss progression
        
        Returns:
            Dictionary with SL progression details
        """
        return {
            "initial_sl": self.initial_sl_total,
            "current_sl": self.current_sl,
            "current_stage": self.sl_stage.value,
            "max_profit_seen": self.max_profit_seen,
            "sl_history": self.sl_history,
            "last_update": self.last_update_time.isoformat() if self.last_update_time else None
        }
    
    def calculate_trading_days(self, entry_time: datetime, current_time: datetime) -> int:
        """
        Calculate number of trading days elapsed (excluding weekends)
        
        Args:
            entry_time: Entry timestamp
            current_time: Current timestamp
            
        Returns:
            Number of trading days elapsed
        """
        days = 0
        current_date = entry_time.date()
        target_date = current_time.date()
        
        while current_date < target_date:
            current_date += timedelta(days=1)
            # Skip weekends (Saturday=5, Sunday=6)
            if current_date.weekday() < 5:
                days += 1
        
        # Add 1 to make it 1-indexed (entry day is day 1)
        return days + 1