"""
Backtest Engine Interface
Application interface for backtesting engine
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import date, datetime
from decimal import Decimal


class IBacktestEngine(ABC):
    """Interface for backtest execution engine"""
    
    @abstractmethod
    async def initialize_backtest(
        self,
        strategy_name: str,
        from_date: date,
        to_date: date,
        initial_capital: Decimal,
        parameters: Dict[str, Any]
    ) -> str:
        """Initialize a new backtest session"""
        pass
    
    @abstractmethod
    async def load_historical_data(
        self,
        backtest_id: str,
        symbols: List[str],
        data_types: List[str]  # 'index', 'options', 'futures'
    ) -> Dict[str, Any]:
        """Load historical data for backtest"""
        pass
    
    @abstractmethod
    async def run_backtest(
        self,
        backtest_id: str,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Execute the backtest"""
        pass
    
    @abstractmethod
    async def get_backtest_status(
        self,
        backtest_id: str
    ) -> Dict[str, Any]:
        """Get current backtest status"""
        pass
    
    @abstractmethod
    async def pause_backtest(
        self,
        backtest_id: str
    ) -> bool:
        """Pause running backtest"""
        pass
    
    @abstractmethod
    async def resume_backtest(
        self,
        backtest_id: str
    ) -> bool:
        """Resume paused backtest"""
        pass
    
    @abstractmethod
    async def stop_backtest(
        self,
        backtest_id: str
    ) -> bool:
        """Stop and cleanup backtest"""
        pass
    
    @abstractmethod
    async def get_backtest_results(
        self,
        backtest_id: str
    ) -> Dict[str, Any]:
        """Get detailed backtest results"""
        pass
    
    @abstractmethod
    async def export_backtest_results(
        self,
        backtest_id: str,
        format: str = "json"  # json, csv, excel
    ) -> bytes:
        """Export backtest results"""
        pass
    
    @abstractmethod
    async def optimize_parameters(
        self,
        strategy_name: str,
        parameter_ranges: Dict[str, List[Any]],
        optimization_metric: str,
        from_date: date,
        to_date: date
    ) -> Dict[str, Any]:
        """Run parameter optimization"""
        pass
    
    @abstractmethod
    async def run_walk_forward_analysis(
        self,
        strategy_name: str,
        parameters: Dict[str, Any],
        window_size: int,
        step_size: int,
        from_date: date,
        to_date: date
    ) -> Dict[str, Any]:
        """Run walk-forward analysis"""
        pass
    
    @abstractmethod
    async def run_monte_carlo_simulation(
        self,
        backtest_id: str,
        iterations: int,
        confidence_levels: List[float]
    ) -> Dict[str, Any]:
        """Run Monte Carlo simulation on backtest results"""
        pass