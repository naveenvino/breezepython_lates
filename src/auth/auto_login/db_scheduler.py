"""
Database-backed Scheduler using APScheduler
Stores jobs in SQL Server for persistence across restarts
"""
import logging
from datetime import datetime, time as dt_time
from typing import Dict, List, Optional, Any
import os
from pathlib import Path
import json

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from .breeze_login import BreezeAutoLogin
from .kite_login import KiteAutoLogin

logger = logging.getLogger(__name__)

# Standalone functions for APScheduler (to avoid serialization issues)
def run_breeze_login_job(config: Dict[str, Any]):
    """Standalone function to run Breeze login"""
    logger.info("Executing scheduled Breeze login...")
    
    try:
        breeze_login = BreezeAutoLogin(headless=config.get('headless', True))
        success, result = breeze_login.retry_login(
            max_attempts=config.get('max_retries', 3)
        )
        
        if success:
            logger.info(f"Breeze login successful: {result[:20]}...")
        else:
            logger.error(f"Breeze login failed: {result}")
            
        return {"success": success, "result": result}
        
    except Exception as e:
        logger.error(f"Error in Breeze login job: {e}")
        return {"success": False, "result": str(e)}

def run_kite_login_job(config: Dict[str, Any]):
    """Standalone function to run Kite login"""
    logger.info("Executing scheduled Kite login...")
    
    try:
        kite_login = KiteAutoLogin(headless=config.get('headless', True))
        success, result = kite_login.retry_login(
            max_attempts=config.get('max_retries', 3)
        )
        
        if success:
            logger.info(f"Kite login successful: {result[:20]}...")
        else:
            logger.error(f"Kite login failed: {result}")
            
        return {"success": success, "result": result}
        
    except Exception as e:
        logger.error(f"Error in Kite login job: {e}")
        return {"success": False, "result": str(e)}

class DatabaseScheduler:
    """
    Production-grade scheduler with database persistence
    Jobs are stored in SQL Server and survive API restarts
    """
    
    def __init__(self):
        # Database connection string for SQL Server
        db_server = os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')
        db_name = os.getenv('DB_NAME', 'KiteConnectApi')
        connection_string = f"mssql+pyodbc://@{db_server}/{db_name}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=true"
        
        # Configure job stores (database)
        jobstores = {
            'default': SQLAlchemyJobStore(url=connection_string)
        }
        
        # Configure executors (thread pool)
        executors = {
            'default': ThreadPoolExecutor(max_workers=20),
            'processpool': ThreadPoolExecutor(max_workers=5)
        }
        
        # Job defaults
        job_defaults = {
            'coalesce': True,  # Combine multiple pending executions of same job
            'max_instances': 1,  # Only one instance of each job at a time
            'misfire_grace_time': 300  # 5 minutes grace time for misfired jobs
        }
        
        # Create scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Kolkata'  # Indian timezone for trading
        )
        
        # Add event listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
        # Load configuration
        self.config_file = Path("config/scheduler_config.json")
        self.load_config()
        
        # Track execution history (in memory for current session)
        self.execution_history = []
        
    def load_config(self):
        """Load scheduler configuration from JSON file"""
        default_config = {
            "breeze": {
                "enabled": True,
                "times": ["05:30", "08:30"],
                "weekdays_only": True,
                "headless": True,
                "max_retries": 3
            },
            "kite": {
                "enabled": True,
                "times": ["05:45", "08:45"],
                "weekdays_only": True,
                "headless": True,
                "max_retries": 3
            },
            "notifications": {
                "enabled": True,
                "on_success": True,
                "on_failure": True
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                self.config = default_config
        else:
            self.config = default_config
            self.save_config()
    
    def save_config(self):
        """Save configuration to file"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Scheduler configuration saved")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def start(self):
        """Start the scheduler"""
        try:
            # Check if scheduler is already running
            if self.scheduler.running:
                logger.warning("Scheduler is already running")
                return {"status": "already_running", "message": "Scheduler is already running"}
            
            # Start scheduler
            self.scheduler.start()
            
            # Setup jobs based on configuration
            self.setup_jobs()
            
            logger.info("Database scheduler started successfully")
            return {"status": "started", "message": "Scheduler started successfully"}
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            return {"status": "error", "message": str(e)}
    
    def stop(self):
        """Stop the scheduler (jobs remain in database)"""
        try:
            if not self.scheduler.running:
                return {"status": "not_running", "message": "Scheduler is not running"}
            
            self.scheduler.shutdown(wait=True)
            logger.info("Database scheduler stopped")
            return {"status": "stopped", "message": "Scheduler stopped successfully"}
            
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            return {"status": "error", "message": str(e)}
    
    def setup_jobs(self):
        """Setup scheduled jobs based on configuration"""
        # Remove all existing jobs first
        self.scheduler.remove_all_jobs()
        
        # Setup Breeze jobs
        if self.config['breeze']['enabled']:
            for time_str in self.config['breeze']['times']:
                hour, minute = map(int, time_str.split(':'))
                
                # Create cron trigger
                if self.config['breeze']['weekdays_only']:
                    trigger = CronTrigger(
                        day_of_week='mon-fri',
                        hour=hour,
                        minute=minute,
                        timezone='Asia/Kolkata'
                    )
                else:
                    trigger = CronTrigger(
                        hour=hour,
                        minute=minute,
                        timezone='Asia/Kolkata'
                    )
                
                # Add job (use standalone function to avoid serialization issues)
                job_id = f"breeze_login_{time_str.replace(':', '')}"
                self.scheduler.add_job(
                    func=run_breeze_login_job,
                    trigger=trigger,
                    id=job_id,
                    name=f"Breeze Auto-Login at {time_str}",
                    replace_existing=True,
                    kwargs={'config': self.config['breeze']}
                )
                logger.info(f"Scheduled Breeze login at {time_str} (Job ID: {job_id})")
        
        # Setup Kite jobs
        if self.config['kite']['enabled']:
            for time_str in self.config['kite']['times']:
                hour, minute = map(int, time_str.split(':'))
                
                # Create cron trigger
                if self.config['kite']['weekdays_only']:
                    trigger = CronTrigger(
                        day_of_week='mon-fri',
                        hour=hour,
                        minute=minute,
                        timezone='Asia/Kolkata'
                    )
                else:
                    trigger = CronTrigger(
                        hour=hour,
                        minute=minute,
                        timezone='Asia/Kolkata'
                    )
                
                # Add job (use standalone function to avoid serialization issues)
                job_id = f"kite_login_{time_str.replace(':', '')}"
                self.scheduler.add_job(
                    func=run_kite_login_job,
                    trigger=trigger,
                    id=job_id,
                    name=f"Kite Auto-Login at {time_str}",
                    replace_existing=True,
                    kwargs={'config': self.config['kite']}
                )
                logger.info(f"Scheduled Kite login at {time_str} (Job ID: {job_id})")
    
    def run_breeze_login(self):
        """Execute Breeze auto-login"""
        logger.info("Executing scheduled Breeze login...")
        
        try:
            breeze_login = BreezeAutoLogin(
                headless=self.config['breeze']['headless']
            )
            
            success, result = breeze_login.retry_login(
                max_attempts=self.config['breeze']['max_retries']
            )
            
            # Record execution
            self.execution_history.append({
                "platform": "breeze",
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "result": result[:100] if success else result
            })
            
            if success:
                logger.info(f"Breeze login successful")
                self._send_notification("Breeze Login Success", "Token updated successfully")
            else:
                logger.error(f"Breeze login failed: {result}")
                self._send_notification("Breeze Login Failed", f"Error: {result}")
                
        except Exception as e:
            logger.error(f"Error in Breeze login job: {e}")
            self._send_notification("Breeze Login Error", str(e))
    
    def run_kite_login(self):
        """Execute Kite auto-login"""
        logger.info("Executing scheduled Kite login...")
        
        try:
            kite_login = KiteAutoLogin(
                headless=self.config['kite']['headless']
            )
            
            success, result = kite_login.retry_login(
                max_attempts=self.config['kite']['max_retries']
            )
            
            # Record execution
            self.execution_history.append({
                "platform": "kite",
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "result": result[:100] if success else result
            })
            
            if success:
                logger.info(f"Kite login successful")
                self._send_notification("Kite Login Success", "Token updated successfully")
            else:
                logger.error(f"Kite login failed: {result}")
                self._send_notification("Kite Login Failed", f"Error: {result}")
                
        except Exception as e:
            logger.error(f"Error in Kite login job: {e}")
            self._send_notification("Kite Login Error", str(e))
    
    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        return {
            "running": self.scheduler.running,
            "jobs": self.get_jobs(),
            "config": self.config,
            "recent_executions": self.execution_history[-10:],  # Last 10 executions
            "next_run_times": self.get_next_run_times()
        }
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get all scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "pending": job.pending
            })
        return jobs
    
    def get_next_run_times(self) -> List[Dict[str, Any]]:
        """Get next run times for all jobs"""
        next_runs = []
        for job in self.scheduler.get_jobs():
            if job.next_run_time:
                next_runs.append({
                    "job_name": job.name,
                    "job_id": job.id,
                    "next_run": job.next_run_time.isoformat(),
                    "platform": "breeze" if "breeze" in job.id else "kite"
                })
        
        # Sort by next run time
        next_runs.sort(key=lambda x: x['next_run'])
        return next_runs[:20]  # Return next 20 runs
    
    def update_job_schedule(self, platform: str, times: List[str]):
        """Update schedule for a specific platform"""
        if platform not in ['breeze', 'kite']:
            return {"status": "error", "message": "Invalid platform"}
        
        # Update config
        self.config[platform]['times'] = times
        self.save_config()
        
        # Recreate jobs
        self.setup_jobs()
        
        return {"status": "success", "message": f"Updated {platform} schedule"}
    
    def pause_job(self, job_id: str):
        """Pause a specific job"""
        try:
            self.scheduler.pause_job(job_id)
            return {"status": "success", "message": f"Job {job_id} paused"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def resume_job(self, job_id: str):
        """Resume a specific job"""
        try:
            self.scheduler.resume_job(job_id)
            return {"status": "success", "message": f"Job {job_id} resumed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def run_job_now(self, job_id: str):
        """Manually trigger a job immediately"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.func()
                return {"status": "success", "message": f"Job {job_id} executed"}
            else:
                return {"status": "error", "message": "Job not found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _job_executed(self, event):
        """Event listener for successful job execution"""
        logger.info(f"Job {event.job_id} executed successfully")
    
    def _job_error(self, event):
        """Event listener for job errors"""
        logger.error(f"Job {event.job_id} crashed: {event.exception}")
    
    def _send_notification(self, subject: str, message: str):
        """Send notification (placeholder for email/webhook)"""
        if not self.config['notifications']['enabled']:
            return
        
        # Log notification (implement email/webhook as needed)
        logger.info(f"Notification: {subject} - {message}")
        
        # TODO: Implement actual notification (email, webhook, etc.)
        # For now, just log it