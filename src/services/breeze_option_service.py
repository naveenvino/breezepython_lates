"""
Breeze Option Chain Service
Fetches real option chain data with OI, PCR, and prices
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from breeze_connect import BreezeConnect
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class BreezeOptionService:
    """Service to fetch option chain data from Breeze API"""
    
    def __init__(self):
        self.breeze = None
        self.last_option_data = None
        self.last_update = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Breeze connection"""
        try:
            api_key = os.getenv('BREEZE_API_KEY')
            api_secret = os.getenv('BREEZE_API_SECRET')
            session_token = os.getenv('BREEZE_API_SESSION')
            
            if not all([api_key, api_secret, session_token]):
                logger.error("Breeze credentials not found")
                return False
                
            self.breeze = BreezeConnect(api_key=api_key)
            self.breeze.generate_session(
                api_secret=api_secret,
                session_token=session_token
            )
            logger.info("Breeze Option Service initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Breeze Option Service: {e}")
            return False
    
    def get_current_expiry(self):
        """Get current weekly expiry (Tuesday)"""
        today = datetime.now()
        days_ahead = 1 - today.weekday()  # Tuesday = 1
        if days_ahead <= 0:
            days_ahead += 7
        expiry = today + timedelta(days=days_ahead)
        # Format: 2025-08-28T06:00:00.000Z
        return expiry.strftime("%Y-%m-%dT06:00:00.000Z")
    
    def get_option_chain(self, spot_price: float = None) -> Dict:
        """Get full option chain with OI and prices"""
        try:
            if not self.breeze:
                if not self._initialize():
                    raise RuntimeError("Failed to initialize Breeze connection for option chain data")
            
            expiry = self.get_current_expiry()
            
            # Get both calls and puts separately since API requires either right or strike
            call_response = self.breeze.get_option_chain_quotes(
                stock_code="NIFTY",
                exchange_code="NFO",
                product_type="options",
                expiry_date=expiry,
                right="call",
                strike_price=""  # Get all strikes
            )
            
            put_response = self.breeze.get_option_chain_quotes(
                stock_code="NIFTY",
                exchange_code="NFO",
                product_type="options",
                expiry_date=expiry,
                right="put",
                strike_price=""  # Get all strikes
            )
            
            # Combine responses
            response = {
                'Success': [],
                'Status': 200
            }
            
            if call_response and call_response.get('Success'):
                response['Success'].extend(call_response['Success'])
            
            if put_response and put_response.get('Success'):
                response['Success'].extend(put_response['Success'])
            
            if response and response.get('Success'):
                data = response['Success']
                
                # Calculate PCR and total OI
                total_put_oi = 0
                total_call_oi = 0
                chain_data = []
                
                for item in data:
                    strike = float(item.get('strike_price', 0))
                    right = item.get('right', '').lower()
                    oi = int(item.get('open_interest', 0))
                    ltp = float(item.get('ltp', 0))
                    
                    if right == 'put':
                        total_put_oi += oi
                    elif right == 'call':
                        total_call_oi += oi
                    
                    chain_data.append({
                        'strike': strike,
                        'type': right,
                        'ltp': ltp,
                        'oi': oi,
                        'volume': int(item.get('volume', 0)),
                        'bid': float(item.get('best_bid_price', 0)),
                        'ask': float(item.get('best_offer_price', 0))
                    })
                
                pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 0
                total_oi = total_put_oi + total_call_oi
                
                self.last_option_data = {
                    'pcr': pcr,
                    'total_oi': total_oi,
                    'put_oi': total_put_oi,
                    'call_oi': total_call_oi,
                    'chain': chain_data,
                    'expiry': expiry,
                    'timestamp': datetime.now().isoformat()
                }
                self.last_update = datetime.now()
                
                return self.last_option_data
                
            else:
                logger.error(f"Failed to get option chain: {response}")
                raise ValueError(f"No option chain data received from Breeze API: {response}")
                
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            raise RuntimeError(f"Failed to fetch option chain data: {str(e)}")
    
    def get_vix(self) -> Optional[float]:
        """Get India VIX value"""
        try:
            if not self.breeze:
                if not self._initialize():
                    return None
            
            # Try to get India VIX quote
            response = self.breeze.get_quotes(
                stock_code="INDIAVIX",
                exchange_code="NSE",
                product_type="cash",
                expiry_date="",
                strike_price=""
            )
            
            if response and response.get('Success'):
                return float(response['Success'][0].get('ltp', 0))
            else:
                logger.debug(f"VIX response: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return None

# Singleton instance
_option_service = None

def get_option_service() -> BreezeOptionService:
    """Get or create option service instance"""
    global _option_service
    if _option_service is None:
        _option_service = BreezeOptionService()
    return _option_service