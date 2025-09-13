"""
Multi-Strategy Manager Service with Threading Support
"""

import threading
import sqlite3
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, time, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class StrategyStatus(Enum):
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"

@dataclass
class StrategyConfig:
    strategy_id: str
    strategy_name: str
    signals: List[str]
    lots: int = 10
    hedge_enabled: bool = True
    hedge_percentage: float = 30
    hedge_offset: int = 200
    stop_loss_enabled: bool = True
    profit_lock_enabled: bool = True
    profit_target: float = 10
    profit_lock: float = 5
    exit_day: int = 2
    exit_time: str = "15:15"
    max_positions: int = 3
    auto_square_off: bool = True

@dataclass
class StrategySchedule:
    type: str  # TIME_BASED, DAY_BASED, CONDITION_BASED
    start_time: str = "09:30"
    end_time: str = "15:15"
    days: List[str] = None
    conditions: Dict = None
    auto_stop: bool = True

class StrategyThread(threading.Thread):
    def __init__(self, strategy_id: str, config: StrategyConfig, schedule: StrategySchedule):
        super().__init__(name=f"Strategy_{strategy_id}")
        self.strategy_id = strategy_id
        self.config = config
        self.schedule = schedule
        self.status = StrategyStatus.INACTIVE
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self.active_positions = {}
        self.execution_count = 0
        self.total_pnl = 0.0
        
    def run(self):
        """Main execution loop for the strategy"""
        logger.info(f"Starting strategy thread: {self.strategy_id}")
        self.status = StrategyStatus.ACTIVE
        self._update_database_status(StrategyStatus.ACTIVE)
        
        try:
            while not self._stop_event.is_set():
                # Check if paused
                self._pause_event.wait()
                
                # Check if within scheduled time
                if not self._is_scheduled_time():
                    threading.Event().wait(60)  # Wait 1 minute
                    continue
                
                # Monitor signals and execute trades
                self._execute_strategy_logic()
                
                # Small delay to prevent CPU hogging
                threading.Event().wait(5)  # 5 second interval
                
        except Exception as e:
            logger.error(f"Strategy {self.strategy_id} failed: {e}")
            self.status = StrategyStatus.FAILED
            self._update_database_status(StrategyStatus.FAILED)
        finally:
            logger.info(f"Strategy thread stopped: {self.strategy_id}")
    
    def pause(self):
        """Pause strategy execution"""
        self._pause_event.clear()
        self.status = StrategyStatus.PAUSED
        self._update_database_status(StrategyStatus.PAUSED)
        logger.info(f"Strategy paused: {self.strategy_id}")
    
    def resume(self):
        """Resume strategy execution"""
        self._pause_event.set()
        self.status = StrategyStatus.ACTIVE
        self._update_database_status(StrategyStatus.ACTIVE)
        logger.info(f"Strategy resumed: {self.strategy_id}")
    
    def stop(self):
        """Stop strategy execution"""
        self._stop_event.set()
        self.status = StrategyStatus.STOPPED
        self._update_database_status(StrategyStatus.STOPPED)
        
        # Square off all positions if configured
        if self.config.auto_square_off:
            self._square_off_positions()
    
    def _is_scheduled_time(self) -> bool:
        """Check if current time is within schedule"""
        now = datetime.now()
        current_time = now.time()
        current_day = now.strftime("%A").lower()
        
        # Check day
        if self.schedule.days and current_day not in self.schedule.days:
            return False
        
        # Check time
        start_time = datetime.strptime(self.schedule.start_time, "%H:%M").time()
        end_time = datetime.strptime(self.schedule.end_time, "%H:%M").time()
        
        return start_time <= current_time <= end_time
    
    def _execute_strategy_logic(self):
        """Execute the actual strategy logic"""
        try:
            # Check for signals
            for signal in self.config.signals:
                if self._check_signal_triggered(signal):
                    # Check position limits
                    if len(self.active_positions) >= self.config.max_positions:
                        logger.info(f"Strategy {self.strategy_id}: Max positions reached")
                        continue
                    
                    # Place trade
                    self._place_trade(signal)
            
            # Monitor existing positions
            self._monitor_positions()
            
        except Exception as e:
            logger.error(f"Error in strategy logic for {self.strategy_id}: {e}")
    
    def _check_signal_triggered(self, signal: str) -> bool:
        """Check if a signal is triggered"""
        # This would integrate with the signal detection service
        # For now, return False
        return False
    
    def _place_trade(self, signal: str):
        """Place a trade based on signal"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            # Generate unique execution ID
            execution_id = f"EXEC_{self.strategy_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Record execution
            cursor.execute("""
                INSERT INTO StrategyExecutions (
                    strategy_id, webhook_id, signal, entry_time, 
                    exit_config_day, exit_config_time, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.strategy_id, execution_id, signal, datetime.now(),
                self.config.exit_day, self.config.exit_time, 'OPEN'
            ))
            
            conn.commit()
            conn.close()
            
            # Track position
            self.active_positions[execution_id] = {
                'signal': signal,
                'entry_time': datetime.now(),
                'status': 'OPEN'
            }
            
            self.execution_count += 1
            logger.info(f"Strategy {self.strategy_id}: Placed trade for signal {signal}")
            
        except Exception as e:
            logger.error(f"Error placing trade for {self.strategy_id}: {e}")
    
    def _monitor_positions(self):
        """Monitor and manage existing positions"""
        for exec_id, position in list(self.active_positions.items()):
            if position['status'] == 'OPEN':
                # Check exit conditions
                if self._should_exit_position(position):
                    self._exit_position(exec_id)
    
    def _should_exit_position(self, position: Dict) -> bool:
        """Check if position should be exited"""
        # Check time-based exit
        now = datetime.now()
        entry_time = position['entry_time']
        
        # Calculate exit time based on T+N configuration
        exit_date = entry_time.date() + timedelta(days=self.config.exit_day)
        exit_datetime = datetime.combine(
            exit_date, 
            datetime.strptime(self.config.exit_time, "%H:%M").time()
        )
        
        return now >= exit_datetime
    
    def _exit_position(self, execution_id: str):
        """Exit a position"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            # Update execution status
            cursor.execute("""
                UPDATE StrategyExecutions 
                SET status = 'CLOSED', exit_time = ?
                WHERE webhook_id = ?
            """, (datetime.now(), execution_id))
            
            conn.commit()
            conn.close()
            
            # Update tracking
            if execution_id in self.active_positions:
                self.active_positions[execution_id]['status'] = 'CLOSED'
                del self.active_positions[execution_id]
            
            logger.info(f"Strategy {self.strategy_id}: Exited position {execution_id}")
            
        except Exception as e:
            logger.error(f"Error exiting position for {self.strategy_id}: {e}")
    
    def _square_off_positions(self):
        """Square off all open positions"""
        for exec_id in list(self.active_positions.keys()):
            if self.active_positions[exec_id]['status'] == 'OPEN':
                self._exit_position(exec_id)
    
    def _update_database_status(self, status: StrategyStatus):
        """Update strategy status in database"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE StrategyInstances 
                SET status = ?, updated_at = ?
                WHERE strategy_id = ?
            """, (status.value, datetime.now(), self.strategy_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating database status: {e}")
    
    def get_status(self) -> Dict:
        """Get current strategy status"""
        return {
            'strategy_id': self.strategy_id,
            'status': self.status.value,
            'active_positions': len(self.active_positions),
            'execution_count': self.execution_count,
            'total_pnl': self.total_pnl
        }

class StrategyManagerService:
    def __init__(self):
        self.strategies: Dict[str, StrategyThread] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self._lock = threading.Lock()
        self._load_existing_strategies()
    
    def _load_existing_strategies(self):
        """Load strategies from database on startup"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT strategy_id, strategy_name, signals, configuration, schedule, status
                FROM StrategyInstances
                WHERE status IN ('ACTIVE', 'PAUSED')
            """)
            
            strategies = cursor.fetchall()
            conn.close()
            
            for strategy in strategies:
                strategy_id = strategy[0]
                config_data = json.loads(strategy[3])
                schedule_data = json.loads(strategy[4])
                
                config = StrategyConfig(
                    strategy_id=strategy_id,
                    strategy_name=strategy[1],
                    signals=json.loads(strategy[2]),
                    **config_data
                )
                
                schedule = StrategySchedule(**schedule_data)
                
                # Auto-start previously active strategies
                if strategy[5] == 'ACTIVE':
                    self.start_strategy(strategy_id, config, schedule)
                    
        except Exception as e:
            logger.error(f"Error loading existing strategies: {e}")
    
    def create_strategy(self, name: str, signals: List[str], config: Dict, schedule: Dict) -> str:
        """Create a new strategy"""
        strategy_id = f"STR_{uuid.uuid4().hex[:8].upper()}"
        
        try:
            # Create config and schedule objects
            strategy_config = StrategyConfig(
                strategy_id=strategy_id,
                strategy_name=name,
                signals=signals,
                **config
            )
            
            strategy_schedule = StrategySchedule(**schedule)
            
            # Save to database
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO StrategyInstances (
                    strategy_id, strategy_name, signals, configuration, schedule, status
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                strategy_id, name, json.dumps(signals),
                json.dumps(config), json.dumps(schedule), 'INACTIVE'
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Created strategy: {strategy_id}")
            return strategy_id
            
        except Exception as e:
            logger.error(f"Error creating strategy: {e}")
            raise
    
    def start_strategy(self, strategy_id: str, config: StrategyConfig = None, schedule: StrategySchedule = None) -> bool:
        """Start a strategy"""
        with self._lock:
            if strategy_id in self.strategies and self.strategies[strategy_id].is_alive():
                logger.warning(f"Strategy {strategy_id} is already running")
                return False
            
            try:
                # Load config from DB if not provided
                if not config or not schedule:
                    config, schedule = self._load_strategy_config(strategy_id)
                
                # Create and start thread
                strategy_thread = StrategyThread(strategy_id, config, schedule)
                strategy_thread.start()
                
                self.strategies[strategy_id] = strategy_thread
                logger.info(f"Started strategy: {strategy_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error starting strategy {strategy_id}: {e}")
                return False
    
    def pause_strategy(self, strategy_id: str) -> bool:
        """Pause a running strategy"""
        with self._lock:
            if strategy_id in self.strategies:
                self.strategies[strategy_id].pause()
                return True
            return False
    
    def resume_strategy(self, strategy_id: str) -> bool:
        """Resume a paused strategy"""
        with self._lock:
            if strategy_id in self.strategies:
                self.strategies[strategy_id].resume()
                return True
            return False
    
    def stop_strategy(self, strategy_id: str) -> bool:
        """Stop a strategy"""
        with self._lock:
            if strategy_id in self.strategies:
                self.strategies[strategy_id].stop()
                self.strategies[strategy_id].join(timeout=10)
                del self.strategies[strategy_id]
                return True
            return False
    
    def get_all_strategies(self) -> List[Dict]:
        """Get status of all strategies"""
        strategies_info = []
        
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT strategy_id, strategy_name, signals, status, created_at
                FROM StrategyInstances
                ORDER BY created_at DESC
            """)
            
            db_strategies = cursor.fetchall()
            conn.close()
            
            for strategy in db_strategies:
                strategy_id = strategy[0]
                info = {
                    'strategy_id': strategy_id,
                    'strategy_name': strategy[1],
                    'signals': json.loads(strategy[2]),
                    'status': strategy[3],
                    'created_at': strategy[4]
                }
                
                # Add runtime info if running
                if strategy_id in self.strategies:
                    runtime_status = self.strategies[strategy_id].get_status()
                    info.update(runtime_status)
                
                strategies_info.append(info)
                
        except Exception as e:
            logger.error(f"Error getting strategies: {e}")
        
        return strategies_info
    
    def get_strategy_performance(self, strategy_id: str) -> Dict:
        """Get performance metrics for a strategy"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) as total_trades,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                       SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                       SUM(pnl) as total_pnl
                FROM StrategyExecutions
                WHERE strategy_id = ? AND status = 'CLOSED'
            """, (strategy_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                total_trades = result[0] or 0
                winning_trades = result[1] or 0
                losing_trades = result[2] or 0
                total_pnl = result[3] or 0
                
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                return {
                    'strategy_id': strategy_id,
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'win_rate': win_rate,
                    'total_pnl': total_pnl
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return {}
    
    def _load_strategy_config(self, strategy_id: str) -> tuple:
        """Load strategy configuration from database"""
        conn = sqlite3.connect('data/trading_settings.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT strategy_name, signals, configuration, schedule
            FROM StrategyInstances
            WHERE strategy_id = ?
        """, (strategy_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            config_data = json.loads(result[2])
            schedule_data = json.loads(result[3])
            
            config = StrategyConfig(
                strategy_id=strategy_id,
                strategy_name=result[0],
                signals=json.loads(result[1]),
                **config_data
            )
            
            schedule = StrategySchedule(**schedule_data)
            
            return config, schedule
        
        raise ValueError(f"Strategy {strategy_id} not found")
    
    def shutdown(self):
        """Shutdown all strategies"""
        logger.info("Shutting down Strategy Manager")
        
        # Stop all running strategies
        for strategy_id in list(self.strategies.keys()):
            self.stop_strategy(strategy_id)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)

# Singleton instance
_manager_instance = None

def get_strategy_manager() -> StrategyManagerService:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = StrategyManagerService()
    return _manager_instance