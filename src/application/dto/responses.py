"""
Application Layer Response DTOs
Data Transfer Objects for outgoing responses
"""
from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Generic, TypeVar
from decimal import Decimal
from enum import Enum


T = TypeVar('T')


class ResponseStatus(str, Enum):
    """Response status enum"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"


class BaseResponse(BaseModel, Generic[T]):
    """Base response wrapper"""
    status: ResponseStatus = Field(..., description="Response status")
    message: Optional[str] = Field(None, description="Status message")
    data: Optional[T] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


# ============== Data Collection Responses ==============

class DataCollectionStats(BaseModel):
    """Statistics for data collection"""
    records_collected: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    time_taken_seconds: float = 0
    errors: List[Dict[str, str]] = Field(default_factory=list)


class CollectWeeklyDataResponse(BaseModel):
    """Response for weekly data collection"""
    from_date: date
    to_date: date
    symbol: str
    mondays_processed: List[Dict[str, Any]]
    nifty_stats: DataCollectionStats
    options_stats: DataCollectionStats
    total_time_seconds: float
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class CollectOptionChainResponse(BaseModel):
    """Response for option chain collection"""
    symbol: str
    expiry_date: date
    timestamp: datetime
    strikes_count: int
    records_saved: int
    chain_data: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


# ============== Data Analysis Responses ==============

class DataAvailabilitySummary(BaseModel):
    """Summary of data availability"""
    total_records: int
    date_range: Dict[str, Optional[datetime]]
    unique_days: int
    completeness_percentage: float
    gaps_found: int
    missing_dates: List[date]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            date: lambda v: v.isoformat()
        }


class AnalyzeDataAvailabilityResponse(BaseModel):
    """Response for data availability analysis"""
    nifty_summary: Optional[DataAvailabilitySummary]
    options_summary: Optional[DataAvailabilitySummary]
    recommendations: List[str]
    detailed_gaps: Optional[Dict[str, Any]] = None


class DataCalendarDay(BaseModel):
    """Single day in data calendar"""
    date: date
    day: int
    weekday: str
    is_trading_day: bool
    has_data: bool
    records_count: Optional[int] = None
    data_quality: Optional[str] = None
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class GetDataCalendarResponse(BaseModel):
    """Response for data calendar"""
    year: int
    month: int
    month_name: str
    days: List[DataCalendarDay]
    statistics: Dict[str, Any]


# ============== Trading Responses ==============

class TradeExecutionResponse(BaseModel):
    """Response for trade execution"""
    trade_id: str
    order_id: Optional[str]
    symbol: str
    quantity: int
    executed_price: Optional[Decimal]
    status: str
    execution_time: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class TradeModificationResponse(BaseModel):
    """Response for trade modification"""
    trade_id: str
    modifications: Dict[str, Any]
    success: bool
    message: Optional[str]


class TradeCloseResponse(BaseModel):
    """Response for trade closure"""
    trade_id: str
    close_price: Decimal
    pnl: Decimal
    pnl_percentage: Decimal
    close_time: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


# ============== Backtest Responses ==============

class BacktestMetrics(BaseModel):
    """Backtest performance metrics"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    total_pnl: Decimal
    total_return_pct: Decimal
    
    average_win: Decimal
    average_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    calmar_ratio: Optional[float]
    
    profit_factor: Optional[float]
    expectancy: Decimal
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class BacktestTrade(BaseModel):
    """Individual backtest trade"""
    trade_id: str
    symbol: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: Decimal
    exit_price: Optional[Decimal]
    quantity: int
    pnl: Optional[Decimal]
    pnl_percentage: Optional[Decimal]
    trade_type: str
    exit_reason: Optional[str]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class RunBacktestResponse(BaseModel):
    """Response for backtest execution"""
    strategy_name: str
    from_date: date
    to_date: date
    initial_capital: Decimal
    final_capital: Decimal
    
    metrics: BacktestMetrics
    trades: List[BacktestTrade]
    equity_curve: List[Dict[str, Any]]
    
    execution_time_seconds: float
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


# ============== Option Analysis Responses ==============

class OptionGreeks(BaseModel):
    """Option Greeks data"""
    delta: Optional[Decimal]
    gamma: Optional[Decimal]
    theta: Optional[Decimal]
    vega: Optional[Decimal]
    rho: Optional[Decimal]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v else None
        }


class OptionChainStrike(BaseModel):
    """Single strike in option chain"""
    strike: Decimal
    call_data: Optional[Dict[str, Any]]
    put_data: Optional[Dict[str, Any]]
    call_greeks: Optional[OptionGreeks]
    put_greeks: Optional[OptionGreeks]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class AnalyzeOptionChainResponse(BaseModel):
    """Response for option chain analysis"""
    symbol: str
    expiry_date: date
    spot_price: Decimal
    analysis_time: datetime
    
    strikes: List[OptionChainStrike]
    
    max_call_oi_strike: Optional[Decimal]
    max_put_oi_strike: Optional[Decimal]
    put_call_ratio: Optional[Decimal]
    
    support_levels: List[Decimal]
    resistance_levels: List[Decimal]
    
    iv_skew: Optional[Dict[str, Any]]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class CalculateOptionPriceResponse(BaseModel):
    """Response for option price calculation"""
    theoretical_price: Decimal
    greeks: OptionGreeks
    intrinsic_value: Decimal
    time_value: Decimal
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


# ============== Risk Management Responses ==============

class PositionSizeResponse(BaseModel):
    """Response for position size calculation"""
    recommended_quantity: int
    position_value: Decimal
    risk_amount: Decimal
    stop_loss_amount: Decimal
    risk_reward_ratio: Optional[Decimal]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class PortfolioRiskMetrics(BaseModel):
    """Portfolio risk metrics"""
    total_exposure: Decimal
    total_margin_used: Decimal
    margin_available: Decimal
    
    portfolio_delta: Decimal
    portfolio_gamma: Decimal
    portfolio_theta: Decimal
    portfolio_vega: Decimal
    
    value_at_risk: Optional[Decimal]
    expected_shortfall: Optional[Decimal]
    max_drawdown: Decimal
    
    position_risks: List[Dict[str, Any]]
    concentration_risk: Dict[str, Any]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class AnalyzePortfolioRiskResponse(BaseModel):
    """Response for portfolio risk analysis"""
    analysis_time: datetime
    metrics: PortfolioRiskMetrics
    warnings: List[str]
    suggestions: List[str]
    stress_test_results: Optional[Dict[str, Any]]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }