"""
Risk Manager Service Interface
Domain service for risk management
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..entities.trade import Trade
from ..entities.option import Option
from ..entities.market_data import MarketData


class RiskMetrics:
    """Risk metrics data class"""
    def __init__(self):
        self.total_exposure: Decimal = Decimal('0')
        self.max_loss: Decimal = Decimal('0')
        self.value_at_risk: Decimal = Decimal('0')
        self.position_delta: Decimal = Decimal('0')
        self.position_gamma: Decimal = Decimal('0')
        self.position_theta: Decimal = Decimal('0')
        self.position_vega: Decimal = Decimal('0')
        self.margin_used: Decimal = Decimal('0')
        self.margin_available: Decimal = Decimal('0')
        self.risk_reward_ratio: Decimal = Decimal('0')
        self.sharpe_ratio: Optional[Decimal] = None
        self.max_drawdown: Decimal = Decimal('0')
        self.win_rate: Decimal = Decimal('0')


class PositionRisk:
    """Individual position risk"""
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.quantity: int = 0
        self.exposure: Decimal = Decimal('0')
        self.unrealized_pnl: Decimal = Decimal('0')
        self.realized_pnl: Decimal = Decimal('0')
        self.delta: Decimal = Decimal('0')
        self.gamma: Decimal = Decimal('0')
        self.theta: Decimal = Decimal('0')
        self.vega: Decimal = Decimal('0')
        self.max_loss: Decimal = Decimal('0')
        self.risk_percentage: Decimal = Decimal('0')


class IRiskManager(ABC):
    """Interface for risk management service"""
    
    @abstractmethod
    def calculate_position_risk(
        self,
        trade: Trade,
        current_price: Decimal,
        volatility: Optional[Decimal] = None
    ) -> PositionRisk:
        """Calculate risk for a single position"""
        pass
    
    @abstractmethod
    def calculate_portfolio_risk(
        self,
        trades: List[Trade],
        market_data: Dict[str, MarketData],
        total_capital: Decimal
    ) -> RiskMetrics:
        """Calculate overall portfolio risk metrics"""
        pass
    
    @abstractmethod
    def check_risk_limits(
        self,
        trade: Trade,
        current_positions: List[Trade],
        risk_parameters: Dict[str, Any]
    ) -> Dict[str, bool]:
        """Check if trade violates any risk limits"""
        pass
    
    @abstractmethod
    def calculate_position_size(
        self,
        capital: Decimal,
        risk_percentage: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        lot_size: int = 1
    ) -> int:
        """Calculate appropriate position size based on risk"""
        pass
    
    @abstractmethod
    def calculate_kelly_criterion(
        self,
        win_rate: Decimal,
        average_win: Decimal,
        average_loss: Decimal
    ) -> Decimal:
        """Calculate optimal position size using Kelly Criterion"""
        pass
    
    @abstractmethod
    def calculate_value_at_risk(
        self,
        positions: List[PositionRisk],
        confidence_level: Decimal = Decimal('0.95'),
        time_horizon: int = 1
    ) -> Decimal:
        """Calculate Value at Risk (VaR)"""
        pass
    
    @abstractmethod
    def calculate_expected_shortfall(
        self,
        positions: List[PositionRisk],
        confidence_level: Decimal = Decimal('0.95')
    ) -> Decimal:
        """Calculate Expected Shortfall (Conditional VaR)"""
        pass
    
    @abstractmethod
    def calculate_max_drawdown(
        self,
        equity_curve: List[Decimal]
    ) -> Dict[str, Any]:
        """Calculate maximum drawdown from equity curve"""
        pass
    
    @abstractmethod
    def calculate_sharpe_ratio(
        self,
        returns: List[Decimal],
        risk_free_rate: Decimal = Decimal('0.05')
    ) -> Decimal:
        """Calculate Sharpe ratio"""
        pass
    
    @abstractmethod
    def calculate_options_greeks_exposure(
        self,
        options_positions: List[Dict[str, Any]]
    ) -> Dict[str, Decimal]:
        """Calculate total Greeks exposure for options portfolio"""
        pass
    
    @abstractmethod
    def suggest_hedge(
        self,
        positions: List[Trade],
        risk_tolerance: Dict[str, Decimal]
    ) -> List[Dict[str, Any]]:
        """Suggest hedging strategies to reduce risk"""
        pass
    
    @abstractmethod
    def calculate_stress_test(
        self,
        positions: List[Trade],
        scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Decimal]]:
        """Perform stress testing on portfolio"""
        pass
    
    @abstractmethod
    def is_risk_acceptable(
        self,
        risk_metrics: RiskMetrics,
        risk_limits: Dict[str, Decimal]
    ) -> bool:
        """Check if current risk levels are acceptable"""
        pass
    
    @abstractmethod
    def calculate_risk_adjusted_return(
        self,
        returns: Decimal,
        risk: Decimal
    ) -> Decimal:
        """Calculate risk-adjusted returns"""
        pass