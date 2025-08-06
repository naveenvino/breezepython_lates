"""
Price Calculator Service Implementation
Concrete implementation of IPriceCalculator for option pricing
"""
import logging
import math
from decimal import Decimal
from typing import Optional, Dict, Any

from ...domain.services.iprice_calculator import IPriceCalculator
from ...domain.entities.option import Option, OptionType

logger = logging.getLogger(__name__)


class BlackScholesPriceCalculator(IPriceCalculator):
    """Black-Scholes implementation of option price calculator"""
    
    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Cumulative distribution function for standard normal distribution"""
        # Using approximation for normal CDF
        # Abramowitz and Stegun approximation
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911
        
        # Save the sign of x
        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2.0)
        
        # A&S formula 7.1.26
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
        
        return 0.5 * (1.0 + sign * y)
    
    @staticmethod
    def _normal_pdf(x: float) -> float:
        """Probability density function for standard normal distribution"""
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
    
    def calculate_option_price(
        self,
        spot_price: Decimal,
        strike_price: Decimal,
        time_to_expiry: Decimal,  # in years
        volatility: Decimal,  # annualized
        risk_free_rate: Decimal,
        is_call: bool,
        dividend_yield: Decimal = Decimal('0')
    ) -> Decimal:
        """Calculate option price using Black-Scholes model"""
        try:
            # Convert to float for calculation
            S = float(spot_price)
            K = float(strike_price)
            T = float(time_to_expiry)
            sigma = float(volatility)
            r = float(risk_free_rate)
            q = float(dividend_yield)
            
            # Avoid division by zero
            if T <= 0:
                # Option expired or invalid time
                intrinsic_value = max(0, S - K) if is_call else max(0, K - S)
                return Decimal(str(intrinsic_value))
            
            if sigma <= 0:
                # No volatility, return intrinsic value
                intrinsic_value = max(0, S - K) if is_call else max(0, K - S)
                return Decimal(str(intrinsic_value))
            
            # Calculate d1 and d2
            d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            
            # Calculate option price
            if is_call:
                price = S * math.exp(-q * T) * self._normal_cdf(d1) - K * math.exp(-r * T) * self._normal_cdf(d2)
            else:
                price = K * math.exp(-r * T) * self._normal_cdf(-d2) - S * math.exp(-q * T) * self._normal_cdf(-d1)
            
            return Decimal(str(max(0, price)))
            
        except Exception as e:
            logger.error(f"Error calculating option price: {e}")
            # Return intrinsic value as fallback
            intrinsic = self.calculate_intrinsic_value(spot_price, strike_price, is_call)
            return intrinsic
    
    def calculate_implied_volatility(
        self,
        option_price: Decimal,
        spot_price: Decimal,
        strike_price: Decimal,
        time_to_expiry: Decimal,
        risk_free_rate: Decimal,
        is_call: bool,
        dividend_yield: Decimal = Decimal('0')
    ) -> Decimal:
        """Calculate implied volatility using bisection method"""
        try:
            # Convert to float
            market_price = float(option_price)
            S = float(spot_price)
            K = float(strike_price)
            T = float(time_to_expiry)
            
            # Check for invalid inputs
            if T <= 0 or market_price <= 0:
                return Decimal('0')
            
            # Bisection method parameters
            sigma_low = 0.001  # 0.1%
            sigma_high = 5.0   # 500%
            tolerance = 0.0001
            max_iterations = 100
            
            # Check if market price is within theoretical bounds
            intrinsic = max(0, S - K) if is_call else max(0, K - S)
            if market_price < intrinsic:
                return Decimal('0')
            
            for i in range(max_iterations):
                sigma_mid = (sigma_low + sigma_high) / 2
                
                # Calculate option price with mid volatility
                price_mid = float(self.calculate_option_price(
                    spot_price, strike_price, time_to_expiry,
                    Decimal(str(sigma_mid)), risk_free_rate, is_call, dividend_yield
                ))
                
                # Check convergence
                if abs(price_mid - market_price) < tolerance:
                    return Decimal(str(sigma_mid))
                
                # Update bounds
                if price_mid < market_price:
                    sigma_low = sigma_mid
                else:
                    sigma_high = sigma_mid
                
                # Check if bounds are too close
                if sigma_high - sigma_low < tolerance:
                    return Decimal(str(sigma_mid))
            
            # Return mid-point if not converged
            return Decimal(str((sigma_low + sigma_high) / 2))
            
        except Exception as e:
            logger.error(f"Error calculating implied volatility: {e}")
            return Decimal('0.3')  # Return default 30% volatility
    
    def calculate_greeks(
        self,
        spot_price: Decimal,
        strike_price: Decimal,
        time_to_expiry: Decimal,
        volatility: Decimal,
        risk_free_rate: Decimal,
        is_call: bool,
        dividend_yield: Decimal = Decimal('0')
    ) -> Dict[str, Decimal]:
        """Calculate all Greeks for an option"""
        try:
            # Convert to float
            S = float(spot_price)
            K = float(strike_price)
            T = float(time_to_expiry)
            sigma = float(volatility)
            r = float(risk_free_rate)
            q = float(dividend_yield)
            
            # Handle edge cases
            if T <= 0:
                # Expired option
                return {
                    'delta': Decimal('1') if (is_call and S > K) else Decimal('0'),
                    'gamma': Decimal('0'),
                    'theta': Decimal('0'),
                    'vega': Decimal('0'),
                    'rho': Decimal('0')
                }
            
            if sigma <= 0:
                # No volatility
                return {
                    'delta': Decimal('1') if (is_call and S > K) else Decimal('0'),
                    'gamma': Decimal('0'),
                    'theta': Decimal('0'),
                    'vega': Decimal('0'),
                    'rho': Decimal('0')
                }
            
            # Calculate d1 and d2
            d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            
            # Delta
            if is_call:
                delta = math.exp(-q * T) * self._normal_cdf(d1)
            else:
                delta = -math.exp(-q * T) * self._normal_cdf(-d1)
            
            # Gamma (same for calls and puts)
            gamma = math.exp(-q * T) * self._normal_pdf(d1) / (S * sigma * math.sqrt(T))
            
            # Theta
            term1 = -S * self._normal_pdf(d1) * sigma * math.exp(-q * T) / (2 * math.sqrt(T))
            if is_call:
                term2 = -r * K * math.exp(-r * T) * self._normal_cdf(d2)
                term3 = q * S * math.exp(-q * T) * self._normal_cdf(d1)
                theta = (term1 + term2 + term3) / 365  # Convert to daily theta
            else:
                term2 = r * K * math.exp(-r * T) * self._normal_cdf(-d2)
                term3 = -q * S * math.exp(-q * T) * self._normal_cdf(-d1)
                theta = (term1 + term2 + term3) / 365
            
            # Vega (same for calls and puts)
            vega = S * math.exp(-q * T) * self._normal_pdf(d1) * math.sqrt(T) / 100  # Per 1% change
            
            # Rho
            if is_call:
                rho = K * T * math.exp(-r * T) * self._normal_cdf(d2) / 100  # Per 1% change
            else:
                rho = -K * T * math.exp(-r * T) * self._normal_cdf(-d2) / 100
            
            return {
                'delta': Decimal(str(delta)),
                'gamma': Decimal(str(gamma)),
                'theta': Decimal(str(theta)),
                'vega': Decimal(str(vega)),
                'rho': Decimal(str(rho))
            }
            
        except Exception as e:
            logger.error(f"Error calculating Greeks: {e}")
            return {
                'delta': Decimal('0'),
                'gamma': Decimal('0'),
                'theta': Decimal('0'),
                'vega': Decimal('0'),
                'rho': Decimal('0')
            }
    
    def calculate_intrinsic_value(
        self,
        spot_price: Decimal,
        strike_price: Decimal,
        is_call: bool
    ) -> Decimal:
        """Calculate intrinsic value of option"""
        if is_call:
            return max(Decimal('0'), spot_price - strike_price)
        else:
            return max(Decimal('0'), strike_price - spot_price)
    
    def calculate_time_value(
        self,
        option_price: Decimal,
        intrinsic_value: Decimal
    ) -> Decimal:
        """Calculate time value of option"""
        return max(Decimal('0'), option_price - intrinsic_value)
    
    def calculate_breakeven_price(
        self,
        strike_price: Decimal,
        premium: Decimal,
        is_call: bool
    ) -> Decimal:
        """Calculate breakeven price for option"""
        if is_call:
            return strike_price + premium
        else:
            return strike_price - premium
    
    def calculate_profit_loss(
        self,
        spot_price: Decimal,
        strike_price: Decimal,
        premium: Decimal,
        is_call: bool,
        is_long: bool,
        quantity: int = 1
    ) -> Decimal:
        """Calculate profit/loss at given spot price"""
        intrinsic = self.calculate_intrinsic_value(spot_price, strike_price, is_call)
        
        if is_long:
            # Long position: profit = intrinsic value - premium paid
            pnl = (intrinsic - premium) * quantity
        else:
            # Short position: profit = premium received - intrinsic value
            pnl = (premium - intrinsic) * quantity
        
        return pnl
    
    def calculate_margin_requirement(
        self,
        option: Option,
        spot_price: Decimal,
        lot_size: int
    ) -> Decimal:
        """Calculate margin requirement for option position"""
        # Simplified margin calculation
        # In practice, this would use exchange-specific rules
        
        if option.option_type == OptionType.CALL:
            # For call options
            margin = spot_price * Decimal('0.15') * lot_size  # 15% of notional
        else:
            # For put options
            margin = option.strike_price.price * Decimal('0.15') * lot_size
        
        # Add premium for short positions
        margin += option.last_price * lot_size
        
        return margin