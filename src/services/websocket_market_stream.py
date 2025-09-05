"""
WebSocket Market Data Streaming Service
Handles real-time market data streaming via WebSocket
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
from src.services.live_market_service import get_market_service

logger = logging.getLogger(__name__)

class MarketDataWebSocket:
    """Manages WebSocket connections for market data streaming"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Dict] = {}
        self.market_service = get_market_service()
        self.streaming_task = None
        self.is_streaming = False
        
    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = {
            'symbols': [],
            'data_types': ['quote']
        }
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
        
        # Send initial connection message
        await self.send_personal_message(
            {"type": "connection", "status": "connected", "timestamp": datetime.now().isoformat()},
            websocket
        )
        
        # Start streaming if not already running
        if not self.is_streaming:
            await self.start_streaming()
    
    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")
        
        # Stop streaming if no connections
        if not self.active_connections and self.is_streaming:
            self.stop_streaming()
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific WebSocket client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def handle_message(self, websocket: WebSocket, data: dict):
        """Handle incoming WebSocket messages"""
        try:
            action = data.get('action')
            
            if action == 'subscribe':
                await self.handle_subscription(websocket, data)
            elif action == 'unsubscribe':
                await self.handle_unsubscription(websocket, data)
            elif action == 'ping':
                await self.send_personal_message(
                    {"type": "pong", "timestamp": datetime.now().isoformat()},
                    websocket
                )
            else:
                logger.warning(f"Unknown action: {action}")
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def handle_subscription(self, websocket: WebSocket, data: dict):
        """Handle subscription request"""
        symbols = data.get('symbols', [])
        data_types = data.get('data_types', ['quote'])
        
        if websocket in self.subscriptions:
            self.subscriptions[websocket]['symbols'] = symbols
            self.subscriptions[websocket]['data_types'] = data_types
        
        # Send confirmation
        await self.send_personal_message({
            "type": "subscription",
            "status": "confirmed",
            "symbols": symbols,
            "data_types": data_types,
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        logger.info(f"Client subscribed to symbols: {symbols}, data types: {data_types}")
    
    async def handle_unsubscription(self, websocket: WebSocket, data: dict):
        """Handle unsubscription request"""
        symbols = data.get('symbols', [])
        
        if websocket in self.subscriptions:
            current_symbols = self.subscriptions[websocket]['symbols']
            self.subscriptions[websocket]['symbols'] = [
                s for s in current_symbols if s not in symbols
            ]
        
        # Send confirmation
        await self.send_personal_message({
            "type": "unsubscription",
            "status": "confirmed",
            "symbols": symbols,
            "timestamp": datetime.now().isoformat()
        }, websocket)
    
    async def start_streaming(self):
        """Start market data streaming"""
        if self.is_streaming:
            return
        
        self.is_streaming = True
        self.streaming_task = asyncio.create_task(self.stream_market_data())
        logger.info("Started market data streaming")
    
    def stop_streaming(self):
        """Stop market data streaming"""
        self.is_streaming = False
        
        if self.streaming_task:
            self.streaming_task.cancel()
            self.streaming_task = None
        
        logger.info("Stopped market data streaming")
    
    async def stream_market_data(self):
        """Stream market data to all connected clients"""
        # Initialize market service
        await self.market_service.initialize()
        
        while self.is_streaming and self.active_connections:
            try:
                # Get all subscribed symbols
                all_symbols = set()
                for subscription in self.subscriptions.values():
                    all_symbols.update(subscription.get('symbols', []))
                
                # If no specific symbols, stream default indices
                if not all_symbols:
                    all_symbols = {'NIFTY', 'BANKNIFTY'}
                
                # Fetch market data
                market_data = await self.market_service.get_all_market_data()
                
                # Broadcast quotes
                if market_data:
                    await self.broadcast({
                        "type": "quote",
                        "data": market_data,
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Stream option chain for NIFTY (if subscribed)
                if 'NIFTY' in all_symbols:
                    # Get ATM strike
                    nifty_spot = market_data.get('NIFTY', {}).get('ltp', 25000)
                    atm_strike = round(nifty_spot / 50) * 50
                    
                    # Fetch option chain
                    option_chain = await self.market_service.get_option_chain(
                        center_strike=atm_strike,
                        range_count=5
                    )
                    
                    if option_chain:
                        await self.broadcast({
                            "type": "option_chain",
                            "data": option_chain,
                            "timestamp": datetime.now().isoformat()
                        })
                
                # Wait before next update (1 second for quotes)
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in market data streaming: {e}")
                await asyncio.sleep(5)  # Wait longer on error
    
    async def stream_positions(self, positions: List[Dict]):
        """Stream position updates to all clients"""
        await self.broadcast({
            "type": "position",
            "data": positions,
            "timestamp": datetime.now().isoformat()
        })
    
    async def stream_alerts(self, alert: Dict):
        """Stream alert notifications to all clients"""
        await self.broadcast({
            "type": "alert",
            "data": alert,
            "timestamp": datetime.now().isoformat()
        })
    
    async def stream_orders(self, order: Dict):
        """Stream order updates to all clients"""
        await self.broadcast({
            "type": "order",
            "data": order,
            "timestamp": datetime.now().isoformat()
        })

# Singleton instance
_websocket_manager = None

def get_websocket_manager() -> MarketDataWebSocket:
    """Get singleton WebSocket manager instance"""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = MarketDataWebSocket()
    return _websocket_manager

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint handler"""
    manager = get_websocket_manager()
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            await manager.handle_message(websocket, data)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)