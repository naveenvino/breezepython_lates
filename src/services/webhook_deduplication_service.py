"""
Webhook Deduplication Service
Prevents duplicate orders from same signal
"""

import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import json
import logging

logger = logging.getLogger(__name__)

class WebhookDeduplicationService:
    """Prevents duplicate webhook processing"""
    
    def __init__(self):
        self.processed_signals = {}  # Store processed signal hashes
        self.signal_window = 300  # 5 minute window for same signal
        self.max_cache_size = 1000
        
    def create_signal_hash(self, webhook_data: Dict) -> str:
        """Create unique hash for webhook signal"""
        # Create hash from critical fields
        key_fields = {
            "signal": webhook_data.get("signal"),
            "strike": webhook_data.get("strike"),
            "option_type": webhook_data.get("option_type"),
            "timestamp": self._normalize_timestamp(webhook_data.get("timestamp"))
        }
        
        # Add idempotency key if provided
        if webhook_data.get("idempotency_key"):
            key_fields["idempotency_key"] = webhook_data["idempotency_key"]
        
        # Create deterministic hash
        hash_string = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def _normalize_timestamp(self, timestamp: Optional[str]) -> str:
        """Normalize timestamp to 1-minute buckets"""
        if not timestamp:
            timestamp = datetime.now().isoformat()
        
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            # Round to nearest minute
            dt = dt.replace(second=0, microsecond=0)
            return dt.isoformat()
        except:
            return datetime.now().replace(second=0, microsecond=0).isoformat()
    
    def is_duplicate(self, webhook_data: Dict) -> bool:
        """Check if webhook is duplicate"""
        signal_hash = self.create_signal_hash(webhook_data)
        current_time = time.time()
        
        # Clean old entries
        self._cleanup_old_signals(current_time)
        
        # Check if already processed
        if signal_hash in self.processed_signals:
            signal_time = self.processed_signals[signal_hash]
            time_diff = current_time - signal_time
            
            if time_diff < self.signal_window:
                logger.warning(f"Duplicate signal detected: {signal_hash} (processed {time_diff:.1f}s ago)")
                return True
        
        # Mark as processed
        self.processed_signals[signal_hash] = current_time
        logger.info(f"New signal processed: {signal_hash}")
        return False
    
    def _cleanup_old_signals(self, current_time: float):
        """Remove old signals from cache"""
        expired = []
        for hash_key, signal_time in self.processed_signals.items():
            if current_time - signal_time > self.signal_window:
                expired.append(hash_key)
        
        for hash_key in expired:
            del self.processed_signals[hash_key]
        
        # Prevent cache from growing too large
        if len(self.processed_signals) > self.max_cache_size:
            # Keep only recent half
            sorted_signals = sorted(self.processed_signals.items(), key=lambda x: x[1], reverse=True)
            self.processed_signals = dict(sorted_signals[:self.max_cache_size // 2])

# Singleton instance
_deduplication_service = None

def get_deduplication_service() -> WebhookDeduplicationService:
    """Get singleton deduplication service"""
    global _deduplication_service
    if _deduplication_service is None:
        _deduplication_service = WebhookDeduplicationService()
    return _deduplication_service