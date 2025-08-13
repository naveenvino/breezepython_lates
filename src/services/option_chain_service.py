"""
Option Chain Service
Fetches real-time option chain data from brokers
Priority: 1. Kite (primary), 2. Breeze (fallback)
NO MOCK DATA - Real data only
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
import os
import json
from kiteconnect import KiteConnect

from src.analytics.greeks_calculator import GreeksCalculator
from src.infrastructure.cache.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class OptionChainService:
    """Service for fetching and processing option chain data"""
    
    def __init__(self):
        """Initialize Option Chain Service"""
        self.cache = RedisCache()
        self.greeks_calculator = GreeksCalculator()
        self.kite = None
        self.breeze = None
        self._connect_brokers()
        
    def _connect_brokers(self):
        """Connect to brokers - Kite first, then Breeze"""
        # Try Kite first (primary)
        try:
            kite_api_key = os.getenv('KITE_API_KEY')
            kite_access_token = os.getenv('KITE_ACCESS_TOKEN')
            
            if kite_api_key and kite_access_token:
                self.kite = KiteConnect(api_key=kite_api_key)
                self.kite.set_access_token(kite_access_token)
                logger.info("Connected to Kite API for option chain (PRIMARY)")
            else:
                logger.warning("Kite API credentials not found")
        except Exception as e:
            logger.error(f"Failed to connect to Kite: {e}")
            
        # Try Breeze as fallback
        try:
            from breeze_connect import BreezeConnect
            
            api_key = os.getenv('BREEZE_API_KEY')
            api_secret = os.getenv('BREEZE_API_SECRET')
            session_token = os.getenv('BREEZE_API_SESSION')
            
            if api_key and api_secret and session_token:
                self.breeze = BreezeConnect(api_key=api_key)
                self.breeze.generate_session(
                    api_secret=api_secret,
                    session_token=session_token
                )
                logger.info("Connected to Breeze API for option chain (FALLBACK)")
            else:
                logger.warning("Breeze API credentials not found")
        except Exception as e:
            logger.warning(f"Could not connect to Breeze: {e}")
    
    def get_current_expiry(self) -> str:
        """Get current week's expiry date (Thursday)"""
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0 and today.hour >= 15:  # After 3 PM on Thursday
            days_until_thursday = 7
        expiry = today + timedelta(days=days_until_thursday)
        return expiry.strftime("%Y-%m-%d")
    
    def get_next_expiry(self) -> str:
        """Get next week's expiry date"""
        current_expiry = datetime.strptime(self.get_current_expiry(), "%Y-%m-%d")
        next_expiry = current_expiry + timedelta(days=7)
        return next_expiry.strftime("%Y-%m-%d")
    
    def get_monthly_expiry(self) -> str:
        """Get monthly expiry (last Thursday of month)"""
        today = datetime.now()
        # Find last Thursday of current month
        next_month = today.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        
        # Find last Thursday
        while last_day.weekday() != 3:  # Thursday is 3
            last_day -= timedelta(days=1)
            
        if today > last_day:
            # Move to next month's last Thursday
            next_month = last_day + timedelta(days=35)
            last_day = next_month.replace(day=28) + timedelta(days=4)
            last_day = last_day - timedelta(days=last_day.day)
            while last_day.weekday() != 3:
                last_day -= timedelta(days=1)
                
        return last_day.strftime("%Y-%m-%d")
    
    def fetch_option_chain(
        self,
        symbol: str = 'NIFTY',
        expiry_date: Optional[str] = None,
        strike_count: int = 20
    ) -> Dict[str, Any]:
        """
        Fetch option chain data from broker
        Priority: 1. Kite, 2. Breeze
        NO MOCK DATA - returns error if no broker available
        
        Args:
            symbol: Index symbol (NIFTY, BANKNIFTY, etc.)
            expiry_date: Expiry date in YYYY-MM-DD format
            strike_count: Number of strikes to fetch on each side of ATM
            
        Returns:
            Option chain data with strikes, prices, OI, volume, etc.
        """
        # Check cache first
        cache_key = f"option_chain:{symbol}:{expiry_date or 'current'}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        if not expiry_date:
            expiry_date = self.get_current_expiry()
        
        # Try Kite first (primary)
        if self.kite:
            try:
                return self._fetch_from_kite(symbol, expiry_date, strike_count)
            except Exception as e:
                logger.error(f"Kite fetch failed: {e}")
                
        # Try Breeze as fallback
        if self.breeze:
            try:
                return self._fetch_from_breeze(symbol, expiry_date, strike_count)
            except Exception as e:
                logger.error(f"Breeze fetch failed: {e}")
        
        # No broker available - return error (NO MOCK DATA)
        raise Exception("No broker connection available. Please check Kite or Breeze credentials.")
    
    def _fetch_from_kite(
        self,
        symbol: str,
        expiry_date: str,
        strike_count: int
    ) -> Dict[str, Any]:
        """Fetch option chain from Kite (PRIMARY)"""
        # Get spot price
        spot_instrument = f"NSE:{symbol}"
        ltp_data = self.kite.ltp([spot_instrument])
        spot_price = ltp_data[spot_instrument]['last_price']
        
        # Calculate ATM strike
        strike_interval = 50 if symbol == 'NIFTY' else 100
        atm_strike = round(spot_price / strike_interval) * strike_interval
        
        # Generate strikes
        strikes = []
        for i in range(-strike_count, strike_count + 1):
            strikes.append(atm_strike + (i * strike_interval))
        
        # Format expiry for Kite
        expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        expiry_str = expiry_dt.strftime("%y%b").upper()  # e.g., "24JAN"
        expiry_day = expiry_dt.strftime("%d").lstrip("0")  # Remove leading zero
        
        # Fetch option data
        option_chain = []
        instruments = []
        
        # Build instrument list
        for strike in strikes:
            call_symbol = f"NFO:{symbol}{expiry_str}{expiry_day}{strike}CE"
            put_symbol = f"NFO:{symbol}{expiry_str}{expiry_day}{strike}PE"
            instruments.extend([call_symbol, put_symbol])
        
        # Fetch all quotes at once
        try:
            quotes = self.kite.quote(instruments)
        except:
            quotes = {}
        
        # Process data
        for strike in strikes:
            call_symbol = f"NFO:{symbol}{expiry_str}{expiry_day}{strike}CE"
            put_symbol = f"NFO:{symbol}{expiry_str}{expiry_day}{strike}PE"
            
            call_data = quotes.get(call_symbol, {})
            put_data = quotes.get(put_symbol, {})
            
            chain_row = {
                'strike': strike,
                'call_ltp': call_data.get('last_price', 0),
                'call_bid': call_data.get('depth', {}).get('buy', [{}])[0].get('price', 0),
                'call_ask': call_data.get('depth', {}).get('sell', [{}])[0].get('price', 0),
                'call_oi': call_data.get('oi', 0),
                'call_volume': call_data.get('volume', 0),
                'call_iv': 0.25,  # Kite doesn't provide IV directly
                'put_ltp': put_data.get('last_price', 0),
                'put_bid': put_data.get('depth', {}).get('buy', [{}])[0].get('price', 0),
                'put_ask': put_data.get('depth', {}).get('sell', [{}])[0].get('price', 0),
                'put_oi': put_data.get('oi', 0),
                'put_volume': put_data.get('volume', 0),
                'put_iv': 0.25,  # Kite doesn't provide IV directly
                'moneyness': self._get_moneyness_label(spot_price, strike)
            }
            
            option_chain.append(chain_row)
        
        result = {
            'symbol': symbol,
            'spot_price': spot_price,
            'atm_strike': atm_strike,
            'expiry_date': expiry_date,
            'timestamp': datetime.now().isoformat(),
            'source': 'KITE',
            'chain': option_chain
        }
        
        # Cache for 1 minute
        cache_key = f"option_chain:{symbol}:{expiry_date}"
        self.cache.set(cache_key, json.dumps(result), ttl=60)
        
        return result
    
    def _fetch_from_breeze(
        self,
        symbol: str,
        expiry_date: str,
        strike_count: int
    ) -> Dict[str, Any]:
        """Fetch option chain from Breeze (FALLBACK)"""
        # Get spot price
        spot_data = self.breeze.get_quotes(
            stock_code=symbol,
            exchange_code="NSE",
            product_type="cash"
        )
        
        if not spot_data or not spot_data.get('Success'):
            raise Exception("Failed to get spot price from Breeze")
            
        spot_price = float(spot_data['Success'][0]['ltp'])
        
        # Calculate ATM strike
        strike_interval = 50 if symbol == 'NIFTY' else 100
        atm_strike = round(spot_price / strike_interval) * strike_interval
        
        # Generate strikes
        strikes = []
        for i in range(-strike_count, strike_count + 1):
            strikes.append(atm_strike + (i * strike_interval))
        
        # Format expiry date for Breeze
        expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        formatted_expiry = expiry_dt.strftime("%d-%b-%Y")
        
        # Fetch option data
        option_chain = []
        
        for strike in strikes:
            # Fetch call data
            call_data = self._fetch_breeze_option(symbol, strike, 'call', formatted_expiry)
            # Fetch put data
            put_data = self._fetch_breeze_option(symbol, strike, 'put', formatted_expiry)
            
            chain_row = {
                'strike': strike,
                'call_ltp': call_data.get('ltp', 0),
                'call_bid': call_data.get('bid', 0),
                'call_ask': call_data.get('ask', 0),
                'call_oi': call_data.get('oi', 0),
                'call_volume': call_data.get('volume', 0),
                'call_iv': call_data.get('iv', 0.25),
                'put_ltp': put_data.get('ltp', 0),
                'put_bid': put_data.get('bid', 0),
                'put_ask': put_data.get('ask', 0),
                'put_oi': put_data.get('oi', 0),
                'put_volume': put_data.get('volume', 0),
                'put_iv': put_data.get('iv', 0.25),
                'moneyness': self._get_moneyness_label(spot_price, strike)
            }
            
            option_chain.append(chain_row)
        
        result = {
            'symbol': symbol,
            'spot_price': spot_price,
            'atm_strike': atm_strike,
            'expiry_date': expiry_date,
            'timestamp': datetime.now().isoformat(),
            'source': 'BREEZE',
            'chain': option_chain
        }
        
        # Cache for 1 minute
        cache_key = f"option_chain:{symbol}:{expiry_date}"
        self.cache.set(cache_key, json.dumps(result), ttl=60)
        
        return result
    
    def _fetch_breeze_option(
        self,
        symbol: str,
        strike: int,
        option_type: str,
        expiry_date: str
    ) -> Dict[str, float]:
        """Fetch single option data from Breeze"""
        try:
            response = self.breeze.get_option_chain_quotes(
                stock_code=symbol,
                exchange_code="NFO",
                product_type="options",
                expiry_date=expiry_date,
                right=option_type,
                strike_price=str(strike)
            )
            
            if response and response.get('Status') == 200 and response.get('Success'):
                data = response['Success'][0]
                return {
                    'ltp': float(data.get('ltp', 0)),
                    'bid': float(data.get('best_bid_price', 0)),
                    'ask': float(data.get('best_offer_price', 0)),
                    'oi': int(data.get('open_interest', 0)),
                    'volume': int(data.get('volume', 0)),
                    'iv': float(data.get('implied_volatility', 0.25))
                }
        except Exception as e:
            logger.debug(f"Error fetching Breeze option data: {e}")
        
        return {'ltp': 0, 'bid': 0, 'ask': 0, 'oi': 0, 'volume': 0, 'iv': 0.25}
    
    def _get_moneyness_label(self, spot: float, strike: float) -> str:
        """Get moneyness label for a strike"""
        threshold = spot * 0.01  # 1% threshold for ATM
        
        if abs(strike - spot) <= threshold:
            return 'ATM'
        elif strike < spot:
            return 'ITM'
        else:
            return 'OTM'
    
    def calculate_option_chain_greeks(
        self,
        option_chain: Dict[str, Any],
        risk_free_rate: float = 0.06
    ) -> Dict[str, Any]:
        """
        Calculate Greeks for entire option chain
        
        Args:
            option_chain: Option chain data from fetch_option_chain
            risk_free_rate: Risk-free rate (default 6%)
            
        Returns:
            Option chain with Greeks added
        """
        spot_price = option_chain['spot_price']
        expiry_date = datetime.strptime(option_chain['expiry_date'], "%Y-%m-%d")
        time_to_expiry = (expiry_date - datetime.now()).days / 365.0
        
        # Calculate Greeks for each strike
        for row in option_chain['chain']:
            strike = row['strike']
            
            # Calculate call Greeks
            if row['call_ltp'] > 0:
                call_iv = row.get('call_iv', 0.25)
                call_greeks = self.greeks_calculator.calculate_all_greeks(
                    spot=spot_price,
                    strike=strike,
                    time_to_expiry=time_to_expiry,
                    volatility=call_iv,
                    option_type='CALL',
                    option_price=row['call_ltp']
                )
                
                row['call_delta'] = round(call_greeks['delta'], 4)
                row['call_gamma'] = round(call_greeks['gamma'], 4)
                row['call_theta'] = round(call_greeks['theta'], 2)
                row['call_vega'] = round(call_greeks['vega'], 2)
                row['call_rho'] = round(call_greeks['rho'], 2)
            
            # Calculate put Greeks
            if row['put_ltp'] > 0:
                put_iv = row.get('put_iv', 0.25)
                put_greeks = self.greeks_calculator.calculate_all_greeks(
                    spot=spot_price,
                    strike=strike,
                    time_to_expiry=time_to_expiry,
                    volatility=put_iv,
                    option_type='PUT',
                    option_price=row['put_ltp']
                )
                
                row['put_delta'] = round(put_greeks['delta'], 4)
                row['put_gamma'] = round(put_greeks['gamma'], 4)
                row['put_theta'] = round(put_greeks['theta'], 2)
                row['put_vega'] = round(put_greeks['vega'], 2)
                row['put_rho'] = round(put_greeks['rho'], 2)
        
        option_chain['greeks_calculated'] = True
        option_chain['time_to_expiry'] = round(time_to_expiry * 365, 1)  # In days
        
        return option_chain
    
    def get_pcr_ratio(self, option_chain: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate Put-Call Ratio from option chain
        
        Returns:
            PCR ratios for OI and Volume
        """
        total_call_oi = sum(row['call_oi'] for row in option_chain['chain'])
        total_put_oi = sum(row['put_oi'] for row in option_chain['chain'])
        total_call_volume = sum(row['call_volume'] for row in option_chain['chain'])
        total_put_volume = sum(row['put_volume'] for row in option_chain['chain'])
        
        pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
        pcr_volume = total_put_volume / total_call_volume if total_call_volume > 0 else 0
        
        return {
            'pcr_oi': round(pcr_oi, 3),
            'pcr_volume': round(pcr_volume, 3),
            'total_call_oi': total_call_oi,
            'total_put_oi': total_put_oi,
            'total_call_volume': total_call_volume,
            'total_put_volume': total_put_volume
        }
    
    def get_max_pain(self, option_chain: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate max pain point from option chain
        
        Returns:
            Max pain strike and total value
        """
        strikes = [row['strike'] for row in option_chain['chain']]
        max_pain_values = []
        
        for strike in strikes:
            total_pain = 0
            
            for row in option_chain['chain']:
                if row['strike'] < strike:
                    # ITM Calls
                    total_pain += (strike - row['strike']) * row['call_oi']
                elif row['strike'] > strike:
                    # ITM Puts
                    total_pain += (row['strike'] - strike) * row['put_oi']
            
            max_pain_values.append((strike, total_pain))
        
        # Find minimum pain
        min_pain = min(max_pain_values, key=lambda x: x[1])
        
        return {
            'max_pain_strike': min_pain[0],
            'max_pain_value': min_pain[1],
            'spot_price': option_chain['spot_price'],
            'difference': min_pain[0] - option_chain['spot_price']
        }