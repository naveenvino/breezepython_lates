"""
Strategy Scheduler Service - Handles scheduling logic for strategies
"""

import schedule
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import logging
import json
import sqlite3

logger = logging.getLogger(__name__)

class StrategySchedulerService:
    def __init__(self, strategy_manager=None):
        self.strategy_manager = strategy_manager
        self.scheduler_thread = None
        self.running = False
        self.scheduled_jobs = {}
        
    def start(self):
        """Start the scheduler service"""
        if self.running:
            logger.info("Scheduler already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        # Load existing schedules
        self._load_schedules()
        
        logger.info("Strategy Scheduler Service started")
    
    def stop(self):
        """Stop the scheduler service"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        # Clear all scheduled jobs
        schedule.clear()
        self.scheduled_jobs.clear()
        
        logger.info("Strategy Scheduler Service stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(5)
    
    def _load_schedules(self):
        """Load schedules from database"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT schedule_id, strategy_id, schedule_type, schedule_config, is_active
                FROM StrategySchedules
                WHERE is_active = 1
            """)
            
            schedules = cursor.fetchall()
            conn.close()
            
            for sched in schedules:
                schedule_id = sched[0]
                strategy_id = sched[1]
                schedule_type = sched[2]
                config = json.loads(sched[3])
                
                self._create_schedule(schedule_id, strategy_id, schedule_type, config)
                
        except Exception as e:
            logger.error(f"Error loading schedules: {e}")
    
    def _create_schedule(self, schedule_id: int, strategy_id: str, schedule_type: str, config: Dict):
        """Create a schedule based on configuration"""
        try:
            if schedule_type == "TIME_BASED":
                self._create_time_based_schedule(schedule_id, strategy_id, config)
            elif schedule_type == "DAY_BASED":
                self._create_day_based_schedule(schedule_id, strategy_id, config)
            elif schedule_type == "CONDITION_BASED":
                self._create_condition_based_schedule(schedule_id, strategy_id, config)
                
        except Exception as e:
            logger.error(f"Error creating schedule {schedule_id}: {e}")
    
    def _create_time_based_schedule(self, schedule_id: int, strategy_id: str, config: Dict):
        """Create time-based schedule (daily at specific times)"""
        start_time = config.get('start_time', '09:30')
        end_time = config.get('end_time', '15:15')
        days = config.get('days', ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])
        
        # Schedule start
        for day in days:
            job = getattr(schedule.every(), day.lower()).at(start_time).do(
                self._start_strategy, strategy_id
            )
            self._track_job(schedule_id, job, 'start')
        
        # Schedule stop if auto_stop enabled
        if config.get('auto_stop', True):
            for day in days:
                job = getattr(schedule.every(), day.lower()).at(end_time).do(
                    self._stop_strategy, strategy_id
                )
                self._track_job(schedule_id, job, 'stop')
    
    def _create_day_based_schedule(self, schedule_id: int, strategy_id: str, config: Dict):
        """Create day-based schedule (specific days of month)"""
        days_of_month = config.get('days_of_month', [])
        start_time = config.get('start_time', '09:30')
        
        # Schedule daily check
        schedule.every().day.at("00:01").do(
            self._check_day_based_schedule, strategy_id, days_of_month, start_time
        )
    
    def _create_condition_based_schedule(self, schedule_id: int, strategy_id: str, config: Dict):
        """Create condition-based schedule"""
        check_interval = config.get('check_interval', 60)  # seconds
        conditions = config.get('conditions', {})
        
        # Schedule periodic condition check
        schedule.every(check_interval).seconds.do(
            self._check_conditions, strategy_id, conditions
        )
    
    def _start_strategy(self, strategy_id: str):
        """Start a strategy"""
        try:
            if self.strategy_manager:
                success = self.strategy_manager.start_strategy(strategy_id)
                if success:
                    logger.info(f"Scheduled start of strategy {strategy_id}")
                    self._update_next_run(strategy_id, 'start')
        except Exception as e:
            logger.error(f"Error starting strategy {strategy_id}: {e}")
    
    def _stop_strategy(self, strategy_id: str):
        """Stop a strategy"""
        try:
            if self.strategy_manager:
                success = self.strategy_manager.stop_strategy(strategy_id)
                if success:
                    logger.info(f"Scheduled stop of strategy {strategy_id}")
                    self._update_next_run(strategy_id, 'stop')
        except Exception as e:
            logger.error(f"Error stopping strategy {strategy_id}: {e}")
    
    def _check_day_based_schedule(self, strategy_id: str, days_of_month: List[int], start_time: str):
        """Check if today matches day-based schedule"""
        today = datetime.now().day
        if today in days_of_month:
            # Schedule for today at start_time
            schedule.every().day.at(start_time).do(
                self._start_strategy, strategy_id
            ).tag(f"day_based_{strategy_id}")
    
    def _check_conditions(self, strategy_id: str, conditions: Dict):
        """Check conditions for strategy activation"""
        try:
            # Example conditions: market volatility, specific price levels, etc.
            should_start = self._evaluate_conditions(conditions)
            
            if should_start:
                self._start_strategy(strategy_id)
                
        except Exception as e:
            logger.error(f"Error checking conditions for {strategy_id}: {e}")
    
    def _evaluate_conditions(self, conditions: Dict) -> bool:
        """Evaluate custom conditions"""
        # Implement condition evaluation logic
        # For now, return False
        return False
    
    def _track_job(self, schedule_id: int, job, job_type: str):
        """Track scheduled jobs"""
        if schedule_id not in self.scheduled_jobs:
            self.scheduled_jobs[schedule_id] = []
        self.scheduled_jobs[schedule_id].append({
            'job': job,
            'type': job_type
        })
    
    def _update_next_run(self, strategy_id: str, action: str):
        """Update next run time in database"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            # Calculate next run based on schedule
            next_run = self._calculate_next_run(strategy_id)
            
            cursor.execute("""
                UPDATE StrategySchedules 
                SET last_run = ?, next_run = ?
                WHERE strategy_id = ? AND is_active = 1
            """, (datetime.now(), next_run, strategy_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating next run: {e}")
    
    def _calculate_next_run(self, strategy_id: str) -> datetime:
        """Calculate next scheduled run time"""
        # Get next scheduled job for this strategy
        for job in schedule.jobs:
            if hasattr(job, 'job_func') and job.job_func.args and strategy_id in job.job_func.args:
                return job.next_run
        
        return datetime.now() + timedelta(days=1)
    
    def add_schedule(self, strategy_id: str, schedule_type: str, config: Dict) -> int:
        """Add a new schedule for a strategy"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO StrategySchedules (
                    strategy_id, schedule_type, schedule_config, next_run, is_active
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                strategy_id, schedule_type, json.dumps(config),
                datetime.now() + timedelta(minutes=1), 1
            ))
            
            schedule_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Create the schedule
            self._create_schedule(schedule_id, strategy_id, schedule_type, config)
            
            logger.info(f"Added schedule {schedule_id} for strategy {strategy_id}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"Error adding schedule: {e}")
            return -1
    
    def remove_schedule(self, schedule_id: int):
        """Remove a schedule"""
        try:
            # Remove from database
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE StrategySchedules 
                SET is_active = 0
                WHERE schedule_id = ?
            """, (schedule_id,))
            
            conn.commit()
            conn.close()
            
            # Remove scheduled jobs
            if schedule_id in self.scheduled_jobs:
                for job_info in self.scheduled_jobs[schedule_id]:
                    schedule.cancel_job(job_info['job'])
                del self.scheduled_jobs[schedule_id]
            
            logger.info(f"Removed schedule {schedule_id}")
            
        except Exception as e:
            logger.error(f"Error removing schedule: {e}")
    
    def get_schedules(self, strategy_id: Optional[str] = None) -> List[Dict]:
        """Get schedules for a strategy or all schedules"""
        try:
            conn = sqlite3.connect('data/trading_settings.db')
            cursor = conn.cursor()
            
            if strategy_id:
                cursor.execute("""
                    SELECT schedule_id, strategy_id, schedule_type, 
                           schedule_config, next_run, last_run, is_active
                    FROM StrategySchedules
                    WHERE strategy_id = ?
                """, (strategy_id,))
            else:
                cursor.execute("""
                    SELECT schedule_id, strategy_id, schedule_type, 
                           schedule_config, next_run, last_run, is_active
                    FROM StrategySchedules
                """)
            
            schedules = []
            for row in cursor.fetchall():
                schedules.append({
                    'schedule_id': row[0],
                    'strategy_id': row[1],
                    'schedule_type': row[2],
                    'config': json.loads(row[3]),
                    'next_run': row[4],
                    'last_run': row[5],
                    'is_active': row[6]
                })
            
            conn.close()
            return schedules
            
        except Exception as e:
            logger.error(f"Error getting schedules: {e}")
            return []

# Singleton instance
_scheduler_instance = None

def get_strategy_scheduler(strategy_manager=None) -> StrategySchedulerService:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = StrategySchedulerService(strategy_manager)
    return _scheduler_instance