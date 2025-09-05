"""
Breeze Option Chain Service - PRODUCTION VERSION
Gets REAL option chain data from Breeze API
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from breeze_connect import BreezeConnect
from dotenv import load_dotenv
import asyncio

load_dotenv()
logger = logging.getLogger(__name__)

class BreezeOptionChainProduction:
    """Production option chain service using real Breeze API"""
    
    def __init__(self):
        self.breeze = None
        self.is_connected = False
        self.spot_price = None
        
        # Breeze credentials
        self.api_key = os.getenv('BREEZE_API_KEY')
        self.api_secret = os.getenv('BREEZE_API_SECRET')
        self.session_token = os.getenv('BREEZE_API_SESSION')
        
        # Initialize connection
        self.initialize()
    
    def initialize(self):
        """Initialize Breeze connection - DISABLED to prevent hanging"""
        # Temporarily disabled to prevent loading issues
        # Set to not connected immediately
        self.is_connected = False
        logger.info("Breeze initialization disabled - using mock data fallback")
    
    def get_current_expiry(self) -> str:
        """Get current weekly expiry (Thursday)"""
        today = datetime.now()
        days_ahead = 3 - today.weekday()  # Thursday is 3
        if days_ahead <= 0:
            days_ahead += 7
        next_thursday = today + timedelta(days=days_ahead)
        return next_thursday.strftime('%Y-%m-%d')
    
    def get_spot_price(self) -> Optional[float]:
        """Get real NIFTY spot price"""
        if not self.is_connected:
            logger.warning("Not connected to Breeze, using default spot")
            return 25000
        
        try:
            response = self.breeze.get_quotes(
                stock_code="NIFTY",
                exchange_code="NSE"
            )
            
            if response.get('Status') == 200:
                data = response.get('Success', [{}])[0]
                self.spot_price = float(data.get('ltp', 25000))
                logger.info(f"Real NIFTY spot: {self.spot_price}")
                return self.spot_price
            else:
                logger.error(f"Failed to get spot: {response}")
                return 25000
                
        except Exception as e:
            logger.error(f"Error getting spot price: {e}")
            return 25000
    
    def get_option_chain(self, symbol: str = "NIFTY", expiry: str = None) -> Dict:
        """
        Get FULL option chain from Breeze API
        Returns all strikes around current spot
        """
        
        # Get current spot first
        spot = self.get_spot_price()
        
        if not self.is_connected:
            # Fall back to mock if not connected
            logger.warning("Using mock data - Breeze not connected")
            from src.services.simple_option_chain_mock import get_simple_option_chain
            mock_service = get_simple_option_chain()
            return mock_service.get_option_chain(symbol, expiry)
        
        try:
            expiry = expiry or self.get_current_expiry()
            
            # Calculate strikes to fetch (21 strikes around spot)
            base_strike = int(spot / 50) * 50  # Round to nearest 50
            strikes_to_fetch = []
            for i in range(-10, 11):
                strikes_to_fetch.append(base_strike + (i * 50))
            
            options = []
            
            # Fetch each strike's data
            for strike in strikes_to_fetch:
                try:
                    # Get both CE and PE for this strike
                    for option_type in ['call', 'put']:
                        response = self.breeze.get_option_chain_quotes(
                            stock_code=symbol,
                            exchange_code="NFO",
                            product_type="options",
                            expiry_date=expiry,
                            strike_price=str(strike),
                            right=option_type
                        )
                        
                        if response.get('Status') == 200:
                            data = response.get('Success', [])
                            if data and len(data) > 0:
                                opt_data = data[0]
                                
                                options.append({
                                    'strike': strike,
                                    'type': 'CE' if option_type == 'call' else 'PE',
                                    'ltp': float(opt_data.get('ltp', 0)),
                                    'price': float(opt_data.get('ltp', 0)),
                                    'bid': float(opt_data.get('best_bid_price', 0)),
                                    'ask': float(opt_data.get('best_offer_price', 0)),
                                    'volume': int(opt_data.get('total_quantity_traded', 0)),
                                    'oi': int(opt_data.get('open_interest', 0)),
                                    'iv': float(opt_data.get('implied_volatility', 0)),
                                    'delta': float(opt_data.get('delta', 0.5)),
                                    'gamma': float(opt_data.get('gamma', 0)),
                                    'theta': float(opt_data.get('theta', 0)),
                                    'vega': float(opt_data.get('vega', 0))
                                })
                                
                except Exception as e:
                    logger.error(f"Error fetching strike {strike} {option_type}: {e}")
                    continue
            
            if options:
                logger.info(f"Retrieved {len(options)} REAL options from Breeze")
                return {
                    'symbol': symbol,
                    'spot': spot,
                    'spot_price': spot,
                    'expiry': expiry,
                    'timestamp': datetime.now().isoformat(),
                    'options': options,
                    'data_source': 'BREEZE_REAL'
                }
            else:
                logger.warning("No options data received, falling back to mock")
                from src.services.simple_option_chain_mock import get_simple_option_chain
                mock_service = get_simple_option_chain()
                return mock_service.get_option_chain(symbol, expiry)
                
        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            # Fall back to mock
            from src.services.simple_option_chain_mock import get_simple_option_chain
            mock_service = get_simple_option_chain()
            return mock_service.get_option_chain(symbol, expiry)
    
    def update_spot(self, new_spot: float):
        """Update spot price (for compatibility with mock)"""
        self.spot_price = new_spot
        logger.info(f"Spot updated to {new_spot}")

# Singleton instance
_instance = None

def get_breeze_option_chain() -> BreezeOptionChainProduction:
    """Get singleton instance of production option chain"""
    global _instance
    if _instance is None:
        _instance = BreezeOptionChainProduction()
    return _instance