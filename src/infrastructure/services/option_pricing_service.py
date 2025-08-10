"""
Option Pricing Service
Service for calculating option prices and managing option data
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict

from ..database.models import OptionsHistoricalData
from .data_collection_service import DataCollectionService


logger = logging.getLogger(__name__)


class OptionPricingService:
    """
    Service for option pricing and strike selection
    """
    
    def __init__(self, data_collection_service: DataCollectionService, db_manager=None, lot_size: int = 75):
        self.data_collection = data_collection_service
        self.db_manager = db_manager  # Can be None, service will handle it
        self.lot_size = lot_size  # Configurable lot size, default 75 for NIFTY
    
    def calculate_atm_strike(self, spot_price: float, strike_interval: int = 50) -> int:
        """
        Calculate At-The-Money (ATM) strike price
        
        Args:
            spot_price: Current NIFTY spot price
            strike_interval: Strike interval (default 50 for NIFTY)
            
        Returns:
            ATM strike price
        """
        return int(round(spot_price / strike_interval) * strike_interval)
    
    def get_option_strikes_for_signal(
        self, 
        spot_price: float,
        signal_type: str,
        hedge_offset: int = 500
    ) -> Tuple[int, int]:
        """
        Get main and hedge strikes for a signal
        
        Args:
            spot_price: Current NIFTY spot price
            signal_type: Signal type (S1-S8)
            hedge_offset: Points away from main strike for hedge
            
        Returns:
            Tuple of (main_strike, hedge_strike)
        """
        atm_strike = self.calculate_atm_strike(spot_price)
        
        # Determine strikes based on signal type
        if signal_type in ['S1', 'S2', 'S4', 'S7']:  # Bullish signals
            # Sell PUT at or below ATM
            main_strike = atm_strike
            # Buy PUT further OTM for hedge
            hedge_strike = main_strike - hedge_offset
        else:  # Bearish signals (S3, S5, S6, S8)
            # Sell CALL at or above ATM
            main_strike = atm_strike
            # Buy CALL further OTM for hedge
            hedge_strike = main_strike + hedge_offset
        
        return main_strike, hedge_strike
    
    async def get_option_price_at_time(
        self,
        timestamp: datetime,
        strike: int,
        option_type: str,
        expiry: datetime
    ) -> Optional[float]:
        """
        Get option price at specific timestamp from database
        
        Returns:
            Option price or None if not found
        """
        option_data = await self.data_collection.get_option_data(
            timestamp, strike, option_type, expiry
        )
        
        if option_data:
            # Use mid price between bid and ask if available
            if option_data.bid_price and option_data.ask_price:
                return float((option_data.bid_price + option_data.ask_price) / 2)
            elif option_data.last_price:
                return float(option_data.last_price)
            else:
                logger.warning(f"Option data found but no price available for {strike} {option_type} at {timestamp}")
                return None
        
        # No data found
        logger.warning(f"No option data found for {strike} {option_type} at {timestamp}")
        return None
    
    def calculate_option_payoff(
        self,
        option_type: str,
        strike: int,
        spot_at_expiry: float,
        premium: float,
        quantity: int,  # Negative for sell
        commission: float = 40
    ) -> float:
        """
        Calculate option P&L at expiry
        
        Args:
            option_type: 'CE' or 'PE'
            strike: Strike price
            spot_at_expiry: NIFTY price at expiry
            premium: Premium paid/received per unit
            quantity: Quantity (negative for sell)
            commission: Commission per lot
            
        Returns:
            Net P&L including commission
        """
        # Calculate intrinsic value at expiry
        if option_type == 'CE':
            intrinsic_value = max(0, spot_at_expiry - strike)
        else:  # PE
            intrinsic_value = max(0, strike - spot_at_expiry)
        
        # P&L calculation
        if quantity < 0:  # Sold option
            # Received premium, pay intrinsic value if ITM
            pnl = abs(quantity) * (premium - intrinsic_value)
        else:  # Bought option
            # Paid premium, receive intrinsic value if ITM
            pnl = quantity * (intrinsic_value - premium)
        
        # Subtract commission
        lots = abs(quantity) // self.lot_size  # Use configured lot size
        total_commission = lots * commission * 2  # Entry and exit
        
        return pnl - total_commission
    
    async def get_option_chain_at_time(
        self,
        timestamp: datetime,
        expiry: datetime,
        strikes: List[int]
    ) -> dict:
        """
        Get option chain data at specific timestamp
        
        Returns:
            Dictionary with strike as key and CE/PE prices
        """
        chain = {}
        
        for strike in strikes:
            ce_price = await self.get_option_price_at_time(
                timestamp, strike, 'CE', expiry
            )
            pe_price = await self.get_option_price_at_time(
                timestamp, strike, 'PE', expiry
            )
            
            chain[strike] = {
                'CE': ce_price,
                'PE': pe_price,
                'total': (ce_price or 0) + (pe_price or 0)
            }
        
        return chain
    
    def calculate_margin_required(
        self,
        spot_price: float,
        strike: int,
        option_type: str,
        quantity: int,
        lot_size: int = None
    ) -> float:
        """
        Calculate margin required for option position
        
        Simplified calculation - actual margin varies by broker
        """
        # Use instance lot size if not provided
        if lot_size is None:
            lot_size = self.lot_size
            
        # For option selling, approximate margin requirement
        if quantity < 0:  # Selling option
            # Roughly 15% of notional value
            notional_value = abs(quantity) * spot_price
            margin = notional_value * 0.15
            
            # Add some buffer for OTM options
            moneyness = spot_price / strike if option_type == 'CE' else strike / spot_price
            if moneyness < 0.95:  # OTM
                margin *= 0.8
            
            return margin
        else:  # Buying option
            # Only premium required
            return 0  # Premium handled separately
    
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