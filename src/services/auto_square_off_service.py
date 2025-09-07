"""
Auto Square-Off Service
Monitors positions and executes automatic square-off at configured times
"""
import asyncio
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class AutoSquareOffService:
    """Manages automatic position square-off based on configured timing"""
    
    def __init__(self, kite_client=None):
        self.kite_client = kite_client
        self.monitored_positions = {}
        self.is_monitoring = False
        self.square_off_schedule = []
        self.load_schedule()
    
    def load_schedule(self):
        """Load scheduled square-offs from file"""
        schedule_file = Path("square_off_schedule.json")
        if schedule_file.exists():
            try:
                with open(schedule_file, "r") as f:
                    self.square_off_schedule = json.load(f)
                logger.info(f"Loaded {len(self.square_off_schedule)} scheduled square-offs")
            except Exception as e:
                logger.error(f"Error loading schedule: {e}")
                self.square_off_schedule = []
    
    def save_schedule(self):
        """Save scheduled square-offs to file"""
        try:
            with open("square_off_schedule.json", "w") as f:
                json.dump(self.square_off_schedule, f, indent=2)
            logger.info("Square-off schedule saved")
        except Exception as e:
            logger.error(f"Error saving schedule: {e}")
    
    def add_position_to_monitor(self, position_data: Dict):
        """
        Add a position to monitoring for auto square-off
        
        Args:
            position_data: Dict with position details including:
                - symbol: Trading symbol
                - entry_time: Entry timestamp
                - exit_day_offset: T+N days for exit
                - exit_time: Time of day for exit (HH:MM)
                - quantity: Position quantity
                - order_id: Original order ID
        """
        try:
            entry_time = datetime.fromisoformat(position_data['entry_time'])
            exit_day_offset = position_data.get('exit_day_offset', 2)
            exit_time_str = position_data.get('exit_time', '15:15')
            
            # Calculate exit datetime
            from src.services.expiry_management_service import get_expiry_service
            expiry_service = get_expiry_service()
            exit_date, _ = expiry_service.calculate_exit_date(entry_time, exit_day_offset)
            
            # Parse exit time
            hour, minute = map(int, exit_time_str.split(':'))
            exit_datetime = exit_date.replace(hour=hour, minute=minute, second=0)
            
            # Add to schedule
            schedule_entry = {
                "symbol": position_data['symbol'],
                "quantity": position_data['quantity'],
                "exit_datetime": exit_datetime.isoformat(),
                "order_id": position_data.get('order_id'),
                "entry_time": entry_time.isoformat(),
                "status": "scheduled"
            }
            
            self.square_off_schedule.append(schedule_entry)
            self.save_schedule()
            
            logger.info(f"Scheduled square-off for {position_data['symbol']} at {exit_datetime}")
            
            return {
                "success": True,
                "message": f"Square-off scheduled for {exit_datetime.strftime('%Y-%m-%d %H:%M')}",
                "exit_datetime": exit_datetime.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error adding position to monitor: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    async def start_monitoring(self):
        """Start monitoring loop for auto square-off"""
        if self.is_monitoring:
            logger.warning("Monitoring already active")
            return
        
        self.is_monitoring = True
        logger.info("Starting auto square-off monitoring")
        
        while self.is_monitoring:
            try:
                await self.check_and_execute_square_offs()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def check_and_execute_square_offs(self):
        """Check for positions that need to be squared off"""
        current_time = datetime.now()
        
        for entry in self.square_off_schedule:
            if entry['status'] != 'scheduled':
                continue
            
            exit_time = datetime.fromisoformat(entry['exit_datetime'])
            
            # Check if it's time to square off (within 1 minute window)
            if current_time >= exit_time and current_time < exit_time + timedelta(minutes=1):
                logger.info(f"Executing auto square-off for {entry['symbol']}")
                await self.execute_square_off(entry)
    
    async def execute_square_off(self, schedule_entry: Dict):
        """Execute square-off for a scheduled position"""
        try:
            symbol = schedule_entry['symbol']
            quantity = schedule_entry['quantity']
            
            if self.kite_client:
                # Determine if it's a PUT or CALL from symbol
                if 'PE' in symbol:
                    option_type = 'PE'
                    transaction_type = 'BUY'  # Buy back the sold PUT
                elif 'CE' in symbol:
                    option_type = 'CE'
                    transaction_type = 'BUY'  # Buy back the sold CALL
                else:
                    logger.error(f"Cannot determine option type for {symbol}")
                    schedule_entry['status'] = 'error'
                    self.save_schedule()
                    return
                
                # Place square-off order
                order_params = {
                    'tradingsymbol': symbol,
                    'exchange': 'NFO',
                    'transaction_type': transaction_type,
                    'quantity': quantity,
                    'product': 'MIS',
                    'order_type': 'MARKET',
                    'variety': 'regular',
                    'tag': 'AUTO_SQUARE_OFF'
                }
                
                order_id = self.kite_client.place_order(**order_params)
                
                logger.info(f"Square-off order placed: {order_id} for {symbol}")
                
                # Update schedule entry
                schedule_entry['status'] = 'executed'
                schedule_entry['square_off_order_id'] = order_id
                schedule_entry['execution_time'] = datetime.now().isoformat()
                
            else:
                # Mock execution for testing
                logger.info(f"[MOCK] Would square off {quantity} qty of {symbol}")
                schedule_entry['status'] = 'executed_mock'
                schedule_entry['execution_time'] = datetime.now().isoformat()
            
            self.save_schedule()
            
        except Exception as e:
            logger.error(f"Error executing square-off: {e}")
            schedule_entry['status'] = 'error'
            schedule_entry['error'] = str(e)
            self.save_schedule()
    
    def get_pending_square_offs(self) -> List[Dict]:
        """Get list of pending square-offs"""
        pending = []
        current_time = datetime.now()
        
        for entry in self.square_off_schedule:
            if entry['status'] == 'scheduled':
                exit_time = datetime.fromisoformat(entry['exit_datetime'])
                if exit_time > current_time:
                    pending.append({
                        "symbol": entry['symbol'],
                        "quantity": entry['quantity'],
                        "exit_datetime": entry['exit_datetime'],
                        "time_remaining": str(exit_time - current_time).split('.')[0]
                    })
        
        return pending
    
    def cancel_square_off(self, symbol: str) -> bool:
        """Cancel scheduled square-off for a symbol"""
        for entry in self.square_off_schedule:
            if entry['symbol'] == symbol and entry['status'] == 'scheduled':
                entry['status'] = 'cancelled'
                entry['cancelled_at'] = datetime.now().isoformat()
                self.save_schedule()
                logger.info(f"Cancelled square-off for {symbol}")
                return True
        
        return False
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.is_monitoring = False
        logger.info("Stopping auto square-off monitoring")
    
    def cleanup_old_entries(self, days_to_keep: int = 7):
        """Remove old executed/cancelled entries"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        self.square_off_schedule = [
            entry for entry in self.square_off_schedule
            if entry['status'] == 'scheduled' or 
            datetime.fromisoformat(entry.get('execution_time', entry['exit_datetime'])) > cutoff_date
        ]
        
        self.save_schedule()
        logger.info(f"Cleaned up old entries older than {days_to_keep} days")


# Singleton instance
_square_off_service = None

def get_square_off_service(kite_client=None) -> AutoSquareOffService:
    """Get singleton instance of square-off service"""
    global _square_off_service
    if _square_off_service is None:
        _square_off_service = AutoSquareOffService(kite_client)
    return _square_off_service