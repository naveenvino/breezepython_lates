"""
Asynchronous Option Pricing Service
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict

from ..database.models import OptionsHistoricalData
from .data_collection_service_async import AsyncDataCollectionService


logger = logging.getLogger(__name__)


class AsyncOptionPricingService:
    """
    Asynchronous service for option pricing and strike selection
    """
    
    def __init__(self, data_collection_service: AsyncDataCollectionService, db_manager=None, lot_size: int = 75):
        self.data_collection = data_collection_service
        self.db_manager = db_manager
        self.lot_size = lot_size
    
    def calculate_atm_strike(self, spot_price: float, strike_interval: int = 50) -> int:
        return int(round(spot_price / strike_interval) * strike_interval)
    
    def get_option_strikes_for_signal(self, spot_price: float, signal_type: str, hedge_offset: int = 500) -> Tuple[int, int]:
        atm_strike = self.calculate_atm_strike(spot_price)
        
        if signal_type in ['S1', 'S2', 'S4', 'S7']:
            main_strike = atm_strike
            hedge_strike = main_strike - hedge_offset
        else:
            main_strike = atm_strike
            hedge_strike = main_strike + hedge_offset
        
        return main_strike, hedge_strike
    
    def calculate_greeks(
        self,
        option_type: str,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,  # in years
        risk_free_rate: float,
        volatility: float,
        option_price: Optional[float] = None # For implied volatility
    ) -> Dict[str, float]:
        """
        Calculate option Greeks (Delta, Gamma, Theta, Vega, Rho)
        
        Args:
            option_type: 'c' for Call, 'p' for Put
            spot_price: Current underlying price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            risk_free_rate: Risk-free interest rate (e.g., 0.05 for 5%)
            volatility: Implied volatility (e.g., 0.20 for 20%)
            option_price: Optional, for calculating implied volatility
            
        Returns:
            Dictionary of Greeks
        """
        from py_vollib.black_scholes import black_scholes as bs
        from py_vollib.black_scholes.greeks.analytical import delta, gamma, theta, vega, rho
        from py_vollib.black_scholes.implied_volatility import implied_volatility as iv

        try:
            if option_price is not None:
                # Calculate implied volatility if option_price is provided
                try:
                    volatility = iv(
                        option_price,
                        spot_price,
                        strike_price,
                        time_to_expiry,
                        risk_free_rate,
                        option_type
                    )
                except Exception as e:
                    logger.warning(f"Could not calculate implied volatility: {e}. Using provided volatility.")

            if volatility <= 0:
                logger.warning("Volatility is non-positive, cannot calculate Greeks.")
                return {
                    "delta": 0.0, "gamma": 0.0, "theta": 0.0,
                    "vega": 0.0, "rho": 0.0, "implied_volatility": 0.0
                }

            return {
                "delta": delta(option_type, spot_price, strike_price, time_to_expiry, risk_free_rate, volatility),
                "gamma": gamma(option_type, spot_price, strike_price, time_to_expiry, risk_free_rate, volatility),
                "theta": theta(option_type, spot_price, strike_price, time_to_expiry, risk_free_rate, volatility),
                "vega": vega(option_type, spot_price, strike_price, time_to_expiry, risk_free_rate, volatility),
                "rho": rho(option_type, spot_price, strike_price, time_to_expiry, risk_free_rate, volatility),
                "implied_volatility": volatility
            }
        except Exception as e:
            logger.error(f"Error calculating Greeks: {e}")
            return {
                "delta": 0.0, "gamma": 0.0, "theta": 0.0,
                "vega": 0.0, "rho": 0.0, "implied_volatility": 0.0
            }
