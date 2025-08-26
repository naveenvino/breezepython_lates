"""
ZeroMQ-based WebSocket Server for High-Performance Real-time Data
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime
import zmq
import zmq.asyncio
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class ZMQWebSocketServer:
    """
    High-performance WebSocket server using ZeroMQ for message distribution
    """
    
    def __init__(self, zmq_pub_port: int = 5555, zmq_sub_port: int = 5556):
        self.zmq_pub_port = zmq_pub_port
        self.zmq_sub_port = zmq_sub_port
        
        # ZeroMQ context
        self.zmq_context = zmq.asyncio.Context()
        
        # Publishers and subscribers
        self.pub_socket = None
        self.sub_socket = None
        
        # Connected WebSocket clients
        self.clients: Dict[str, WebSocket] = {}
        self.client_subscriptions: Dict[str, Set[str]] = {}
        
        # Market data cache for new connections
        self.market_data_cache: Dict[str, Any] = {}
        
        # Performance metrics
        self.metrics = {
            'messages_sent': 0,
            'messages_received': 0,
            'clients_connected': 0,
            'errors': 0
        }
    
    async def start(self):
        """Start ZeroMQ sockets"""
        try:
            # Publisher socket for sending data to clients
            self.pub_socket = self.zmq_context.socket(zmq.PUB)
            self.pub_socket.bind(f"tcp://127.0.0.1:{self.zmq_pub_port}")
            
            # Subscriber socket for receiving market data
            self.sub_socket = self.zmq_context.socket(zmq.SUB)
            self.sub_socket.connect(f"tcp://127.0.0.1:{self.zmq_sub_port}")
            self.sub_socket.subscribe(b"")  # Subscribe to all topics
            
            logger.info(f"ZMQ WebSocket server started - PUB:{self.zmq_pub_port}, SUB:{self.zmq_sub_port}")
            
            # Start the message distributor
            asyncio.create_task(self._message_distributor())
            
        except Exception as e:
            logger.error(f"Failed to start ZMQ server: {e}")
            raise
    
    async def stop(self):
        """Stop ZeroMQ sockets"""
        if self.pub_socket:
            self.pub_socket.close()
        if self.sub_socket:
            self.sub_socket.close()
        self.zmq_context.term()
        logger.info("ZMQ WebSocket server stopped")
    
    async def _message_distributor(self):
        """Distribute messages from ZeroMQ to WebSocket clients"""
        while True:
            try:
                # Receive message from ZeroMQ
                message = await self.sub_socket.recv_multipart()
                
                if len(message) >= 2:
                    topic = message[0].decode('utf-8')
                    data = json.loads(message[1].decode('utf-8'))
                    
                    # Cache market data for new connections
                    if topic in ['market_data', 'option_chain', 'positions']:
                        self.market_data_cache[topic] = data
                    
                    # Send to subscribed clients
                    await self._broadcast_to_clients(topic, data)
                    
                    self.metrics['messages_received'] += 1
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message distributor: {e}")
                self.metrics['errors'] += 1
                await asyncio.sleep(0.1)
    
    async def _broadcast_to_clients(self, topic: str, data: Dict):
        """Broadcast message to all subscribed clients"""
        disconnected_clients = []
        
        for client_id, websocket in self.clients.items():
            try:
                # Check if client is subscribed to this topic
                if topic in self.client_subscriptions.get(client_id, set()):
                    await websocket.send_json({
                        'type': topic,
                        'data': data,
                        'timestamp': datetime.now().isoformat()
                    })
                    self.metrics['messages_sent'] += 1
            except:
                # Mark for disconnection
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect_client(client_id)
    
    async def connect_client(self, websocket: WebSocket) -> str:
        """Connect a new WebSocket client"""
        await websocket.accept()
        
        client_id = f"client_{id(websocket)}"
        self.clients[client_id] = websocket
        self.client_subscriptions[client_id] = set()
        self.metrics['clients_connected'] += 1
        
        # Send connection confirmation
        await websocket.send_json({
            'type': 'connection',
            'status': 'connected',
            'client_id': client_id,
            'timestamp': datetime.now().isoformat()
        })
        
        # Send cached market data
        for topic, data in self.market_data_cache.items():
            await websocket.send_json({
                'type': topic,
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'cached': True
            })
        
        logger.info(f"Client connected: {client_id}")
        return client_id
    
    async def disconnect_client(self, client_id: str):
        """Disconnect a WebSocket client"""
        if client_id in self.clients:
            del self.clients[client_id]
            del self.client_subscriptions[client_id]
            self.metrics['clients_connected'] -= 1
            logger.info(f"Client disconnected: {client_id}")
    
    async def handle_client_message(self, client_id: str, message: Dict):
        """Handle incoming message from client"""
        msg_type = message.get('type')
        
        if msg_type == 'subscribe':
            channels = message.get('channels', [])
            self.client_subscriptions[client_id].update(channels)
            
            await self.clients[client_id].send_json({
                'type': 'subscription',
                'status': 'subscribed',
                'channels': channels,
                'timestamp': datetime.now().isoformat()
            })
            
        elif msg_type == 'unsubscribe':
            channels = message.get('channels', [])
            self.client_subscriptions[client_id].difference_update(channels)
            
            await self.clients[client_id].send_json({
                'type': 'subscription',
                'status': 'unsubscribed',
                'channels': channels,
                'timestamp': datetime.now().isoformat()
            })
            
        elif msg_type == 'ping':
            await self.clients[client_id].send_json({
                'type': 'pong',
                'timestamp': datetime.now().isoformat()
            })
    
    async def publish_market_data(self, symbol: str, data: Dict):
        """Publish market data to ZeroMQ"""
        if self.pub_socket:
            message = {
                'symbol': symbol,
                'ltp': data.get('ltp'),
                'volume': data.get('volume'),
                'bid': data.get('bid'),
                'ask': data.get('ask'),
                'timestamp': datetime.now().isoformat()
            }
            
            await self.pub_socket.send_multipart([
                b'market_data',
                json.dumps(message).encode('utf-8')
            ])
    
    async def publish_order_update(self, order_data: Dict):
        """Publish order update to ZeroMQ"""
        if self.pub_socket:
            await self.pub_socket.send_multipart([
                b'order_update',
                json.dumps(order_data).encode('utf-8')
            ])
    
    async def publish_position_update(self, position_data: Dict):
        """Publish position update to ZeroMQ"""
        if self.pub_socket:
            await self.pub_socket.send_multipart([
                b'positions',
                json.dumps(position_data).encode('utf-8')
            ])
    
    def get_metrics(self) -> Dict:
        """Get server metrics"""
        return {
            **self.metrics,
            'active_clients': len(self.clients),
            'timestamp': datetime.now().isoformat()
        }


class MarketDataPublisher:
    """
    Publishes market data to ZeroMQ for distribution
    """
    
    def __init__(self, port: int = 5556):
        self.port = port
        self.context = zmq.asyncio.Context()
        self.socket = None
    
    async def start(self):
        """Start the publisher"""
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://127.0.0.1:{self.port}")
        logger.info(f"Market data publisher started on port {self.port}")
    
    async def stop(self):
        """Stop the publisher"""
        if self.socket:
            self.socket.close()
        self.context.term()
    
    async def publish(self, topic: str, data: Dict):
        """Publish data to a topic"""
        if self.socket:
            await self.socket.send_multipart([
                topic.encode('utf-8'),
                json.dumps(data).encode('utf-8')
            ])


# Global instance
_zmq_server: Optional[ZMQWebSocketServer] = None
_market_publisher: Optional[MarketDataPublisher] = None

async def get_zmq_server() -> ZMQWebSocketServer:
    """Get or create ZMQ WebSocket server instance"""
    global _zmq_server
    if _zmq_server is None:
        _zmq_server = ZMQWebSocketServer()
        await _zmq_server.start()
    return _zmq_server

async def get_market_publisher() -> MarketDataPublisher:
    """Get or create market data publisher instance"""
    global _market_publisher
    if _market_publisher is None:
        _market_publisher = MarketDataPublisher()
        await _market_publisher.start()
    return _market_publisher

@asynccontextmanager
async def zmq_lifespan():
    """Lifecycle manager for ZMQ components"""
    server = await get_zmq_server()
    publisher = await get_market_publisher()
    
    yield
    
    await server.stop()
    await publisher.stop()