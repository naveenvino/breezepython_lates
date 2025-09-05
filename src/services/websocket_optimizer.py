"""
WebSocket Performance Optimizer
Optimizes WebSocket connections for multiple data streams
"""

import logging
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import websockets
from collections import deque, defaultdict
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class StreamType(Enum):
    TICK = "tick"
    DEPTH = "depth"
    OHLC = "ohlc"
    ORDER_UPDATE = "order_update"

class ConnectionState(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"

@dataclass
class StreamConfig:
    """Configuration for a data stream"""
    stream_type: StreamType
    symbols: List[str]
    throttle_ms: int = 100  # Minimum time between updates
    batch_size: int = 10  # Batch multiple updates
    compression: bool = True
    priority: int = 1  # Lower = higher priority
    
@dataclass
class StreamMetrics:
    """Metrics for stream performance"""
    messages_received: int = 0
    messages_processed: int = 0
    messages_dropped: int = 0
    bytes_received: int = 0
    avg_latency_ms: float = 0
    peak_latency_ms: float = 0
    last_message_time: Optional[datetime] = None
    reconnect_count: int = 0
    error_count: int = 0

@dataclass
class WebSocketPool:
    """Pool of WebSocket connections"""
    url: str
    max_connections: int = 5
    connections: List[Any] = field(default_factory=list)
    available: List[Any] = field(default_factory=list)
    in_use: Dict[str, Any] = field(default_factory=dict)

class WebSocketOptimizer:
    """
    Optimizes WebSocket performance with connection pooling and smart batching
    """
    
    def __init__(self):
        # Connection management
        self.pools: Dict[str, WebSocketPool] = {}
        self.connection_states: Dict[str, ConnectionState] = {}
        
        # Stream management
        self.stream_configs: Dict[str, StreamConfig] = {}
        self.stream_metrics: Dict[str, StreamMetrics] = defaultdict(StreamMetrics)
        self.stream_handlers: Dict[StreamType, List[Callable]] = defaultdict(list)
        
        # Message processing
        self.message_queue: Dict[StreamType, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.batch_buffers: Dict[StreamType, List] = defaultdict(list)
        self.last_batch_time: Dict[StreamType, float] = defaultdict(float)
        
        # Performance optimization
        self.throttle_timers: Dict[str, float] = {}
        self.dedupe_cache: Dict[str, str] = {}  # For deduplication
        self.compression_enabled = True
        
        # Symbol subscriptions
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self.symbol_mapping: Dict[str, str] = {}  # Symbol to stream mapping
        
        # Threading
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.processing_tasks = {}
        
        # Start background tasks
        self._start_background_tasks()
    
    def create_pool(self, name: str, url: str, max_connections: int = 5) -> WebSocketPool:
        """Create a WebSocket connection pool"""
        pool = WebSocketPool(
            url=url,
            max_connections=max_connections
        )
        self.pools[name] = pool
        
        # Create initial connections
        for i in range(min(2, max_connections)):  # Start with 2 connections
            asyncio.create_task(self._create_connection(pool))
        
        logger.info(f"Created WebSocket pool '{name}' with max {max_connections} connections")
        return pool
    
    async def _create_connection(self, pool: WebSocketPool) -> Any:
        """Create a new WebSocket connection for the pool"""
        try:
            ws = await websockets.connect(
                pool.url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10,
                max_size=10 * 1024 * 1024,  # 10MB max message size
                compression='deflate' if self.compression_enabled else None
            )
            
            pool.connections.append(ws)
            pool.available.append(ws)
            
            # Start message receiver
            asyncio.create_task(self._receive_messages(ws))
            
            logger.info(f"Created WebSocket connection to {pool.url}")
            return ws
            
        except Exception as e:
            logger.error(f"Error creating WebSocket connection: {e}")
            return None
    
    async def subscribe(self, stream_type: StreamType, symbols: List[str], config: Optional[StreamConfig] = None):
        """
        Subscribe to symbols with optimized streaming
        
        Args:
            stream_type: Type of data stream
            symbols: List of symbols to subscribe
            config: Optional stream configuration
        """
        # Create or update stream config
        stream_id = f"{stream_type.value}_{len(self.stream_configs)}"
        
        if config:
            self.stream_configs[stream_id] = config
        else:
            self.stream_configs[stream_id] = StreamConfig(
                stream_type=stream_type,
                symbols=symbols
            )
        
        # Batch symbols for efficient subscription
        batch_size = 50  # Subscribe 50 symbols at a time
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            await self._subscribe_batch(stream_type, batch)
            
            # Small delay between batches to avoid overwhelming the server
            if i + batch_size < len(symbols):
                await asyncio.sleep(0.1)
        
        # Update subscriptions
        for symbol in symbols:
            self.subscriptions[stream_type.value].add(symbol)
            self.symbol_mapping[symbol] = stream_id
        
        logger.info(f"Subscribed to {len(symbols)} symbols for {stream_type.value}")
    
    async def _subscribe_batch(self, stream_type: StreamType, symbols: List[str]):
        """Subscribe a batch of symbols"""
        # Get available connection from pool
        pool = self.pools.get("main")
        if not pool or not pool.available:
            logger.error("No available WebSocket connections")
            return
        
        ws = pool.available[0]
        
        # Create subscription message
        message = {
            "action": "subscribe",
            "stream_type": stream_type.value,
            "symbols": symbols
        }
        
        try:
            await ws.send(json.dumps(message))
            self.stream_metrics[stream_type.value].messages_processed += 1
        except Exception as e:
            logger.error(f"Error subscribing to symbols: {e}")
            self.stream_metrics[stream_type.value].error_count += 1
    
    async def _receive_messages(self, ws):
        """Receive and process messages from WebSocket"""
        try:
            async for message in ws:
                await self._process_message(message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            await self._handle_disconnection(ws)
            
        except Exception as e:
            logger.error(f"Error receiving WebSocket messages: {e}")
            await self._handle_disconnection(ws)
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message with optimization"""
        try:
            # Track metrics
            receive_time = time.time()
            
            # Parse message
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            
            data = json.loads(message)
            
            # Get stream type
            stream_type = StreamType(data.get('type', 'tick'))
            
            # Update metrics
            metrics = self.stream_metrics[stream_type.value]
            metrics.messages_received += 1
            metrics.bytes_received += len(message)
            metrics.last_message_time = datetime.now()
            
            # Check for duplicate (deduplication)
            message_hash = hash(message)
            if message_hash in self.dedupe_cache:
                metrics.messages_dropped += 1
                return
            
            self.dedupe_cache[message_hash] = message
            
            # Clean dedupe cache periodically (keep last 1000)
            if len(self.dedupe_cache) > 1000:
                self.dedupe_cache = dict(list(self.dedupe_cache.items())[-500:])
            
            # Apply throttling
            stream_config = self._get_stream_config(stream_type)
            if stream_config and stream_config.throttle_ms > 0:
                last_time = self.throttle_timers.get(stream_type.value, 0)
                current_time = time.time() * 1000
                
                if current_time - last_time < stream_config.throttle_ms:
                    # Too soon, add to batch buffer instead
                    self.batch_buffers[stream_type].append(data)
                    
                    # Check if batch is ready
                    if len(self.batch_buffers[stream_type]) >= stream_config.batch_size:
                        await self._process_batch(stream_type)
                    return
                
                self.throttle_timers[stream_type.value] = current_time
            
            # Process immediately for high priority or add to queue
            if stream_config and stream_config.priority == 1:
                await self._dispatch_message(stream_type, data)
            else:
                self.message_queue[stream_type].append(data)
            
            # Update latency metrics
            process_time = (time.time() - receive_time) * 1000
            metrics.avg_latency_ms = (metrics.avg_latency_ms * 0.9) + (process_time * 0.1)
            metrics.peak_latency_ms = max(metrics.peak_latency_ms, process_time)
            
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
            self.stream_metrics["error"].error_count += 1
    
    async def _process_batch(self, stream_type: StreamType):
        """Process batched messages"""
        if not self.batch_buffers[stream_type]:
            return
        
        batch = self.batch_buffers[stream_type].copy()
        self.batch_buffers[stream_type].clear()
        
        # Dispatch batch
        await self._dispatch_message(stream_type, {"batch": batch})
    
    async def _dispatch_message(self, stream_type: StreamType, data: Dict):
        """Dispatch message to registered handlers"""
        handlers = self.stream_handlers.get(stream_type, [])
        
        for handler in handlers:
            try:
                # Run handler in executor to avoid blocking
                self.executor.submit(handler, data)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")
    
    def register_handler(self, stream_type: StreamType, handler: Callable):
        """Register a message handler for a stream type"""
        self.stream_handlers[stream_type].append(handler)
        logger.info(f"Registered handler for {stream_type.value}")
    
    async def _handle_disconnection(self, ws):
        """Handle WebSocket disconnection with reconnection logic"""
        # Find which pool this connection belongs to
        for pool_name, pool in self.pools.items():
            if ws in pool.connections:
                pool.connections.remove(ws)
                if ws in pool.available:
                    pool.available.remove(ws)
                
                # Update state
                self.connection_states[pool_name] = ConnectionState.RECONNECTING
                
                # Attempt reconnection with exponential backoff
                await self._reconnect_with_backoff(pool)
                break
    
    async def _reconnect_with_backoff(self, pool: WebSocketPool, attempt: int = 0):
        """Reconnect with exponential backoff"""
        max_attempts = 5
        base_delay = 1  # seconds
        
        if attempt >= max_attempts:
            logger.error(f"Max reconnection attempts reached for {pool.url}")
            return
        
        delay = base_delay * (2 ** attempt)
        logger.info(f"Reconnecting to {pool.url} in {delay} seconds (attempt {attempt + 1})")
        
        await asyncio.sleep(delay)
        
        ws = await self._create_connection(pool)
        if ws:
            # Resubscribe to all symbols
            await self._resubscribe_all()
        else:
            # Try again
            await self._reconnect_with_backoff(pool, attempt + 1)
    
    async def _resubscribe_all(self):
        """Resubscribe to all symbols after reconnection"""
        for stream_type_str, symbols in self.subscriptions.items():
            if symbols:
                stream_type = StreamType(stream_type_str)
                await self.subscribe(stream_type, list(symbols))
    
    def _get_stream_config(self, stream_type: StreamType) -> Optional[StreamConfig]:
        """Get stream configuration"""
        for config in self.stream_configs.values():
            if config.stream_type == stream_type:
                return config
        return None
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for all streams"""
        metrics = {}
        
        for stream_type, stream_metrics in self.stream_metrics.items():
            metrics[stream_type] = {
                "messages_received": stream_metrics.messages_received,
                "messages_processed": stream_metrics.messages_processed,
                "messages_dropped": stream_metrics.messages_dropped,
                "bytes_received": f"{stream_metrics.bytes_received / 1024:.2f} KB",
                "avg_latency_ms": f"{stream_metrics.avg_latency_ms:.2f}",
                "peak_latency_ms": f"{stream_metrics.peak_latency_ms:.2f}",
                "reconnect_count": stream_metrics.reconnect_count,
                "error_count": stream_metrics.error_count,
                "last_message": stream_metrics.last_message_time.isoformat() if stream_metrics.last_message_time else None
            }
        
        # Add connection pool metrics
        for pool_name, pool in self.pools.items():
            metrics[f"pool_{pool_name}"] = {
                "total_connections": len(pool.connections),
                "available_connections": len(pool.available),
                "in_use_connections": len(pool.in_use)
            }
        
        # Add queue metrics
        for stream_type, queue in self.message_queue.items():
            metrics[f"queue_{stream_type.value}"] = {
                "size": len(queue),
                "batch_buffer": len(self.batch_buffers[stream_type])
            }
        
        return metrics
    
    def optimize_performance(self):
        """Run performance optimization analysis"""
        optimizations = []
        
        # Check for slow streams
        for stream_type, metrics in self.stream_metrics.items():
            if metrics.avg_latency_ms > 100:
                optimizations.append({
                    "stream": stream_type,
                    "issue": "High latency",
                    "recommendation": "Increase throttle_ms or reduce symbol count"
                })
            
            if metrics.messages_dropped > metrics.messages_processed * 0.1:
                optimizations.append({
                    "stream": stream_type,
                    "issue": "High message drop rate",
                    "recommendation": "Increase batch_size or add more handlers"
                })
        
        # Check connection pools
        for pool_name, pool in self.pools.items():
            utilization = len(pool.in_use) / max(len(pool.connections), 1)
            if utilization > 0.8:
                optimizations.append({
                    "pool": pool_name,
                    "issue": "High connection utilization",
                    "recommendation": f"Increase max_connections from {pool.max_connections}"
                })
        
        # Check message queues
        for stream_type, queue in self.message_queue.items():
            if len(queue) > 5000:
                optimizations.append({
                    "queue": stream_type.value,
                    "issue": "Large message queue",
                    "recommendation": "Add more message processors or increase batch processing"
                })
        
        return optimizations
    
    def _start_background_tasks(self):
        """Start background processing tasks"""
        # Start message queue processor
        asyncio.create_task(self._process_message_queues())
        
        # Start metrics reporter
        asyncio.create_task(self._report_metrics())
        
        # Start optimization checker
        asyncio.create_task(self._check_optimizations())
    
    async def _process_message_queues(self):
        """Process message queues in background"""
        while True:
            try:
                for stream_type, queue in self.message_queue.items():
                    if queue:
                        # Process up to 100 messages at a time
                        batch = []
                        for _ in range(min(100, len(queue))):
                            if queue:
                                batch.append(queue.popleft())
                        
                        if batch:
                            await self._dispatch_message(stream_type, {"batch": batch})
                
                await asyncio.sleep(0.1)  # Process every 100ms
                
            except Exception as e:
                logger.error(f"Error processing message queues: {e}")
    
    async def _report_metrics(self):
        """Report metrics periodically"""
        while True:
            await asyncio.sleep(60)  # Report every minute
            
            metrics = self.get_metrics()
            logger.info(f"WebSocket metrics: {json.dumps(metrics, indent=2)}")
    
    async def _check_optimizations(self):
        """Check for optimization opportunities"""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            
            optimizations = self.optimize_performance()
            if optimizations:
                logger.warning(f"Performance optimizations suggested: {json.dumps(optimizations, indent=2)}")

# Singleton instance
_instance = None

def get_websocket_optimizer() -> WebSocketOptimizer:
    """Get singleton instance"""
    global _instance
    if _instance is None:
        _instance = WebSocketOptimizer()
    return _instance