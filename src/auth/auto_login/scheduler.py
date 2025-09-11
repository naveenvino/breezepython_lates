"""
Scheduler for automated daily login
Handles scheduling and execution of auto-login tasks
"""
import logging
import threading
import time
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, List, Optional
import schedule
from pathlib import Path
import json

from .breeze_login import BreezeAutoLogin
from .kite_login import KiteAutoLogin

logger = logging.getLogger(__name__)

class LoginScheduler:
    """
    Manages scheduled auto-login tasks
    """
    
    def __init__(self):
        self.scheduler_thread = None
        self.is_running = False
        self.config_file = Path("config/scheduler_config.json")
        self.load_config()
        
    def load_config(self):
        """Load scheduler configuration"""
        default_config = {
            "breeze": {
                "enabled": True,
                "times": ["05:30", "08:30"],  # Morning and backup
                "weekdays_only": True,
                "headless": True,
                "max_retries": 3
            },
            "kite": {
                "enabled": True,
                "times": ["05:45", "08:45"],  # After Breeze
                "weekdays_only": True,
                "headless": True,
                "max_retries": 3
            },
            "notifications": {
                "enabled": True,
                "on_success": True,
                "on_failure": True,
                "email": None,
                "webhook": None
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
        """Save scheduler configuration"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Scheduler configuration saved")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.setup_schedules()
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Login scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.is_running = False
        schedule.clear()
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Login scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def setup_schedules(self):
        """Setup scheduled tasks based on configuration"""
        schedule.clear()
        
        # Schedule Breeze login
        if self.config['breeze']['enabled']:
            for time_str in self.config['breeze']['times']:
                if self.config['breeze']['weekdays_only']:
                    schedule.every().monday.at(time_str).do(self.run_breeze_login)
                    schedule.every().tuesday.at(time_str).do(self.run_breeze_login)
                    schedule.every().wednesday.at(time_str).do(self.run_breeze_login)
                    schedule.every().tuesday.at(time_str).do(self.run_breeze_login)
                    schedule.every().friday.at(time_str).do(self.run_breeze_login)
                else:
                    schedule.every().day.at(time_str).do(self.run_breeze_login)
                
                logger.info(f"Scheduled Breeze login at {time_str}")
        
        # Schedule Kite login
        if self.config['kite']['enabled']:
            for time_str in self.config['kite']['times']:
                if self.config['kite']['weekdays_only']:
                    schedule.every().monday.at(time_str).do(self.run_kite_login)
                    schedule.every().tuesday.at(time_str).do(self.run_kite_login)
                    schedule.every().wednesday.at(time_str).do(self.run_kite_login)
                    schedule.every().tuesday.at(time_str).do(self.run_kite_login)
                    schedule.every().friday.at(time_str).do(self.run_kite_login)
                else:
                    schedule.every().day.at(time_str).do(self.run_kite_login)
                
                logger.info(f"Scheduled Kite login at {time_str}")
    
    def run_breeze_login(self):
        """Execute Breeze auto-login"""
        logger.info("Running scheduled Breeze login...")
        
        try:
            breeze_login = BreezeAutoLogin(
                headless=self.config['breeze']['headless']
            )
            
            success, result = breeze_login.retry_login(
                max_attempts=self.config['breeze']['max_retries']
            )
            
            if success:
                logger.info(f"Breeze login successful: {result[:20]}...")
                self.send_notification("Breeze Login Success", f"Token updated successfully")
            else:
                logger.error(f"Breeze login failed: {result}")
                self.send_notification("Breeze Login Failed", f"Error: {result}")
                
        except Exception as e:
            logger.error(f"Error in scheduled Breeze login: {e}")
            self.send_notification("Breeze Login Error", str(e))
    
    def run_kite_login(self):
        """Execute Kite auto-login"""
        logger.info("Running scheduled Kite login...")
        
        try:
            kite_login = KiteAutoLogin(
                headless=self.config['kite']['headless']
            )
            
            success, result = kite_login.retry_login(
                max_attempts=self.config['kite']['max_retries']
            )
            
            if success:
                logger.info(f"Kite login successful: {result[:20]}...")
                self.send_notification("Kite Login Success", f"Token updated successfully")
            else:
                logger.error(f"Kite login failed: {result}")
                self.send_notification("Kite Login Failed", f"Error: {result}")
                
        except Exception as e:
            logger.error(f"Error in scheduled Kite login: {e}")
            self.send_notification("Kite Login Error", str(e))
    
    def send_notification(self, subject: str, message: str):
        """
        Send notification about login status
        
        Args:
            subject: Notification subject
            message: Notification message
        """
        if not self.config['notifications']['enabled']:
            return
        
        # Check if we should send this type of notification
        is_success = "Success" in subject
        if is_success and not self.config['notifications']['on_success']:
            return
        if not is_success and not self.config['notifications']['on_failure']:
            return
        
        # Send email notification
        if self.config['notifications'].get('email'):
            self.send_email_notification(subject, message)
        
        # Send webhook notification
        if self.config['notifications'].get('webhook'):
            self.send_webhook_notification(subject, message)
    
    def send_email_notification(self, subject: str, message: str):
        """Send email notification"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Email configuration from environment
            from dotenv import load_dotenv
            import os
            load_dotenv()
            
            smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_user = os.getenv('SMTP_USER')
            smtp_password = os.getenv('SMTP_PASSWORD')
            
            if not smtp_user or not smtp_password:
                logger.warning("Email credentials not configured")
                return
            
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = self.config['notifications']['email']
            msg['Subject'] = f"[Auto Login] {subject}"
            
            body = f"""
            Auto Login Notification
            
            {subject}
            
            {message}
            
            Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    def send_webhook_notification(self, subject: str, message: str):
        """Send webhook notification"""
        try:
            import requests
            
            webhook_url = self.config['notifications']['webhook']
            
            payload = {
                "subject": subject,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "service": "Auto Login Scheduler"
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Webhook notification sent: {subject}")
            else:
                logger.error(f"Webhook notification failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
    
    def get_next_runs(self) -> List[Dict]:
        """Get list of next scheduled runs"""
        jobs = schedule.get_jobs()
        next_runs = []
        
        for job in jobs:
            next_runs.append({
                "job": str(job),
                "next_run": job.next_run.isoformat() if job.next_run else None
            })
        
        return next_runs
    
    def trigger_manual_login(self, service: str) -> Dict:
        """
        Manually trigger login for a service
        
        Args:
            service: 'breeze' or 'kite'
            
        Returns:
            Result dictionary
        """
        if service.lower() == 'breeze':
            self.run_breeze_login()
            return {"status": "triggered", "service": "breeze"}
        elif service.lower() == 'kite':
            self.run_kite_login()
            return {"status": "triggered", "service": "kite"}
        else:
            return {"status": "error", "message": f"Unknown service: {service}"}
    
    def update_schedule(self, service: str, config: Dict):
        """
        Update schedule configuration for a service
        
        Args:
            service: 'breeze' or 'kite'
            config: New configuration
        """
        if service in self.config:
            self.config[service].update(config)
            self.save_config()
            self.setup_schedules()
            return {"status": "success", "message": f"Schedule updated for {service}"}
        else:
            return {"status": "error", "message": f"Unknown service: {service}"}