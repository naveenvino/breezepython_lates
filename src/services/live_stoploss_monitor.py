"""
Live Stop Loss Monitor
Monitors positions and triggers stop loss based on multiple strategies
"""

import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from src.services.hybrid_data_manager import get_hybrid_data_manager, LivePosition, HourlyCandle
from src.services.realtime_candle_service import get_realtime_candle_service

logger = logging.getLogger(__name__)

class StopLossType(Enum):
    HOURLY_CLOSE = "hourly_close"  # Based on hourly candle close beyond strike
    PROFIT_LOCK = "profit_lock"    # Lock profit after target
    TIME_BASED = "time_based"      # T+N exit timing from configuration
    TRAILING = "trailing"          # Trailing stop loss

@dataclass
class StopLossRule:
    """Defines a stop loss rule"""
    type: StopLossType
    enabled: bool
    params: Dict[str, Any]
    
    def __post_init__(self):
        # Set default parameters
        if self.type == StopLossType.PROFIT_LOCK:
            self.params.setdefault('target_percent', 2.0)
            self.params.setdefault('lock_percent', 1.0)
        elif self.type == StopLossType.TIME_BASED:
            self.params.setdefault('square_off_time', time(15, 15))
        elif self.type == StopLossType.TRAILING:
            self.params.setdefault('trail_percent', 1.0)
        elif self.type == StopLossType.HOURLY_CLOSE:
            self.params.setdefault('stop_buffer', 20)

class LiveStopLossMonitor:
    """
    Monitors stop loss conditions and triggers exits
    Checks on every hourly candle close and continuously for critical conditions
    """
    
    def __init__(self):
        self.data_manager = get_hybrid_data_manager()
        self.candle_service = get_realtime_candle_service()
        
        # Stop loss rules - Hourly close based on strike is the main stop loss
        self.stop_loss_rules = [
            StopLossRule(
                type=StopLossType.HOURLY_CLOSE,
                enabled=True,  # MANDATORY - Check on hourly close if beyond strike
                params={'stop_buffer': 0}  # No buffer - exact strike
            ),
            StopLossRule(
                type=StopLossType.PROFIT_LOCK,
                enabled=True,
                params={
                    'target_percent': 10.0,  # User configurable: When to activate lock
                    'lock_percent': 5.0,      # User configurable: Minimum profit to maintain
                    'user_configurable': True
                }
            ),
            StopLossRule(
                type=StopLossType.TIME_BASED,
                enabled=True,  # ENABLED - For T+N exit timing from configuration
                params={'square_off_time': time(15, 15)}  # Will be overridden by config
            ),
            StopLossRule(
                type=StopLossType.TRAILING,
                enabled=False,
                params={'trail_percent': 1.0}
            )
        ]
        
        # Remove STRIKE_BASED as it's duplicate of HOURLY_CLOSE
        # Store webhook_id to position mapping for combined tracking
        self.webhook_positions: Dict[str, List[int]] = {}  # webhook_id -> [position_ids]
        
        # Position tracking
        self.position_high_water_marks: Dict[int, float] = {}  # For trailing stops
        self.position_profit_locked: Dict[int, bool] = {}      # For profit locking
        
        # Callbacks
        self.on_stop_loss_triggered: Optional[Callable[[LivePosition, StopLossType, str], None]] = None
        
        # Register for candle completion
        self.candle_service.on_stop_loss_check = self._on_hourly_candle_close
    
    def _on_hourly_candle_close(self, candle: HourlyCandle):
        """Called when hourly candle closes"""
        logger.info(f"Checking stop loss at hourly close: {candle.timestamp}")
        
        # Check all active positions
        positions = self.data_manager.memory_cache['active_positions'].values()
        
        for position in positions:
            # Check hourly close based stop loss
            if self._check_hourly_close_stop(position, candle):
                self._trigger_stop_loss(position, StopLossType.HOURLY_CLOSE, 
                                       f"Hourly close at {candle.close} breached stop")
                continue
            
            # Check other stop loss conditions
            self._check_all_stops(position, candle.close)
    
    def _check_all_stops(self, position: LivePosition, spot_price: float):
        """Check all stop loss conditions for a position"""
        
        # Profit lock
        if self._is_rule_enabled(StopLossType.PROFIT_LOCK):
            if self._check_profit_lock(position):
                self._trigger_stop_loss(position, StopLossType.PROFIT_LOCK,
                                       "Profit lock triggered")
                return
        
        # Time-based T+N exit
        if self._is_rule_enabled(StopLossType.TIME_BASED):
            if self._check_time_based_exit(position):
                self._trigger_stop_loss(position, StopLossType.TIME_BASED,
                                       "T+N exit timing triggered")
                return
        
        # Trailing stop loss
        if self._is_rule_enabled(StopLossType.TRAILING):
            if self._check_trailing_stop(position):
                self._trigger_stop_loss(position, StopLossType.TRAILING,
                                       "Trailing stop triggered")
                return
    
    def register_position_with_webhook(self, webhook_id: str, position_id: int):
        """Register a position with its webhook_id for combined tracking"""
        if webhook_id not in self.webhook_positions:
            self.webhook_positions[webhook_id] = []
        if position_id not in self.webhook_positions[webhook_id]:
            self.webhook_positions[webhook_id].append(position_id)
            logger.info(f"Registered position {position_id} with webhook {webhook_id}")
    
    def get_combined_positions(self, webhook_id: str) -> List[LivePosition]:
        """Get all positions (main + hedge) for a webhook_id"""
        positions = []
        if webhook_id in self.webhook_positions:
            for pos_id in self.webhook_positions[webhook_id]:
                if pos_id in self.data_manager.memory_cache['active_positions']:
                    positions.append(self.data_manager.memory_cache['active_positions'][pos_id])
        return positions
    
    def _check_hourly_close_stop(self, position: LivePosition, candle: HourlyCandle) -> bool:
        """Check if hourly candle closed beyond strike (MANDATORY DEFAULT - exact strike as stop loss)
        
        Option Seller Logic:
        - PUT selling is BULLISH strategy - exit if market turns BEARISH
        - CALL selling is BEARISH strategy - exit if market turns BULLISH
        """
        
        # CORRECTED LOGIC - Matching option seller expectations:
        # PUT selling: Stop if hourly close goes BELOW strike (market turned bearish against bullish bet)
        # CALL selling: Stop if hourly close goes ABOVE strike (market turned bullish against bearish bet)
        
        if 'PE' in position.signal_type or position.signal_type in ['S1', 'S2', 'S4', 'S7']:
            # Sold PUT (bullish bet) - stop if close goes BELOW strike (bearish move)
            return candle.close < position.main_strike
        else:
            # Sold CALL (bearish bet) - stop if close goes ABOVE strike (bullish move)
            return candle.close > position.main_strike
    
    def _check_profit_lock(self, position: LivePosition) -> bool:
        """Check if profit should be locked
        Example: target=10%, lock=5%
        - Activate when profit reaches 10%
        - Exit if profit falls below 5%
        """
        rule = self._get_rule(StopLossType.PROFIT_LOCK)
        target_percent = rule.params.get('target_percent', 10.0)  # Default 10%
        lock_percent = rule.params.get('lock_percent', 5.0)       # Default 5%
        
        # Calculate NET profit percentage (including hedge)
        # Main leg: We sold, so profit when price decreases
        main_entry = position.main_price * position.main_quantity * 75
        main_current = position.current_main_price * position.main_quantity * 75
        main_profit = main_entry - main_current  # Profit when current < entry
        
        # Hedge leg (if exists): We bought, so loss when price decreases
        hedge_profit = 0
        if position.hedge_price and position.hedge_quantity > 0:
            hedge_entry = position.hedge_price * position.hedge_quantity * 75
            hedge_current = (position.current_hedge_price or position.hedge_price) * position.hedge_quantity * 75
            hedge_profit = hedge_current - hedge_entry  # Profit when current > entry (we bought)
        
        # Net profit = Main profit + Hedge profit (hedge profit is usually negative, reducing main profit)
        net_profit = main_profit + hedge_profit
        
        # Calculate profit percentage based on main entry value
        profit_percent = (net_profit / main_entry) * 100
        
        # Log current profit status
        if position.id not in self.position_profit_locked:
            logger.debug(f"Position {position.id} P&L: {profit_percent:.2f}% (Target: {target_percent}%)")
        
        # Check if position has already been marked as profit locked
        if position.id in self.position_profit_locked and self.position_profit_locked[position.id]:
            # Already hit target, now monitor for lock level
            if profit_percent < lock_percent:
                logger.warning(f"Profit lock triggered for position {position.id}: "
                             f"Profit {profit_percent:.2f}% fell below lock {lock_percent}%")
                return True  # Trigger stop loss
            else:
                logger.debug(f"Position {position.id} maintaining profit: {profit_percent:.2f}% > {lock_percent}%")
        else:
            # Check if we've reached target for the first time
            if profit_percent >= target_percent:
                self.position_profit_locked[position.id] = True
                logger.info(f"🎯 Profit target reached for position {position.id}: {profit_percent:.2f}% >= {target_percent}%")
                logger.info(f"Now monitoring to maintain minimum {lock_percent}% profit")
        
        return False
    
    def _check_time_based_exit(self, position: LivePosition) -> bool:
        """Check if it's time for T+N exit based on configuration STORED AT ENTRY TIME"""
        try:
            # Get exit timing configuration from database
            import sqlite3
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            # Get the webhook_id and EXIT CONFIG STORED AT ENTRY for this position
            cursor.execute("""
                SELECT webhook_id, created_at, exit_config_day, exit_config_time
                FROM OrderTracking 
                WHERE (main_order_id = ? OR hedge_order_id = ?)
                AND status != 'failed'
            """, (position.order_id, position.order_id))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return False
                
            webhook_id, entry_time_str, exit_day, exit_time_str = result
            
            # If no exit config was stored (old orders), return False
            if exit_day is None or exit_time_str is None:
                return False
                
            entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M:%S')
            
            # Calculate target exit datetime
            # exit_day: 0 = expiry day, 1-7 = T+N days
            if exit_day == 0:
                # Exit on expiry day - get expiry date from position
                # For now, return False as expiry logic is handled elsewhere
                return False
            else:
                # T+N days from entry
                target_date = entry_time
                trading_days_added = 0
                
                while trading_days_added < exit_day:
                    target_date += timedelta(days=1)
                    # Skip weekends
                    if target_date.weekday() < 5:  # Monday=0, Friday=4
                        trading_days_added += 1
                
                # Set the exit time
                exit_hour, exit_minute = map(int, exit_time_str.split(':'))
                target_exit = target_date.replace(hour=exit_hour, minute=exit_minute, second=0)
                
                # Check if current time is past target exit time
                current_time = datetime.now()
                
                # Allow 1 minute window
                time_diff = abs((current_time - target_exit).total_seconds())
                
                if current_time >= target_exit and time_diff <= 60:
                    logger.info(f"T+{exit_day} exit triggered for position {position.id} at {exit_time_str}")
                    return True
                    
        except Exception as e:
            logger.error(f"Error checking time-based exit: {e}")
            
        return False
    
    def _check_trailing_stop(self, position: LivePosition) -> bool:
        """Check trailing stop loss INCLUDING HEDGE in calculation"""
        rule = self._get_rule(StopLossType.TRAILING)
        trail_percent = rule.params['trail_percent']
        
        # Calculate NET profit (including hedge)
        # Main leg: We sold, so profit when price decreases
        main_entry = position.main_price * position.main_quantity * 75
        main_current = position.current_main_price * position.main_quantity * 75
        main_profit = main_entry - main_current  # Profit when current < entry
        
        # Hedge leg (if exists): We bought, so loss when price decreases
        hedge_profit = 0
        if position.hedge_price and position.hedge_quantity > 0:
            hedge_entry = position.hedge_price * position.hedge_quantity * 75
            hedge_current = (position.current_hedge_price or position.hedge_price) * position.hedge_quantity * 75
            hedge_profit = hedge_current - hedge_entry  # Profit when current > entry (we bought)
        
        # Net profit = Main profit + Hedge profit
        net_profit = main_profit + hedge_profit
        
        # Track high water mark (highest profit achieved)
        if position.id not in self.position_high_water_marks:
            self.position_high_water_marks[position.id] = net_profit
            logger.debug(f"Position {position.id} initial profit: ₹{net_profit:.2f}")
        else:
            if net_profit > self.position_high_water_marks[position.id]:
                old_high = self.position_high_water_marks[position.id]
                self.position_high_water_marks[position.id] = net_profit
                logger.info(f"Position {position.id} new high profit: ₹{net_profit:.2f} (was ₹{old_high:.2f})")
        
        # Check if profit has fallen by trail percent from high
        high_water_mark = self.position_high_water_marks[position.id]
        if high_water_mark > 0:  # Only trail when in profit
            drawdown = high_water_mark - net_profit
            # Calculate drawdown as percentage of entry value
            drawdown_percent = (drawdown / main_entry) * 100
            
            logger.debug(f"Position {position.id} trailing: High ₹{high_water_mark:.2f}, "
                        f"Current ₹{net_profit:.2f}, Drawdown {drawdown_percent:.2f}%")
            
            if drawdown_percent >= trail_percent:
                logger.warning(f"Trailing stop triggered for position {position.id}: "
                             f"Drawdown {drawdown_percent:.2f}% >= {trail_percent}%")
                return True
        
        return False
    
    def _trigger_stop_loss(self, position: LivePosition, stop_type: StopLossType, reason: str):
        """Trigger stop loss for combined main + hedge positions"""
        logger.warning(f"STOP LOSS TRIGGERED for position {position.id}: {reason}")
        
        # Find webhook_id for this position
        webhook_id = None
        for wid, pos_ids in self.webhook_positions.items():
            if position.id in pos_ids:
                webhook_id = wid
                break
        
        if webhook_id:
            # Close all positions for this webhook_id (main + hedge)
            positions_to_close = self.get_combined_positions(webhook_id)
            logger.info(f"Closing {len(positions_to_close)} positions for webhook {webhook_id}")
            
            total_pnl = 0
            for pos in positions_to_close:
                total_pnl += pos.pnl
                self.data_manager.close_position(pos.id, pos.pnl)
                
                # Clean up tracking
                if pos.id in self.position_high_water_marks:
                    del self.position_high_water_marks[pos.id]
                if pos.id in self.position_profit_locked:
                    del self.position_profit_locked[pos.id]
            
            # Remove webhook tracking
            del self.webhook_positions[webhook_id]
            
            # Send alert with combined P&L
            pnl = total_pnl
        else:
            # Fallback to single position close
            pnl = position.pnl
            self.data_manager.close_position(position.id, pnl)
            
            # Clean up tracking
            if position.id in self.position_high_water_marks:
                del self.position_high_water_marks[position.id]
            if position.id in self.position_profit_locked:
                del self.position_profit_locked[position.id]
        
        # Calculate final P&L
        pnl = position.pnl
        
        # Send alert notification
        try:
            from src.services.alert_notification_service import get_alert_service
            alert_service = get_alert_service()
            alert_service.send_stop_loss(
                strike=position.main_strike,
                option_type="PE" if position.signal_type in ['S1', 'S2', 'S4', 'S7'] else "CE",
                loss=pnl if pnl < 0 else 0,
                reason=f"{stop_type.value}: {reason}"
            )
        except Exception as e:
            logger.error(f"Failed to send stop loss alert: {e}")
        
        # Update position status
        self.data_manager.close_position(position.id, pnl)
        
        # Clean up tracking
        if position.id in self.position_high_water_marks:
            del self.position_high_water_marks[position.id]
        if position.id in self.position_profit_locked:
            del self.position_profit_locked[position.id]
        
        # Trigger callback
        if self.on_stop_loss_triggered:
            self.on_stop_loss_triggered(position, stop_type, reason)
    
    def _is_rule_enabled(self, stop_type: StopLossType) -> bool:
        """Check if a stop loss rule is enabled"""
        rule = self._get_rule(stop_type)
        return rule and rule.enabled
    
    def _get_rule(self, stop_type: StopLossType) -> Optional[StopLossRule]:
        """Get stop loss rule by type"""
        for rule in self.stop_loss_rules:
            if rule.type == stop_type:
                return rule
        return None
    
    def update_rules(self, rules: List[StopLossRule]):
        """Update stop loss rules"""
        self.stop_loss_rules = rules
        logger.info(f"Updated stop loss rules: {[r.type.value for r in rules if r.enabled]}")
    
    def check_position_now(self, position_id: int):
        """Manually check stop loss for a specific position"""
        if position_id in self.data_manager.memory_cache['active_positions']:
            position = self.data_manager.memory_cache['active_positions'][position_id]
            spot_price = self.data_manager.memory_cache.get('spot_price')
            
            if spot_price:
                self._check_all_stops(position, spot_price)
    
    def get_position_status(self, position_id: int) -> Dict[str, Any]:
        """Get stop loss status for a position"""
        if position_id not in self.data_manager.memory_cache['active_positions']:
            return {'error': 'Position not found'}
        
        position = self.data_manager.memory_cache['active_positions'][position_id]
        spot_price = self.data_manager.memory_cache.get('spot_price', 0)
        
        # Calculate current P&L
        main_entry = position.main_price * position.main_quantity * 75
        main_current = position.current_main_price * position.main_quantity * 75
        main_pnl = main_entry - main_current
        
        hedge_pnl = 0
        if position.hedge_price:
            hedge_entry = position.hedge_price * position.hedge_quantity * 75
            hedge_current = (position.current_hedge_price or position.hedge_price) * position.hedge_quantity * 75
            hedge_pnl = hedge_current - hedge_entry
        
        net_pnl = main_pnl + hedge_pnl
        pnl_percent = (net_pnl / main_entry) * 100
        
        status = {
            'position_id': position_id,
            'signal_type': position.signal_type,
            'main_strike': position.main_strike,
            'current_pnl': net_pnl,
            'pnl_percent': round(pnl_percent, 2),
            'spot_price': spot_price,
            'main_price': {
                'entry': position.main_price,
                'current': position.current_main_price
            },
            'hedge_price': {
                'entry': position.hedge_price,
                'current': position.current_hedge_price
            } if position.hedge_price else None,
            'profit_locked': self.position_profit_locked.get(position_id, False),
            'high_water_mark': self.position_high_water_marks.get(position_id, 0),
            'stop_loss_status': {}
        }
        
        # Check each stop type
        for rule in self.stop_loss_rules:
            if rule.enabled:
                if rule.type == StopLossType.PROFIT_LOCK:
                    triggered = self._check_profit_lock(position)
                elif rule.type == StopLossType.TIME_BASED:
                    triggered = self._check_time_based_exit(position)
                elif rule.type == StopLossType.TRAILING:
                    triggered = self._check_trailing_stop(position)
                else:
                    triggered = False
                
                status['stop_loss_status'][rule.type.value] = {
                    'enabled': True,
                    'triggered': triggered,
                    'params': rule.params
                }
        
        return status
    
    def update_option_prices(self, position_id: int, main_price: float = None, hedge_price: float = None):
        """Update current option prices for a position (for continuous monitoring)"""
        if position_id not in self.data_manager.memory_cache['active_positions']:
            return False
        
        position = self.data_manager.memory_cache['active_positions'][position_id]
        
        if main_price is not None:
            position.current_main_price = main_price
            logger.debug(f"Updated main price for position {position_id}: ₹{main_price}")
        
        if hedge_price is not None and position.hedge_price:
            position.current_hedge_price = hedge_price
            logger.debug(f"Updated hedge price for position {position_id}: ₹{hedge_price}")
        
        # Check stop losses after price update
        spot_price = self.data_manager.memory_cache.get('spot_price')
        if spot_price:
            self._check_all_stops(position, spot_price)
        
        return True
    
    def monitor_all_positions(self):
        """Monitor all active positions for stop loss triggers
        This should be called periodically (e.g., every 30 seconds) for continuous monitoring
        """
        positions = list(self.data_manager.memory_cache['active_positions'].values())
        spot_price = self.data_manager.memory_cache.get('spot_price', 0)
        
        if not positions:
            return {'status': 'No active positions'}
        
        monitored = []
        for position in positions:
            # Skip if already closing
            if position.status in ['closing', 'closed']:
                continue
            
            # Check all stops
            self._check_all_stops(position, spot_price)
            
            # Get status
            status = self.get_position_status(position.id)
            monitored.append(status)
        
        return {
            'status': 'Monitoring active',
            'positions_monitored': len(monitored),
            'spot_price': spot_price,
            'positions': monitored
        }

# Singleton instance
_instance = None

def get_live_stoploss_monitor() -> LiveStopLossMonitor:
    """Get singleton instance of live stop loss monitor"""
    global _instance
    if _instance is None:
        _instance = LiveStopLossMonitor()
    return _instance