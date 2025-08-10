"""
Portfolio Optimizer Module
Advanced portfolio optimization techniques for trading strategies
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
from scipy.optimize import minimize, differential_evolution
from scipy import stats
import cvxpy as cp
from pypfopt import EfficientFrontier, risk_models, expected_returns
from pypfopt import HRPOpt, BlackLittermanModel, objective_functions
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

@dataclass
class OptimizationConstraints:
    """Portfolio optimization constraints"""
    min_weight: float = 0.0
    max_weight: float = 0.3
    max_positions: int = 10
    target_return: Optional[float] = None
    max_risk: Optional[float] = None
    leverage_limit: float = 1.0
    sector_limits: Dict[str, float] = field(default_factory=dict)
    correlation_limit: float = 0.7

@dataclass
class OptimizationResult:
    """Optimization result"""
    weights: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    diversification_ratio: float
    effective_n: float
    optimization_method: str
    convergence_status: bool

class PortfolioOptimizer:
    """Advanced portfolio optimization"""
    
    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize portfolio optimizer
        
        Args:
            risk_free_rate: Annual risk-free rate
        """
        self.risk_free_rate = risk_free_rate
        self.returns_data = None
        self.cov_matrix = None
        self.expected_returns = None
        
    def optimize(self,
                returns: pd.DataFrame,
                method: str = 'mean_variance',
                constraints: Optional[OptimizationConstraints] = None,
                views: Optional[Dict[str, float]] = None) -> OptimizationResult:
        """
        Optimize portfolio allocation
        
        Args:
            returns: Historical returns DataFrame
            method: Optimization method
            constraints: Optimization constraints
            views: Black-Litterman views (optional)
            
        Returns:
            OptimizationResult object
        """
        self.returns_data = returns
        constraints = constraints or OptimizationConstraints()
        
        # Calculate expected returns and covariance
        self._prepare_optimization_inputs(views)
        
        # Select optimization method
        if method == 'mean_variance':
            result = self._mean_variance_optimization(constraints)
        elif method == 'minimum_variance':
            result = self._minimum_variance_optimization(constraints)
        elif method == 'maximum_sharpe':
            result = self._maximum_sharpe_optimization(constraints)
        elif method == 'risk_parity':
            result = self._risk_parity_optimization(constraints)
        elif method == 'hierarchical_risk_parity':
            result = self._hierarchical_risk_parity(constraints)
        elif method == 'black_litterman':
            result = self._black_litterman_optimization(constraints, views)
        elif method == 'kelly':
            result = self._kelly_optimization(constraints)
        elif method == 'cvar':
            result = self._cvar_optimization(constraints)
        elif method == 'max_diversification':
            result = self._max_diversification_optimization(constraints)
        elif method == 'equal_weight':
            result = self._equal_weight_optimization()
        else:
            raise ValueError(f"Unknown optimization method: {method}")
            
        # Calculate portfolio metrics
        result = self._calculate_portfolio_metrics(result, method)
        
        return result
        
    def efficient_frontier(self,
                          returns: pd.DataFrame,
                          n_portfolios: int = 100) -> pd.DataFrame:
        """
        Calculate efficient frontier
        
        Args:
            returns: Historical returns
            n_portfolios: Number of portfolios on frontier
            
        Returns:
            DataFrame with frontier portfolios
        """
        self.returns_data = returns
        self._prepare_optimization_inputs()
        
        # Use pypfopt for efficient frontier
        ef = EfficientFrontier(self.expected_returns, self.cov_matrix)
        
        frontier_portfolios = []
        
        # Generate frontier by varying target return
        min_ret = self.expected_returns.min()
        max_ret = self.expected_returns.max()
        target_returns = np.linspace(min_ret, max_ret, n_portfolios)
        
        for target_return in target_returns:
            try:
                ef = EfficientFrontier(self.expected_returns, self.cov_matrix)
                ef.efficient_return(target_return)
                weights = ef.clean_weights()
                
                portfolio_return = self._calculate_return(weights)
                portfolio_risk = self._calculate_risk(weights)
                sharpe = (portfolio_return - self.risk_free_rate) / portfolio_risk
                
                frontier_portfolios.append({
                    'return': portfolio_return,
                    'risk': portfolio_risk,
                    'sharpe': sharpe,
                    'weights': weights
                })
            except:
                continue
                
        return pd.DataFrame(frontier_portfolios)
        
    def monte_carlo_optimization(self,
                                returns: pd.DataFrame,
                                n_simulations: int = 10000,
                                constraints: Optional[OptimizationConstraints] = None) -> OptimizationResult:
        """
        Monte Carlo portfolio optimization
        
        Args:
            returns: Historical returns
            n_simulations: Number of simulations
            constraints: Optimization constraints
            
        Returns:
            Best portfolio from simulations
        """
        self.returns_data = returns
        self._prepare_optimization_inputs()
        constraints = constraints or OptimizationConstraints()
        
        n_assets = len(returns.columns)
        results = []
        
        for _ in range(n_simulations):
            # Generate random weights
            weights = np.random.random(n_assets)
            weights = weights / weights.sum()
            
            # Apply constraints
            weights = self._apply_weight_constraints(weights, constraints)
            
            # Calculate metrics
            weights_dict = dict(zip(returns.columns, weights))
            portfolio_return = self._calculate_return(weights_dict)
            portfolio_risk = self._calculate_risk(weights_dict)
            sharpe = (portfolio_return - self.risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0
            
            results.append({
                'weights': weights_dict,
                'return': portfolio_return,
                'risk': portfolio_risk,
                'sharpe': sharpe
            })
            
        # Find best portfolio (highest Sharpe)
        best_portfolio = max(results, key=lambda x: x['sharpe'])
        
        return OptimizationResult(
            weights=best_portfolio['weights'],
            expected_return=best_portfolio['return'],
            expected_risk=best_portfolio['risk'],
            sharpe_ratio=best_portfolio['sharpe'],
            sortino_ratio=0,  # Will be calculated
            max_drawdown=0,  # Will be calculated
            diversification_ratio=0,  # Will be calculated
            effective_n=0,  # Will be calculated
            optimization_method='monte_carlo',
            convergence_status=True
        )
        
    def genetic_algorithm_optimization(self,
                                      returns: pd.DataFrame,
                                      population_size: int = 100,
                                      generations: int = 500,
                                      constraints: Optional[OptimizationConstraints] = None) -> OptimizationResult:
        """
        Genetic algorithm portfolio optimization
        
        Args:
            returns: Historical returns
            population_size: GA population size
            generations: Number of generations
            constraints: Optimization constraints
            
        Returns:
            Optimized portfolio
        """
        self.returns_data = returns
        self._prepare_optimization_inputs()
        constraints = constraints or OptimizationConstraints()
        
        n_assets = len(returns.columns)
        
        def fitness_function(weights):
            # Normalize weights
            weights = weights / weights.sum()
            weights_dict = dict(zip(returns.columns, weights))
            
            # Calculate Sharpe ratio (negative for minimization)
            portfolio_return = self._calculate_return(weights_dict)
            portfolio_risk = self._calculate_risk(weights_dict)
            
            if portfolio_risk == 0:
                return 1e10
                
            sharpe = (portfolio_return - self.risk_free_rate) / portfolio_risk
            return -sharpe  # Negative because we minimize
            
        # Bounds for weights
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n_assets)]
        
        # Run differential evolution
        result = differential_evolution(
            fitness_function,
            bounds,
            strategy='best1bin',
            popsize=population_size,
            maxiter=generations,
            tol=1e-7,
            atol=1e-7,
            disp=False
        )
        
        # Normalize final weights
        weights = result.x / result.x.sum()
        weights_dict = dict(zip(returns.columns, weights))
        
        return OptimizationResult(
            weights=weights_dict,
            expected_return=self._calculate_return(weights_dict),
            expected_risk=self._calculate_risk(weights_dict),
            sharpe_ratio=-result.fun,  # Convert back from negative
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=0,
            effective_n=0,
            optimization_method='genetic_algorithm',
            convergence_status=result.success
        )
        
    def _prepare_optimization_inputs(self, views: Optional[Dict[str, float]] = None):
        """Prepare optimization inputs"""
        # Calculate expected returns
        self.expected_returns = expected_returns.mean_historical_return(self.returns_data)
        
        # Calculate covariance matrix
        self.cov_matrix = risk_models.sample_cov(self.returns_data)
        
        # Apply Black-Litterman if views provided
        if views:
            bl = BlackLittermanModel(
                self.cov_matrix,
                pi=self.expected_returns,
                absolute_views=views
            )
            self.expected_returns = bl.bl_returns()
            self.cov_matrix = bl.bl_cov()
            
    def _mean_variance_optimization(self, constraints: OptimizationConstraints) -> OptimizationResult:
        """Mean-variance optimization"""
        ef = EfficientFrontier(self.expected_returns, self.cov_matrix)
        
        # Apply constraints
        ef.add_constraint(lambda w: w >= constraints.min_weight)
        ef.add_constraint(lambda w: w <= constraints.max_weight)
        
        if constraints.target_return:
            ef.efficient_return(constraints.target_return)
        else:
            ef.max_sharpe(risk_free_rate=self.risk_free_rate)
            
        weights = ef.clean_weights()
        
        return OptimizationResult(
            weights=weights,
            expected_return=0,
            expected_risk=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=0,
            effective_n=0,
            optimization_method='mean_variance',
            convergence_status=True
        )
        
    def _minimum_variance_optimization(self, constraints: OptimizationConstraints) -> OptimizationResult:
        """Minimum variance optimization"""
        ef = EfficientFrontier(self.expected_returns, self.cov_matrix)
        
        ef.add_constraint(lambda w: w >= constraints.min_weight)
        ef.add_constraint(lambda w: w <= constraints.max_weight)
        
        ef.min_volatility()
        weights = ef.clean_weights()
        
        return OptimizationResult(
            weights=weights,
            expected_return=0,
            expected_risk=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=0,
            effective_n=0,
            optimization_method='minimum_variance',
            convergence_status=True
        )
        
    def _maximum_sharpe_optimization(self, constraints: OptimizationConstraints) -> OptimizationResult:
        """Maximum Sharpe ratio optimization"""
        ef = EfficientFrontier(self.expected_returns, self.cov_matrix)
        
        ef.add_constraint(lambda w: w >= constraints.min_weight)
        ef.add_constraint(lambda w: w <= constraints.max_weight)
        
        ef.max_sharpe(risk_free_rate=self.risk_free_rate)
        weights = ef.clean_weights()
        
        return OptimizationResult(
            weights=weights,
            expected_return=0,
            expected_risk=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=0,
            effective_n=0,
            optimization_method='maximum_sharpe',
            convergence_status=True
        )
        
    def _risk_parity_optimization(self, constraints: OptimizationConstraints) -> OptimizationResult:
        """Risk parity optimization"""
        n_assets = len(self.expected_returns)
        
        def risk_parity_objective(weights):
            portfolio_vol = np.sqrt(weights @ self.cov_matrix @ weights)
            marginal_contrib = self.cov_matrix @ weights / portfolio_vol
            contrib = weights * marginal_contrib
            target_contrib = portfolio_vol / n_assets
            return np.sum((contrib - target_contrib) ** 2)
            
        # Initial guess
        x0 = np.ones(n_assets) / n_assets
        
        # Bounds
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n_assets)]
        
        # Constraints
        cons = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}
        
        # Optimize
        result = minimize(
            risk_parity_objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        weights = dict(zip(self.expected_returns.index, result.x))
        
        return OptimizationResult(
            weights=weights,
            expected_return=0,
            expected_risk=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=0,
            effective_n=0,
            optimization_method='risk_parity',
            convergence_status=result.success
        )
        
    def _hierarchical_risk_parity(self, constraints: OptimizationConstraints) -> OptimizationResult:
        """Hierarchical risk parity optimization"""
        hrp = HRPOpt(self.returns_data)
        weights = hrp.optimize()
        
        # Apply constraints
        weights = self._apply_constraints_to_weights(weights, constraints)
        
        return OptimizationResult(
            weights=weights,
            expected_return=0,
            expected_risk=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=0,
            effective_n=0,
            optimization_method='hierarchical_risk_parity',
            convergence_status=True
        )
        
    def _black_litterman_optimization(self, 
                                     constraints: OptimizationConstraints,
                                     views: Optional[Dict[str, float]]) -> OptimizationResult:
        """Black-Litterman optimization"""
        # Already applied in _prepare_optimization_inputs if views provided
        return self._mean_variance_optimization(constraints)
        
    def _kelly_optimization(self, constraints: OptimizationConstraints) -> OptimizationResult:
        """Kelly criterion optimization"""
        n_assets = len(self.expected_returns)
        
        def kelly_objective(weights):
            portfolio_return = weights @ self.expected_returns
            portfolio_variance = weights @ self.cov_matrix @ weights
            
            # Kelly criterion (simplified)
            kelly = portfolio_return / portfolio_variance if portfolio_variance > 0 else 0
            return -kelly  # Negative for maximization
            
        # Initial guess
        x0 = np.ones(n_assets) / n_assets
        
        # Bounds
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n_assets)]
        
        # Constraints
        cons = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}
        
        # Optimize
        result = minimize(
            kelly_objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        # Apply Kelly fraction (typically 25% of full Kelly)
        weights = result.x * 0.25
        weights = weights / weights.sum()
        weights_dict = dict(zip(self.expected_returns.index, weights))
        
        return OptimizationResult(
            weights=weights_dict,
            expected_return=0,
            expected_risk=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=0,
            effective_n=0,
            optimization_method='kelly',
            convergence_status=result.success
        )
        
    def _cvar_optimization(self, constraints: OptimizationConstraints, alpha: float = 0.95) -> OptimizationResult:
        """Conditional Value at Risk (CVaR) optimization"""
        returns_matrix = self.returns_data.values
        n_assets = returns_matrix.shape[1]
        n_scenarios = returns_matrix.shape[0]
        
        # CVX optimization
        w = cp.Variable(n_assets)
        z = cp.Variable(n_scenarios)
        zeta = cp.Variable()
        
        # Portfolio returns for each scenario
        portfolio_returns = returns_matrix @ w
        
        # CVaR formulation
        cvar = zeta + (1.0 / (n_scenarios * (1 - alpha))) * cp.sum(z)
        
        # Constraints
        constraints_list = [
            z >= 0,
            z >= -portfolio_returns - zeta,
            cp.sum(w) == 1,
            w >= constraints.min_weight,
            w <= constraints.max_weight
        ]
        
        # Objective: minimize CVaR
        objective = cp.Minimize(cvar)
        
        # Solve
        prob = cp.Problem(objective, constraints_list)
        prob.solve(solver=cp.OSQP)
        
        weights = dict(zip(self.returns_data.columns, w.value))
        
        return OptimizationResult(
            weights=weights,
            expected_return=0,
            expected_risk=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=0,
            effective_n=0,
            optimization_method='cvar',
            convergence_status=prob.status == 'optimal'
        )
        
    def _max_diversification_optimization(self, constraints: OptimizationConstraints) -> OptimizationResult:
        """Maximum diversification ratio optimization"""
        n_assets = len(self.expected_returns)
        asset_vols = np.sqrt(np.diag(self.cov_matrix))
        
        def diversification_ratio(weights):
            weighted_avg_vol = weights @ asset_vols
            portfolio_vol = np.sqrt(weights @ self.cov_matrix @ weights)
            return -weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 0
            
        # Initial guess
        x0 = np.ones(n_assets) / n_assets
        
        # Bounds
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n_assets)]
        
        # Constraints
        cons = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}
        
        # Optimize
        result = minimize(
            diversification_ratio,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        weights = dict(zip(self.expected_returns.index, result.x))
        
        return OptimizationResult(
            weights=weights,
            expected_return=0,
            expected_risk=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=-result.fun,
            effective_n=0,
            optimization_method='max_diversification',
            convergence_status=result.success
        )
        
    def _equal_weight_optimization(self) -> OptimizationResult:
        """Equal weight portfolio"""
        n_assets = len(self.expected_returns)
        weights = dict(zip(self.expected_returns.index, [1/n_assets] * n_assets))
        
        return OptimizationResult(
            weights=weights,
            expected_return=0,
            expected_risk=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            diversification_ratio=0,
            effective_n=n_assets,
            optimization_method='equal_weight',
            convergence_status=True
        )
        
    def _calculate_portfolio_metrics(self, result: OptimizationResult, method: str) -> OptimizationResult:
        """Calculate all portfolio metrics"""
        weights = result.weights
        
        # Expected return and risk
        result.expected_return = self._calculate_return(weights)
        result.expected_risk = self._calculate_risk(weights)
        
        # Sharpe ratio
        if result.expected_risk > 0:
            result.sharpe_ratio = (result.expected_return - self.risk_free_rate) / result.expected_risk
            
        # Sortino ratio
        result.sortino_ratio = self._calculate_sortino(weights)
        
        # Max drawdown
        result.max_drawdown = self._calculate_max_drawdown(weights)
        
        # Diversification ratio
        if result.diversification_ratio == 0:
            result.diversification_ratio = self._calculate_diversification_ratio(weights)
            
        # Effective N
        result.effective_n = self._calculate_effective_n(weights)
        
        result.optimization_method = method
        
        return result
        
    def _calculate_return(self, weights: Dict[str, float]) -> float:
        """Calculate portfolio expected return"""
        weights_array = np.array([weights.get(asset, 0) for asset in self.expected_returns.index])
        return float(weights_array @ self.expected_returns)
        
    def _calculate_risk(self, weights: Dict[str, float]) -> float:
        """Calculate portfolio risk (volatility)"""
        weights_array = np.array([weights.get(asset, 0) for asset in self.expected_returns.index])
        return float(np.sqrt(weights_array @ self.cov_matrix @ weights_array))
        
    def _calculate_sortino(self, weights: Dict[str, float], target: float = 0) -> float:
        """Calculate Sortino ratio"""
        weights_array = np.array([weights.get(asset, 0) for asset in self.returns_data.columns])
        portfolio_returns = self.returns_data @ weights_array
        
        downside_returns = portfolio_returns[portfolio_returns < target]
        
        if len(downside_returns) == 0:
            return float('inf') if portfolio_returns.mean() > target else 0
            
        downside_std = np.sqrt(np.mean((downside_returns - target) ** 2))
        
        if downside_std == 0:
            return 0
            
        return (portfolio_returns.mean() - target) / downside_std * np.sqrt(252)
        
    def _calculate_max_drawdown(self, weights: Dict[str, float]) -> float:
        """Calculate maximum drawdown"""
        weights_array = np.array([weights.get(asset, 0) for asset in self.returns_data.columns])
        portfolio_returns = self.returns_data @ weights_array
        
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        
        return abs(drawdown.min())
        
    def _calculate_diversification_ratio(self, weights: Dict[str, float]) -> float:
        """Calculate diversification ratio"""
        weights_array = np.array([weights.get(asset, 0) for asset in self.expected_returns.index])
        asset_vols = np.sqrt(np.diag(self.cov_matrix))
        
        weighted_avg_vol = weights_array @ asset_vols
        portfolio_vol = np.sqrt(weights_array @ self.cov_matrix @ weights_array)
        
        return weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 0
        
    def _calculate_effective_n(self, weights: Dict[str, float]) -> float:
        """Calculate effective number of assets (inverse HHI)"""
        weights_array = np.array(list(weights.values()))
        hhi = np.sum(weights_array ** 2)
        return 1 / hhi if hhi > 0 else 0
        
    def _apply_weight_constraints(self, weights: np.ndarray, constraints: OptimizationConstraints) -> np.ndarray:
        """Apply constraints to weights"""
        # Min/max weight constraints
        weights = np.clip(weights, constraints.min_weight, constraints.max_weight)
        
        # Normalize
        weights = weights / weights.sum()
        
        return weights
        
    def _apply_constraints_to_weights(self, weights: Dict[str, float], constraints: OptimizationConstraints) -> Dict[str, float]:
        """Apply constraints to weight dictionary"""
        # Apply min/max constraints
        for asset in weights:
            weights[asset] = max(constraints.min_weight, min(constraints.max_weight, weights[asset]))
            
        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}
            
        return weights