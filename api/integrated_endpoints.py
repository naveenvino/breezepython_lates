"""
Integrated API Endpoints for all new services
"""

from fastapi import APIRouter, HTTPException, Depends, Header, BackgroundTasks
from typing import Dict, Optional, List
from datetime import datetime
import logging

# Import all services
from src.services.breeze_connection_service import get_breeze_service
from src.services.tradingview_webhook_service import get_webhook_service
from src.services.safety_manager_service import get_safety_manager
from src.services.trading_execution_service import get_trading_service
from src.services.strategy_automation_service import get_strategy_service
from src.services.alert_service import get_alert_service
from src.services.risk_management_service import get_risk_management_service
from src.services.performance_analytics_service import get_performance_analytics_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v2", tags=["Integrated Trading"])

# ============= BROKER CONNECTION ENDPOINTS =============

@router.get("/broker/status")
async def get_broker_status():
    """Get broker connection status"""
    try:
        service = get_breeze_service()
        return {
            "success": True,
            "status": service.get_connection_status(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting broker status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/broker/reconnect")
async def reconnect_broker():
    """Reconnect to broker"""
    try:
        service = get_breeze_service()
        success = await service.reconnect()
        return {
            "success": success,
            "message": "Reconnected successfully" if success else "Reconnection failed"
        }
    except Exception as e:
        logger.error(f"Error reconnecting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/broker/funds")
async def get_account_funds():
    """Get account funds"""
    try:
        service = get_breeze_service()
        funds = await service.get_funds()
        return {
            "success": True,
            "funds": funds
        }
    except Exception as e:
        logger.error(f"Error getting funds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/broker/positions")
async def get_broker_positions():
    """Get current positions from broker"""
    try:
        service = get_breeze_service()
        positions = await service.get_positions()
        return {
            "success": True,
            "positions": positions
        }
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= TRADINGVIEW WEBHOOK ENDPOINTS =============

@router.post("/webhook/tradingview")
async def receive_tradingview_webhook(
    data: Dict,
    background_tasks: BackgroundTasks,
    x_signature: Optional[str] = Header(None)
):
    """Receive and process TradingView webhook"""
    try:
        webhook_service = get_webhook_service(
            trading_service=get_trading_service(),
            risk_service=get_risk_management_service()
        )
        
        # Process webhook
        result = await webhook_service.process_webhook(data, {"x-signature": x_signature})
        
        return result
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/webhook/signals/active")
async def get_active_webhook_signals():
    """Get active signal positions"""
    try:
        service = get_webhook_service()
        return {
            "success": True,
            "active_signals": service.get_active_signals()
        }
    except Exception as e:
        logger.error(f"Error getting active signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/webhook/signals/history")
async def get_webhook_signal_history(limit: int = 50):
    """Get webhook signal history"""
    try:
        service = get_webhook_service()
        return {
            "success": True,
            "history": service.get_signal_history(limit)
        }
    except Exception as e:
        logger.error(f"Error getting signal history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= SAFETY MANAGER ENDPOINTS =============

@router.get("/safety/status")
async def get_safety_status():
    """Get safety manager status"""
    try:
        service = get_safety_manager()
        return {
            "success": True,
            "safety": service.get_safety_status()
        }
    except Exception as e:
        logger.error(f"Error getting safety status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/safety/kill-switch")
async def trigger_kill_switch(reason: str = "Manual trigger"):
    """Activate kill switch"""
    try:
        service = get_safety_manager(
            trading_service=get_trading_service(),
            risk_service=get_risk_management_service()
        )
        await service.trigger_kill_switch(reason)
        return {
            "success": True,
            "message": "Kill switch activated",
            "reason": reason
        }
    except Exception as e:
        logger.error(f"Error triggering kill switch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/safety/kill-switch/release")
async def release_kill_switch():
    """Release kill switch"""
    try:
        service = get_safety_manager()
        await service.release_kill_switch()
        return {
            "success": True,
            "message": "Kill switch released"
        }
    except Exception as e:
        logger.error(f"Error releasing kill switch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/safety/emergency-stop")
async def trigger_emergency_stop(reason: str = "Manual trigger"):
    """Trigger emergency stop"""
    try:
        service = get_safety_manager(
            trading_service=get_trading_service(),
            risk_service=get_risk_management_service()
        )
        await service.trigger_emergency_stop(reason)
        return {
            "success": True,
            "message": "Emergency stop activated",
            "reason": reason
        }
    except Exception as e:
        logger.error(f"Error triggering emergency stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/safety/validate-order")
async def validate_order(order_data: Dict):
    """Validate order before execution"""
    try:
        service = get_safety_manager()
        is_valid, message = await service.validate_order(order_data)
        return {
            "success": is_valid,
            "message": message
        }
    except Exception as e:
        logger.error(f"Error validating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= TRADING EXECUTION ENDPOINTS =============

@router.post("/trading/place-order")
async def place_trading_order(order_data: Dict):
    """Place a trading order"""
    try:
        # Safety check first
        safety_service = get_safety_manager()
        is_valid, message = await safety_service.validate_order(order_data)
        
        if not is_valid:
            return {
                "success": False,
                "message": f"Order blocked: {message}"
            }
        
        # Place order
        trading_service = get_trading_service()
        from src.services.trading_execution_service import OrderRequest, OrderSide, OrderType, ProductType
        
        order_request = OrderRequest(
            symbol=order_data['symbol'],
            side=OrderSide[order_data['side']],
            quantity=order_data['quantity'],
            order_type=OrderType[order_data.get('order_type', 'MARKET')],
            product_type=ProductType[order_data.get('product_type', 'OPTIONS')],
            price=order_data.get('price', 0),
            stop_loss=order_data.get('stop_loss', 0),
            target=order_data.get('target', 0)
        )
        
        response = await trading_service.place_order(order_request)
        
        return {
            "success": response.status == 'SUCCESS',
            "order_id": response.order_id,
            "message": response.message,
            "details": response.details
        }
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trading/square-off-all")
async def square_off_all_positions():
    """Square off all positions"""
    try:
        service = get_trading_service()
        responses = await service.square_off_all()
        return {
            "success": True,
            "message": f"Squared off {len(responses)} positions",
            "responses": responses
        }
    except Exception as e:
        logger.error(f"Error squaring off: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trading/toggle-paper-mode")
async def toggle_paper_trading(enabled: bool):
    """Toggle paper trading mode"""
    try:
        service = get_trading_service()
        service.toggle_paper_trading(enabled)
        return {
            "success": True,
            "paper_trading": enabled,
            "message": f"Paper trading {'enabled' if enabled else 'disabled'}"
        }
    except Exception as e:
        logger.error(f"Error toggling paper mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trading/positions")
async def get_trading_positions():
    """Get current trading positions"""
    try:
        service = get_trading_service()
        if service.paper_trading:
            positions = service.get_paper_positions()
        else:
            # Get from broker
            broker_service = get_breeze_service()
            positions = await broker_service.get_positions()
        
        return {
            "success": True,
            "is_paper": service.paper_trading,
            "positions": positions
        }
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= STRATEGY AUTOMATION ENDPOINTS =============

@router.post("/strategy/start-automation")
async def start_strategy_automation():
    """Start strategy automation"""
    try:
        service = get_strategy_service(
            trading_service=get_trading_service(),
            market_service=None  # Use live market service
        )
        await service.start_automation()
        return {
            "success": True,
            "message": "Strategy automation started"
        }
    except Exception as e:
        logger.error(f"Error starting automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategy/stop-automation")
async def stop_strategy_automation():
    """Stop strategy automation"""
    try:
        service = get_strategy_service()
        await service.stop_automation()
        return {
            "success": True,
            "message": "Strategy automation stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategy/active-signals")
async def get_active_strategy_signals():
    """Get active strategy signals"""
    try:
        service = get_strategy_service()
        return {
            "success": True,
            "active_signals": service.get_active_signals()
        }
    except Exception as e:
        logger.error(f"Error getting active signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= ALERT SERVICE ENDPOINTS =============

@router.get("/alerts/active")
async def get_active_alerts():
    """Get active alerts"""
    try:
        service = get_alert_service()
        alerts = service.get_active_alerts()
        return {
            "success": True,
            "alerts": [
                {
                    "alert_id": alert.alert_id,
                    "type": alert.alert_type.value,
                    "priority": alert.priority.value,
                    "title": alert.title,
                    "message": alert.message,
                    "created_at": alert.created_at.isoformat()
                }
                for alert in alerts
            ]
        }
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/create")
async def create_alert(alert_data: Dict):
    """Create new alert"""
    try:
        service = get_alert_service()
        
        alert_id = await service.create_alert(
            alert_type=alert_data['type'],
            title=alert_data['title'],
            message=alert_data['message'],
            condition=alert_data.get('condition', {}),
            priority=alert_data.get('priority', 'MEDIUM')
        )
        
        return {
            "success": True,
            "alert_id": alert_id
        }
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= RISK MANAGEMENT ENDPOINTS =============

@router.get("/risk/metrics")
async def get_risk_metrics():
    """Get risk management metrics"""
    try:
        service = get_risk_management_service()
        return {
            "success": True,
            **service.get_risk_metrics()
        }
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk/status")
async def get_risk_status():
    """Get risk status"""
    try:
        service = get_risk_management_service()
        status = service.get_risk_status()
        return {
            "success": True,
            "risk_status": {
                "open_positions": status.open_positions,
                "total_exposure": status.total_exposure,
                "daily_pnl": status.daily_pnl,
                "risk_level": status.risk_level,
                "can_open_new": status.can_open_new,
                "warnings": status.warnings
            }
        }
    except Exception as e:
        logger.error(f"Error getting risk status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= PERFORMANCE ANALYTICS ENDPOINTS =============

@router.get("/performance/analytics")
async def get_performance_analytics(period: str = "month"):
    """Get performance analytics"""
    try:
        service = get_performance_analytics_service()
        analytics = service.get_performance_analytics(period=period)
        return analytics
    except Exception as e:
        logger.error(f"Error getting performance analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= SYSTEM HEALTH CHECK =============

@router.get("/health")
async def system_health_check():
    """Complete system health check"""
    try:
        health = {
            "timestamp": datetime.now().isoformat(),
            "services": {}
        }
        
        # Check broker connection
        try:
            broker = get_breeze_service()
            health["services"]["broker"] = {
                "status": "connected" if broker.is_connected else "disconnected",
                "details": broker.get_connection_status()
            }
        except:
            health["services"]["broker"] = {"status": "error"}
        
        # Check safety manager
        try:
            safety = get_safety_manager()
            safety_status = safety.get_safety_status()
            health["services"]["safety"] = {
                "status": safety_status["status"],
                "kill_switch": safety_status["kill_switch"],
                "emergency_stop": safety_status["emergency_stop"]
            }
        except:
            health["services"]["safety"] = {"status": "error"}
        
        # Check trading service
        try:
            trading = get_trading_service()
            health["services"]["trading"] = {
                "status": "active",
                "paper_mode": trading.paper_trading
            }
        except:
            health["services"]["trading"] = {"status": "error"}
        
        # Check risk management
        try:
            risk = get_risk_management_service()
            risk_status = risk.get_risk_status()
            health["services"]["risk"] = {
                "status": "active",
                "risk_level": risk_status.risk_level,
                "can_trade": risk_status.can_open_new
            }
        except:
            health["services"]["risk"] = {"status": "error"}
        
        # Overall status
        all_ok = all(
            s.get("status") not in ["error", "disconnected", "CRITICAL", "EMERGENCY", "HALTED"]
            for s in health["services"].values()
        )
        
        health["overall_status"] = "healthy" if all_ok else "degraded"
        
        return health
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "overall_status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }