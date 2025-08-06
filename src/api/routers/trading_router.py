"""
Trading Operations Router
API endpoints for trading operations
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List

from ...application.dto.requests import (
    PlaceTradeRequest,
    ModifyTradeRequest,
    CloseTradeRequest,
    CalculatePositionSizeRequest,
    AnalyzePortfolioRiskRequest
)
from ...application.dto.responses import BaseResponse
from ...infrastructure.di.container import get_service
from ...domain.repositories.itrade_repository import ITradeRepository
from ...domain.services.irisk_manager import IRiskManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/trades/place", response_model=BaseResponse)
async def place_trade(
    request: PlaceTradeRequest,
    trade_repo: ITradeRepository = Depends(lambda: get_service(ITradeRepository))
):
    """
    Place a new trade
    
    - **symbol**: Trading symbol
    - **quantity**: Trade quantity
    - **trade_type**: BUY or SELL
    - **order_type**: MARKET or LIMIT
    - **price**: Limit price (required for LIMIT orders)
    - **stop_loss**: Stop loss price
    - **take_profit**: Take profit price
    """
    try:
        logger.info(f"Placing {request.trade_type} trade for {request.symbol}")
        
        # This would integrate with actual trading logic
        # For now, return success response
        return BaseResponse(
            status="success",
            message=f"Trade placed successfully",
            data={
                "trade_id": "TRADE123",
                "symbol": request.symbol,
                "quantity": request.quantity,
                "status": "PENDING"
            }
        )
    except Exception as e:
        logger.error(f"Error placing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/trades/{trade_id}/modify", response_model=BaseResponse)
async def modify_trade(
    trade_id: str,
    request: ModifyTradeRequest,
    trade_repo: ITradeRepository = Depends(lambda: get_service(ITradeRepository))
):
    """Modify an existing trade"""
    try:
        logger.info(f"Modifying trade {trade_id}")
        
        # Fetch and modify trade
        trade = await trade_repo.get_by_id(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        
        # Apply modifications
        if request.stop_loss:
            trade.stop_loss = request.stop_loss
        if request.take_profit:
            trade.target = request.take_profit
        
        # Save changes
        await trade_repo.save(trade)
        
        return BaseResponse(
            status="success",
            message="Trade modified successfully",
            data={"trade_id": trade_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error modifying trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trades/{trade_id}/close", response_model=BaseResponse)
async def close_trade(
    trade_id: str,
    request: CloseTradeRequest,
    trade_repo: ITradeRepository = Depends(lambda: get_service(ITradeRepository))
):
    """Close an open trade"""
    try:
        logger.info(f"Closing trade {trade_id}")
        
        # This would integrate with actual trading logic
        return BaseResponse(
            status="success",
            message="Trade closed successfully",
            data={
                "trade_id": trade_id,
                "close_price": request.price,
                "pnl": 1500.00
            }
        )
    except Exception as e:
        logger.error(f"Error closing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades")
async def get_trades(
    status: Optional[str] = Query(None, description="Filter by status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(default=100, le=1000),
    trade_repo: ITradeRepository = Depends(lambda: get_service(ITradeRepository))
):
    """Get list of trades"""
    try:
        trades = await trade_repo.get_active_trades()
        
        # Convert to response format
        trade_list = []
        for trade in trades[:limit]:
            trade_list.append({
                "id": trade.id,
                "symbol": trade.symbol,
                "type": trade.trade_type.value,
                "entry_price": float(trade.entry_price),
                "quantity": trade.quantity,
                "status": trade.status.value,
                "entry_time": trade.entry_time.isoformat()
            })
        
        return {
            "trades": trade_list,
            "total": len(trades)
        }
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/position-size", response_model=BaseResponse)
async def calculate_position_size(
    request: CalculatePositionSizeRequest,
    risk_manager: IRiskManager = Depends(lambda: get_service(IRiskManager))
):
    """
    Calculate appropriate position size based on risk
    
    - **capital**: Available capital
    - **risk_percentage**: Risk per trade (%)
    - **entry_price**: Entry price
    - **stop_loss**: Stop loss price
    - **lot_size**: Lot size for the instrument
    """
    try:
        position_size = risk_manager.calculate_position_size(
            capital=request.capital,
            risk_percentage=request.risk_percentage,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            lot_size=request.lot_size
        )
        
        risk_amount = request.capital * (request.risk_percentage / 100)
        
        return BaseResponse(
            status="success",
            message="Position size calculated",
            data={
                "recommended_quantity": position_size,
                "position_value": float(request.entry_price * position_size),
                "risk_amount": float(risk_amount),
                "stop_loss_amount": float(abs(request.entry_price - request.stop_loss) * position_size)
            }
        )
    except Exception as e:
        logger.error(f"Error calculating position size: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/portfolio-analysis", response_model=BaseResponse)
async def analyze_portfolio_risk(
    request: AnalyzePortfolioRiskRequest,
    risk_manager: IRiskManager = Depends(lambda: get_service(IRiskManager)),
    trade_repo: ITradeRepository = Depends(lambda: get_service(ITradeRepository))
):
    """Analyze portfolio risk metrics"""
    try:
        # Get active trades
        trades = await trade_repo.get_active_trades()
        
        # Calculate risk metrics
        # This is simplified - would need market data in real implementation
        metrics = {
            "total_positions": len(trades),
            "total_exposure": sum(float(t.entry_price * t.quantity) for t in trades),
            "portfolio_metrics": {
                "value_at_risk": 5000.00,
                "expected_shortfall": 7500.00,
                "max_drawdown": 3.5,
                "sharpe_ratio": 1.25
            },
            "position_risks": [],
            "suggestions": []
        }
        
        return BaseResponse(
            status="success",
            message="Portfolio risk analysis completed",
            data=metrics
        )
    except Exception as e:
        logger.error(f"Error analyzing portfolio risk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(
    trade_repo: ITradeRepository = Depends(lambda: get_service(ITradeRepository))
):
    """Get current open positions"""
    try:
        trades = await trade_repo.get_active_trades()
        
        positions = []
        for trade in trades:
            positions.append({
                "symbol": trade.symbol,
                "quantity": trade.quantity,
                "side": trade.trade_type.value,
                "entry_price": float(trade.entry_price),
                "current_price": float(trade.entry_price),  # Would get from market data
                "pnl": 0.0,  # Would calculate actual P&L
                "pnl_percentage": 0.0
            })
        
        return {
            "positions": positions,
            "total_pnl": sum(p["pnl"] for p in positions)
        }
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))