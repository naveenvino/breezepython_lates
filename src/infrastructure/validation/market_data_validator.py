"""
Market Data Validator
Validates market data for reasonableness, integrity, and staleness
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict
from decimal import Decimal
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation check"""
    is_valid: bool
    error_message: Optional[str] = None
    warning_message: Optional[str] = None
    confidence_score: float = 1.0  # 0-1, 1 being highest confidence


class MarketDataValidator:
    """
    Validate market data for trading decisions
    """
    
    def __init__(
        self,
        max_staleness_minutes: int = 5,
        max_price_change_percent: float = 10.0,
        max_spread_percent: float = 5.0,
        min_volume: int = 100
    ):
        self.max_staleness_minutes = max_staleness_minutes
        self.max_price_change_percent = max_price_change_percent
        self.max_spread_percent = max_spread_percent
        self.min_volume = min_volume
        
        # NIFTY specific limits
        self.nifty_daily_limit_percent = 20.0  # Circuit breaker
        self.option_max_spread_points = 50  # Max bid-ask spread in points
        
    def validate_nifty_data(
        self,
        timestamp: datetime,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: int,
        prev_close: Optional[float] = None
    ) -> ValidationResult:
        """Validate NIFTY index data"""
        
        # Check data staleness
        staleness_result = self._check_staleness(timestamp)
        if not staleness_result.is_valid:
            return staleness_result
            
        # Check OHLC consistency
        ohlc_result = self._validate_ohlc(open_price, high_price, low_price, close_price)
        if not ohlc_result.is_valid:
            return ohlc_result
            
        # Check price ranges
        if high_price - low_price > (high_price * 0.05):  # 5% intraday range
            logger.warning(f"Large intraday range: {(high_price-low_price)/high_price*100:.2f}%")
            
        # Check against previous close if available
        if prev_close:
            change_percent = abs((close_price - prev_close) / prev_close * 100)
            if change_percent > self.nifty_daily_limit_percent:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Price change {change_percent:.2f}% exceeds circuit limit"
                )
            elif change_percent > self.max_price_change_percent:
                return ValidationResult(
                    is_valid=True,
                    warning_message=f"Large price change: {change_percent:.2f}%",
                    confidence_score=0.7
                )
                
        # Check volume
        if volume < self.min_volume:
            return ValidationResult(
                is_valid=True,
                warning_message=f"Low volume: {volume}",
                confidence_score=0.8
            )
            
        return ValidationResult(is_valid=True)
        
    def validate_option_price(
        self,
        timestamp: datetime,
        strike: int,
        option_type: str,
        spot_price: float,
        option_price: float,
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None,
        volume: Optional[int] = None,
        implied_volatility: Optional[float] = None
    ) -> ValidationResult:
        """Validate option price data"""
        
        # Check staleness
        staleness_result = self._check_staleness(timestamp)
        if not staleness_result.is_valid:
            return staleness_result
            
        # Check if price is positive
        if option_price <= 0:
            return ValidationResult(
                is_valid=False,
                error_message="Option price must be positive"
            )
            
        # Check intrinsic value
        intrinsic_result = self._check_intrinsic_value(
            option_price, strike, spot_price, option_type
        )
        if not intrinsic_result.is_valid:
            return intrinsic_result
            
        # Check bid-ask spread if available
        if bid_price is not None and ask_price is not None:
            spread_result = self._check_spread(bid_price, ask_price, option_price)
            if not spread_result.is_valid:
                return spread_result
                
        # Check implied volatility if available
        if implied_volatility is not None:
            iv_result = self._check_implied_volatility(implied_volatility)
            if not iv_result.is_valid:
                return iv_result
                
        # Check time value reasonableness
        time_value_result = self._check_time_value(
            option_price, strike, spot_price, option_type
        )
        if not time_value_result.is_valid:
            return time_value_result
            
        return ValidationResult(is_valid=True)
        
    def validate_option_chain(
        self,
        timestamp: datetime,
        spot_price: float,
        option_chain: Dict[int, Dict[str, float]]
    ) -> ValidationResult:
        """Validate entire option chain for consistency"""
        
        strikes = sorted(option_chain.keys())
        if len(strikes) < 3:
            return ValidationResult(
                is_valid=False,
                error_message="Insufficient strikes in option chain"
            )
            
        # Check put-call parity for ATM options
        atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
        if atm_strike in option_chain:
            ce_price = option_chain[atm_strike].get('CE', 0)
            pe_price = option_chain[atm_strike].get('PE', 0)
            
            if ce_price > 0 and pe_price > 0:
                # Simplified put-call parity check
                parity_diff = abs(ce_price - pe_price - (spot_price - atm_strike))
                max_allowed_diff = spot_price * 0.01  # 1% of spot
                
                if parity_diff > max_allowed_diff:
                    logger.warning(f"Put-call parity violation at {atm_strike}: diff={parity_diff:.2f}")
                    
        # Check monotonicity of option prices
        for i in range(1, len(strikes)):
            curr_strike = strikes[i]
            prev_strike = strikes[i-1]
            
            # Call prices should decrease as strike increases
            if 'CE' in option_chain[curr_strike] and 'CE' in option_chain[prev_strike]:
                if option_chain[curr_strike]['CE'] > option_chain[prev_strike]['CE']:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Call price monotonicity violated at strike {curr_strike}"
                    )
                    
            # Put prices should increase as strike increases
            if 'PE' in option_chain[curr_strike] and 'PE' in option_chain[prev_strike]:
                if option_chain[curr_strike]['PE'] < option_chain[prev_strike]['PE']:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Put price monotonicity violated at strike {curr_strike}"
                    )
                    
        return ValidationResult(is_valid=True)
        
    def validate_price_sequence(
        self,
        prices: List[float],
        timestamps: List[datetime],
        max_gap_minutes: int = 15
    ) -> ValidationResult:
        """Validate sequence of prices for spikes and gaps"""
        
        if len(prices) != len(timestamps):
            return ValidationResult(
                is_valid=False,
                error_message="Price and timestamp lists must have same length"
            )
            
        if len(prices) < 2:
            return ValidationResult(is_valid=True)  # Can't validate single price
            
        for i in range(1, len(prices)):
            # Check time gap
            time_diff = timestamps[i] - timestamps[i-1]
            if time_diff > timedelta(minutes=max_gap_minutes):
                logger.warning(f"Large time gap: {time_diff} between prices")
                
            # Check price change
            if prices[i-1] > 0:  # Avoid division by zero
                price_change_percent = abs((prices[i] - prices[i-1]) / prices[i-1] * 100)
                
                if price_change_percent > self.max_price_change_percent:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Price spike detected: {price_change_percent:.2f}% change"
                    )
                elif price_change_percent > self.max_price_change_percent / 2:
                    logger.warning(f"Large price movement: {price_change_percent:.2f}%")
                    
        return ValidationResult(is_valid=True)
        
    def _check_staleness(self, timestamp: datetime) -> ValidationResult:
        """Check if data is too old"""
        age = datetime.now() - timestamp
        
        if age > timedelta(minutes=self.max_staleness_minutes):
            return ValidationResult(
                is_valid=False,
                error_message=f"Data is {age.total_seconds()/60:.1f} minutes old"
            )
        elif age > timedelta(minutes=self.max_staleness_minutes / 2):
            return ValidationResult(
                is_valid=True,
                warning_message=f"Data is {age.total_seconds()/60:.1f} minutes old",
                confidence_score=0.8
            )
            
        return ValidationResult(is_valid=True)
        
    def _validate_ohlc(
        self,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float
    ) -> ValidationResult:
        """Validate OHLC data consistency"""
        
        # All prices must be positive
        if any(p <= 0 for p in [open_price, high_price, low_price, close_price]):
            return ValidationResult(
                is_valid=False,
                error_message="All OHLC prices must be positive"
            )
            
        # High must be highest
        if high_price < max(open_price, close_price, low_price):
            return ValidationResult(
                is_valid=False,
                error_message="High price is not the highest"
            )
            
        # Low must be lowest
        if low_price > min(open_price, close_price, high_price):
            return ValidationResult(
                is_valid=False,
                error_message="Low price is not the lowest"
            )
            
        return ValidationResult(is_valid=True)
        
    def _check_intrinsic_value(
        self,
        option_price: float,
        strike: int,
        spot_price: float,
        option_type: str
    ) -> ValidationResult:
        """Check if option price is above intrinsic value"""
        
        if option_type == "CE":
            intrinsic = max(0, spot_price - strike)
        else:  # PE
            intrinsic = max(0, strike - spot_price)
            
        if option_price < intrinsic:
            return ValidationResult(
                is_valid=False,
                error_message=f"Option price {option_price:.2f} below intrinsic value {intrinsic:.2f}"
            )
            
        # Warn if price is exactly at intrinsic (might be expiry)
        if abs(option_price - intrinsic) < 0.5:
            return ValidationResult(
                is_valid=True,
                warning_message="Option trading near intrinsic value",
                confidence_score=0.9
            )
            
        return ValidationResult(is_valid=True)
        
    def _check_spread(
        self,
        bid_price: float,
        ask_price: float,
        last_price: float
    ) -> ValidationResult:
        """Check bid-ask spread reasonableness"""
        
        if bid_price >= ask_price:
            return ValidationResult(
                is_valid=False,
                error_message=f"Bid {bid_price} >= Ask {ask_price}"
            )
            
        spread = ask_price - bid_price
        mid_price = (bid_price + ask_price) / 2
        
        # Check absolute spread
        if spread > self.option_max_spread_points:
            return ValidationResult(
                is_valid=False,
                error_message=f"Spread {spread:.2f} exceeds maximum"
            )
            
        # Check relative spread
        spread_percent = (spread / mid_price) * 100 if mid_price > 0 else 0
        
        if spread_percent > self.max_spread_percent:
            return ValidationResult(
                is_valid=True,
                warning_message=f"Wide spread: {spread_percent:.2f}%",
                confidence_score=0.7
            )
            
        # Check if last price is within spread
        if last_price < bid_price or last_price > ask_price:
            logger.warning(f"Last price {last_price} outside bid-ask spread [{bid_price}, {ask_price}]")
            
        return ValidationResult(is_valid=True)
        
    def _check_implied_volatility(self, iv: float) -> ValidationResult:
        """Check if implied volatility is reasonable"""
        
        if iv <= 0 or iv > 200:  # IV as percentage
            return ValidationResult(
                is_valid=False,
                error_message=f"Implied volatility {iv}% out of reasonable range"
            )
        elif iv > 100:
            return ValidationResult(
                is_valid=True,
                warning_message=f"Very high implied volatility: {iv}%",
                confidence_score=0.7
            )
        elif iv < 5:
            return ValidationResult(
                is_valid=True,
                warning_message=f"Very low implied volatility: {iv}%",
                confidence_score=0.8
            )
            
        return ValidationResult(is_valid=True)
        
    def _check_time_value(
        self,
        option_price: float,
        strike: int,
        spot_price: float,
        option_type: str
    ) -> ValidationResult:
        """Check if time value is reasonable"""
        
        # Calculate intrinsic value
        if option_type == "CE":
            intrinsic = max(0, spot_price - strike)
        else:
            intrinsic = max(0, strike - spot_price)
            
        time_value = option_price - intrinsic
        
        # Time value should be positive
        if time_value < 0:
            return ValidationResult(
                is_valid=False,
                error_message="Negative time value"
            )
            
        # Check if time value is too high
        max_time_value = spot_price * 0.05  # 5% of spot
        
        if time_value > max_time_value:
            # More lenient for ATM options
            moneyness = abs(strike - spot_price) / spot_price
            if moneyness < 0.02:  # Within 2% of ATM
                max_time_value *= 1.5
                
            if time_value > max_time_value:
                return ValidationResult(
                    is_valid=True,
                    warning_message=f"High time value: {time_value:.2f}",
                    confidence_score=0.8
                )
                
        return ValidationResult(is_valid=True)