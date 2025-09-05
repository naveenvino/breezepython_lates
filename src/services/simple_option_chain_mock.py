"""
Simple Option Chain Mock Service
Provides mock option chain data for testing without async complexity
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random

logger = logging.getLogger(__name__)

class SimpleOptionChainMock:
    """Mock option chain service for testing"""
    
    def __init__(self):
        self.spot_price = 25000  # Default NIFTY spot
        
    def get_option_chain(self, symbol: str = "NIFTY", expiry: str = None) -> Dict:
        """Get mock option chain data"""
        # Generate mock option chain around current spot
        strikes = []
        base_strike = int(self.spot_price / 100) * 100  # Round to nearest 100
        
        for i in range(-10, 11):  # 21 strikes total
            strike = base_strike + (i * 50)
            
            # Calculate mock prices based on moneyness
            distance = abs(strike - self.spot_price)
            atm_price = 150  # ATM option price
            
            # PE prices
            if strike < self.spot_price:
                # ITM PUT
                pe_price = atm_price + (self.spot_price - strike) * 0.8
            else:
                # OTM PUT
                pe_price = max(10, atm_price - distance * 0.3)
            
            # CE prices
            if strike > self.spot_price:
                # ITM CALL
                ce_price = atm_price + (strike - self.spot_price) * 0.8
            else:
                # OTM CALL
                ce_price = max(10, atm_price - distance * 0.3)
            
            # Add PUT option
            strikes.append({
                'strike': strike,
                'type': 'PE',
                'ltp': round(pe_price, 2),
                'price': round(pe_price, 2),
                'bid': round(pe_price * 0.98, 2),
                'ask': round(pe_price * 1.02, 2),
                'volume': random.randint(1000, 10000),
                'oi': random.randint(10000, 100000),
                'delta': round(-0.5 + (self.spot_price - strike) / 1000, 3)
            })
            
            # Add CALL option
            strikes.append({
                'strike': strike,
                'type': 'CE',
                'ltp': round(ce_price, 2),
                'price': round(ce_price, 2),
                'bid': round(ce_price * 0.98, 2),
                'ask': round(ce_price * 1.02, 2),
                'volume': random.randint(1000, 10000),
                'oi': random.randint(10000, 100000),
                'delta': round(0.5 - (strike - self.spot_price) / 1000, 3)
            })
        
        return {
            'symbol': symbol,
            'spot': self.spot_price,
            'expiry': expiry or self._get_next_expiry(),
            'timestamp': datetime.now().isoformat(),
            'options': strikes
        }
    
    def update_spot(self, new_spot: float):
        """Update spot price for mock data"""
        self.spot_price = new_spot
    
    def _get_next_expiry(self) -> str:
        """Get next Thursday expiry"""
        today = datetime.now()
        days_ahead = 3 - today.weekday()  # Thursday is 3
        if days_ahead <= 0:
            days_ahead += 7
        next_thursday = today + timedelta(days=days_ahead)
        return next_thursday.strftime('%Y-%m-%d')

# Singleton instance
_instance = None

def get_simple_option_chain() -> SimpleOptionChainMock:
    """Get singleton instance"""
    global _instance
    if _instance is None:
        _instance = SimpleOptionChainMock()
    return _instance