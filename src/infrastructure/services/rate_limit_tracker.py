"""
Rate limit tracker for API calls
"""
import os
import json
from datetime import datetime, date
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class RateLimitTracker:
    """Track API calls to prevent rate limiting"""
    
    DAILY_LIMIT = 86400
    WARNING_THRESHOLD = 80000
    CRITICAL_THRESHOLD = 85000
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.calls_file = os.path.join(log_dir, "api_calls.json")
        self.ensure_log_dir()
    
    def ensure_log_dir(self):
        """Ensure log directory exists"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def load_calls(self) -> Dict[str, Any]:
        """Load call tracking data"""
        if os.path.exists(self.calls_file):
            try:
                with open(self.calls_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "date": str(date.today()),
            "calls": 0,
            "rate_limited": False,
            "last_reset": str(datetime.now())
        }
    
    def save_calls(self, data: Dict[str, Any]):
        """Save call tracking data"""
        with open(self.calls_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def increment_calls(self, count: int = 1) -> bool:
        """
        Increment API call counter
        Returns True if OK to proceed, False if rate limited
        """
        data = self.load_calls()
        
        # Reset counter if it's a new day
        today_str = str(date.today())
        if data["date"] != today_str:
            data = {
                "date": today_str,
                "calls": 0,
                "rate_limited": False,
                "last_reset": str(datetime.now())
            }
            logger.info("Daily API call counter reset")
        
        # Check if already rate limited
        if data["rate_limited"]:
            logger.warning("API is rate limited. Refusing new calls.")
            return False
        
        # Increment counter
        data["calls"] += count
        
        # Check thresholds
        if data["calls"] >= self.CRITICAL_THRESHOLD:
            data["rate_limited"] = True
            logger.error(f"CRITICAL: API call limit reached ({data['calls']}/{self.DAILY_LIMIT})")
            
            # Create rate limit marker file
            marker_file = os.path.join(self.log_dir, "rate_limited.txt")
            with open(marker_file, 'w') as f:
                f.write(f"Rate limited at {datetime.now()}\nCalls: {data['calls']}")
            
            self.save_calls(data)
            return False
        
        elif data["calls"] >= self.WARNING_THRESHOLD:
            logger.warning(f"WARNING: Approaching API limit ({data['calls']}/{self.DAILY_LIMIT})")
        
        # Save updated count
        self.save_calls(data)
        
        # Also save simple count for quick checks
        count_file = os.path.join(self.log_dir, "api_calls_today.txt")
        with open(count_file, 'w') as f:
            f.write(str(data["calls"]))
        
        return True
    
    def get_current_count(self) -> int:
        """Get current API call count"""
        data = self.load_calls()
        
        # Reset if new day
        if data["date"] != str(date.today()):
            return 0
        
        return data["calls"]
    
    def is_rate_limited(self) -> bool:
        """Check if currently rate limited"""
        data = self.load_calls()
        
        # Reset if new day
        if data["date"] != str(date.today()):
            return False
        
        return data["rate_limited"] or data["calls"] >= self.CRITICAL_THRESHOLD
    
    def is_approaching_limit(self) -> bool:
        """Check if approaching rate limit"""
        count = self.get_current_count()
        return count >= self.WARNING_THRESHOLD
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        data = self.load_calls()
        
        # Reset if new day
        if data["date"] != str(date.today()):
            data = {
                "date": str(date.today()),
                "calls": 0,
                "rate_limited": False,
                "last_reset": str(datetime.now())
            }
        
        return {
            "calls_today": data["calls"],
            "daily_limit": self.DAILY_LIMIT,
            "percentage_used": (data["calls"] / self.DAILY_LIMIT) * 100,
            "is_rate_limited": data["rate_limited"],
            "is_warning": data["calls"] >= self.WARNING_THRESHOLD,
            "is_critical": data["calls"] >= self.CRITICAL_THRESHOLD,
            "calls_remaining": max(0, self.DAILY_LIMIT - data["calls"])
        }


# Global instance
_tracker = None

def get_rate_limit_tracker() -> RateLimitTracker:
    """Get or create the global rate limit tracker"""
    global _tracker
    if _tracker is None:
        _tracker = RateLimitTracker()
    return _tracker