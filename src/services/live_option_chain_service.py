"""
Live Option Chain Service with Proper Strike Selection
Handles real-time option chain data with intelligent strike selection
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from breeze_connect import BreezeConnect
from dotenv import load_dotenv
import numpy as np

load_dotenv()
logger = logging.getLogger(__name__)

class LiveOptionChainService:
    """Live option chain service with proper strike selection"""
    
    def __init__(self):
        self.breeze = None
        self.is_connected = False
        self.spot_price = None
        self.cache = {}
        self.cache_ttl = 30  # 30 seconds cache
        self.last_cache_time = None
        
        # Breeze credentials
        self.api_key = os.getenv('BREEZE_API_KEY')
        self.api_secret = os.getenv('BREEZE_API_SECRET')
        self.session_token = os.getenv('BREEZE_API_SESSION')
        
        # Strike selection parameters
        self.strike_interval = 50  # NIFTY strike interval
        self.min_strikes_around_spot = 10  # Minimum strikes on each side
        self.max_strikes_around_spot = 20  # Maximum strikes on each side
        
        # Initialize connection
        self.connect()
    
    def connect(self) -> bool:
        """Connect to Breeze API"""
        try:
            if not all([self.api_key, self.api_secret, self.session_token]):
                logger.error("Missing Breeze API credentials")
                return False
            
            self.breeze = BreezeConnect(api_key=self.api_key)
            self.breeze.generate_session(
                api_secret=self.api_secret,
                session_token=self.session_token
            )
            
            # Test connection with a simple call
            response = self.breeze.get_funds()
            if response and (response.get('Status') == 200 or response.get('Success')):
                self.is_connected = True
                logger.info("Successfully connected to Breeze API")
                return True
            else:
                logger.error(f"Breeze connection test failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to Breeze: {e}")
            self.is_connected = False
            return False
    
    def get_current_expiry(self) -> Tuple[str, str]:
        """
        Get current weekly expiry date
        Returns: (date_string, breeze_format)
        """
        today = datetime.now()
        
        # Tuesday is weekday 1
        days_until_tuesday = (1 - today.weekday()) % 7
        
        # If today is Tuesday after 3:30 PM, get next Tuesday
        if days_until_tuesday == 0:
            current_time = today.time()
            if current_time.hour >= 15 and current_time.minute >= 30:
                days_until_tuesday = 7
        
        expiry_date = today + timedelta(days=days_until_tuesday)
        
        # Format for display: YYYY-MM-DD
        date_string = expiry_date.strftime('%Y-%m-%d')
        
        # Format for Breeze API: DD-Mon-YYYY
        breeze_format = expiry_date.strftime('%d-%b-%Y')
        
        return date_string, breeze_format
    
    def get_spot_price(self, force_refresh: bool = False) -> Optional[float]:
        """Get real NIFTY spot price"""
        
        # Use cache if available and not forcing refresh
        if not force_refresh and self.spot_price and self.last_cache_time:
            if (datetime.now() - self.last_cache_time).seconds < self.cache_ttl:
                return self.spot_price
        
        if not self.is_connected:
            logger.error("Not connected to Breeze API")
            return None
        
        try:
            response = self.breeze.get_quotes(
                stock_code="NIFTY",
                exchange_code="NSE",
                product_type="cash"
            )
            
            if response and response.get('Success'):
                data = response['Success'][0]
                self.spot_price = float(data.get('ltp', 0))
                self.last_cache_time = datetime.now()
                logger.info(f"NIFTY spot price: {self.spot_price}")
                return self.spot_price
            else:
                logger.error(f"Failed to get spot price: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting spot price: {e}")
            return None
    
    def calculate_strikes_to_fetch(self, spot: float, num_strikes: int = 15) -> List[int]:
        """
        Calculate which strikes to fetch based on spot price
        
        Args:
            spot: Current spot price
            num_strikes: Number of strikes on each side of ATM
            
        Returns:
            List of strike prices to fetch
        """
        # Find ATM strike (rounded to nearest strike interval)
        atm_strike = round(spot / self.strike_interval) * self.strike_interval
        
        strikes = []
        
        # Add strikes below ATM (ITM puts, OTM calls)
        for i in range(num_strikes, 0, -1):
            strikes.append(atm_strike - (i * self.strike_interval))
        
        # Add ATM strike
        strikes.append(atm_strike)
        
        # Add strikes above ATM (OTM puts, ITM calls)
        for i in range(1, num_strikes + 1):
            strikes.append(atm_strike + (i * self.strike_interval))
        
        return strikes
    
    def get_option_data(self, strike: int, option_type: str, expiry_format: str) -> Optional[Dict]:
        """
        Get option data for a specific strike
        
        Args:
            strike: Strike price
            option_type: 'CE' or 'PE'
            expiry_format: Expiry date in Breeze format
            
        Returns:
            Option data dictionary or None
        """
        try:
            right = 'call' if option_type == 'CE' else 'put'
            
            response = self.breeze.get_option_chain_quotes(
                stock_code="NIFTY",
                exchange_code="NFO",
                product_type="options",
                expiry_date=expiry_format,
                strike_price=str(strike),
                right=right
            )
            
            if response and response.get('Success'):
                data = response['Success'][0]
                
                return {
                    'strike': strike,
                    'type': option_type,
                    'ltp': float(data.get('ltp', 0)),
                    'bid': float(data.get('best_bid_price', 0)),
                    'ask': float(data.get('best_offer_price', 0)),
                    'volume': int(data.get('total_quantity_traded', 0)),
                    'oi': int(data.get('open_interest', 0)),
                    'iv': float(data.get('implied_volatility', 0)) if data.get('implied_volatility') else 0,
                    'bid_qty': int(data.get('best_bid_quantity', 0)),
                    'ask_qty': int(data.get('best_offer_quantity', 0)),
                    'change': float(data.get('change', 0)),
                    'change_percent': float(data.get('change_percent', 0))
                }
            else:
                logger.warning(f"No data for {strike} {option_type}: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching {strike} {option_type}: {e}")
            return None
    
    def get_option_chain(self, symbol: str = "NIFTY", expiry: str = None, num_strikes: int = 15) -> Dict:
        """
        Get complete option chain with proper strike selection
        
        Args:
            symbol: Symbol (default NIFTY)
            expiry: Expiry date (default current weekly)
            num_strikes: Number of strikes on each side of ATM
            
        Returns:
            Complete option chain data
        """
        
        if not self.is_connected:
            if not self.connect():
                raise RuntimeError("Cannot connect to Breeze API. Please check credentials.")
        
        # Get spot price
        spot = self.get_spot_price()
        if not spot:
            raise RuntimeError("Cannot get NIFTY spot price")
        
        # Get expiry dates
        display_expiry, breeze_expiry = self.get_current_expiry()
        if expiry:
            # Convert user-provided expiry to Breeze format
            expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
            breeze_expiry = expiry_date.strftime('%d-%b-%Y')
            display_expiry = expiry
        
        logger.info(f"Fetching option chain for {display_expiry} (Breeze format: {breeze_expiry})")
        
        # Calculate strikes to fetch
        strikes = self.calculate_strikes_to_fetch(spot, num_strikes)
        logger.info(f"Fetching {len(strikes)} strikes from {strikes[0]} to {strikes[-1]}")
        
        # Fetch option data
        options = []
        ce_data = []
        pe_data = []
        
        for strike in strikes:
            # Fetch CE data
            ce = self.get_option_data(strike, 'CE', breeze_expiry)
            if ce:
                options.append(ce)
                ce_data.append(ce)
            
            # Fetch PE data
            pe = self.get_option_data(strike, 'PE', breeze_expiry)
            if pe:
                options.append(pe)
                pe_data.append(pe)
        
        # Calculate summary statistics
        total_ce_oi = sum(opt['oi'] for opt in ce_data)
        total_pe_oi = sum(opt['oi'] for opt in pe_data)
        pcr_oi = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
        
        total_ce_vol = sum(opt['volume'] for opt in ce_data)
        total_pe_vol = sum(opt['volume'] for opt in pe_data)
        pcr_volume = total_pe_vol / total_ce_vol if total_ce_vol > 0 else 0
        
        # Find max OI strikes
        max_ce_oi = max(ce_data, key=lambda x: x['oi']) if ce_data else None
        max_pe_oi = max(pe_data, key=lambda x: x['oi']) if pe_data else None
        
        # Find ATM strike
        atm_strike = round(spot / self.strike_interval) * self.strike_interval
        
        return {
            'symbol': symbol,
            'spot': spot,
            'spot_price': spot,
            'expiry': display_expiry,
            'timestamp': datetime.now().isoformat(),
            'options': options,
            'strikes': strikes,
            'atm_strike': atm_strike,
            'summary': {
                'total_ce_oi': total_ce_oi,
                'total_pe_oi': total_pe_oi,
                'pcr_oi': round(pcr_oi, 2),
                'pcr_volume': round(pcr_volume, 2),
                'max_ce_oi_strike': max_ce_oi['strike'] if max_ce_oi else None,
                'max_pe_oi_strike': max_pe_oi['strike'] if max_pe_oi else None,
                'total_strikes': len(strikes),
                'ce_count': len(ce_data),
                'pe_count': len(pe_data)
            },
            'data_source': 'BREEZE_LIVE'
        }
    
    def get_strike_for_hedge(self, main_strike: int, option_type: str, hedge_method: str = 'offset', 
                            hedge_offset: int = 200, hedge_percent: float = 30.0) -> int:
        """
        Calculate hedge strike based on configuration
        
        Args:
            main_strike: Main position strike
            option_type: 'CE' or 'PE'
            hedge_method: 'offset' or 'percentage'
            hedge_offset: Points offset for hedge
            hedge_percent: Percentage of main premium for hedge
            
        Returns:
            Hedge strike price
        """
        
        if hedge_method == 'offset':
            # Simple offset method
            if option_type == 'PE':
                return main_strike - hedge_offset
            else:  # CE
                return main_strike + hedge_offset
        
        elif hedge_method == 'percentage':
            # Get option chain to find strike with desired premium percentage
            try:
                expiry_display, expiry_breeze = self.get_current_expiry()
                
                # Get main leg premium
                main_data = self.get_option_data(main_strike, option_type, expiry_breeze)
                if not main_data:
                    logger.warning(f"Cannot get main leg data, using offset method")
                    if option_type == 'PE':
                        return main_strike - hedge_offset
                    else:
                        return main_strike + hedge_offset
                
                main_premium = main_data['ltp']
                target_premium = main_premium * (hedge_percent / 100)
                
                logger.info(f"Main premium: {main_premium}, Target hedge premium: {target_premium} ({hedge_percent}%)")
                
                # Search for strike with closest premium to target
                search_range = 10  # Search 10 strikes away
                best_strike = None
                best_diff = float('inf')
                
                for i in range(1, search_range + 1):
                    if option_type == 'PE':
                        test_strike = main_strike - (i * self.strike_interval)
                    else:  # CE
                        test_strike = main_strike + (i * self.strike_interval)
                    
                    test_data = self.get_option_data(test_strike, option_type, expiry_breeze)
                    if test_data:
                        premium_diff = abs(test_data['ltp'] - target_premium)
                        if premium_diff < best_diff:
                            best_diff = premium_diff
                            best_strike = test_strike
                            
                            # If we found a close match, stop searching
                            if premium_diff < target_premium * 0.1:  # Within 10% of target
                                break
                
                if best_strike:
                    logger.info(f"Selected hedge strike: {best_strike}")
                    return best_strike
                else:
                    # Fallback to offset if search fails
                    logger.warning("Could not find suitable hedge strike, using offset")
                    if option_type == 'PE':
                        return main_strike - hedge_offset
                    else:
                        return main_strike + hedge_offset
                        
            except Exception as e:
                logger.error(f"Error calculating percentage-based hedge: {e}")
                # Fallback to offset
                if option_type == 'PE':
                    return main_strike - hedge_offset
                else:
                    return main_strike + hedge_offset
        
        else:
            # Default to offset
            if option_type == 'PE':
                return main_strike - hedge_offset
            else:
                return main_strike + hedge_offset

# Singleton instance
_instance = None

def get_live_option_chain_service() -> LiveOptionChainService:
    """Get singleton instance of live option chain service"""
    global _instance
    if _instance is None:
        _instance = LiveOptionChainService()
    return _instance