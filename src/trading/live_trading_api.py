"""
Live Trading API Endpoints
Provides REST API for live trading functionality
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .live_trading_engine import get_trading_engine, TradingMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-trading", tags=["Live Trading"])


@router.post("/start")
async def start_trading(
    mode: str = "paper",
    capital: float = 500000,
    max_positions: int = 3,
    lots_per_trade: int = 10,
    stop_loss_percent: float = 2.0,
    signals: List[str] = Query(["S1", "S2", "S3", "S4"])
):
    """
    Start live trading
    
    Args:
        mode: Trading mode - "paper" or "live"
        capital: Trading capital
        max_positions: Maximum concurrent positions
        lots_per_trade: Number of lots per trade
        stop_loss_percent: Stop loss percentage
        signals: List of signals to trade (S1-S8)
    """
    try:
        # Get or create trading engine
        engine = get_trading_engine(mode)
        
        # Update parameters
        engine.capital = capital
        engine.max_positions = max_positions
        engine.lots_per_trade = lots_per_trade
        engine.stop_loss_percent = stop_loss_percent
        
        # Start trading
        result = engine.start_trading(signals)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to start trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_trading(close_all: bool = False):
    """
    Stop trading
    
    Args:
        close_all: Whether to close all open positions
    """
    try:
        engine = get_trading_engine()
        result = engine.stop_trading(close_all)
        return result
        
    except Exception as e:
        logger.error(f"Failed to stop trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause")
async def pause_trading():
    """Pause/Resume trading"""
    try:
        engine = get_trading_engine()
        result = engine.pause_trading()
        return result
        
    except Exception as e:
        logger.error(f"Failed to pause trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emergency-stop")
async def emergency_stop():
    """Emergency stop - immediately close all positions and stop trading"""
    try:
        engine = get_trading_engine()
        result = engine.emergency_stop()
        return result
        
    except Exception as e:
        logger.error(f"Emergency stop failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/place-order")
async def place_order(
    signal_type: str,
    strike_price: int,
    option_type: str,
    action: str = "SELL"
):
    """
    Place an order
    
    Args:
        signal_type: Signal that triggered the order (S1-S8)
        strike_price: Option strike price
        option_type: CE or PE
        action: BUY or SELL
    """
    try:
        engine = get_trading_engine()
        
        if not engine.is_trading:
            return {"status": "error", "message": "Trading not active"}
            
        result = engine.place_order(signal_type, strike_price, option_type, action)
        return result
        
    except Exception as e:
        logger.error(f"Failed to place order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/close-position/{position_id}")
async def close_position(position_id: str, reason: str = "Manual"):
    """
    Close a specific position
    
    Args:
        position_id: Position ID to close
        reason: Reason for closing
    """
    try:
        engine = get_trading_engine()
        result = engine.close_position(position_id, reason)
        return result
        
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions():
    """Get all open positions"""
    try:
        engine = get_trading_engine()
        positions = engine.get_positions()
        return {
            "status": "success",
            "positions": positions,
            "count": len(positions)
        }
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-positions")
async def update_positions():
    """Update all position prices and check stop losses"""
    try:
        engine = get_trading_engine()
        result = engine.update_positions()
        return {
            "status": "success",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Failed to update positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """Get trading statistics"""
    try:
        engine = get_trading_engine()
        stats = engine.get_statistics()
        return {
            "status": "success",
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_trading_status():
    """Get current trading status"""
    try:
        engine = get_trading_engine()
        
        return {
            "status": "success",
            "mode": engine.mode.value,
            "is_trading": engine.is_trading,
            "is_paused": engine.is_paused,
            "open_positions": len(engine.positions),
            "active_signals": engine.active_signals,
            "today_pnl": engine.today_pnl,
            "today_trades": engine.today_trades
        }
        
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/live")
async def get_live_market_data():
    """Get live market data (NIFTY, VIX, PCR, etc.)"""
    try:
        # This would connect to real market data feed
        # For now, returning simulated data
        import random
        
        nifty_price = 21500 + random.uniform(-100, 100)
        change = random.uniform(-1, 1)
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "market_status": "OPEN" if 9 <= datetime.now().hour < 16 else "CLOSED",
            "nifty": {
                "price": round(nifty_price, 2),
                "change": round(change, 2),
                "change_percent": round(change / nifty_price * 100, 2)
            },
            "vix": round(12 + random.uniform(-2, 2), 2),
            "pcr": round(0.9 + random.uniform(-0.3, 0.3), 2),
            "open_interest": f"{random.randint(1000000, 2000000):,}"
        }
        
    except Exception as e:
        logger.error(f"Failed to get market data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/detect")
async def detect_signals():
    """Detect trading signals from current market conditions"""
    try:
        # This would connect to real signal detection logic
        # For demo, returning sample signals
        import random
        
        signals = []
        
        # Randomly generate signals for demo
        if random.random() > 0.7:  # 30% chance of signal
            signal_types = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
            selected_signal = random.choice(signal_types)
            
            signals.append({
                "signal_type": selected_signal,
                "datetime": datetime.now().isoformat(),
                "entry_price": 21500 + random.uniform(-200, 200),
                "stop_loss": 21500,
                "option_type": "PUT" if selected_signal in ["S1", "S2", "S4", "S7"] else "CALL",
                "confidence": round(random.uniform(0.6, 0.95), 2)
            })
        
        return {
            "status": "success",
            "signals": signals,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to detect signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/price")
async def get_option_price(
    strike: int,
    type: str,
    expiry: Optional[str] = None
):
    """
    Get current option price
    
    Args:
        strike: Strike price
        type: CE or PE
        expiry: Expiry date (optional, defaults to current week)
    """
    try:
        engine = get_trading_engine()
        price = engine._get_option_price(strike, type)
        
        if price:
            return {
                "status": "success",
                "strike": strike,
                "type": type,
                "price": price,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "Could not fetch option price"
            }
            
    except Exception as e:
        logger.error(f"Failed to get option price: {e}")
        raise HTTPException(status_code=500, detail=str(e))