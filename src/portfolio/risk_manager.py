"""
Portfolio Risk Manager
Comprehensive risk management for portfolio-level trading
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
from scipy import stats
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

@dataclass
class RiskMetrics:
    """Portfolio risk metrics"""
    value_at_risk_95: float
    value_at_risk_99: float
    conditional_var_95: float
    expected_shortfall: float
    beta: float
    alpha: float
    treynor_ratio: float
    information_ratio: float
    downside_deviation: float
    upside_potential_ratio: float
    omega_ratio: float
    tail_ratio: float
    maximum_drawdown: float
    recovery_time: int
    risk_adjusted_return: float

@dataclass
class PositionRisk:
    """Individual position risk assessment"""
    symbol: str
    position_size: float
    current_value: float
    risk_contribution: float
    var_contribution: float
    marginal_var: float
    correlation_risk: float
    concentration_risk: float
    liquidity_risk: float
    stop_loss_distance: float
    risk_score: float

@dataclass 
class RiskLimits:
    """Risk limits for portfolio"""
    max_position_size: float = 0.1  # 10% max per position
    max_sector_exposure: float = 0.3  # 30% max per sector
    max_correlation: float = 0.7  # Max correlation between positions
    max_leverage: float = 2.0  # Maximum leverage
    max_var_95: float = 0.05  # 5% VaR limit
    max_drawdown: float = 0.15  # 15% max drawdown
    min_liquidity_ratio: float = 0.2  # 20% min cash
    max_concentration_score: float = 0.4  # HHI concentration limit

class PortfolioRiskManager:
    """Manages portfolio-level risk"""
    
    def __init__(self, 
                 initial_capital: float,
                 risk_limits: Optional[RiskLimits] = None):
        """
        Initialize risk manager
        
        Args:
            initial_capital: Starting portfolio capital
            risk_limits: Risk limit configuration
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_limits = risk_limits or RiskLimits()
        self.positions = {}
        self.historical_returns = []
        self.correlation_matrix = pd.DataFrame()
        self.risk_factors = {}
        
    def calculate_portfolio_risk(self,
                                positions: Dict[str, Any],
                                market_data: pd.DataFrame) -> RiskMetrics:
        """
        Calculate comprehensive portfolio risk metrics
        
        Args:
            positions: Current positions
            market_data: Historical market data
            
        Returns:
            RiskMetrics object
        """
        if not positions:
            return self._empty_risk_metrics()
            
        # Calculate returns
        returns = self._calculate_portfolio_returns(positions, market_data)
        
        # VaR and CVaR
        var_95 = self._calculate_var(returns, 0.95)
        var_99 = self._calculate_var(returns, 0.99)
        cvar_95 = self._calculate_cvar(returns, 0.95)
        expected_shortfall = self._calculate_expected_shortfall(returns, 0.95)
        
        # Greeks and ratios
        beta = self._calculate_beta(returns, market_data)
        alpha = self._calculate_alpha(returns, market_data, beta)
        treynor = self._calculate_treynor_ratio(returns, beta)
        info_ratio = self._calculate_information_ratio(returns, market_data)
        
        # Downside metrics
        downside_dev = self._calculate_downside_deviation(returns)
        upside_potential = self._calculate_upside_potential_ratio(returns)
        omega = self._calculate_omega_ratio(returns)
        tail_ratio = self._calculate_tail_ratio(returns)
        
        # Drawdown metrics
        max_dd, recovery = self._calculate_drawdown_metrics(returns)
        
        # Risk-adjusted return
        risk_adj_return = self._calculate_risk_adjusted_return(returns, var_95)
        
        return RiskMetrics(
            value_at_risk_95=var_95,
            value_at_risk_99=var_99,
            conditional_var_95=cvar_95,
            expected_shortfall=expected_shortfall,
            beta=beta,
            alpha=alpha,
            treynor_ratio=treynor,
            information_ratio=info_ratio,
            downside_deviation=downside_dev,
            upside_potential_ratio=upside_potential,
            omega_ratio=omega,
            tail_ratio=tail_ratio,
            maximum_drawdown=max_dd,
            recovery_time=recovery,
            risk_adjusted_return=risk_adj_return
        )
    
    def assess_position_risk(self,
                            position: Dict[str, Any],
                            portfolio_value: float) -> PositionRisk:
        """
        Assess risk for individual position
        
        Args:
            position: Position details
            portfolio_value: Total portfolio value
            
        Returns:
            PositionRisk assessment
        """
        symbol = position.get('symbol', 'UNKNOWN')
        position_size = position.get('quantity', 0)
        current_price = position.get('current_price', 0)
        current_value = position_size * current_price
        
        # Risk contribution
        risk_contribution = current_value / portfolio_value if portfolio_value > 0 else 0
        
        # VaR contribution (simplified)
        position_volatility = position.get('volatility', 0.02)
        var_contribution = current_value * position_volatility * 2.33  # 99% confidence
        marginal_var = var_contribution / portfolio_value if portfolio_value > 0 else 0
        
        # Correlation risk
        correlation_risk = self._calculate_correlation_risk(symbol)
        
        # Concentration risk (HHI)
        concentration_risk = (risk_contribution ** 2)
        
        # Liquidity risk
        avg_volume = position.get('avg_volume', 1000000)
        liquidity_risk = position_size / avg_volume if avg_volume > 0 else 1
        
        # Stop loss distance
        stop_loss = position.get('stop_loss', current_price * 0.98)
        stop_loss_distance = abs(current_price - stop_loss) / current_price
        
        # Overall risk score (0-100)
        risk_score = self._calculate_position_risk_score(
            risk_contribution,
            marginal_var,
            correlation_risk,
            concentration_risk,
            liquidity_risk,
            stop_loss_distance
        )
        
        return PositionRisk(
            symbol=symbol,
            position_size=position_size,
            current_value=current_value,
            risk_contribution=risk_contribution,
            var_contribution=var_contribution,
            marginal_var=marginal_var,
            correlation_risk=correlation_risk,
            concentration_risk=concentration_risk,
            liquidity_risk=liquidity_risk,
            stop_loss_distance=stop_loss_distance,
            risk_score=risk_score
        )
    
    def check_risk_limits(self,
                         positions: Dict[str, Any],
                         new_position: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        """
        Check if portfolio meets risk limits
        
        Args:
            positions: Current positions
            new_position: Optional new position to add
            
        Returns:
            Tuple of (is_within_limits, list_of_violations)
        """
        violations = []
        
        # Include new position if provided
        test_positions = positions.copy()
        if new_position:
            test_positions[new_position['symbol']] = new_position
            
        portfolio_value = sum(p.get('value', 0) for p in test_positions.values())
        
        # Check position size limits
        for symbol, pos in test_positions.items():
            position_weight = pos.get('value', 0) / portfolio_value if portfolio_value > 0 else 0
            if position_weight > self.risk_limits.max_position_size:
                violations.append(f"Position size limit exceeded for {symbol}: {position_weight:.2%}")
                
        # Check concentration
        concentration = self._calculate_concentration(test_positions)
        if concentration > self.risk_limits.max_concentration_score:
            violations.append(f"Concentration limit exceeded: {concentration:.2f}")
            
        # Check correlation
        max_corr = self._get_max_correlation(test_positions)
        if max_corr > self.risk_limits.max_correlation:
            violations.append(f"Correlation limit exceeded: {max_corr:.2f}")
            
        # Check leverage
        leverage = self._calculate_leverage(test_positions)
        if leverage > self.risk_limits.max_leverage:
            violations.append(f"Leverage limit exceeded: {leverage:.2f}")
            
        # Check VaR
        if self.historical_returns:
            var_95 = self._calculate_var(self.historical_returns, 0.95)
            if abs(var_95) > self.risk_limits.max_var_95:
                violations.append(f"VaR limit exceeded: {var_95:.2%}")
                
        # Check liquidity
        cash_ratio = self.current_capital / portfolio_value if portfolio_value > 0 else 1
        if cash_ratio < self.risk_limits.min_liquidity_ratio:
            violations.append(f"Liquidity below minimum: {cash_ratio:.2%}")
            
        return len(violations) == 0, violations
    
    def optimize_position_sizes(self,
                              signals: List[Dict],
                              available_capital: float,
                              method: str = 'min_variance') -> Dict[str, float]:
        """
        Optimize position sizes based on risk
        
        Args:
            signals: List of trading signals
            available_capital: Capital available for allocation
            method: Optimization method
            
        Returns:
            Dictionary of optimal position sizes
        """
        if not signals:
            return {}
            
        n = len(signals)
        
        # Expected returns and covariance
        expected_returns = np.array([s.get('expected_return', 0.01) for s in signals])
        
        # Build covariance matrix (simplified - would use historical data)
        cov_matrix = self._estimate_covariance_matrix(signals)
        
        # Optimization constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0},  # Weights sum to 1
        ]
        
        # Bounds (0 to max position size)
        bounds = tuple((0, self.risk_limits.max_position_size) for _ in range(n))
        
        # Initial guess (equal weight)
        x0 = np.array([1.0/n] * n)
        
        if method == 'min_variance':
            # Minimize portfolio variance
            objective = lambda x: np.dot(x.T, np.dot(cov_matrix, x))
            
        elif method == 'max_sharpe':
            # Maximize Sharpe ratio
            risk_free_rate = 0.05 / 252  # Daily risk-free rate
            objective = lambda x: -(np.dot(x, expected_returns) - risk_free_rate) / \
                                  np.sqrt(np.dot(x.T, np.dot(cov_matrix, x)))
                                  
        elif method == 'risk_parity':
            # Risk parity allocation
            objective = lambda x: self._risk_parity_objective(x, cov_matrix)
            
        else:
            # Default to equal weight
            return {signals[i]['symbol']: available_capital/n for i in range(n)}
            
        # Optimize
        result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints)
        
        if result.success:
            weights = result.x
        else:
            logger.warning("Optimization failed, using equal weights")
            weights = x0
            
        # Convert to position sizes
        position_sizes = {}
        for i, signal in enumerate(signals):
            position_sizes[signal['symbol']] = available_capital * weights[i]
            
        return position_sizes
    
    def calculate_stress_scenarios(self,
                                  positions: Dict[str, Any]) -> Dict[str, Dict]:
        """
        Calculate portfolio impact under stress scenarios
        
        Args:
            positions: Current positions
            
        Returns:
            Dictionary of scenario results
        """
        scenarios = {}
        base_value = sum(p.get('value', 0) for p in positions.values())
        
        # Market crash scenario (-20%)
        scenarios['market_crash'] = self._stress_scenario(
            positions, 
            market_shock=-0.20,
            volatility_multiplier=2.0
        )
        
        # Flash crash scenario (-10% instant)
        scenarios['flash_crash'] = self._stress_scenario(
            positions,
            market_shock=-0.10,
            volatility_multiplier=3.0
        )
        
        # Volatility spike scenario
        scenarios['vol_spike'] = self._stress_scenario(
            positions,
            market_shock=0,
            volatility_multiplier=3.0
        )
        
        # Correlation breakdown
        scenarios['correlation_breakdown'] = self._stress_scenario(
            positions,
            market_shock=-0.05,
            correlation_shock=0.9
        )
        
        # Liquidity crisis
        scenarios['liquidity_crisis'] = self._stress_scenario(
            positions,
            market_shock=-0.15,
            liquidity_discount=0.10
        )
        
        # Calculate worst case
        worst_losses = [s['total_loss'] for s in scenarios.values()]
        scenarios['worst_case'] = {
            'total_loss': min(worst_losses),
            'percentage_loss': min(worst_losses) / base_value if base_value > 0 else 0,
            'survival_probability': self._calculate_survival_probability(min(worst_losses))
        }
        
        return scenarios
    
    def _calculate_var(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Value at Risk"""
        if len(returns) == 0:
            return 0
        return np.percentile(returns, (1 - confidence) * 100)
    
    def _calculate_cvar(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Conditional Value at Risk"""
        var = self._calculate_var(returns, confidence)
        return returns[returns <= var].mean() if len(returns[returns <= var]) > 0 else var
    
    def _calculate_expected_shortfall(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Expected Shortfall"""
        var = self._calculate_var(returns, confidence)
        tail_losses = returns[returns <= var]
        return tail_losses.mean() if len(tail_losses) > 0 else var
    
    def _calculate_beta(self, returns: np.ndarray, market_data: pd.DataFrame) -> float:
        """Calculate portfolio beta"""
        if len(returns) < 2:
            return 1.0
            
        # Use NIFTY as market proxy
        market_returns = market_data['Close'].pct_change().dropna().values[-len(returns):]
        
        if len(market_returns) != len(returns):
            return 1.0
            
        covariance = np.cov(returns, market_returns)[0, 1]
        market_variance = np.var(market_returns)
        
        return covariance / market_variance if market_variance > 0 else 1.0
    
    def _calculate_alpha(self, returns: np.ndarray, market_data: pd.DataFrame, beta: float) -> float:
        """Calculate portfolio alpha"""
        if len(returns) < 2:
            return 0
            
        risk_free_rate = 0.05 / 252  # Daily risk-free rate
        market_returns = market_data['Close'].pct_change().dropna().values[-len(returns):]
        
        if len(market_returns) != len(returns):
            return 0
            
        portfolio_return = returns.mean()
        market_return = market_returns.mean()
        
        return portfolio_return - (risk_free_rate + beta * (market_return - risk_free_rate))
    
    def _calculate_treynor_ratio(self, returns: np.ndarray, beta: float) -> float:
        """Calculate Treynor ratio"""
        if beta == 0:
            return 0
            
        risk_free_rate = 0.05 / 252
        excess_return = returns.mean() - risk_free_rate
        
        return excess_return / beta
    
    def _calculate_information_ratio(self, returns: np.ndarray, market_data: pd.DataFrame) -> float:
        """Calculate Information ratio"""
        if len(returns) < 2:
            return 0
            
        market_returns = market_data['Close'].pct_change().dropna().values[-len(returns):]
        
        if len(market_returns) != len(returns):
            return 0
            
        active_returns = returns - market_returns
        
        if active_returns.std() == 0:
            return 0
            
        return active_returns.mean() / active_returns.std()
    
    def _calculate_downside_deviation(self, returns: np.ndarray, target: float = 0) -> float:
        """Calculate downside deviation"""
        downside_returns = returns[returns < target]
        
        if len(downside_returns) == 0:
            return 0
            
        return np.sqrt(np.mean((downside_returns - target) ** 2))
    
    def _calculate_upside_potential_ratio(self, returns: np.ndarray, target: float = 0) -> float:
        """Calculate upside potential ratio"""
        upside = returns[returns > target] - target
        downside = target - returns[returns < target]
        
        if len(downside) == 0 or downside.sum() == 0:
            return float('inf') if len(upside) > 0 else 0
            
        return upside.sum() / downside.sum()
    
    def _calculate_omega_ratio(self, returns: np.ndarray, threshold: float = 0) -> float:
        """Calculate Omega ratio"""
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns <= threshold]
        
        if losses.sum() == 0:
            return float('inf') if gains.sum() > 0 else 1
            
        return gains.sum() / losses.sum()
    
    def _calculate_tail_ratio(self, returns: np.ndarray, percentile: float = 0.05) -> float:
        """Calculate tail ratio"""
        right_tail = np.percentile(returns, 100 * (1 - percentile))
        left_tail = abs(np.percentile(returns, 100 * percentile))
        
        if left_tail == 0:
            return float('inf') if right_tail > 0 else 0
            
        return right_tail / left_tail
    
    def _calculate_drawdown_metrics(self, returns: np.ndarray) -> Tuple[float, int]:
        """Calculate maximum drawdown and recovery time"""
        if len(returns) == 0:
            return 0, 0
            
        cumulative = (1 + returns).cumprod()
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        
        max_drawdown = abs(drawdown.min())
        
        # Recovery time (simplified)
        if max_drawdown > 0:
            drawdown_idx = drawdown.argmin()
            recovery_idx = np.where(cumulative[drawdown_idx:] >= running_max[drawdown_idx])[0]
            recovery_time = recovery_idx[0] if len(recovery_idx) > 0 else len(returns) - drawdown_idx
        else:
            recovery_time = 0
            
        return max_drawdown, recovery_time
    
    def _calculate_risk_adjusted_return(self, returns: np.ndarray, var_95: float) -> float:
        """Calculate risk-adjusted return"""
        if var_95 == 0:
            return 0
            
        return returns.mean() / abs(var_95)
    
    def _calculate_portfolio_returns(self, positions: Dict, market_data: pd.DataFrame) -> np.ndarray:
        """Calculate portfolio returns from positions"""
        # Simplified - would use actual position data
        returns = []
        
        for date in market_data.index[-252:]:  # Last year
            daily_return = np.random.normal(0.001, 0.02)  # Placeholder
            returns.append(daily_return)
            
        return np.array(returns)
    
    def _calculate_correlation_risk(self, symbol: str) -> float:
        """Calculate correlation risk for a symbol"""
        if self.correlation_matrix.empty:
            return 0
            
        if symbol in self.correlation_matrix.columns:
            correlations = self.correlation_matrix[symbol].abs()
            return correlations[correlations.index != symbol].mean()
        
        return 0
    
    def _calculate_position_risk_score(self, *args) -> float:
        """Calculate overall risk score for position"""
        # Weight different risk factors
        weights = [0.2, 0.2, 0.15, 0.15, 0.15, 0.15]
        risk_factors = args[:6]
        
        # Normalize and weight
        score = sum(w * min(f, 1) for w, f in zip(weights, risk_factors))
        
        return min(score * 100, 100)
    
    def _calculate_concentration(self, positions: Dict) -> float:
        """Calculate portfolio concentration (HHI)"""
        if not positions:
            return 0
            
        total_value = sum(p.get('value', 0) for p in positions.values())
        
        if total_value == 0:
            return 0
            
        weights = [p.get('value', 0) / total_value for p in positions.values()]
        
        return sum(w ** 2 for w in weights)
    
    def _get_max_correlation(self, positions: Dict) -> float:
        """Get maximum correlation between positions"""
        if len(positions) < 2:
            return 0
            
        # Simplified - would use actual correlation matrix
        return 0.5
    
    def _calculate_leverage(self, positions: Dict) -> float:
        """Calculate portfolio leverage"""
        total_exposure = sum(abs(p.get('value', 0)) for p in positions.values())
        
        return total_exposure / self.current_capital if self.current_capital > 0 else 0
    
    def _estimate_covariance_matrix(self, signals: List[Dict]) -> np.ndarray:
        """Estimate covariance matrix for signals"""
        n = len(signals)
        
        # Simplified - would use historical data
        cov_matrix = np.eye(n) * 0.04  # 20% volatility squared
        
        # Add some correlation
        for i in range(n):
            for j in range(n):
                if i != j:
                    cov_matrix[i, j] = 0.01  # Low correlation
                    
        return cov_matrix
    
    def _risk_parity_objective(self, weights: np.ndarray, cov_matrix: np.ndarray) -> float:
        """Risk parity optimization objective"""
        portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        
        marginal_contrib = np.dot(cov_matrix, weights) / portfolio_vol
        contrib = weights * marginal_contrib
        
        # Want equal risk contribution
        target_contrib = portfolio_vol / len(weights)
        
        return np.sum((contrib - target_contrib) ** 2)
    
    def _stress_scenario(self,
                        positions: Dict,
                        market_shock: float = 0,
                        volatility_multiplier: float = 1,
                        correlation_shock: float = 0,
                        liquidity_discount: float = 0) -> Dict:
        """Run stress scenario on portfolio"""
        total_loss = 0
        stressed_positions = {}
        
        for symbol, pos in positions.items():
            current_value = pos.get('value', 0)
            
            # Apply market shock
            shocked_value = current_value * (1 + market_shock)
            
            # Apply volatility impact
            vol_impact = current_value * 0.02 * (volatility_multiplier - 1)
            shocked_value -= vol_impact
            
            # Apply liquidity discount
            shocked_value *= (1 - liquidity_discount)
            
            loss = current_value - shocked_value
            total_loss += loss
            
            stressed_positions[symbol] = {
                'original_value': current_value,
                'stressed_value': shocked_value,
                'loss': loss
            }
            
        return {
            'total_loss': total_loss,
            'percentage_loss': total_loss / sum(p.get('value', 0) for p in positions.values()),
            'stressed_positions': stressed_positions
        }
    
    def _calculate_survival_probability(self, loss: float) -> float:
        """Calculate probability of surviving loss"""
        if loss >= self.current_capital:
            return 0
            
        return 1 - (abs(loss) / self.current_capital)
    
    def _empty_risk_metrics(self) -> RiskMetrics:
        """Return empty risk metrics"""
        return RiskMetrics(
            value_at_risk_95=0,
            value_at_risk_99=0,
            conditional_var_95=0,
            expected_shortfall=0,
            beta=1,
            alpha=0,
            treynor_ratio=0,
            information_ratio=0,
            downside_deviation=0,
            upside_potential_ratio=0,
            omega_ratio=1,
            tail_ratio=1,
            maximum_drawdown=0,
            recovery_time=0,
            risk_adjusted_return=0
        )