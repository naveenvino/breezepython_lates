"""
Signals Router
API endpoints for testing and monitoring trading signals
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import List, Dict, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel, Field
import asyncio
import json

from ...infrastructure.di.container import get_service


# Request/Response Models
class WeeklyZonesData(BaseModel):
    """Weekly support and resistance zones"""
    upper_zone_top: float
    upper_zone_bottom: float
    lower_zone_top: float
    lower_zone_bottom: float
    margin_high: float = 0.0025  # 0.25% default
    margin_low: float = 0.0025   # 0.25% default
    prev_week_high: float
    prev_week_low: float
    prev_week_close: float

class BarData(BaseModel):
    """OHLC bar data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0

class SignalTestRequest(BaseModel):
    """Request for testing a specific signal"""
    signal_type: Optional[str] = Field(None, description="Specific signal to test (S1-S8)")
    weekly_zones: WeeklyZonesData
    weekly_bias: str = Field(..., description="BULLISH, BEARISH, or NEUTRAL")
    candles: List[BarData] = Field(..., description="Hourly candles for the week")
    first_hour_bar: Optional[BarData] = None

class BacktestSignalsRequest(BaseModel):
    """Request for backtesting signals"""
    start_date: date
    end_date: date
    signals_to_test: List[str] = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
    initial_capital: float = 100000
    lot_size: int = 50

class SignalResponse(BaseModel):
    """Signal evaluation response"""
    signal_triggered: bool
    signal_type: Optional[str] = None
    option_type: Optional[str] = None  # CE or PE
    strike_price: Optional[float] = None
    stop_loss: Optional[float] = None
    direction: Optional[str] = None  # BULLISH or BEARISH
    entry_time: Optional[datetime] = None
    confidence: Optional[float] = None
    message: str = ""


# Create router
router = APIRouter(
    prefix="/api/v1/signals",
    tags=["signals"],
    responses={404: {"description": "Not found"}},
)


@router.post("/test", response_model=SignalResponse)
async def test_signal(request: SignalTestRequest):
    """
    Test a specific signal or all signals with provided data
    
    This endpoint allows you to test signal triggers with mock data
    """
    try:
        # For now, return a mock response showing how the system would work
        # In production, this would use the actual SignalEvaluator
        
        # Example logic for S1 (Bear Trap)
        if request.signal_type == "S1" and len(request.candles) >= 2:
            first_candle = request.candles[0]
            second_candle = request.candles[1]
            
            zones = request.weekly_zones
            
            # S1 conditions
            cond1 = first_candle.open >= zones.lower_zone_bottom
            cond2 = first_candle.close < zones.lower_zone_bottom
            cond3 = second_candle.close > first_candle.low
            
            if cond1 and cond2 and cond3:
                stop_loss = first_candle.low - abs(first_candle.open - first_candle.close)
                strike = round(stop_loss / 100) * 100  # Round to nearest 100
                
                return SignalResponse(
                    signal_triggered=True,
                    signal_type="S1",
                    option_type="PE",
                    strike_price=strike,
                    stop_loss=stop_loss,
                    direction="BULLISH",
                    entry_time=second_candle.timestamp,
                    confidence=0.75,
                    message="S1 Bear Trap signal triggered - Bullish reversal detected"
                )
        
        # Default: no signal
        return SignalResponse(
            signal_triggered=False,
            message=f"No signal triggered for {request.signal_type or 'any signal'}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-all", response_model=List[SignalResponse])
async def test_all_signals(request: SignalTestRequest):
    """
    Test all signals (S1-S8) with the provided data
    Returns which signals would trigger
    """
    signals_to_test = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
    results = []
    
    for signal in signals_to_test:
        request.signal_type = signal
        result = await test_signal(request)
        if result.signal_triggered:
            results.append(result)
    
    if not results:
        results.append(SignalResponse(
            signal_triggered=False,
            message="No signals triggered with the provided data"
        ))
    
    return results


@router.get("/current", response_model=SignalResponse)
async def get_current_signals():
    """
    Get current signal status based on live market data
    """
    # Mock response for now
    return SignalResponse(
        signal_triggered=False,
        message="No active signals at the moment. Market data integration pending."
    )


@router.post("/backtest", response_model=Dict[str, Any])
async def backtest_signals(request: BacktestSignalsRequest):
    """
    Backtest signals over historical period
    """
    # Mock backtest results
    results = {}
    
    for signal in request.signals_to_test:
        results[signal] = {
            "total_trades": 12,
            "wins": 8,
            "losses": 4,
            "win_rate": 66.67,
            "total_pnl": 25000,
            "avg_pnl_per_trade": 2083.33,
            "max_drawdown": -5000,
            "sharpe_ratio": 1.45
        }
    
    summary = {
        "period": f"{request.start_date} to {request.end_date}",
        "initial_capital": request.initial_capital,
        "final_capital": request.initial_capital + 45000,
        "total_return": 45.0,
        "best_signal": "S7",
        "worst_signal": "S5",
        "results_by_signal": results
    }
    
    return summary


@router.get("/examples/{signal_type}")
async def get_signal_example(signal_type: str):
    """
    Get example test data for a specific signal type
    
    This helps understand what conditions trigger each signal
    """
    examples = {
        "S1": {
            "description": "Bear Trap - Fake breakdown below support that recovers",
            "required_bias": "Any",
            "triggers_on": "2nd hourly candle",
            "test_data": {
                "weekly_zones": {
                    "upper_zone_top": 23600,
                    "upper_zone_bottom": 23550,
                    "lower_zone_top": 23250,
                    "lower_zone_bottom": 23200,
                    "prev_week_high": 23600,
                    "prev_week_low": 23200,
                    "prev_week_close": 23400
                },
                "weekly_bias": "NEUTRAL",
                "candles": [
                    {
                        "timestamp": "2024-01-22T09:15:00",
                        "open": 23220,
                        "high": 23280,
                        "low": 23150,
                        "close": 23180,
                        "volume": 1000
                    },
                    {
                        "timestamp": "2024-01-22T10:15:00",
                        "open": 23185,
                        "high": 23220,
                        "low": 23170,
                        "close": 23200,
                        "volume": 1200
                    }
                ]
            }
        },
        "S2": {
            "description": "Support Hold - Price respects support with bullish bias",
            "required_bias": "BULLISH",
            "triggers_on": "2nd hourly candle",
            "test_data": {
                "weekly_zones": {
                    "upper_zone_top": 23600,
                    "upper_zone_bottom": 23550,
                    "lower_zone_top": 23250,
                    "lower_zone_bottom": 23200,
                    "prev_week_high": 23600,
                    "prev_week_low": 23200,
                    "prev_week_close": 23220
                },
                "weekly_bias": "BULLISH",
                "candles": [
                    {
                        "timestamp": "2024-01-22T09:15:00",
                        "open": 23210,
                        "high": 23250,
                        "low": 23195,
                        "close": 23230,
                        "volume": 1000
                    },
                    {
                        "timestamp": "2024-01-22T10:15:00",
                        "open": 23235,
                        "high": 23260,
                        "low": 23220,
                        "close": 23250,
                        "volume": 1200
                    }
                ]
            }
        },
        # Add more examples for S3-S8...
    }
    
    if signal_type not in examples:
        raise HTTPException(status_code=404, detail=f"No example found for signal {signal_type}")
    
    return examples[signal_type]


@router.websocket("/ws")
async def signal_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time signal monitoring
    
    Sends updates when signals trigger or market conditions change
    """
    await websocket.accept()
    
    try:
        while True:
            # Mock signal update
            await websocket.send_json({
                "type": "market_update",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "current_price": 23450,
                    "weekly_bias": "BULLISH",
                    "near_support": False,
                    "near_resistance": True,
                    "active_signal": None
                }
            })
            
            # Send updates every 5 seconds (in production, would be event-driven)
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        print("Client disconnected from signal websocket")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()


@router.get("/performance/{signal_type}")
async def get_signal_performance(
    signal_type: str,
    days: int = 30
):
    """
    Get historical performance metrics for a specific signal
    """
    # Mock performance data
    return {
        "signal": signal_type,
        "period_days": days,
        "metrics": {
            "total_signals": 15,
            "trades_taken": 12,
            "wins": 8,
            "losses": 4,
            "win_rate": 66.67,
            "avg_profit": 3500,
            "avg_loss": -1200,
            "profit_factor": 2.33,
            "max_consecutive_wins": 4,
            "max_consecutive_losses": 2,
            "best_trade": {
                "date": "2024-01-15",
                "pnl": 7500,
                "holding_hours": 48
            },
            "worst_trade": {
                "date": "2024-01-08", 
                "pnl": -2500,
                "holding_hours": 72
            }
        }
    }


@router.get("/zones/current")
async def get_current_zones():
    """
    Get current weekly support and resistance zones
    """
    # Mock current zones
    return {
        "week_start": "2024-01-22",
        "calculation_time": datetime.now().isoformat(),
        "zones": {
            "resistance": {
                "top": 23650,
                "bottom": 23600,
                "strength": "Strong"
            },
            "support": {
                "top": 23250,
                "bottom": 23200,
                "strength": "Moderate"
            }
        },
        "weekly_bias": "BULLISH",
        "bias_strength": 0.65,
        "key_levels": {
            "prev_week_high": 23600,
            "prev_week_low": 23200,
            "prev_week_close": 23450,
            "current_week_high": 23520,
            "current_week_low": 23380
        }
    }