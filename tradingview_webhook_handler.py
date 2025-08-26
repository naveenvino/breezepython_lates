"""
TradingView Webhook Handler
Implements real webhook functionality for receiving NIFTY data from TradingView
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, date
import json
import logging
import pyodbc
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Webhook data storage
webhook_data = {
    "listening": False,
    "received_count": 0,
    "last_received": None,
    "data_buffer": [],
    "errors": []
}

class TradingViewWebhookData(BaseModel):
    """TradingView webhook payload structure"""
    ticker: str = Field(..., description="Symbol (e.g., NIFTY)")
    time: str = Field(..., description="Timestamp")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: Optional[float] = Field(0, description="Volume")
    interval: Optional[str] = Field("5", description="Timeframe in minutes")
    
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
            # Update webhook stats
            webhook_data["received_count"] += 1
            webhook_data["last_received"] = datetime.now()
            webhook_data["data_buffer"].append(data.dict())
            
            # Keep only last 100 entries in buffer
            if len(webhook_data["data_buffer"]) > 100:
                webhook_data["data_buffer"] = webhook_data["data_buffer"][-100:]
            
            # Store data in background
            background_tasks.add_task(store_nifty_data, data)
            
            logger.info(f"Received TradingView data for {data.ticker} at {data.time}")
            
            return {
                "status": "success",
                "message": "Webhook data received",
                "ticker": data.ticker,
                "timestamp": data.time,
                "received_count": webhook_data["received_count"]
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

# Export the function to add endpoints
__all__ = ['add_tradingview_endpoints', 'TradingViewWebhookData', 'WebhookStatus']