"""
Greeks Calculator for Options
Implements Black-Scholes model for European options Greeks calculation
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, Tuple, Optional
import math
from datetime import datetime, timedelta


class GreeksCalculator:
    """Calculate Greeks for options using Black-Scholes model"""
    
    def __init__(self, risk_free_rate: float = 0.06):
        """
        Initialize Greeks Calculator
        
        Args:
            risk_free_rate: Annual risk-free rate (default 6% for India)
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_d1_d2(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        dividend_yield: float = 0
    ) -> Tuple[float, float]:
        """
        Calculate d1 and d2 for Black-Scholes formula
        
        Args:
            spot: Current spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility (annualized)
            dividend_yield: Dividend yield (default 0)
            
        Returns:
            Tuple of (d1, d2)
        """
        if time_to_expiry <= 0:
            return 0, 0
            
        d1 = (np.log(spot / strike) + (self.risk_free_rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        return d1, d2
    
    def calculate_call_price(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        dividend_yield: float = 0
    ) -> float:
        """Calculate theoretical call option price"""
        if time_to_expiry <= 0:
            return max(spot - strike, 0)
            
        d1, d2 = self.calculate_d1_d2(spot, strike, time_to_expiry, volatility, dividend_yield)
        
        call_price = (spot * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1) - 
                     strike * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2))
        
        return call_price
    
    def calculate_put_price(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        dividend_yield: float = 0
    ) -> float:
        """Calculate theoretical put option price"""
        if time_to_expiry <= 0:
            return max(strike - spot, 0)
            
        d1, d2 = self.calculate_d1_d2(spot, strike, time_to_expiry, volatility, dividend_yield)
        
        put_price = (strike * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2) - 
                    spot * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1))
        
        return put_price
    
    def calculate_delta(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str = 'CALL',
        dividend_yield: float = 0
    ) -> float:
        """
        Calculate Delta - rate of change of option price with respect to spot price
        
        Returns:
            Delta value (between -1 and 1)
        """
        if time_to_expiry <= 0:
            if option_type.upper() == 'CALL':
                return 1 if spot > strike else 0
            else:
                return -1 if spot < strike else 0
                
        d1, _ = self.calculate_d1_d2(spot, strike, time_to_expiry, volatility, dividend_yield)
        
        if option_type.upper() == 'CALL' or option_type.upper() == 'CE':
            delta = np.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1)
        else:  # PUT
            delta = -np.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1)
        
        return delta
    
    def calculate_gamma(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        dividend_yield: float = 0
    ) -> float:
        """
        Calculate Gamma - rate of change of Delta with respect to spot price
        
        Returns:
            Gamma value (always positive)
        """
        if time_to_expiry <= 0:
            return 0
            
        d1, _ = self.calculate_d1_d2(spot, strike, time_to_expiry, volatility, dividend_yield)
        
        gamma = (np.exp(-dividend_yield * time_to_expiry) * norm.pdf(d1)) / (spot * volatility * np.sqrt(time_to_expiry))
        
        return gamma
    
    def calculate_theta(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str = 'CALL',
        dividend_yield: float = 0
    ) -> float:
        """
        Calculate Theta - rate of change of option price with respect to time
        
        Returns:
            Theta value (typically negative, in rupees per day)
        """
        if time_to_expiry <= 0:
            return 0
            
        d1, d2 = self.calculate_d1_d2(spot, strike, time_to_expiry, volatility, dividend_yield)
        
        if option_type.upper() == 'CALL' or option_type.upper() == 'CE':
            theta = (- (spot * norm.pdf(d1) * volatility * np.exp(-dividend_yield * time_to_expiry)) / (2 * np.sqrt(time_to_expiry))
                    - self.risk_free_rate * strike * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2)
                    + dividend_yield * spot * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1))
        else:  # PUT
            theta = (- (spot * norm.pdf(d1) * volatility * np.exp(-dividend_yield * time_to_expiry)) / (2 * np.sqrt(time_to_expiry))
                    + self.risk_free_rate * strike * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2)
                    - dividend_yield * spot * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1))
        
        # Convert to per day (from per year)
        theta = theta / 365
        
        return theta
    
    def calculate_vega(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        dividend_yield: float = 0
    ) -> float:
        """
        Calculate Vega - rate of change of option price with respect to volatility
        
        Returns:
            Vega value (in rupees per 1% change in volatility)
        """
        if time_to_expiry <= 0:
            return 0
            
        d1, _ = self.calculate_d1_d2(spot, strike, time_to_expiry, volatility, dividend_yield)
        
        vega = spot * np.exp(-dividend_yield * time_to_expiry) * norm.pdf(d1) * np.sqrt(time_to_expiry)
        
        # Convert to per 1% change (from per 100% change)
        vega = vega / 100
        
        return vega
    
    def calculate_rho(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str = 'CALL',
        dividend_yield: float = 0
    ) -> float:
        """
        Calculate Rho - rate of change of option price with respect to interest rate
        
        Returns:
            Rho value (in rupees per 1% change in interest rate)
        """
        if time_to_expiry <= 0:
            return 0
            
        d1, d2 = self.calculate_d1_d2(spot, strike, time_to_expiry, volatility, dividend_yield)
        
        if option_type.upper() == 'CALL' or option_type.upper() == 'CE':
            rho = strike * time_to_expiry * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2)
        else:  # PUT
            rho = -strike * time_to_expiry * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2)
        
        # Convert to per 1% change (from per 100% change)
        rho = rho / 100
        
        return rho
    
    def calculate_all_greeks(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str = 'CALL',
        dividend_yield: float = 0,
        option_price: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate all Greeks for an option
        
        Args:
            spot: Current spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility (annualized)
            option_type: 'CALL' or 'PUT'
            dividend_yield: Dividend yield (default 0)
            option_price: Market price of option (optional)
            
        Returns:
            Dictionary with all Greeks
        """
        greeks = {
            'delta': self.calculate_delta(spot, strike, time_to_expiry, volatility, option_type, dividend_yield),
            'gamma': self.calculate_gamma(spot, strike, time_to_expiry, volatility, dividend_yield),
            'theta': self.calculate_theta(spot, strike, time_to_expiry, volatility, option_type, dividend_yield),
            'vega': self.calculate_vega(spot, strike, time_to_expiry, volatility, dividend_yield),
            'rho': self.calculate_rho(spot, strike, time_to_expiry, volatility, option_type, dividend_yield)
        }
        
        # Calculate theoretical price
        if option_type.upper() in ['CALL', 'CE']:
            greeks['theoretical_price'] = self.calculate_call_price(spot, strike, time_to_expiry, volatility, dividend_yield)
        else:
            greeks['theoretical_price'] = self.calculate_put_price(spot, strike, time_to_expiry, volatility, dividend_yield)
        
        # Calculate IV if market price is provided
        if option_price is not None:
            greeks['market_price'] = option_price
            greeks['price_difference'] = option_price - greeks['theoretical_price']
            
        return greeks
    
    def calculate_implied_volatility(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        option_price: float,
        option_type: str = 'CALL',
        dividend_yield: float = 0,
        max_iterations: int = 100,
        tolerance: float = 0.0001
    ) -> float:
        """
        Calculate implied volatility using Newton-Raphson method
        
        Args:
            spot: Current spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            option_price: Market price of option
            option_type: 'CALL' or 'PUT'
            dividend_yield: Dividend yield
            max_iterations: Maximum iterations for convergence
            tolerance: Convergence tolerance
            
        Returns:
            Implied volatility
        """
        # Initial guess
        iv = 0.3  # Start with 30% volatility
        
        for i in range(max_iterations):
            if option_type.upper() in ['CALL', 'CE']:
                price = self.calculate_call_price(spot, strike, time_to_expiry, iv, dividend_yield)
            else:
                price = self.calculate_put_price(spot, strike, time_to_expiry, iv, dividend_yield)
            
            vega = self.calculate_vega(spot, strike, time_to_expiry, iv, dividend_yield) * 100
            
            price_diff = option_price - price
            
            if abs(price_diff) < tolerance:
                return iv
            
            if vega == 0:
                return iv
                
            iv = iv + price_diff / vega
            
            # Keep IV in reasonable bounds
            iv = max(0.01, min(5.0, iv))
        
        return iv
    
    def get_moneyness(self, spot: float, strike: float, option_type: str = 'CALL') -> str:
        """
        Determine if option is ITM, ATM, or OTM
        
        Returns:
            'ITM', 'ATM', or 'OTM'
        """
        threshold = spot * 0.01  # 1% threshold for ATM
        
        if option_type.upper() in ['CALL', 'CE']:
            if strike < spot - threshold:
                return 'ITM'
            elif strike > spot + threshold:
                return 'OTM'
            else:
                return 'ATM'
        else:  # PUT
            if strike > spot + threshold:
                return 'ITM'
            elif strike < spot - threshold:
                return 'OTM'
            else:
                return 'ATM'