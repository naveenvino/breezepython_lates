"""
Fast cached option chain service for real-time updates
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
import logging

logger = logging.getLogger(__name__)

class OptionChainCacheService:
    def __init__(self):
        self.cache = {}
        self.last_update = {}
        self.cache_duration = 1  # Cache for 1 second for near real-time
        self.spot_price = 24850  # Starting price
        self.last_spot_update = datetime.now()
        
    async def get_spot_price(self) -> float:
        """Get current spot price with simulated movement"""
        now = datetime.now()
        if (now - self.last_spot_update).total_seconds() > 1:
            # Simulate small price movements
            change = random.uniform(-5, 5)
            self.spot_price += change
            self.spot_price = round(self.spot_price, 2)
            self.last_spot_update = now
        return self.spot_price
    
    async def get_option_chain(self, symbol: str = "NIFTY", expiry: str = None, strikes: int = 20) -> Dict:
        """Get option chain data with caching"""
        cache_key = f"{symbol}_{expiry}_{strikes}"
        now = datetime.now()
        
        # Check cache
        if cache_key in self.cache and cache_key in self.last_update:
            if (now - self.last_update[cache_key]).total_seconds() < self.cache_duration:
                return self.cache[cache_key]
        
        # Generate fresh data
        data = await self._generate_option_chain(symbol, expiry, strikes)
        
        # Update cache
        self.cache[cache_key] = data
        self.last_update[cache_key] = now
        
        return data
    
    async def _generate_option_chain(self, symbol: str, expiry: str, strikes: int) -> Dict:
        """Generate option chain data"""
        spot_price = await self.get_spot_price()
        atm_strike = round(spot_price / 50) * 50  # Round to nearest 50
        
        # Generate strikes
        strike_list = []
        for i in range(-strikes//2, strikes//2 + 1):
            strike_list.append(atm_strike + (i * 50))
        
        # Generate option data
        chain = []
        total_call_oi = 0
        total_put_oi = 0
        max_pain_data = {}
        
        for strike in strike_list:
            # Calculate moneyness
            if strike == atm_strike:
                moneyness = "ATM"
            elif strike < spot_price:
                moneyness = "ITM"  # ITM for calls
            else:
                moneyness = "OTM"  # OTM for calls
            
            # Generate realistic premiums based on moneyness
            intrinsic_ce = max(spot_price - strike, 0)
            intrinsic_pe = max(strike - spot_price, 0)
            
            # Time value decreases as we move away from ATM
            distance_from_atm = abs(strike - atm_strike)
            time_value = max(50 - distance_from_atm * 0.3, 5)
            
            # Add some randomness for realism
            ce_premium = intrinsic_ce + time_value + random.uniform(-2, 2)
            pe_premium = intrinsic_pe + time_value + random.uniform(-2, 2)
            
            # Generate volume and OI
            oi_multiplier = max(100 - distance_from_atm // 50, 10)
            call_oi = int(1000 * oi_multiplier + random.uniform(-500, 500))
            put_oi = int(1000 * oi_multiplier + random.uniform(-500, 500))
            call_volume = int(call_oi * 0.3 + random.uniform(-100, 100))
            put_volume = int(put_oi * 0.3 + random.uniform(-100, 100))
            
            # Calculate IV (higher for OTM options)
            base_iv = 0.15  # 15% base IV
            iv_adjustment = distance_from_atm * 0.00002
            call_iv = base_iv + iv_adjustment + random.uniform(-0.01, 0.01)
            put_iv = base_iv + iv_adjustment + random.uniform(-0.01, 0.01)
            
            # Greeks (simplified calculations)
            call_delta = max(0.9 - distance_from_atm * 0.002, 0.05) if strike <= spot_price else max(0.5 - distance_from_atm * 0.002, 0.05)
            put_delta = -max(0.9 - distance_from_atm * 0.002, 0.05) if strike >= spot_price else -max(0.5 - distance_from_atm * 0.002, 0.05)
            
            gamma = 0.001 * max(1 - distance_from_atm / 1000, 0.1)
            theta = -(ce_premium * 0.02)  # Simplified theta
            vega = ce_premium * 0.1  # Simplified vega
            
            # Bid-Ask spread
            spread = max(1, ce_premium * 0.02)
            
            chain.append({
                "strike": strike,
                "moneyness": moneyness,
                "call_ltp": round(ce_premium, 2),
                "call_bid": round(ce_premium - spread/2, 2),
                "call_ask": round(ce_premium + spread/2, 2),
                "call_volume": call_volume,
                "call_oi": call_oi,
                "call_iv": call_iv,
                "call_delta": round(call_delta, 3),
                "call_gamma": round(gamma, 4),
                "call_theta": round(theta, 2),
                "call_vega": round(vega, 2),
                "put_ltp": round(pe_premium, 2),
                "put_bid": round(pe_premium - spread/2, 2),
                "put_ask": round(pe_premium + spread/2, 2),
                "put_volume": put_volume,
                "put_oi": put_oi,
                "put_iv": put_iv,
                "put_delta": round(put_delta, 3),
                "put_gamma": round(gamma, 4),
                "put_theta": round(-(pe_premium * 0.02), 2),
                "put_vega": round(pe_premium * 0.1, 2)
            })
            
            total_call_oi += call_oi
            total_put_oi += put_oi
            max_pain_data[strike] = call_oi + put_oi
        
        # Calculate max pain
        max_pain_strike = max(max_pain_data, key=max_pain_data.get)
        
        # Calculate PCR
        pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 1
        pcr_volume = sum(r["put_volume"] for r in chain) / sum(r["call_volume"] for r in chain) if sum(r["call_volume"] for r in chain) > 0 else 1
        
        # Calculate expiry
        if not expiry:
            # Get next Thursday
            today = datetime.now()
            days_ahead = 3 - today.weekday()  # Thursday is 3
            if days_ahead <= 0:
                days_ahead += 7
            expiry_date = today + timedelta(days=days_ahead)
            expiry = expiry_date.strftime("%Y-%m-%d")
        else:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d")
        
        time_to_expiry = (expiry_date - datetime.now()).days
        
        return {
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "expiry": expiry,
            "time_to_expiry": time_to_expiry,
            "chain": chain,
            "pcr": {
                "pcr_oi": round(pcr_oi, 3),
                "pcr_volume": round(pcr_volume, 3),
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi
            },
            "max_pain": {
                "max_pain_strike": max_pain_strike,
                "difference": max_pain_strike - spot_price
            },
            "timestamp": datetime.now().isoformat(),
            "source": "cache"
        }

# Singleton instance
_cache_service = None

def get_option_chain_cache() -> OptionChainCacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = OptionChainCacheService()
    return _cache_service