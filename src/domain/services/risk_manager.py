"""
Risk Manager Service
Enforces trading risk limits and position sizing rules
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Risk limit configuration"""
    max_position_value: Decimal  # Max value per position
    max_daily_loss: Decimal      # Daily stop loss
    max_open_positions: int      # Max concurrent positions
    max_account_exposure: float  # As percentage of capital (0-1)
    max_single_trade_risk: float # Max risk per trade as % of capital
    

@dataclass
class RiskMetrics:
    """Current risk metrics"""
    daily_pnl: Decimal = Decimal("0")
    open_positions: int = 0
    total_exposure: Decimal = Decimal("0")
    positions_opened_today: int = 0
    largest_position: Decimal = Decimal("0")
    total_margin_used: Decimal = Decimal("0")
    
    
@dataclass
class RiskCheckResult:
    """Result of risk check"""
    allowed: bool
    reason: Optional[str] = None
    current_metrics: Optional[RiskMetrics] = None
    suggested_position_size: Optional[int] = None


class RiskManager:
    """
    Enforce trading risk limits and position management
    """
    
    def __init__(
        self, 
        initial_capital: Decimal,
        lot_size: int = 75,
        max_daily_loss_percent: float = 2.0,
        max_position_percent: float = 10.0,
        max_exposure_percent: float = 50.0
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.lot_size = lot_size
        
        # Initialize risk limits
        self.limits = RiskLimits(
            max_position_value=initial_capital * Decimal(str(max_position_percent / 100)),
            max_daily_loss=initial_capital * Decimal(str(max_daily_loss_percent / 100)),
            max_open_positions=5,
            max_account_exposure=max_exposure_percent / 100,
            max_single_trade_risk=0.10  # 10% max risk per trade
        )
        
        # Track daily metrics
        self.daily_metrics: Dict[date, RiskMetrics] = {}
        self.current_date = None
        
        # Track open positions
        self.open_positions: List[Dict] = []
        
    def update_capital(self, new_capital: Decimal):
        """Update current capital (after profits/losses)"""
        self.current_capital = new_capital
        
        # Optionally adjust limits based on new capital
        # For now, keeping limits based on initial capital
        
    def get_or_create_daily_metrics(self, current_date: date) -> RiskMetrics:
        """Get or create metrics for current date"""
        if current_date not in self.daily_metrics:
            self.daily_metrics[current_date] = RiskMetrics()
        return self.daily_metrics[current_date]
        
    def can_open_position(
        self,
        position_value: Decimal,
        margin_required: Decimal,
        stop_loss_amount: Decimal,
        current_date: datetime
    ) -> RiskCheckResult:
        """
        Check if new position is within risk limits
        
        Args:
            position_value: Notional value of position
            margin_required: Margin needed for position
            stop_loss_amount: Potential loss if stop hit
            current_date: Current datetime
            
        Returns:
            RiskCheckResult with allowed status and reason
        """
        # Get daily metrics
        metrics = self.get_or_create_daily_metrics(current_date.date())
        
        # Check 1: Position size limit
        if position_value > self.limits.max_position_value:
            return RiskCheckResult(
                allowed=False,
                reason=f"Position size {position_value:.0f} exceeds limit {self.limits.max_position_value:.0f}",
                current_metrics=metrics
            )
            
        # Check 2: Daily loss limit
        if abs(metrics.daily_pnl) >= self.limits.max_daily_loss:
            return RiskCheckResult(
                allowed=False,
                reason=f"Daily loss limit reached: {metrics.daily_pnl:.0f} / {self.limits.max_daily_loss:.0f}",
                current_metrics=metrics
            )
            
        # Check 3: Max open positions
        if metrics.open_positions >= self.limits.max_open_positions:
            return RiskCheckResult(
                allowed=False,
                reason=f"Maximum {self.limits.max_open_positions} open positions reached",
                current_metrics=metrics
            )
            
        # Check 4: Account exposure
        total_new_exposure = metrics.total_exposure + position_value
        exposure_ratio = float(total_new_exposure / self.current_capital)
        
        if exposure_ratio > self.limits.max_account_exposure:
            return RiskCheckResult(
                allowed=False,
                reason=f"Total exposure {exposure_ratio*100:.1f}% would exceed limit {self.limits.max_account_exposure*100:.0f}%",
                current_metrics=metrics
            )
            
        # Check 5: Available capital for margin
        available_capital = self.current_capital - metrics.total_margin_used
        if margin_required > available_capital:
            return RiskCheckResult(
                allowed=False,
                reason=f"Insufficient margin. Required: {margin_required:.0f}, Available: {available_capital:.0f}",
                current_metrics=metrics
            )
            
        # Check 6: Single trade risk
        risk_percent = float(stop_loss_amount / self.current_capital)
        if risk_percent > self.limits.max_single_trade_risk:
            # Suggest reduced position size
            suggested_lots = int((self.limits.max_single_trade_risk * float(self.current_capital)) / 
                               float(stop_loss_amount / (position_value / (self.lot_size * 75))))
            
            return RiskCheckResult(
                allowed=False,
                reason=f"Trade risk {risk_percent*100:.1f}% exceeds limit {self.limits.max_single_trade_risk*100:.0f}%",
                current_metrics=metrics,
                suggested_position_size=suggested_lots
            )
            
        # All checks passed
        return RiskCheckResult(
            allowed=True,
            reason=None,
            current_metrics=metrics
        )
        
    def record_position_opened(
        self,
        position_id: str,
        position_value: Decimal,
        margin_used: Decimal,
        position_details: Dict,
        current_date: datetime
    ):
        """Record a new position opened"""
        metrics = self.get_or_create_daily_metrics(current_date.date())
        
        # Update metrics
        metrics.open_positions += 1
        metrics.positions_opened_today += 1
        metrics.total_exposure += position_value
        metrics.total_margin_used += margin_used
        metrics.largest_position = max(metrics.largest_position, position_value)
        
        # Track position
        self.open_positions.append({
            "id": position_id,
            "value": position_value,
            "margin": margin_used,
            "opened_at": current_date,
            "details": position_details
        })
        
        logger.info(f"Position opened: {position_id}, Value: {position_value:.0f}, "
                   f"Total exposure: {metrics.total_exposure:.0f}")
        
    def record_position_closed(
        self,
        position_id: str,
        pnl: Decimal,
        current_date: datetime
    ):
        """Record a position closed"""
        metrics = self.get_or_create_daily_metrics(current_date.date())
        
        # Find and remove position
        position = None
        for i, pos in enumerate(self.open_positions):
            if pos["id"] == position_id:
                position = pos
                self.open_positions.pop(i)
                break
                
        if position:
            # Update metrics
            metrics.open_positions -= 1
            metrics.daily_pnl += pnl
            metrics.total_exposure -= position["value"]
            metrics.total_margin_used -= position["margin"]
            
            # Update capital
            self.current_capital += pnl
            
            logger.info(f"Position closed: {position_id}, PnL: {pnl:.0f}, "
                       f"Daily PnL: {metrics.daily_pnl:.0f}")
            
    def get_position_size_for_risk(
        self,
        stop_loss_points: float,
        max_risk_amount: Optional[Decimal] = None
    ) -> int:
        """
        Calculate position size (lots) for given risk
        
        Args:
            stop_loss_points: Points of stop loss
            max_risk_amount: Max amount to risk (default: based on limits)
            
        Returns:
            Number of lots
        """
        if max_risk_amount is None:
            max_risk_amount = self.current_capital * Decimal(str(self.limits.max_single_trade_risk))
            
        # Risk per lot = stop_loss_points * lot_size
        risk_per_lot = Decimal(str(stop_loss_points * self.lot_size))
        
        # Calculate lots
        lots = int(max_risk_amount / risk_per_lot)
        
        # Ensure at least 1 lot
        return max(1, lots)
        
    def get_risk_summary(self, current_date: datetime) -> Dict:
        """Get current risk summary"""
        metrics = self.get_or_create_daily_metrics(current_date.date())
        
        return {
            "current_capital": float(self.current_capital),
            "initial_capital": float(self.initial_capital),
            "daily_pnl": float(metrics.daily_pnl),
            "daily_pnl_percent": float(metrics.daily_pnl / self.initial_capital * 100),
            "open_positions": metrics.open_positions,
            "total_exposure": float(metrics.total_exposure),
            "exposure_percent": float(metrics.total_exposure / self.current_capital * 100),
            "margin_utilization": float(metrics.total_margin_used / self.current_capital * 100),
            "positions_opened_today": metrics.positions_opened_today,
            "largest_position": float(metrics.largest_position),
            "can_trade": abs(metrics.daily_pnl) < self.limits.max_daily_loss
        }
        
    def reset_daily_metrics(self, current_date: date):
        """Reset daily metrics (call at start of new trading day)"""
        self.daily_metrics[current_date] = RiskMetrics()
        
    def should_stop_trading(self, current_date: datetime) -> bool:
        """Check if should stop trading for the day"""
        metrics = self.get_or_create_daily_metrics(current_date.date())
        
        # Stop if daily loss limit hit
        if abs(metrics.daily_pnl) >= self.limits.max_daily_loss:
            return True
            
        # Stop if drawdown too severe
        drawdown = (self.initial_capital - self.current_capital) / self.initial_capital
        if drawdown > 0.05:  # 5% drawdown
            return True
            
        return False
        
    def validate_stop_loss(
        self,
        entry_price: float,
        stop_loss_price: float,
        position_type: str,
        lots: int
    ) -> RiskCheckResult:
        """
        Validate stop loss placement
        
        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            position_type: 'SELL_CE' or 'SELL_PE'
            lots: Number of lots
            
        Returns:
            RiskCheckResult
        """
        # Calculate stop loss distance
        if position_type == "SELL_CE":
            # For call selling, stop loss should be above entry
            if stop_loss_price <= entry_price:
                return RiskCheckResult(
                    allowed=False,
                    reason="Stop loss for sold call must be above entry price"
                )
            stop_distance = stop_loss_price - entry_price
        else:  # SELL_PE
            # For put selling, stop loss should be below entry
            if stop_loss_price >= entry_price:
                return RiskCheckResult(
                    allowed=False,
                    reason="Stop loss for sold put must be below entry price"
                )
            stop_distance = entry_price - stop_loss_price
            
        # Calculate potential loss
        potential_loss = Decimal(str(stop_distance * lots * self.lot_size))
        
        # Check if loss is within acceptable range
        max_acceptable_loss = self.current_capital * Decimal(str(self.limits.max_single_trade_risk))
        
        if potential_loss > max_acceptable_loss:
            suggested_lots = int(max_acceptable_loss / (Decimal(str(stop_distance * self.lot_size))))
            return RiskCheckResult(
                allowed=False,
                reason=f"Stop loss risk {potential_loss:.0f} exceeds limit {max_acceptable_loss:.0f}",
                suggested_position_size=suggested_lots
            )
            
        return RiskCheckResult(allowed=True)