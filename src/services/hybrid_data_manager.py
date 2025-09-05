"""
Hybrid Data Manager for TradingView Pro Trading
Combines in-memory cache with database persistence for optimal performance
"""

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Deque
from collections import deque
from dataclasses import dataclass, asdict
import json
import pyodbc
from contextlib import contextmanager
import threading
import time as time_module

logger = logging.getLogger(__name__)

@dataclass
class HourlyCandle:
    """Represents an hourly OHLC candle"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    tick_count: int
    is_complete: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'tick_count': self.tick_count,
            'is_complete': self.is_complete
        }

@dataclass
class LivePosition:
    """Represents a live trading position"""
    id: int
    signal_type: str
    main_strike: int
    main_price: float
    main_quantity: int
    hedge_strike: Optional[int]
    hedge_price: Optional[float]
    hedge_quantity: Optional[int]
    entry_time: datetime
    current_main_price: float
    current_hedge_price: Optional[float]
    status: str  # 'open', 'closed', 'stopped'
    option_type: str = 'PE'  # CE or PE
    quantity: int = 10  # Number of lots
    lot_size: int = 75  # Size per lot
    
    @property
    def breakeven(self) -> float:
        """Calculate breakeven including hedge"""
        if self.hedge_strike and self.hedge_price:
            net_premium = self.main_price - self.hedge_price
            # Determine option type from signal
            is_put = self.signal_type in ['S1', 'S2', 'S4', 'S7']
            return self.main_strike - net_premium if is_put else self.main_strike + net_premium
        return self.main_strike
    
    @property
    def pnl(self) -> float:
        """Calculate current P&L"""
        main_pnl = (self.main_price - self.current_main_price) * self.main_quantity * 75
        hedge_pnl = 0
        if self.hedge_strike and self.hedge_price and self.current_hedge_price:
            hedge_pnl = (self.current_hedge_price - self.hedge_price) * self.hedge_quantity * 75
        return main_pnl + hedge_pnl

@dataclass 
class TradingSignal:
    """Represents a trading signal from TradingView"""
    signal_type: str  # S1-S8
    action: str  # 'ENTRY' or 'EXIT'
    strike: int
    option_type: str  # 'CE' or 'PE'
    timestamp: datetime
    price: Optional[float] = None
    processed: bool = False
    execution_id: Optional[int] = None

class HybridDataManager:
    """
    Manages trading data with hybrid memory-database architecture
    Memory for speed, database for persistence
    """
    
    def __init__(self):
        # Memory cache
        self.memory_cache = {
            'hourly_candles': deque(maxlen=24),  # Last 24 hours
            'current_hour_ticks': [],  # Current hour's tick data
            'active_positions': {},  # position_id -> LivePosition
            'pending_signals': deque(maxlen=100),  # Recent signals
            'spot_price': None,
            'last_update': None
        }
        
        # Current candle being formed
        self.current_candle: Optional[HourlyCandle] = None
        self.candle_start_time: Optional[datetime] = None
        
        # Database connection
        self.conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=(localdb)\\mssqllocaldb;"
            "DATABASE=KiteConnectApi;"
            "Trusted_Connection=yes;"
        )
        
        # Sync settings
        self.db_sync_interval = 60  # Sync every minute
        self.last_db_sync = datetime.now()
        self.is_running = False
        self._lock = threading.Lock()
        
        # Initialize database tables
        self._init_database()
        
        # Load recent data from database
        self._load_from_database()
    
    @contextmanager
    def get_db(self):
        """Database connection context manager"""
        conn = pyodbc.connect(self.conn_str)
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database tables if not exists"""
        with self.get_db() as conn:
            cursor = conn.cursor()
            
            # TradingView signals table
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'TradingViewSignals')
                CREATE TABLE TradingViewSignals (
                    id INT PRIMARY KEY IDENTITY,
                    signal_type VARCHAR(10),
                    action VARCHAR(10),
                    strike INT,
                    option_type VARCHAR(2),
                    timestamp DATETIME,
                    price DECIMAL(10,2),
                    processed BIT DEFAULT 0,
                    execution_id INT,
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            
            # Live hourly candles table
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'LiveHourlyCandles')
                CREATE TABLE LiveHourlyCandles (
                    timestamp DATETIME PRIMARY KEY,
                    [open] DECIMAL(10,2),
                    high DECIMAL(10,2),
                    low DECIMAL(10,2),
                    [close] DECIMAL(10,2),
                    volume DECIMAL(15,2),
                    tick_count INT,
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            
            # Live positions table
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'LivePositions')
                CREATE TABLE LivePositions (
                    id INT PRIMARY KEY IDENTITY,
                    signal_type VARCHAR(10),
                    main_strike INT,
                    main_price DECIMAL(10,2),
                    main_quantity INT,
                    hedge_strike INT,
                    hedge_price DECIMAL(10,2),
                    hedge_quantity INT,
                    breakeven DECIMAL(10,2),
                    entry_time DATETIME,
                    exit_time DATETIME,
                    pnl DECIMAL(10,2),
                    status VARCHAR(20),
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            
            conn.commit()
            logger.info("Database tables initialized")
    
    def _load_from_database(self):
        """Load recent data from database into memory cache"""
        try:
            with self.get_db() as conn:
                cursor = conn.cursor()
                
                # Load last 24 hourly candles
                twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
                cursor.execute("""
                    SELECT TOP 24 timestamp, [open], high, low, [close], volume, tick_count
                    FROM LiveHourlyCandles
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (twenty_four_hours_ago,))
                
                for row in cursor.fetchall():
                    candle = HourlyCandle(
                        timestamp=row[0],
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                        tick_count=row[6],
                        is_complete=True
                    )
                    self.memory_cache['hourly_candles'].appendleft(candle)
                
                # Load active positions
                cursor.execute("""
                    SELECT id, signal_type, main_strike, main_price, main_quantity,
                           hedge_strike, hedge_price, hedge_quantity, entry_time
                    FROM LivePositions
                    WHERE status = 'open'
                """)
                
                for row in cursor.fetchall():
                    position = LivePosition(
                        id=row[0],
                        signal_type=row[1],
                        main_strike=row[2],
                        main_price=float(row[3]),
                        main_quantity=row[4],
                        hedge_strike=row[5],
                        hedge_price=float(row[6]) if row[6] else None,
                        hedge_quantity=row[7],
                        entry_time=row[8],
                        current_main_price=float(row[3]),
                        current_hedge_price=float(row[6]) if row[6] else None,
                        status='open'
                    )
                    self.memory_cache['active_positions'][position.id] = position
                
                logger.info(f"Loaded {len(self.memory_cache['hourly_candles'])} candles and "
                          f"{len(self.memory_cache['active_positions'])} positions from database")
                
        except Exception as e:
            logger.error(f"Error loading from database: {e}")
    
    def update_tick(self, price: float, timestamp: Optional[datetime] = None):
        """Update with new tick data"""
        with self._lock:
            timestamp = timestamp or datetime.now()
            self.memory_cache['spot_price'] = price
            self.memory_cache['last_update'] = timestamp
            
            # Add to current hour ticks
            self.memory_cache['current_hour_ticks'].append({
                'price': price,
                'timestamp': timestamp
            })
            
            # Update current candle
            if self.current_candle is None or self._is_new_hour(timestamp):
                self._start_new_candle(timestamp)
            
            self._update_current_candle(price)
    
    def _is_new_hour(self, timestamp: datetime) -> bool:
        """Check if we need to start a new hourly candle"""
        if self.candle_start_time is None:
            return True
        
        # Indian market hours: candles at 9:15, 10:15, 11:15, etc.
        current_hour_start = timestamp.replace(minute=15 if timestamp.minute >= 15 else 0, second=0, microsecond=0)
        if timestamp.minute < 15:
            current_hour_start = current_hour_start - timedelta(hours=1)
        
        return current_hour_start > self.candle_start_time
    
    def _start_new_candle(self, timestamp: datetime):
        """Start forming a new hourly candle"""
        # Complete previous candle
        if self.current_candle:
            self._complete_candle()
        
        # Start new candle
        hour_start = timestamp.replace(minute=15 if timestamp.minute >= 15 else 0, second=0, microsecond=0)
        if timestamp.minute < 15:
            hour_start = hour_start - timedelta(hours=1)
        
        self.current_candle = HourlyCandle(
            timestamp=hour_start,
            open=self.memory_cache['spot_price'],
            high=self.memory_cache['spot_price'],
            low=self.memory_cache['spot_price'],
            close=self.memory_cache['spot_price'],
            volume=0,
            tick_count=0,
            is_complete=False
        )
        self.candle_start_time = hour_start
        self.memory_cache['current_hour_ticks'] = []
        
        logger.info(f"Started new candle at {hour_start}")
    
    def _update_current_candle(self, price: float):
        """Update current candle with new price"""
        if self.current_candle:
            if self.current_candle.high is None or price > self.current_candle.high:
                self.current_candle.high = price
            if self.current_candle.low is None or price < self.current_candle.low:
                self.current_candle.low = price
            self.current_candle.close = price
            self.current_candle.tick_count += 1
    
    def _complete_candle(self):
        """Complete current candle and store it"""
        if self.current_candle:
            self.current_candle.is_complete = True
            self.memory_cache['hourly_candles'].append(self.current_candle)
            
            # Store in database
            self._store_candle_to_db(self.current_candle)
            
            logger.info(f"Completed candle: {self.current_candle.timestamp} "
                       f"O:{self.current_candle.open} H:{self.current_candle.high} "
                       f"L:{self.current_candle.low} C:{self.current_candle.close}")
    
    def _store_candle_to_db(self, candle: HourlyCandle):
        """Store completed candle to database"""
        try:
            with self.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO LiveHourlyCandles 
                    (timestamp, [open], high, low, [close], volume, tick_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    candle.timestamp,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                    candle.tick_count
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error storing candle to database: {e}")
    
    def add_signal(self, signal: TradingSignal):
        """Add new trading signal"""
        with self._lock:
            self.memory_cache['pending_signals'].append(signal)
            self._store_signal_to_db(signal)
    
    def _store_signal_to_db(self, signal: TradingSignal):
        """Store signal to database"""
        try:
            with self.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO TradingViewSignals 
                    (signal_type, action, strike, option_type, timestamp, price, processed, execution_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal.signal_type,
                    signal.action,
                    signal.strike,
                    signal.option_type,
                    signal.timestamp,
                    signal.price,
                    signal.processed,
                    signal.execution_id
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error storing signal to database: {e}")
    
    def add_position(self, position: LivePosition):
        """Add new position"""
        with self._lock:
            self.memory_cache['active_positions'][position.id] = position
            self._store_position_to_db(position)
    
    def update_position(self, position_id: int, main_price: float, hedge_price: Optional[float] = None):
        """Update position prices"""
        with self._lock:
            if position_id in self.memory_cache['active_positions']:
                position = self.memory_cache['active_positions'][position_id]
                position.current_main_price = main_price
                if hedge_price:
                    position.current_hedge_price = hedge_price
    
    def close_position(self, position_id: int, pnl: float):
        """Close a position"""
        with self._lock:
            if position_id in self.memory_cache['active_positions']:
                position = self.memory_cache['active_positions'][position_id]
                position.status = 'closed'
                self._update_position_in_db(position_id, 'closed', pnl)
                del self.memory_cache['active_positions'][position_id]
    
    def _store_position_to_db(self, position: LivePosition):
        """Store position to database"""
        try:
            with self.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO LivePositions 
                    (signal_type, main_strike, main_price, main_quantity,
                     hedge_strike, hedge_price, hedge_quantity, breakeven,
                     entry_time, status, option_type, quantity, lot_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    position.signal_type,
                    position.main_strike,
                    position.main_price,
                    position.main_quantity,
                    position.hedge_strike,
                    position.hedge_price,
                    position.hedge_quantity,
                    position.breakeven,
                    position.entry_time,
                    position.status,
                    position.option_type if hasattr(position, 'option_type') else 'PE',
                    position.quantity if hasattr(position, 'quantity') else 10,
                    position.lot_size if hasattr(position, 'lot_size') else 75
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error storing position to database: {e}")
    
    def _update_position_in_db(self, position_id: int, status: str, pnl: float):
        """Update position in database"""
        try:
            with self.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE LivePositions 
                    SET status = ?, pnl = ?, exit_time = GETDATE()
                    WHERE id = ?
                """, (status, pnl, position_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating position in database: {e}")
    
    def get_latest_candles(self, count: int = 24) -> List[Dict]:
        """Get latest hourly candles from memory"""
        with self._lock:
            candles = list(self.memory_cache['hourly_candles'])
            if self.current_candle and not self.current_candle.is_complete:
                candles.append(self.current_candle)
            return [c.to_dict() for c in candles[-count:]]
    
    def get_active_positions(self) -> List[Dict]:
        """Get all active positions"""
        with self._lock:
            return [asdict(p) for p in self.memory_cache['active_positions'].values()]
    
    def get_pending_signals(self) -> List[Dict]:
        """Get pending signals"""
        with self._lock:
            return [asdict(s) for s in self.memory_cache['pending_signals'] if not s.processed]
    
    async def sync_to_database(self):
        """Periodic sync to database"""
        while self.is_running:
            try:
                await asyncio.sleep(self.db_sync_interval)
                
                # Sync positions
                with self._lock:
                    for position in self.memory_cache['active_positions'].values():
                        self._update_position_in_db(
                            position.id, 
                            position.status,
                            position.pnl
                        )
                
                self.last_db_sync = datetime.now()
                logger.debug(f"Database sync completed at {self.last_db_sync}")
                
            except Exception as e:
                logger.error(f"Error during database sync: {e}")
    
    def start(self):
        """Start the hybrid data manager"""
        self.is_running = True
        logger.info("Hybrid Data Manager started")
    
    def stop(self):
        """Stop the hybrid data manager"""
        self.is_running = False
        
        # Final sync
        with self._lock:
            if self.current_candle:
                self._complete_candle()
        
        logger.info("Hybrid Data Manager stopped")

# Singleton instance
_instance = None

def get_hybrid_data_manager() -> HybridDataManager:
    """Get singleton instance of hybrid data manager"""
    global _instance
    if _instance is None:
        _instance = HybridDataManager()
    return _instance