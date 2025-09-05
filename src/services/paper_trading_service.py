"""
Paper Trading Service
Simulates trading without real money for strategy testing
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import json
import pyodbc
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class TradingMode(Enum):
    LIVE = "live"
    PAPER = "paper"
    BACKTEST = "backtest"

@dataclass
class VirtualPortfolio:
    """Virtual portfolio for paper trading"""
    initial_capital: float = 500000
    current_capital: float = 500000
    used_margin: float = 0
    available_margin: float = 500000
    total_pnl: float = 0
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    trade_count: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    max_drawdown: float = 0
    peak_capital: float = 500000
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class PaperTrade:
    """Paper trade record"""
    trade_id: str
    signal_type: str
    strike: int
    option_type: str
    action: str  # BUY or SELL
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: datetime = field(default_factory=datetime.now)
    exit_time: Optional[datetime] = None
    pnl: float = 0
    status: str = "open"  # open, closed, cancelled
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    hedge_strike: Optional[int] = None
    hedge_price: Optional[float] = None
    notes: str = ""

@dataclass
class StrategyComparison:
    """Strategy performance comparison"""
    strategy_name: str
    total_trades: int
    win_rate: float
    avg_profit: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_pnl: float
    best_trade: float
    worst_trade: float
    avg_holding_time: float  # in minutes

class PaperTradingService:
    """
    Manages paper trading and strategy testing
    """
    
    def __init__(self):
        self.conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=(localdb)\\mssqllocaldb;"
            "DATABASE=KiteConnectApi;"
            "Trusted_Connection=yes;"
        )
        
        # Trading mode
        self.mode = TradingMode.PAPER
        
        # Virtual portfolios by strategy
        self.portfolios: Dict[str, VirtualPortfolio] = {}
        
        # Active paper trades
        self.active_trades: Dict[str, List[PaperTrade]] = {}
        
        # Historical trades
        self.trade_history: List[PaperTrade] = []
        
        # Strategy parameters for testing
        self.strategy_params = {
            "default": {
                "num_lots": 10,
                "stop_loss_percent": 30,
                "target_percent": 50,
                "enable_hedge": True,
                "hedge_offset": 200
            },
            "aggressive": {
                "num_lots": 15,
                "stop_loss_percent": 40,
                "target_percent": 70,
                "enable_hedge": False,
                "hedge_offset": 0
            },
            "conservative": {
                "num_lots": 5,
                "stop_loss_percent": 20,
                "target_percent": 30,
                "enable_hedge": True,
                "hedge_offset": 300
            }
        }
        
        # Initialize default portfolio
        self.portfolios["default"] = VirtualPortfolio()
        
        # Load saved state if exists
        self.load_state()
    
    @contextmanager
    def get_db(self):
        """Database connection context manager"""
        conn = pyodbc.connect(self.conn_str)
        try:
            yield conn
        finally:
            conn.close()
    
    def set_mode(self, mode: str) -> bool:
        """
        Set trading mode (live/paper/backtest)
        """
        try:
            self.mode = TradingMode(mode.lower())
            logger.info(f"Trading mode set to: {self.mode.value}")
            return True
        except ValueError:
            logger.error(f"Invalid trading mode: {mode}")
            return False
    
    def get_mode(self) -> str:
        """Get current trading mode"""
        return self.mode.value
    
    def create_portfolio(self, strategy_name: str, initial_capital: float = 500000) -> VirtualPortfolio:
        """
        Create a new virtual portfolio for strategy testing
        """
        portfolio = VirtualPortfolio(
            initial_capital=initial_capital,
            current_capital=initial_capital,
            available_margin=initial_capital
        )
        self.portfolios[strategy_name] = portfolio
        logger.info(f"Created portfolio for strategy: {strategy_name}")
        return portfolio
    
    def execute_paper_trade(
        self,
        strategy: str,
        signal_type: str,
        strike: int,
        option_type: str,
        action: str,
        quantity: int,
        price: float,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        hedge_strike: Optional[int] = None,
        hedge_price: Optional[float] = None
    ) -> Tuple[bool, str, PaperTrade]:
        """
        Execute a paper trade
        
        Returns:
            Tuple of (success, message, trade)
        """
        # Get or create portfolio
        if strategy not in self.portfolios:
            self.create_portfolio(strategy)
        
        portfolio = self.portfolios[strategy]
        
        # Calculate required margin
        lot_size = 75
        required_margin = quantity * lot_size * price
        
        # Check if sufficient margin
        if required_margin > portfolio.available_margin:
            return False, f"Insufficient margin. Required: {required_margin}, Available: {portfolio.available_margin}", None
        
        # Create trade
        trade = PaperTrade(
            trade_id=f"PT_{strategy}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            signal_type=signal_type,
            strike=strike,
            option_type=option_type,
            action=action,
            quantity=quantity,
            entry_price=price,
            stop_loss=stop_loss,
            target=target,
            hedge_strike=hedge_strike,
            hedge_price=hedge_price
        )
        
        # Update portfolio
        portfolio.used_margin += required_margin
        portfolio.available_margin -= required_margin
        portfolio.trade_count += 1
        portfolio.last_updated = datetime.now()
        
        # Add to active trades
        if strategy not in self.active_trades:
            self.active_trades[strategy] = []
        self.active_trades[strategy].append(trade)
        
        # Log trade
        logger.info(f"Paper trade executed: {trade.trade_id} - {action} {quantity} {strike}{option_type} @ {price}")
        
        # Save state
        self.save_state()
        
        return True, f"Paper trade executed: {trade.trade_id}", trade
    
    def close_paper_trade(
        self,
        strategy: str,
        trade_id: str,
        exit_price: float,
        reason: str = "Manual close"
    ) -> Tuple[bool, str, float]:
        """
        Close a paper trade
        
        Returns:
            Tuple of (success, message, pnl)
        """
        if strategy not in self.active_trades:
            return False, f"Strategy {strategy} not found", 0
        
        # Find trade
        trade = None
        for t in self.active_trades[strategy]:
            if t.trade_id == trade_id:
                trade = t
                break
        
        if not trade:
            return False, f"Trade {trade_id} not found", 0
        
        # Calculate P&L
        lot_size = 75
        if trade.action == "SELL":
            # For sold options, profit when price decreases
            pnl = (trade.entry_price - exit_price) * trade.quantity * lot_size
        else:
            # For bought options, profit when price increases
            pnl = (exit_price - trade.entry_price) * trade.quantity * lot_size
        
        # Consider hedge if exists
        if trade.hedge_strike and trade.hedge_price:
            # Hedge is opposite action
            hedge_pnl = 0
            if trade.action == "SELL":
                # Main is SELL, hedge is BUY
                hedge_pnl = (exit_price - trade.hedge_price) * trade.quantity * lot_size
            else:
                # Main is BUY, hedge is SELL
                hedge_pnl = (trade.hedge_price - exit_price) * trade.quantity * lot_size
            pnl += hedge_pnl
        
        # Update trade
        trade.exit_price = exit_price
        trade.exit_time = datetime.now()
        trade.pnl = pnl
        trade.status = "closed"
        trade.notes = reason
        
        # Update portfolio
        portfolio = self.portfolios[strategy]
        portfolio.realized_pnl += pnl
        portfolio.total_pnl = portfolio.realized_pnl + portfolio.unrealized_pnl
        portfolio.current_capital = portfolio.initial_capital + portfolio.total_pnl
        
        # Release margin
        released_margin = trade.quantity * lot_size * trade.entry_price
        portfolio.used_margin -= released_margin
        portfolio.available_margin += released_margin + pnl
        
        # Update win/loss stats
        if pnl > 0:
            portfolio.winning_trades += 1
        elif pnl < 0:
            portfolio.losing_trades += 1
        
        # Update drawdown
        if portfolio.current_capital > portfolio.peak_capital:
            portfolio.peak_capital = portfolio.current_capital
        else:
            drawdown = (portfolio.peak_capital - portfolio.current_capital) / portfolio.peak_capital * 100
            portfolio.max_drawdown = max(portfolio.max_drawdown, drawdown)
        
        # Move to history
        self.active_trades[strategy].remove(trade)
        self.trade_history.append(trade)
        
        # Log
        logger.info(f"Paper trade closed: {trade_id} - P&L: {pnl:.2f}")
        
        # Save state
        self.save_state()
        
        return True, f"Trade closed with P&L: ₹{pnl:.2f}", pnl
    
    def update_paper_prices(self, current_prices: Dict[str, float]):
        """
        Update current prices and calculate unrealized P&L
        
        Args:
            current_prices: Dict of {symbol: price}
        """
        for strategy, trades in self.active_trades.items():
            portfolio = self.portfolios[strategy]
            unrealized_pnl = 0
            
            for trade in trades:
                symbol = f"{trade.strike}{trade.option_type}"
                if symbol in current_prices:
                    current_price = current_prices[symbol]
                    
                    # Calculate unrealized P&L
                    lot_size = 75
                    if trade.action == "SELL":
                        trade_pnl = (trade.entry_price - current_price) * trade.quantity * lot_size
                    else:
                        trade_pnl = (current_price - trade.entry_price) * trade.quantity * lot_size
                    
                    unrealized_pnl += trade_pnl
            
            # Update portfolio
            portfolio.unrealized_pnl = unrealized_pnl
            portfolio.total_pnl = portfolio.realized_pnl + portfolio.unrealized_pnl
            portfolio.current_capital = portfolio.initial_capital + portfolio.total_pnl
    
    def get_portfolio_status(self, strategy: str = "default") -> Dict[str, Any]:
        """Get portfolio status"""
        if strategy not in self.portfolios:
            return {"error": f"Strategy {strategy} not found"}
        
        portfolio = self.portfolios[strategy]
        active_count = len(self.active_trades.get(strategy, []))
        
        return {
            "strategy": strategy,
            "mode": self.mode.value,
            "capital": {
                "initial": portfolio.initial_capital,
                "current": portfolio.current_capital,
                "used_margin": portfolio.used_margin,
                "available_margin": portfolio.available_margin
            },
            "pnl": {
                "total": portfolio.total_pnl,
                "realized": portfolio.realized_pnl,
                "unrealized": portfolio.unrealized_pnl
            },
            "trades": {
                "total": portfolio.trade_count,
                "active": active_count,
                "winning": portfolio.winning_trades,
                "losing": portfolio.losing_trades,
                "win_rate": (portfolio.winning_trades / portfolio.trade_count * 100) if portfolio.trade_count > 0 else 0
            },
            "risk": {
                "max_drawdown": portfolio.max_drawdown,
                "peak_capital": portfolio.peak_capital
            },
            "created_at": portfolio.created_at.isoformat(),
            "last_updated": portfolio.last_updated.isoformat()
        }
    
    def get_active_trades(self, strategy: str = None) -> List[Dict[str, Any]]:
        """Get active paper trades"""
        trades = []
        
        strategies = [strategy] if strategy else self.active_trades.keys()
        
        for strat in strategies:
            if strat in self.active_trades:
                for trade in self.active_trades[strat]:
                    trades.append({
                        "strategy": strat,
                        "trade_id": trade.trade_id,
                        "signal": trade.signal_type,
                        "strike": trade.strike,
                        "type": trade.option_type,
                        "action": trade.action,
                        "quantity": trade.quantity,
                        "entry_price": trade.entry_price,
                        "entry_time": trade.entry_time.isoformat(),
                        "status": trade.status,
                        "pnl": trade.pnl
                    })
        
        return trades
    
    def compare_strategies(self) -> List[StrategyComparison]:
        """
        Compare performance of different strategies
        """
        comparisons = []
        
        for strategy_name, portfolio in self.portfolios.items():
            # Get trades for this strategy
            strategy_trades = [t for t in self.trade_history if t.trade_id.startswith(f"PT_{strategy_name}_")]
            
            if not strategy_trades:
                continue
            
            # Calculate metrics
            total_trades = len(strategy_trades)
            winning = [t for t in strategy_trades if t.pnl > 0]
            losing = [t for t in strategy_trades if t.pnl < 0]
            
            win_rate = (len(winning) / total_trades * 100) if total_trades > 0 else 0
            avg_profit = sum(t.pnl for t in winning) / len(winning) if winning else 0
            avg_loss = abs(sum(t.pnl for t in losing) / len(losing)) if losing else 0
            
            gross_profit = sum(t.pnl for t in winning) if winning else 0
            gross_loss = abs(sum(t.pnl for t in losing)) if losing else 0
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
            
            # Calculate Sharpe ratio (simplified)
            returns = [t.pnl for t in strategy_trades]
            if len(returns) > 1:
                import numpy as np
                sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0
            else:
                sharpe_ratio = 0
            
            # Best and worst trades
            best_trade = max(t.pnl for t in strategy_trades) if strategy_trades else 0
            worst_trade = min(t.pnl for t in strategy_trades) if strategy_trades else 0
            
            # Average holding time
            closed_trades = [t for t in strategy_trades if t.exit_time]
            if closed_trades:
                holding_times = [(t.exit_time - t.entry_time).total_seconds() / 60 for t in closed_trades]
                avg_holding_time = sum(holding_times) / len(holding_times)
            else:
                avg_holding_time = 0
            
            comparison = StrategyComparison(
                strategy_name=strategy_name,
                total_trades=total_trades,
                win_rate=win_rate,
                avg_profit=avg_profit,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=portfolio.max_drawdown,
                total_pnl=portfolio.total_pnl,
                best_trade=best_trade,
                worst_trade=worst_trade,
                avg_holding_time=avg_holding_time
            )
            
            comparisons.append(comparison)
        
        # Sort by total P&L
        comparisons.sort(key=lambda x: x.total_pnl, reverse=True)
        
        return comparisons
    
    def reset_portfolio(self, strategy: str = "default"):
        """Reset a portfolio to initial state"""
        self.portfolios[strategy] = VirtualPortfolio()
        
        # Clear active trades for this strategy
        if strategy in self.active_trades:
            # Move all to history as cancelled
            for trade in self.active_trades[strategy]:
                trade.status = "cancelled"
                trade.notes = "Portfolio reset"
                self.trade_history.append(trade)
            self.active_trades[strategy] = []
        
        logger.info(f"Portfolio reset for strategy: {strategy}")
        self.save_state()
    
    def save_state(self):
        """Save current state to file"""
        try:
            state = {
                "mode": self.mode.value,
                "portfolios": {k: asdict(v) for k, v in self.portfolios.items()},
                "active_trades": {
                    k: [asdict(t) for t in trades]
                    for k, trades in self.active_trades.items()
                },
                "trade_history": [asdict(t) for t in self.trade_history[-100:]]  # Keep last 100
            }
            
            # Convert datetime objects to strings
            def convert_dates(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_dates(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_dates(item) for item in obj]
                return obj
            
            state = convert_dates(state)
            
            with open("paper_trading_state.json", "w") as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def load_state(self):
        """Load saved state from file"""
        try:
            with open("paper_trading_state.json", "r") as f:
                state = json.load(f)
            
            # Restore mode
            self.mode = TradingMode(state.get("mode", "paper"))
            
            # Restore portfolios
            for name, data in state.get("portfolios", {}).items():
                portfolio = VirtualPortfolio(**{
                    k: datetime.fromisoformat(v) if k.endswith('_at') else v
                    for k, v in data.items()
                })
                self.portfolios[name] = portfolio
            
            logger.info("Paper trading state loaded")
            
        except FileNotFoundError:
            logger.info("No saved state found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading state: {e}")

# Singleton instance
_instance = None

def get_paper_trading_service() -> PaperTradingService:
    """Get singleton instance"""
    global _instance
    if _instance is None:
        _instance = PaperTradingService()
    return _instance