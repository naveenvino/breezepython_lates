"""
Risk Manager Service Implementation
Concrete implementation of IRiskManager
"""
import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime
import statistics

from ...domain.services.irisk_manager import IRiskManager, RiskMetrics, PositionRisk
from ...domain.entities.trade import Trade, TradeType, TradeStatus
from ...domain.entities.option import Option
from ...domain.entities.market_data import MarketData

logger = logging.getLogger(__name__)


class RiskManagerService(IRiskManager):
    """Implementation of risk management service"""
    
    def calculate_position_risk(
        self,
        trade: Trade,
        current_price: Decimal,
        volatility: Optional[Decimal] = None
    ) -> PositionRisk:
        """Calculate risk for a single position"""
        risk = PositionRisk(trade.symbol)
        risk.quantity = trade.quantity
        
        # Calculate exposure
        risk.exposure = current_price * trade.quantity
        
        # Calculate P&L
        if trade.trade_type == TradeType.BUY:
            risk.unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
        else:  # SELL
            risk.unrealized_pnl = (trade.entry_price - current_price) * trade.quantity
        
        # Calculate max loss
        if trade.stop_loss:
            if trade.trade_type == TradeType.BUY:
                risk.max_loss = (trade.entry_price - trade.stop_loss) * trade.quantity
            else:
                risk.max_loss = (trade.stop_loss - trade.entry_price) * trade.quantity
        else:
            # No stop loss, max loss is full position
            risk.max_loss = trade.entry_price * trade.quantity
        
        # Risk percentage (of position value)
        position_value = trade.entry_price * trade.quantity
        if position_value > 0:
            risk.risk_percentage = (risk.max_loss / position_value) * 100
        
        return risk
    
    def calculate_portfolio_risk(
        self,
        trades: List[Trade],
        market_data: Dict[str, MarketData],
        total_capital: Decimal
    ) -> RiskMetrics:
        """Calculate overall portfolio risk metrics"""
        metrics = RiskMetrics()
        
        if not trades:
            return metrics
        
        # Calculate position-level metrics
        position_risks = []
        for trade in trades:
            if trade.status == TradeStatus.OPEN:
                market = market_data.get(trade.symbol)
                if market:
                    current_price = market.close
                    risk = self.calculate_position_risk(trade, current_price)
                    position_risks.append(risk)
                    
                    # Aggregate metrics
                    metrics.total_exposure += risk.exposure
                    metrics.max_loss += risk.max_loss
                    
                    # Sum Greeks if available (for options)
                    metrics.position_delta += risk.delta
                    metrics.position_gamma += risk.gamma
                    metrics.position_theta += risk.theta
                    metrics.position_vega += risk.vega
        
        # Calculate portfolio-level metrics
        if total_capital > 0:
            metrics.margin_used = metrics.total_exposure
            metrics.margin_available = total_capital - metrics.margin_used
            
            # Calculate win rate from closed trades
            closed_trades = [t for t in trades if t.status == TradeStatus.CLOSED]
            if closed_trades:
                winning_trades = sum(1 for t in closed_trades if t.calculate_pnl() > 0)
                metrics.win_rate = Decimal(str(winning_trades / len(closed_trades) * 100))
        
        # Calculate Value at Risk (simplified)
        if position_risks:
            # Using historical simulation approach
            position_pnls = [r.unrealized_pnl for r in position_risks]
            if position_pnls:
                # 95% VaR
                sorted_pnls = sorted(position_pnls)
                var_index = int(len(sorted_pnls) * 0.05)
                metrics.value_at_risk = abs(sorted_pnls[var_index])
        
        # Calculate max drawdown
        if trades:
            equity_curve = self._calculate_equity_curve(trades, total_capital)
            metrics.max_drawdown = self._calculate_max_drawdown_from_curve(equity_curve)
        
        return metrics
    
    def check_risk_limits(
        self,
        trade: Trade,
        current_positions: List[Trade],
        risk_parameters: Dict[str, Any]
    ) -> Dict[str, bool]:
        """Check if trade violates any risk limits"""
        checks = {
            "position_size": True,
            "max_positions": True,
            "daily_loss": True,
            "exposure": True,
            "margin": True
        }
        
        # Check position size limit
        max_position_size = risk_parameters.get("max_position_size", float('inf'))
        if trade.quantity > max_position_size:
            checks["position_size"] = False
        
        # Check max positions limit
        open_positions = [p for p in current_positions if p.status == TradeStatus.OPEN]
        max_positions = risk_parameters.get("max_positions", float('inf'))
        if len(open_positions) >= max_positions:
            checks["max_positions"] = False
        
        # Check daily loss limit
        daily_loss_limit = risk_parameters.get("max_daily_loss", float('inf'))
        today_losses = self._calculate_today_losses(current_positions)
        potential_loss = self._calculate_potential_loss(trade)
        if abs(today_losses + potential_loss) > daily_loss_limit:
            checks["daily_loss"] = False
        
        # Check exposure limit
        total_capital = Decimal(str(risk_parameters.get("total_capital", 0)))
        max_exposure_pct = Decimal(str(risk_parameters.get("max_exposure_pct", 100)))
        current_exposure = sum(
            p.entry_price * p.quantity 
            for p in open_positions
        )
        new_exposure = trade.entry_price * trade.quantity
        if total_capital > 0:
            exposure_pct = ((current_exposure + new_exposure) / total_capital) * 100
            if exposure_pct > max_exposure_pct:
                checks["exposure"] = False
        
        # Check margin requirement
        available_margin = Decimal(str(risk_parameters.get("available_margin", 0)))
        required_margin = self._calculate_required_margin(trade)
        if required_margin > available_margin:
            checks["margin"] = False
        
        return checks
    
    def calculate_position_size(
        self,
        capital: Decimal,
        risk_percentage: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        lot_size: int = 1
    ) -> int:
        """Calculate appropriate position size based on risk"""
        # Risk amount in currency
        risk_amount = capital * (risk_percentage / 100)
        
        # Risk per unit
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit == 0:
            return 0
        
        # Calculate position size
        position_size = risk_amount / risk_per_unit
        
        # Round to lot size
        lots = int(position_size / lot_size)
        
        return lots * lot_size
    
    def calculate_kelly_criterion(
        self,
        win_rate: Decimal,
        average_win: Decimal,
        average_loss: Decimal
    ) -> Decimal:
        """Calculate optimal position size using Kelly Criterion"""
        if average_loss == 0:
            return Decimal('0')
        
        # Convert win rate to probability
        p = win_rate / 100
        q = 1 - p
        
        # Win/loss ratio
        b = average_win / average_loss
        
        # Kelly percentage
        kelly = (p * b - q) / b
        
        # Cap at 25% for safety
        return min(kelly, Decimal('0.25'))
    
    def calculate_value_at_risk(
        self,
        positions: List[PositionRisk],
        confidence_level: Decimal = Decimal('0.95'),
        time_horizon: int = 1
    ) -> Decimal:
        """Calculate Value at Risk (VaR)"""
        if not positions:
            return Decimal('0')
        
        # Simple historical simulation approach
        # In practice, would use more sophisticated methods
        
        # Simulate P&L scenarios
        simulated_pnls = []
        
        for position in positions:
            # Assume normal distribution of returns
            # This is simplified - real implementation would use historical data
            expected_pnl = position.unrealized_pnl
            volatility = position.exposure * Decimal('0.02')  # 2% daily vol assumption
            
            # Generate scenarios
            for i in range(1000):
                # Simple random walk
                import random
                shock = Decimal(str(random.gauss(0, 1))) * volatility
                scenario_pnl = expected_pnl + shock * Decimal(str(time_horizon ** 0.5))
                simulated_pnls.append(scenario_pnl)
        
        # Sort and find VaR at confidence level
        simulated_pnls.sort()
        var_index = int(len(simulated_pnls) * (1 - float(confidence_level)))
        
        return abs(simulated_pnls[var_index])
    
    def calculate_expected_shortfall(
        self,
        positions: List[PositionRisk],
        confidence_level: Decimal = Decimal('0.95')
    ) -> Decimal:
        """Calculate Expected Shortfall (Conditional VaR)"""
        if not positions:
            return Decimal('0')
        
        # Get VaR first
        var = self.calculate_value_at_risk(positions, confidence_level)
        
        # Calculate average of losses beyond VaR
        # This is simplified - would need the full distribution
        
        return var * Decimal('1.2')  # Rough approximation
    
    def calculate_max_drawdown(
        self,
        equity_curve: List[Decimal]
    ) -> Dict[str, Any]:
        """Calculate maximum drawdown from equity curve"""
        if len(equity_curve) < 2:
            return {
                "max_drawdown": Decimal('0'),
                "max_drawdown_pct": Decimal('0'),
                "peak_index": 0,
                "trough_index": 0
            }
        
        peak = equity_curve[0]
        peak_index = 0
        max_dd = Decimal('0')
        max_dd_pct = Decimal('0')
        trough_index = 0
        
        for i, value in enumerate(equity_curve):
            if value > peak:
                peak = value
                peak_index = i
            
            drawdown = peak - value
            drawdown_pct = (drawdown / peak * 100) if peak > 0 else Decimal('0')
            
            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_pct = drawdown_pct
                trough_index = i
        
        return {
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd_pct,
            "peak_index": peak_index,
            "trough_index": trough_index
        }
    
    def calculate_sharpe_ratio(
        self,
        returns: List[Decimal],
        risk_free_rate: Decimal = Decimal('0.05')
    ) -> Decimal:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return Decimal('0')
        
        # Convert to float for statistics
        returns_float = [float(r) for r in returns]
        
        # Calculate average return
        avg_return = Decimal(str(statistics.mean(returns_float)))
        
        # Calculate standard deviation
        std_dev = Decimal(str(statistics.stdev(returns_float)))
        
        if std_dev == 0:
            return Decimal('0')
        
        # Annualized Sharpe ratio (assuming daily returns)
        annualized_return = avg_return * 252
        annualized_std = std_dev * Decimal(str(252 ** 0.5))
        
        sharpe = (annualized_return - risk_free_rate) / annualized_std
        
        return sharpe
    
    def calculate_options_greeks_exposure(
        self,
        options_positions: List[Dict[str, Any]]
    ) -> Dict[str, Decimal]:
        """Calculate total Greeks exposure for options portfolio"""
        total_greeks = {
            "delta": Decimal('0'),
            "gamma": Decimal('0'),
            "theta": Decimal('0'),
            "vega": Decimal('0'),
            "rho": Decimal('0')
        }
        
        for position in options_positions:
            quantity = position.get("quantity", 0)
            greeks = position.get("greeks", {})
            
            for greek in total_greeks:
                greek_value = Decimal(str(greeks.get(greek, 0)))
                total_greeks[greek] += greek_value * quantity
        
        return total_greeks
    
    def suggest_hedge(
        self,
        positions: List[Trade],
        risk_tolerance: Dict[str, Decimal]
    ) -> List[Dict[str, Any]]:
        """Suggest hedging strategies to reduce risk"""
        suggestions = []
        
        # Calculate current exposure
        net_delta = Decimal('0')
        for position in positions:
            if position.trade_type == TradeType.BUY:
                net_delta += position.quantity
            else:
                net_delta -= position.quantity
        
        # Check if delta exceeds tolerance
        max_delta = risk_tolerance.get("max_delta", Decimal('1000'))
        if abs(net_delta) > max_delta:
            # Suggest delta hedge
            hedge_quantity = -net_delta
            suggestions.append({
                "type": "delta_hedge",
                "action": "SELL" if net_delta > 0 else "BUY",
                "quantity": abs(int(hedge_quantity)),
                "reason": f"Net delta {net_delta} exceeds limit {max_delta}"
            })
        
        # Check concentration risk
        symbol_exposure = {}
        for position in positions:
            exposure = position.entry_price * position.quantity
            symbol_exposure[position.symbol] = symbol_exposure.get(position.symbol, Decimal('0')) + exposure
        
        total_exposure = sum(symbol_exposure.values())
        max_concentration = risk_tolerance.get("max_concentration", Decimal('0.3'))
        
        for symbol, exposure in symbol_exposure.items():
            if total_exposure > 0:
                concentration = exposure / total_exposure
                if concentration > max_concentration:
                    suggestions.append({
                        "type": "reduce_concentration",
                        "symbol": symbol,
                        "current_concentration": float(concentration),
                        "target_concentration": float(max_concentration),
                        "reason": f"Concentration {concentration:.1%} exceeds limit {max_concentration:.1%}"
                    })
        
        return suggestions
    
    def calculate_stress_test(
        self,
        positions: List[Trade],
        scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Decimal]]:
        """Perform stress testing on portfolio"""
        results = {}
        
        for scenario in scenarios:
            scenario_name = scenario.get("name", "Unknown")
            price_shock = Decimal(str(scenario.get("price_shock", 0)))
            vol_shock = Decimal(str(scenario.get("vol_shock", 0)))
            
            scenario_pnl = Decimal('0')
            
            for position in positions:
                # Apply price shock
                shocked_price = position.entry_price * (1 + price_shock)
                
                if position.trade_type == TradeType.BUY:
                    position_pnl = (shocked_price - position.entry_price) * position.quantity
                else:
                    position_pnl = (position.entry_price - shocked_price) * position.quantity
                
                scenario_pnl += position_pnl
            
            results[scenario_name] = {
                "total_pnl": scenario_pnl,
                "price_shock": price_shock,
                "vol_shock": vol_shock
            }
        
        return results
    
    def is_risk_acceptable(
        self,
        risk_metrics: RiskMetrics,
        risk_limits: Dict[str, Decimal]
    ) -> bool:
        """Check if current risk levels are acceptable"""
        # Check max drawdown
        if risk_metrics.max_drawdown > risk_limits.get("max_drawdown", Decimal('20')):
            return False
        
        # Check VaR
        if risk_metrics.value_at_risk > risk_limits.get("max_var", Decimal('10000')):
            return False
        
        # Check exposure
        if risk_metrics.total_exposure > risk_limits.get("max_exposure", Decimal('1000000')):
            return False
        
        # Check margin usage
        margin_limit = risk_limits.get("max_margin_usage", Decimal('0.8'))
        if risk_metrics.margin_available > 0:
            margin_usage = risk_metrics.margin_used / (risk_metrics.margin_used + risk_metrics.margin_available)
            if margin_usage > margin_limit:
                return False
        
        return True
    
    def calculate_risk_adjusted_return(
        self,
        returns: Decimal,
        risk: Decimal
    ) -> Decimal:
        """Calculate risk-adjusted returns"""
        if risk == 0:
            return returns
        
        # Simple risk-adjusted return
        return returns / risk
    
    # Helper methods
    
    def _calculate_equity_curve(
        self,
        trades: List[Trade],
        initial_capital: Decimal
    ) -> List[Decimal]:
        """Calculate equity curve from trades"""
        equity_curve = [initial_capital]
        current_equity = initial_capital
        
        # Sort trades by entry time
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        
        for trade in sorted_trades:
            if trade.status == TradeStatus.CLOSED:
                pnl = trade.calculate_pnl()
                current_equity += pnl
                equity_curve.append(current_equity)
        
        return equity_curve
    
    def _calculate_max_drawdown_from_curve(
        self,
        equity_curve: List[Decimal]
    ) -> Decimal:
        """Calculate max drawdown from equity curve"""
        result = self.calculate_max_drawdown(equity_curve)
        return result["max_drawdown"]
    
    def _calculate_today_losses(
        self,
        positions: List[Trade]
    ) -> Decimal:
        """Calculate today's realized losses"""
        today = datetime.now().date()
        today_losses = Decimal('0')
        
        for position in positions:
            if position.exit_time and position.exit_time.date() == today:
                pnl = position.calculate_pnl()
                if pnl < 0:
                    today_losses += pnl
        
        return today_losses
    
    def _calculate_potential_loss(
        self,
        trade: Trade
    ) -> Decimal:
        """Calculate potential loss for a trade"""
        if trade.stop_loss:
            if trade.trade_type == TradeType.BUY:
                return (trade.entry_price - trade.stop_loss) * trade.quantity
            else:
                return (trade.stop_loss - trade.entry_price) * trade.quantity
        else:
            # No stop loss, assume full loss
            return trade.entry_price * trade.quantity
    
    def _calculate_required_margin(
        self,
        trade: Trade
    ) -> Decimal:
        """Calculate required margin for trade"""
        # Simplified margin calculation
        # In practice, would use broker-specific rules
        return trade.entry_price * trade.quantity * Decimal('0.2')  # 20% margin