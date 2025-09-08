"""
Data Binding Helper - Ensures UI always shows real data or proper fallbacks
"""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DataBinding:
    """Helper class for safe data binding with proper fallbacks"""
    
    @staticmethod
    def get_spot_price(data_source: Any) -> Optional[float]:
        """Get spot price from data source or return None"""
        try:
            if hasattr(data_source, 'get_spot_price'):
                result = data_source.get_spot_price()
                if result and isinstance(result, (int, float)) and result > 0:
                    return float(result)
        except Exception as e:
            logger.debug(f"Could not fetch spot price: {e}")
        return None
    
    @staticmethod
    def format_spot_display(spot_price: Optional[float]) -> str:
        """Format spot price for display"""
        if spot_price is None:
            return "No data available"
        return f"₹{spot_price:,.2f}"
    
    @staticmethod
    def get_hedge_offset(config: Dict) -> Optional[int]:
        """Get hedge offset from config or return None"""
        try:
            offset = config.get('hedge_offset')
            if offset and isinstance(offset, (int, float)) and offset > 0:
                return int(offset)
        except Exception as e:
            logger.debug(f"Could not get hedge offset: {e}")
        return None
    
    @staticmethod
    def format_hedge_display(hedge_offset: Optional[int]) -> str:
        """Format hedge offset for display"""
        if hedge_offset is None:
            return "Not configured"
        return f"{hedge_offset} points"
    
    @staticmethod
    def get_telegram_chat_id(config: Dict) -> Optional[str]:
        """Get Telegram chat ID from config or return None"""
        try:
            chat_id = config.get('telegram_chat_id')
            if chat_id and str(chat_id).strip():
                return str(chat_id).strip()
        except Exception as e:
            logger.debug(f"Could not get Telegram chat ID: {e}")
        return None
    
    @staticmethod
    def format_telegram_display(chat_id: Optional[str]) -> str:
        """Format Telegram chat ID for display"""
        if chat_id is None:
            return "Not configured"
        return f"Chat ID: {chat_id}"

# Usage example:
# from data_binding_helper import DataBinding
# 
# spot = DataBinding.get_spot_price(market_service)
# display_text = DataBinding.format_spot_display(spot)
# 
# This ensures UI never shows hardcoded values
