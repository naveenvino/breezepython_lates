"""
IP Whitelisting/Blacklisting Middleware
Provides security by controlling API access based on IP addresses
"""

import json
import logging
from typing import Set, Optional, Dict
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path

logger = logging.getLogger(__name__)

class IPFilterMiddleware(BaseHTTPMiddleware):
    """
    Middleware for IP-based access control
    """
    
    def __init__(self, app, config_file: str = "config/ip_filter.json"):
        super().__init__(app)
        self.config_file = Path(config_file)
        self.whitelist: Set[str] = set()
        self.blacklist: Set[str] = set()
        self.enabled = True
        self.allow_localhost = True
        self.blocked_attempts: Dict[str, int] = {}
        self.max_attempts = 5
        self.block_duration = timedelta(hours=1)
        self.temp_blocks: Dict[str, datetime] = {}
        
        # Load configuration
        self.load_config()
    
    def load_config(self):
        """Load IP filter configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.whitelist = set(config.get('whitelist', []))
                    self.blacklist = set(config.get('blacklist', []))
                    self.enabled = config.get('enabled', True)
                    self.allow_localhost = config.get('allow_localhost', True)
                    self.max_attempts = config.get('max_attempts', 5)
                    logger.info(f"Loaded IP filter config: {len(self.whitelist)} whitelisted, {len(self.blacklist)} blacklisted")
            else:
                # Create default config
                self.save_config()
        except Exception as e:
            logger.error(f"Error loading IP filter config: {e}")
    
    def save_config(self):
        """Save IP filter configuration to file"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            config = {
                'enabled': self.enabled,
                'allow_localhost': self.allow_localhost,
                'whitelist': list(self.whitelist),
                'blacklist': list(self.blacklist),
                'max_attempts': self.max_attempts,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info("Saved IP filter config")
        except Exception as e:
            logger.error(f"Error saving IP filter config: {e}")
    
    def add_to_whitelist(self, ip: str):
        """Add IP to whitelist"""
        self.whitelist.add(ip)
        # Remove from blacklist if present
        self.blacklist.discard(ip)
        self.save_config()
        logger.info(f"Added {ip} to whitelist")
    
    def remove_from_whitelist(self, ip: str):
        """Remove IP from whitelist"""
        self.whitelist.discard(ip)
        self.save_config()
        logger.info(f"Removed {ip} from whitelist")
    
    def add_to_blacklist(self, ip: str):
        """Add IP to blacklist"""
        self.blacklist.add(ip)
        # Remove from whitelist if present
        self.whitelist.discard(ip)
        self.save_config()
        logger.info(f"Added {ip} to blacklist")
    
    def remove_from_blacklist(self, ip: str):
        """Remove IP from blacklist"""
        self.blacklist.discard(ip)
        self.save_config()
        logger.info(f"Removed {ip} from blacklist")
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is allowed to access the API"""
        if not self.enabled:
            return True
        
        # Check temporary blocks
        if ip in self.temp_blocks:
            if datetime.now() < self.temp_blocks[ip]:
                return False
            else:
                # Block expired, remove it
                del self.temp_blocks[ip]
                self.blocked_attempts[ip] = 0
        
        # Allow localhost if configured
        if self.allow_localhost and ip in ['127.0.0.1', '::1', 'localhost']:
            return True
        
        # Check blacklist first
        if ip in self.blacklist:
            return False
        
        # If whitelist is empty, allow all non-blacklisted IPs
        if not self.whitelist:
            return True
        
        # Check whitelist
        return ip in self.whitelist
    
    def record_failed_attempt(self, ip: str):
        """Record a failed access attempt"""
        self.blocked_attempts[ip] = self.blocked_attempts.get(ip, 0) + 1
        
        if self.blocked_attempts[ip] >= self.max_attempts:
            # Temporarily block the IP
            self.temp_blocks[ip] = datetime.now() + self.block_duration
            logger.warning(f"IP {ip} temporarily blocked after {self.max_attempts} failed attempts")
    
    async def dispatch(self, request: Request, call_next):
        """Process the request through IP filter"""
        # Get client IP
        client_ip = request.client.host
        
        # Get real IP from headers if behind proxy
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        
        # Check if IP is allowed
        if not self.is_ip_allowed(client_ip):
            logger.warning(f"Blocked request from {client_ip} to {request.url.path}")
            self.record_failed_attempt(client_ip)
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Process request
        response = await call_next(request)
        return response
    
    def get_stats(self) -> Dict:
        """Get IP filter statistics"""
        return {
            'enabled': self.enabled,
            'whitelist_count': len(self.whitelist),
            'blacklist_count': len(self.blacklist),
            'temp_blocks': len(self.temp_blocks),
            'blocked_attempts': sum(self.blocked_attempts.values()),
            'allow_localhost': self.allow_localhost
        }


# Global instance
_ip_filter: Optional[IPFilterMiddleware] = None

def get_ip_filter(app=None) -> IPFilterMiddleware:
    """Get or create IP filter instance"""
    global _ip_filter
    if _ip_filter is None and app:
        _ip_filter = IPFilterMiddleware(app)
    return _ip_filter