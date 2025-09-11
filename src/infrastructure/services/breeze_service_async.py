"""
Asynchronous Breeze API Service
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio

# from breeze_connect import BreezeConnect  # Commented out for testing

from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class AsyncBreezeService:
    """Asynchronous service for Breeze API interactions"""
    
    def __init__(self):
        self.settings = get_settings()
        self._breeze = None
        self._initialized = False
    
    def _initialize(self):
        if not self._initialized:
            try:
                from breeze_connect import BreezeConnect
                api_key = self.settings.breeze.api_key or getattr(self.settings.breeze, 'breeze_api_key', '')
                api_secret = self.settings.breeze.api_secret or getattr(self.settings.breeze, 'breeze_api_secret', '')
                session_token = self.settings.breeze.session_token or getattr(self.settings.breeze, 'breeze_api_session', '')
                
                if not api_key or not api_secret:
                    raise ValueError("Breeze API credentials not found in settings")
                
                self._breeze = BreezeConnect(api_key=api_key)
                try:
                    self._breeze.generate_session(
                        api_secret=api_secret,
                        session_token=session_token
                    )
                    self._initialized = True
                    logger.info("Breeze API session generated successfully")
                except Exception as session_error:
                    logger.warning(f"Session generation warning: {session_error}")
                    self._initialized = True
            except ImportError:
                logger.warning("breeze_connect module not installed. Install with: pip install breeze-connect")
                self._breeze = None
                self._initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize Breeze API: {e}")
                self._breeze = None
                self._initialized = True
    
    async def get_historical_data(self, *args, **kwargs) -> Dict[str, Any]:
        self._initialize()
        
        if self._breeze is None:
            logger.error("Breeze API not available")
            raise RuntimeError("Breeze API not initialized - cannot fetch historical data")
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._breeze.get_historical_data_v2(*args, **kwargs)
            )
            logger.debug(f"Breeze API response: {result}")
            return result
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise RuntimeError(f"Failed to fetch historical data from Breeze API: {str(e)}")
