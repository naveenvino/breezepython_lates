"""
Application Layer Request DTOs
Data Transfer Objects for incoming requests
"""
from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from enum import Enum


class DataCollectionInterval(str, Enum):
    """Data collection interval enum"""
    ONE_MINUTE = "1minute"
    FIVE_MINUTE = "5minute"
    THIRTY_MINUTE = "30minute"
    ONE_HOUR = "1hour"
    ONE_DAY = "1day"


# ============== Data Collection Requests ==============

class CollectWeeklyDataRequest(BaseModel):
    """Request to collect weekly options data"""
    from_date: date = Field(..., description="Start date for collection")
    to_date: date = Field(..., description="End date for collection")
    symbol: str = Field(default="NIFTY", description="Underlying symbol")
    strike_range: int = Field(default=1000, description="Strike range from spot price")
    option_interval: DataCollectionInterval = Field(
        default=DataCollectionInterval.FIVE_MINUTE,
        description="Data interval for options"
    )
    index_interval: DataCollectionInterval = Field(
        default=DataCollectionInterval.ONE_HOUR,
        description="Data interval for index"
    )
    use_parallel: bool = Field(default=True, description="Use parallel processing")
    max_workers: int = Field(default=5, ge=1, le=20, description="Max parallel workers")
    force_refresh: bool = Field(default=False, description="Force refresh existing data")
    
    @validator('from_date', 'to_date')
    def validate_dates(cls, v):
        if v > date.today():
            raise ValueError("Date cannot be in the future")
        return v
    
    @validator('to_date')
    def validate_date_range(cls, v, values):
        if 'from_date' in values and v < values['from_date']:
            raise ValueError("to_date must be after from_date")
        return v


class CollectOptionChainRequest(BaseModel):
    """Request to collect option chain data"""
    symbol: str = Field(default="NIFTY", description="Underlying symbol")
    expiry_date: Optional[date] = Field(None, description="Option expiry date")
    save_to_db: bool = Field(default=True, description="Save to database")
    include_greeks: bool = Field(default=False, description="Calculate and include Greeks")


class CollectHistoricalDataRequest(BaseModel):
    """Request to collect historical market data"""
    symbol: str = Field(..., description="Trading symbol")
    from_date: datetime = Field(..., description="Start datetime")
    to_date: datetime = Field(..., description="End datetime")
    interval: DataCollectionInterval = Field(..., description="Data interval")
    force_refresh: bool = Field(default=False, description="Force refresh existing data")


class CollectNiftyDataRequest(BaseModel):
    """Request to collect NIFTY index data"""
    from_date: date = Field(..., description="Start date for collection")
    to_date: date = Field(..., description="End date for collection")
    symbol: str = Field(default="NIFTY", description="Index symbol (NIFTY, BANKNIFTY, etc.)")
    force_refresh: bool = Field(default=False, description="Force refresh existing data")
    
    @validator('from_date', 'to_date')
    def validate_dates(cls, v):
        if v > date.today():
            raise ValueError("Date cannot be in the future")
        return v
    
    @validator('to_date')
    def validate_date_range(cls, v, values):
        if 'from_date' in values and v < values['from_date']:
            raise ValueError("to_date must be after from_date")
        return v


# ============== Data Analysis Requests ==============

class AnalyzeDataAvailabilityRequest(BaseModel):
    """Request to analyze data availability"""
    from_date: Optional[date] = Field(None, description="Start date")
    to_date: Optional[date] = Field(None, description="End date")
    symbol: Optional[str] = Field(None, description="Specific symbol")
    data_type: str = Field(default="all", description="Type: all/nifty/options")
    include_gaps: bool = Field(default=True, description="Include gap analysis")


class GetDataCalendarRequest(BaseModel):
    """Request for calendar view of data"""
    year: int = Field(..., ge=2020, le=2030, description="Year")
    month: int = Field(..., ge=1, le=12, description="Month")
    data_type: str = Field(default="nifty", description="Data type: nifty/options")


# ============== Trading Requests ==============

class PlaceTradeRequest(BaseModel):
    """Request to place a trade"""
    symbol: str = Field(..., description="Trading symbol")
    quantity: int = Field(..., gt=0, description="Quantity")
    trade_type: str = Field(..., description="BUY or SELL")
    order_type: str = Field(default="MARKET", description="Order type")
    price: Optional[Decimal] = Field(None, description="Limit price")
    stop_loss: Optional[Decimal] = Field(None, description="Stop loss price")
    take_profit: Optional[Decimal] = Field(None, description="Take profit price")
    strategy_name: Optional[str] = Field(None, description="Strategy name")
    tags: List[str] = Field(default_factory=list, description="Trade tags")
    
    @validator('trade_type')
    def validate_trade_type(cls, v):
        if v not in ["BUY", "SELL"]:
            raise ValueError("trade_type must be BUY or SELL")
        return v
    
    @validator('order_type')
    def validate_order_type(cls, v):
        if v not in ["MARKET", "LIMIT", "STOP"]:
            raise ValueError("Invalid order type")
        return v


class ModifyTradeRequest(BaseModel):
    """Request to modify an existing trade"""
    trade_id: str = Field(..., description="Trade ID")
    stop_loss: Optional[Decimal] = Field(None, description="New stop loss")
    take_profit: Optional[Decimal] = Field(None, description="New take profit")
    notes: Optional[str] = Field(None, description="Trade notes")


class CloseTradeRequest(BaseModel):
    """Request to close a trade"""
    trade_id: str = Field(..., description="Trade ID")
    price: Optional[Decimal] = Field(None, description="Close price (market if not specified)")
    reason: str = Field(default="Manual", description="Close reason")


# ============== Backtest Requests ==============

class RunBacktestRequest(BaseModel):
    """Request to run a backtest"""
    strategy_name: str = Field(..., description="Strategy to backtest")
    from_date: date = Field(..., description="Backtest start date")
    to_date: date = Field(..., description="Backtest end date")
    initial_capital: Decimal = Field(default=Decimal("100000"), description="Starting capital")
    symbol: str = Field(default="NIFTY", description="Symbol to trade")
    
    # Strategy parameters
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")
    
    # Risk parameters
    max_positions: int = Field(default=1, ge=1, description="Max concurrent positions")
    position_size_pct: Decimal = Field(default=Decimal("10"), description="Position size %")
    stop_loss_pct: Optional[Decimal] = Field(None, description="Stop loss %")
    take_profit_pct: Optional[Decimal] = Field(None, description="Take profit %")
    
    # Execution parameters
    slippage_pct: Decimal = Field(default=Decimal("0.05"), description="Slippage %")
    commission_pct: Decimal = Field(default=Decimal("0.02"), description="Commission %")
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


# ============== Option Analysis Requests ==============

class AnalyzeOptionChainRequest(BaseModel):
    """Request to analyze option chain"""
    symbol: str = Field(default="NIFTY", description="Underlying symbol")
    expiry_date: Optional[date] = Field(None, description="Expiry date")
    spot_price: Optional[Decimal] = Field(None, description="Current spot price")
    include_greeks: bool = Field(default=True, description="Include Greeks analysis")
    strike_range: Optional[int] = Field(None, description="Analyze strikes within range")


class CalculateOptionPriceRequest(BaseModel):
    """Request to calculate option price"""
    spot_price: Decimal = Field(..., description="Current spot price")
    strike_price: Decimal = Field(..., description="Strike price")
    days_to_expiry: int = Field(..., ge=0, description="Days to expiry")
    volatility: Decimal = Field(..., description="Implied volatility (as decimal)")
    risk_free_rate: Decimal = Field(default=Decimal("0.065"), description="Risk-free rate")
    is_call: bool = Field(..., description="True for Call, False for Put")
    
    @validator('volatility')
    def validate_volatility(cls, v):
        if v <= 0 or v > 2:  # IV typically between 0% and 200%
            raise ValueError("Invalid volatility value")
        return v


# ============== Risk Management Requests ==============

class CalculatePositionSizeRequest(BaseModel):
    """Request to calculate position size"""
    capital: Decimal = Field(..., description="Available capital")
    risk_percentage: Decimal = Field(..., description="Risk per trade %")
    entry_price: Decimal = Field(..., description="Entry price")
    stop_loss: Decimal = Field(..., description="Stop loss price")
    lot_size: int = Field(default=1, description="Lot size")
    
    @validator('risk_percentage')
    def validate_risk_percentage(cls, v):
        if v <= 0 or v > 10:
            raise ValueError("Risk percentage should be between 0 and 10")
        return v


class AnalyzePortfolioRiskRequest(BaseModel):
    """Request to analyze portfolio risk"""
    include_var: bool = Field(default=True, description="Include VaR calculation")
    var_confidence: Decimal = Field(default=Decimal("0.95"), description="VaR confidence level")
    include_stress_test: bool = Field(default=False, description="Include stress testing")
    stress_scenarios: Optional[List[Dict[str, Any]]] = Field(None, description="Stress test scenarios")