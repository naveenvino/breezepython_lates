"""
TradingView Webhook Handler
Implements real webhook functionality for receiving signals and data from TradingView
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, date
import json
import logging
import pyodbc
from contextlib import contextmanager
import hmac
import hashlib
import os

# Import new services
from src.services.hybrid_data_manager import get_hybrid_data_manager, TradingSignal
from src.services.position_breakeven_tracker import get_position_breakeven_tracker, PositionEntry
from src.services.live_stoploss_monitor import get_live_stoploss_monitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Webhook data storage with enhanced metrics
webhook_data = {
    "listening": False,
    "received_count": 0,
    "last_received": None,
    "last_received_timestamp": None,
    "data_buffer": [],
    "errors": [],
    "daily_count": 0,
    "daily_reset_date": datetime.now().date(),
    "processing_times": [],  # Store last 100 processing times
    "success_count": 0,
    "failure_count": 0
}

# Webhook metrics tracking
webhook_metrics = {
    "total_received": 0,
    "total_processed": 0,
    "avg_processing_ms": 0,
    "last_alert_time": None,
    "last_alert_message": None,
    "alerts_today": []
}

# Webhook secret for HMAC verification
WEBHOOK_SECRET = os.getenv('TRADINGVIEW_WEBHOOK_SECRET', 'your-secret-key')

def verify_webhook_signature(payload: str, signature: str) -> bool:
    """
    Verify webhook signature using HMAC-SHA256
    
    Args:
        payload: The request body as string
        signature: The signature from X-Signature header
        
    Returns:
        True if signature is valid
    """
    if not signature or not WEBHOOK_SECRET:
        return False
        
    try:
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False

class TradingViewWebhookData(BaseModel):
    """TradingView webhook payload structure for OHLC data"""
    ticker: str = Field(..., description="Symbol (e.g., NIFTY)")
    time: str = Field(..., description="Timestamp")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: Optional[float] = Field(0, description="Volume")
    interval: Optional[str] = Field("5", description="Timeframe in minutes")

class TradingViewSignalData(BaseModel):
    """TradingView webhook payload for entry/exit signals"""
    signal: str = Field(..., description="Signal type (S1-S8)")
    action: str = Field(..., description="Action (ENTRY/EXIT)")
    strike: int = Field(..., description="Strike price")
    option_type: str = Field(..., description="Option type (CE/PE)")
    spot_price: float = Field(..., description="Current spot price")
    timestamp: Optional[str] = Field(None, description="Signal timestamp")
    message: Optional[str] = Field(None, description="Additional message")

class TradingViewHourlyData(BaseModel):
    """TradingView webhook payload for hourly candle close"""
    ticker: str = Field("NIFTY", description="Symbol")
    timestamp: str = Field(..., description="Hourly timestamp")
    open: float = Field(..., description="Hourly open")
    high: float = Field(..., description="Hourly high")
    low: float = Field(..., description="Hourly low")
    close: float = Field(..., description="Hourly close")
    volume: Optional[float] = Field(0, description="Hourly volume")
    
class WebhookStatus(BaseModel):
    """Webhook status response"""
    listening: bool
    received_count: int
    last_received: Optional[datetime]
    buffer_size: int
    errors: List[str]

def get_db_connection():
    """Create database connection"""
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=(localdb)\\mssqllocaldb;"
        "DATABASE=KiteConnectApi;"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)

@contextmanager
def get_db():
    """Database connection context manager"""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def store_nifty_data(data: TradingViewWebhookData):
    """Store NIFTY data in database"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Parse timestamp
            timestamp = datetime.fromisoformat(data.time.replace('Z', '+00:00'))
            
            # Check if data exists
            cursor.execute("""
                SELECT COUNT(*) FROM NiftyIndexData5Minute 
                WHERE timestamp = ? AND symbol = 'NIFTY'
            """, (timestamp,))
            
            if cursor.fetchone()[0] > 0:
                # Update existing record
                cursor.execute("""
                    UPDATE NiftyIndexData5Minute 
                    SET [open] = ?, high = ?, low = ?, [close] = ?, volume = ?
                    WHERE timestamp = ? AND symbol = 'NIFTY'
                """, (data.open, data.high, data.low, data.close, data.volume or 0, timestamp))
                logger.info(f"Updated NIFTY data for {timestamp}")
            else:
                # Insert new record with all required columns
                cursor.execute("""
                    INSERT INTO NiftyIndexData5Minute (
                        symbol, timestamp, [open], high, low, [close], volume,
                        LastPrice, LastUpdateTime, OpenInterest, ChangePercent,
                        BidPrice, AskPrice, BidQuantity, AskQuantity, CreatedAt
                    )
                    VALUES ('NIFTY', ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, GETDATE())
                """, (
                    timestamp, data.open, data.high, data.low, data.close, 
                    data.volume or 0, data.close, timestamp
                ))
                logger.info(f"Inserted new NIFTY data for {timestamp}")
            
            conn.commit()
            
            # Also update hourly data if it's an hour boundary
            if timestamp.minute == 0:
                cursor.execute("""
                    MERGE NiftyIndexDataHourly AS target
                    USING (SELECT 'NIFTY' as symbol, ? as timestamp, ? as [open], ? as high, 
                                  ? as low, ? as [close], ? as volume) AS source
                    ON target.timestamp = source.timestamp AND target.symbol = source.symbol
                    WHEN MATCHED THEN
                        UPDATE SET [open] = source.[open], high = source.high,
                                   low = source.low, [close] = source.[close],
                                   volume = source.volume
                    WHEN NOT MATCHED THEN
                        INSERT (symbol, timestamp, [open], high, low, [close], volume)
                        VALUES (source.symbol, source.timestamp, source.[open], source.high,
                                source.low, source.[close], source.volume);
                """, (timestamp, data.open, data.high, data.low, data.close, data.volume or 0))
                conn.commit()
                logger.info(f"Updated hourly data for {timestamp}")
                
    except Exception as e:
        logger.error(f"Error storing NIFTY data: {str(e)}")
        webhook_data["errors"].append(f"{datetime.now()}: {str(e)}")
        raise

def add_tradingview_endpoints(app: FastAPI):
    """Add TradingView webhook endpoints to FastAPI app"""
    
    @app.post("/webhook/tradingview", tags=["TradingView Webhook"])
    async def receive_tradingview_webhook(
        data: TradingViewWebhookData,
        background_tasks: BackgroundTasks
    ):
        """
        Receive and process TradingView webhook data
        
        Configure this endpoint URL in your TradingView alert:
        http://localhost:8000/webhook/tradingview
        
        Alert message format:
        {
            "ticker": "{{ticker}}",
            "time": "{{time}}",
            "open": {{open}},
            "high": {{high}},
            "low": {{low}},
            "close": {{close}},
            "volume": {{volume}}
        }
        """
        try:
            # Track processing start time
            process_start = datetime.now()
            
            # Reset daily count if new day
            if datetime.now().date() != webhook_data["daily_reset_date"]:
                webhook_data["daily_count"] = 0
                webhook_data["daily_reset_date"] = datetime.now().date()
                webhook_metrics["alerts_today"] = []
            
            # Update webhook stats
            webhook_data["received_count"] += 1
            webhook_data["daily_count"] += 1
            webhook_data["last_received"] = datetime.now()
            webhook_data["last_received_timestamp"] = datetime.now().isoformat()
            webhook_data["data_buffer"].append(data.dict())
            
            # Update metrics
            webhook_metrics["total_received"] += 1
            webhook_metrics["last_alert_time"] = datetime.now().isoformat()
            webhook_metrics["last_alert_message"] = f"{data.ticker} at {data.close}"
            webhook_metrics["alerts_today"].append({
                "time": datetime.now().isoformat(),
                "ticker": data.ticker,
                "close": data.close
            })
            
            # Keep only last 100 entries in buffer
            if len(webhook_data["data_buffer"]) > 100:
                webhook_data["data_buffer"] = webhook_data["data_buffer"][-100:]
            
            # Keep only today's alerts
            if len(webhook_metrics["alerts_today"]) > 100:
                webhook_metrics["alerts_today"] = webhook_metrics["alerts_today"][-100:]
            
            # Store data in background
            background_tasks.add_task(store_nifty_data, data)
            
            # Calculate processing time
            process_end = datetime.now()
            process_time_ms = (process_end - process_start).total_seconds() * 1000
            webhook_data["processing_times"].append(process_time_ms)
            
            # Keep only last 100 processing times
            if len(webhook_data["processing_times"]) > 100:
                webhook_data["processing_times"] = webhook_data["processing_times"][-100:]
            
            # Update average processing time
            if webhook_data["processing_times"]:
                webhook_metrics["avg_processing_ms"] = sum(webhook_data["processing_times"]) / len(webhook_data["processing_times"])
            
            webhook_data["success_count"] += 1
            webhook_metrics["total_processed"] += 1
            
            logger.info(f"Received TradingView data for {data.ticker} at {data.time} - Processing: {process_time_ms:.2f}ms")
            
            return {
                "status": "success",
                "message": "Webhook data received",
                "ticker": data.ticker,
                "timestamp": data.time,
                "received_count": webhook_data["received_count"],
                "processing_ms": round(process_time_ms, 2)
            }
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            webhook_data["errors"].append(f"{datetime.now()}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/webhook/start", tags=["TradingView Webhook"])
    async def start_webhook_listener():
        """Start listening for TradingView webhooks"""
        webhook_data["listening"] = True
        webhook_data["received_count"] = 0
        webhook_data["data_buffer"] = []
        webhook_data["errors"] = []
        
        return {
            "status": "success",
            "message": "Webhook listener started",
            "webhook_url": "http://localhost:8000/webhook/tradingview",
            "instructions": "Configure this URL in your TradingView alert"
        }
    
    @app.post("/webhook/stop", tags=["TradingView Webhook"])
    async def stop_webhook_listener():
        """Stop listening for TradingView webhooks"""
        webhook_data["listening"] = False
        
        return {
            "status": "success",
            "message": "Webhook listener stopped",
            "received_count": webhook_data["received_count"]
        }
    
    @app.get("/webhook/status", response_model=WebhookStatus, tags=["TradingView Webhook"])
    async def get_webhook_status():
        """Get current webhook listener status"""
        return WebhookStatus(
            listening=webhook_data["listening"],
            received_count=webhook_data["received_count"],
            last_received=webhook_data["last_received"],
            buffer_size=len(webhook_data["data_buffer"]),
            errors=webhook_data["errors"][-10:]  # Last 10 errors
        )
    
    @app.get("/webhook/data", tags=["TradingView Webhook"])
    async def get_webhook_data(
        limit: int = 100
    ):
        """Get received webhook data from buffer"""
        return {
            "status": "success",
            "count": len(webhook_data["data_buffer"]),
            "data": webhook_data["data_buffer"][-limit:]
        }
    
    @app.get("/api/webhook/metrics", tags=["TradingView Webhook"])
    async def get_webhook_metrics():
        """Get comprehensive webhook metrics for display"""
        now = datetime.now()
        
        # Calculate seconds since last webhook
        seconds_ago = None
        if webhook_data["last_received"]:
            seconds_ago = (now - webhook_data["last_received"]).total_seconds()
        
        # Determine webhook status
        if seconds_ago is None:
            status = "never"
            status_color = "gray"
        elif seconds_ago < 60:
            status = "active"
            status_color = "green"
        elif seconds_ago < 300:
            status = "idle"
            status_color = "orange"
        else:
            status = "inactive"
            status_color = "red"
        
        return {
            "last_received": webhook_data["last_received_timestamp"],
            "seconds_ago": round(seconds_ago, 0) if seconds_ago else None,
            "webhooks_today": webhook_data["daily_count"],
            "total_webhooks": webhook_data["received_count"],
            "avg_processing_ms": round(webhook_metrics["avg_processing_ms"], 2),
            "status": status,
            "status_color": status_color,
            "last_alert_message": webhook_metrics["last_alert_message"],
            "success_rate": round((webhook_data["success_count"] / max(webhook_data["received_count"], 1)) * 100, 1),
            "recent_alerts": webhook_metrics["alerts_today"][-5:]  # Last 5 alerts
        }
    
    @app.delete("/webhook/buffer", tags=["TradingView Webhook"])
    async def clear_webhook_buffer():
        """Clear webhook data buffer"""
        webhook_data["data_buffer"] = []
        webhook_data["errors"] = []
        
        return {
            "status": "success",
            "message": "Webhook buffer cleared"
        }
    
    @app.post("/collect/tradingview-historical", tags=["TradingView Collection"])
    async def collect_tradingview_historical(
        from_date: date,
        to_date: date,
        symbol: str = "NIFTY"
    ):
        """
        Collect historical data from TradingView buffer
        This processes already received webhook data
        """
        try:
            processed = 0
            errors = []
            
            for data_dict in webhook_data["data_buffer"]:
                try:
                    webhook_payload = TradingViewWebhookData(**data_dict)
                    
                    # Check if within date range
                    data_time = datetime.fromisoformat(webhook_payload.time.replace('Z', '+00:00'))
                    if from_date <= data_time.date() <= to_date:
                        store_nifty_data(webhook_payload)
                        processed += 1
                except Exception as e:
                    errors.append(str(e))
            
            return {
                "status": "success",
                "message": f"Processed {processed} records from buffer",
                "errors": errors[:5] if errors else None
            }
            
        except Exception as e:
            logger.error(f"Error processing historical data: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/webhook/entry", tags=["TradingView Pro"])
    async def receive_entry_signal(
        request: Request,
        background_tasks: BackgroundTasks,
        x_signature: Optional[str] = Header(None),
        x_tradingview_signature: Optional[str] = Header(None)
    ):
        """
        Receive entry signal from TradingView
        
        Accepts both formats:
        1. PineScript format: {"strike": 25000, "type": "PE", "signal": "S1", "action": "Entry"}
        2. Extended format: {"strike": 25000, "option_type": "PE", "signal": "S1", "action": "ENTRY", "spot_price": 25050}
        
        For security, add X-TradingView-Signature header in TradingView alert
        """
        try:
            # Get raw body
            body = await request.body()
            body_str = body.decode()
            
            # Parse JSON manually to handle both formats
            import json
            raw_data = json.loads(body_str)
            
            # Normalize the data to match TradingViewSignalData
            normalized_data = {
                "signal": raw_data.get("signal"),
                "action": raw_data.get("action", "").upper(),  # Normalize to uppercase
                "strike": raw_data.get("strike"),
                "option_type": raw_data.get("option_type") or raw_data.get("type"),  # Accept both field names
                "spot_price": raw_data.get("spot_price", 0.0),  # Default if not provided
                "timestamp": raw_data.get("timestamp"),
                "message": raw_data.get("message")
            }
            
            # If spot_price is 0, try to get current spot from Breeze
            if normalized_data["spot_price"] == 0.0:
                try:
                    from src.services.breeze_ws_manager import get_breeze_manager
                    breeze = get_breeze_manager()
                    status = breeze.get_status()
                    if status.get("spot_price"):
                        normalized_data["spot_price"] = status["spot_price"]
                    else:
                        # Use strike as approximate spot if nothing else available
                        normalized_data["spot_price"] = normalized_data["strike"]
                except:
                    normalized_data["spot_price"] = normalized_data["strike"]
            
            # Create TradingViewSignalData object
            data = TradingViewSignalData(**normalized_data)
            
            # Verify webhook signature if enabled
            signature = x_tradingview_signature or x_signature
            if WEBHOOK_SECRET != 'your-secret-key':
                if signature and not verify_webhook_signature(body_str, signature):
                    logger.warning(f"Invalid webhook signature for signal {data.signal}")
                    raise HTTPException(status_code=401, detail="Invalid webhook signature")
                elif not signature:
                    logger.warning(f"Missing webhook signature for signal {data.signal}")
                    # Optional: Reject if signature is required
                    # raise HTTPException(status_code=401, detail="Missing webhook signature")
            
            logger.info(f"Received entry signal: {data.signal} {data.strike} {data.option_type}")
            
            # Get services
            data_manager = get_hybrid_data_manager()
            position_tracker = get_position_breakeven_tracker()
            
            # Create trading signal
            signal = TradingSignal(
                signal_type=data.signal,
                action=data.action,
                strike=data.strike,
                option_type=data.option_type,
                timestamp=datetime.fromisoformat(data.timestamp) if data.timestamp else datetime.now(),
                price=data.spot_price,
                processed=False
            )
            
            # Store signal
            data_manager.add_signal(signal)
            
            # Create position ONLY if entry signal (not exit)
            if data.action == "ENTRY":
                # Check if position already exists for this signal
                existing_positions = data_manager.get_active_positions()
                for pos in existing_positions:
                    if pos['signal_type'] == data.signal and pos.get('status') not in ['closed', 'closing']:
                        logger.warning(f"Position for {data.signal} already exists, ignoring duplicate entry")
                        return {
                            "status": "duplicate",
                            "message": f"Active position for {data.signal} already exists",
                            "position_id": pos['id']
                        }
                
                entry = PositionEntry(
                    signal_type=data.signal,
                    main_strike=data.strike,
                    option_type=data.option_type,
                    quantity=10,
                    hedge_percent=30.0,
                    enable_hedge=True
                )
                
                result = position_tracker.create_position(entry)
                
                logger.info(f"Entry signal processed: {data.signal} {data.strike} {data.option_type}")
                return {"status": "success", "signal": data.signal, "position": result}
            elif data.action == "EXIT":
                # This should not happen - exit signals should go to /webhook/exit endpoint
                logger.warning(f"EXIT signal received on entry endpoint - redirecting to proper handler")
                return {
                    "status": "wrong_endpoint",
                    "message": "EXIT signals should be sent to /webhook/exit endpoint",
                    "signal": data.signal
                }
            
            return {"status": "success", "signal": data.signal}
            
        except Exception as e:
            logger.error(f"Error processing entry signal: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/webhook/exit", tags=["TradingView Pro"])
    async def receive_exit_signal(
        request: Request,
        background_tasks: BackgroundTasks,
        x_signature: Optional[str] = Header(None),
        x_tradingview_signature: Optional[str] = Header(None)
    ):
        """
        Receive exit/stop loss signal from TradingView
        
        Accepts both formats:
        1. PineScript format: {"strike": 25000, "type": "PE", "signal": "S1", "action": "Exit"}
        2. Extended format: {"strike": 25000, "option_type": "PE", "signal": "S1", "action": "EXIT", "spot_price": 25100}
        """
        try:
            # Get raw body and normalize format (same as entry)
            body = await request.body()
            body_str = body.decode()
            
            import json
            raw_data = json.loads(body_str)
            
            # Normalize the data
            normalized_data = {
                "signal": raw_data.get("signal"),
                "action": raw_data.get("action", "").upper(),
                "strike": raw_data.get("strike"),
                "option_type": raw_data.get("option_type") or raw_data.get("type"),
                "spot_price": raw_data.get("spot_price", 0.0),
                "timestamp": raw_data.get("timestamp"),
                "message": raw_data.get("message", "Exit signal from TradingView")
            }
            
            # If spot_price is 0, get current spot
            if normalized_data["spot_price"] == 0.0:
                try:
                    from src.services.breeze_ws_manager import get_breeze_manager
                    breeze = get_breeze_manager()
                    status = breeze.get_status()
                    if status.get("spot_price"):
                        normalized_data["spot_price"] = status["spot_price"]
                    else:
                        normalized_data["spot_price"] = normalized_data["strike"]
                except:
                    normalized_data["spot_price"] = normalized_data["strike"]
            
            # Create TradingViewSignalData object
            data = TradingViewSignalData(**normalized_data)
            
            # Get services
            data_manager = get_hybrid_data_manager()
            position_tracker = get_position_breakeven_tracker()
            
            # Find and close matching positions
            positions = data_manager.get_active_positions()
            closed_count = 0
            position_found = False
            
            for pos in positions:
                if pos['signal_type'] == data.signal and pos['main_strike'] == data.strike:
                    position_found = True
                    # Check if already closing/closed to prevent duplicate
                    if pos.get('status') in ['closing', 'closed']:
                        logger.warning(f"Position {pos['id']} already {pos.get('status')}, skipping exit")
                        return {
                            "status": "duplicate", 
                            "message": f"Position for {data.signal} already {pos.get('status')}",
                            "position_id": pos['id']
                        }
                    
                    # Mark as closing first to prevent stop-loss monitor from also triggering
                    pos['status'] = 'closing'
                    
                    result = position_tracker.close_position(
                        pos['id'],
                        data.message or "TradingView exit signal"
                    )
                    closed_count += 1
            
            # IMPORTANT: If no position found, DO NOT create new one
            if not position_found:
                logger.warning(f"EXIT signal for {data.signal} {data.strike} - no active position found to close")
                return {
                    "status": "no_position",
                    "message": f"No active position found for {data.signal} at strike {data.strike}",
                    "action": "ignored"
                }
            
            logger.info(f"Exit signal processed: {data.signal} {data.strike}, closed {closed_count} positions")
            return {"status": "success", "closed_positions": closed_count}
            
        except Exception as e:
            logger.error(f"Error processing exit signal: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/webhook/hourly", tags=["TradingView Pro"])
    async def receive_hourly_candle(
        data: TradingViewHourlyData,
        background_tasks: BackgroundTasks
    ):
        """
        Receive hourly candle close from TradingView
        
        Configure on 1H timeframe with alert:
        {
            "ticker": "NIFTY",
            "timestamp": "{{time}}",
            "open": {{open}},
            "high": {{high}},
            "low": {{low}},
            "close": {{close}},
            "volume": {{volume}}
        }
        """
        try:
            # Get services
            data_manager = get_hybrid_data_manager()
            stoploss_monitor = get_live_stoploss_monitor()
            
            # Update data manager with hourly candle
            timestamp = datetime.fromisoformat(data.timestamp) if data.timestamp else datetime.now()
            
            # Force candle completion with this data
            data_manager.update_tick(data.close, timestamp)
            
            # Trigger stop loss check for all positions
            positions = data_manager.get_active_positions()
            for pos in positions:
                stoploss_monitor.check_position_now(pos['id'])
            
            logger.info(f"Hourly candle processed: {timestamp} C:{data.close}")
            return {
                "status": "success",
                "candle": {
                    "time": timestamp.isoformat(),
                    "close": data.close
                },
                "positions_checked": len(positions)
            }
            
        except Exception as e:
            logger.error(f"Error processing hourly candle: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    logger.info("TradingView webhook endpoints added (including Pro trading signals)")

# Export the function to add endpoints
__all__ = ['add_tradingview_endpoints', 'TradingViewWebhookData', 'TradingViewSignalData', 'TradingViewHourlyData', 'WebhookStatus']