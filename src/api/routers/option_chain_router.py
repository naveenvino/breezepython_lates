"""
Option Chain API Router
Provides endpoints for option chain data and Greeks analysis
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from src.services.option_chain_service import OptionChainService
from src.analytics.greeks_calculator import GreeksCalculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/option-chain", tags=["Option Chain"])

# Initialize services lazily
_option_chain_service = None
_greeks_calculator = None

def get_option_chain_service():
    global _option_chain_service
    if _option_chain_service is None:
        _option_chain_service = OptionChainService()
    return _option_chain_service

def get_greeks_calculator():
    global _greeks_calculator
    if _greeks_calculator is None:
        _greeks_calculator = GreeksCalculator()
    return _greeks_calculator


@router.get("/live")
async def get_live_option_chain(
    symbol: str = Query("NIFTY", description="Index symbol (NIFTY, BANKNIFTY, FINNIFTY)"),
    expiry: Optional[str] = Query(None, description="Expiry date in YYYY-MM-DD format"),
    strikes: int = Query(20, description="Number of strikes on each side of ATM")
):
    """
    Get live option chain data with prices, OI, and volume
    
    Args:
        symbol: Index symbol
        expiry: Expiry date (optional, defaults to current expiry)
        strikes: Number of strikes to fetch on each side of ATM
    """
    try:
        # Validate symbol
        valid_symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCAPNIFTY', 'SENSEX', 'BANKEX']
        if symbol.upper() not in valid_symbols:
            raise HTTPException(status_code=400, detail=f"Invalid symbol. Must be one of {valid_symbols}")
        
        # Fetch option chain
        option_chain = get_option_chain_service().fetch_option_chain(
            symbol=symbol.upper(),
            expiry_date=expiry,
            strike_count=strikes
        )
        
        # Add PCR ratio
        pcr = get_option_chain_service().get_pcr_ratio(option_chain)
        option_chain['pcr'] = pcr
        
        # Add max pain
        max_pain = get_option_chain_service().get_max_pain(option_chain)
        option_chain['max_pain'] = max_pain
        
        return {
            "status": "success",
            "data": option_chain
        }
        
    except Exception as e:
        logger.error(f"Failed to get option chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/greeks")
async def get_option_chain_with_greeks(
    symbol: str = Query("NIFTY", description="Index symbol"),
    expiry: Optional[str] = Query(None, description="Expiry date in YYYY-MM-DD format"),
    strikes: int = Query(20, description="Number of strikes on each side of ATM")
):
    """
    Get option chain with calculated Greeks for all strikes
    """
    try:
        # Fetch option chain
        option_chain = get_option_chain_service().fetch_option_chain(
            symbol=symbol.upper(),
            expiry_date=expiry,
            strike_count=strikes
        )
        
        # Calculate Greeks
        option_chain_with_greeks = get_option_chain_service().calculate_option_chain_greeks(option_chain)
        
        # Add analytics
        pcr = get_option_chain_service().get_pcr_ratio(option_chain_with_greeks)
        option_chain_with_greeks['pcr'] = pcr
        
        max_pain = get_option_chain_service().get_max_pain(option_chain_with_greeks)
        option_chain_with_greeks['max_pain'] = max_pain
        
        return {
            "status": "success",
            "data": option_chain_with_greeks
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate Greeks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oi-analysis")
async def get_oi_analysis(
    symbol: str = Query("NIFTY", description="Index symbol"),
    expiry: Optional[str] = Query(None, description="Expiry date")
):
    """
    Get Open Interest analysis including build-up and changes
    """
    try:
        # Fetch option chain
        option_chain = get_option_chain_service().fetch_option_chain(
            symbol=symbol.upper(),
            expiry_date=expiry,
            strike_count=30
        )
        
        # Analyze OI
        analysis = {
            "symbol": symbol,
            "spot_price": option_chain['spot_price'],
            "timestamp": option_chain['timestamp'],
            "pcr": get_option_chain_service().get_pcr_ratio(option_chain),
            "max_pain": get_option_chain_service().get_max_pain(option_chain)
        }
        
        # Find highest OI strikes
        chain_data = option_chain['chain']
        
        # Sort by call OI
        call_oi_sorted = sorted(chain_data, key=lambda x: x['call_oi'], reverse=True)[:5]
        analysis['highest_call_oi'] = [
            {'strike': row['strike'], 'oi': row['call_oi'], 'ltp': row['call_ltp']}
            for row in call_oi_sorted
        ]
        
        # Sort by put OI
        put_oi_sorted = sorted(chain_data, key=lambda x: x['put_oi'], reverse=True)[:5]
        analysis['highest_put_oi'] = [
            {'strike': row['strike'], 'oi': row['put_oi'], 'ltp': row['put_ltp']}
            for row in put_oi_sorted
        ]
        
        # Support and resistance levels
        analysis['support_levels'] = [row['strike'] for row in put_oi_sorted[:3]]
        analysis['resistance_levels'] = [row['strike'] for row in call_oi_sorted[:3]]
        
        return {
            "status": "success",
            "data": analysis
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze OI: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iv-skew")
async def get_iv_skew(
    symbol: str = Query("NIFTY", description="Index symbol"),
    expiry: Optional[str] = Query(None, description="Expiry date")
):
    """
    Get Implied Volatility skew across strikes
    """
    try:
        # Fetch option chain
        option_chain = get_option_chain_service().fetch_option_chain(
            symbol=symbol.upper(),
            expiry_date=expiry,
            strike_count=20
        )
        
        # Extract IV data
        iv_data = {
            "symbol": symbol,
            "spot_price": option_chain['spot_price'],
            "atm_strike": option_chain['atm_strike'],
            "timestamp": option_chain['timestamp'],
            "call_iv": [],
            "put_iv": []
        }
        
        for row in option_chain['chain']:
            if row['call_iv'] > 0:
                iv_data['call_iv'].append({
                    'strike': row['strike'],
                    'iv': row['call_iv'],
                    'moneyness': row['moneyness']
                })
            
            if row['put_iv'] > 0:
                iv_data['put_iv'].append({
                    'strike': row['strike'],
                    'iv': row['put_iv'],
                    'moneyness': row['moneyness']
                })
        
        # Calculate skew metrics
        call_ivs = [x['iv'] for x in iv_data['call_iv']]
        put_ivs = [x['iv'] for x in iv_data['put_iv']]
        
        iv_data['metrics'] = {
            'call_iv_mean': round(sum(call_ivs) / len(call_ivs), 4) if call_ivs else 0,
            'put_iv_mean': round(sum(put_ivs) / len(put_ivs), 4) if put_ivs else 0,
            'call_iv_min': min(call_ivs) if call_ivs else 0,
            'call_iv_max': max(call_ivs) if call_ivs else 0,
            'put_iv_min': min(put_ivs) if put_ivs else 0,
            'put_iv_max': max(put_ivs) if put_ivs else 0
        }
        
        return {
            "status": "success",
            "data": iv_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get IV skew: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calculate-greeks")
async def calculate_single_option_greeks(
    spot: float = Query(..., description="Current spot price"),
    strike: float = Query(..., description="Strike price"),
    time_to_expiry: float = Query(..., description="Time to expiry in days"),
    volatility: float = Query(0.15, description="Implied volatility (e.g., 0.15 for 15%)"),
    option_type: str = Query("CALL", description="Option type (CALL or PUT)"),
    risk_free_rate: float = Query(0.06, description="Risk-free rate"),
    option_price: Optional[float] = Query(None, description="Market price for IV calculation")
):
    """
    Calculate Greeks for a single option
    """
    try:
        # Convert time to expiry from days to years
        time_to_expiry_years = time_to_expiry / 365
        
        # Calculate Greeks
        greeks = get_greeks_calculator().calculate_all_greeks(
            spot=spot,
            strike=strike,
            time_to_expiry=time_to_expiry_years,
            volatility=volatility,
            option_type=option_type.upper(),
            option_price=option_price
        )
        
        # Add moneyness
        greeks['moneyness'] = get_greeks_calculator().get_moneyness(spot, strike, option_type)
        
        # Calculate IV if market price is provided
        if option_price:
            try:
                iv = get_greeks_calculator().calculate_implied_volatility(
                    spot=spot,
                    strike=strike,
                    time_to_expiry=time_to_expiry_years,
                    option_price=option_price,
                    option_type=option_type.upper()
                )
                greeks['implied_volatility'] = round(iv, 4)
            except:
                greeks['implied_volatility'] = None
        
        return {
            "status": "success",
            "data": greeks
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate Greeks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expiry-dates")
async def get_expiry_dates():
    """
    Get available expiry dates
    """
    try:
        current_expiry = get_option_chain_service().get_current_expiry()
        next_expiry = get_option_chain_service().get_next_expiry()
        monthly_expiry = get_option_chain_service().get_monthly_expiry()
        
        return {
            "status": "success",
            "data": {
                "current_weekly": current_expiry,
                "next_weekly": next_expiry,
                "monthly": monthly_expiry,
                "all": [current_expiry, next_expiry, monthly_expiry]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get expiry dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strike-selection")
async def get_strike_selection(
    symbol: str = Query("NIFTY", description="Index symbol"),
    signal_type: str = Query(..., description="Signal type (S1-S8)"),
    expiry: Optional[str] = Query(None, description="Expiry date")
):
    """
    Get recommended strikes based on signal type and current market conditions
    """
    try:
        # Fetch option chain
        option_chain = get_option_chain_service().fetch_option_chain(
            symbol=symbol.upper(),
            expiry_date=expiry,
            strike_count=10
        )
        
        spot_price = option_chain['spot_price']
        atm_strike = option_chain['atm_strike']
        
        # Signal to option type mapping
        signal_map = {
            'S1': {'type': 'PUT', 'moneyness': 'ATM'},  # Bear Trap - Sell PUT
            'S2': {'type': 'PUT', 'moneyness': 'ATM'},  # Support Hold - Sell PUT
            'S3': {'type': 'CALL', 'moneyness': 'ATM'}, # Resistance Hold - Sell CALL
            'S4': {'type': 'PUT', 'moneyness': 'ATM'},  # Bias Failure Bull - Sell PUT
            'S5': {'type': 'CALL', 'moneyness': 'ATM'}, # Bias Failure Bear - Sell CALL
            'S6': {'type': 'CALL', 'moneyness': 'ATM'}, # Weakness Confirmed - Sell CALL
            'S7': {'type': 'PUT', 'moneyness': 'ATM'},  # Breakout Confirmed - Sell PUT
            'S8': {'type': 'CALL', 'moneyness': 'ATM'}, # Breakdown Confirmed - Sell CALL
        }
        
        signal_config = signal_map.get(signal_type.upper())
        if not signal_config:
            raise HTTPException(status_code=400, detail="Invalid signal type")
        
        # Find recommended strikes
        recommended_strikes = []
        
        for row in option_chain['chain']:
            if row['moneyness'] == signal_config['moneyness']:
                option_key = f"{signal_config['type'].lower()}_ltp"
                recommended_strikes.append({
                    'strike': row['strike'],
                    'option_type': signal_config['type'],
                    'premium': row[option_key],
                    'oi': row[f"{signal_config['type'].lower()}_oi"],
                    'volume': row[f"{signal_config['type'].lower()}_volume"],
                    'moneyness': row['moneyness'],
                    'distance_from_spot': abs(row['strike'] - spot_price)
                })
        
        # Sort by distance from spot
        recommended_strikes.sort(key=lambda x: x['distance_from_spot'])
        
        return {
            "status": "success",
            "data": {
                "signal_type": signal_type,
                "spot_price": spot_price,
                "atm_strike": atm_strike,
                "recommended_option_type": signal_config['type'],
                "recommended_strikes": recommended_strikes[:3]  # Top 3 recommendations
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get strike selection: {e}")
        raise HTTPException(status_code=500, detail=str(e))