"""
Signal to Kite Order Converter
Converts trading signals from the signal evaluator to Kite-compatible orders
"""
import logging
from typing import Dict, Tuple, Optional
from datetime import date, datetime, timedelta
from src.domain.value_objects.signal_types import SignalResult, TradeDirection
from src.infrastructure.services.holiday_service import HolidayService

logger = logging.getLogger(__name__)

class SignalToKiteOrderConverter:
    """
    Converts backtest signals to live Kite orders
    """
    
    def __init__(self, kite_client, holiday_service: Optional[HolidayService] = None):
        self.kite_client = kite_client
        self.holiday_service = holiday_service or HolidayService()
        self.strike_interval = 50  # NIFTY strikes are 50 points apart
        self.hedge_offset = 200    # Default hedge offset in points
        
    def convert_signal_to_order_params(self, 
                                     signal: SignalResult, 
                                     current_spot: float,
                                     use_hedging: bool = True) -> Dict[str, any]:
        """
        Convert a signal to Kite order parameters
        
        Args:
            signal: Signal result from evaluator
            current_spot: Current NIFTY spot price
            use_hedging: Whether to include hedge position
            
        Returns:
            Dictionary with order parameters
        """
        if signal.signal_type == "NO_SIGNAL":
            return {}
        
        # Determine option type based on signal direction
        option_type = self._get_option_type(signal)
        
        # Calculate strikes
        main_strike = self._calculate_atm_strike(current_spot)
        
        # Get expiry date (next Thursday or Wednesday if holiday)
        expiry_date = self._get_next_expiry()
        
        # Generate symbols
        main_symbol = self.kite_client.get_option_symbol(expiry_date, main_strike, option_type)
        
        order_params = {
            'signal_type': signal.signal_type,
            'direction': signal.direction,
            'main_position': {
                'symbol': main_symbol,
                'strike': main_strike,
                'option_type': option_type,
                'transaction_type': 'SELL',  # We sell options for premium
                'expiry': expiry_date
            }
        }
        
        if use_hedging:
            # Calculate hedge strike based on direction
            if signal.direction == TradeDirection.BEARISH:
                # For bearish (CALL selling), hedge is higher strike
                hedge_strike = main_strike + self.hedge_offset
            else:
                # For bullish (PUT selling), hedge is lower strike
                hedge_strike = main_strike - self.hedge_offset
            
            hedge_symbol = self.kite_client.get_option_symbol(expiry_date, hedge_strike, option_type)
            
            order_params['hedge_position'] = {
                'symbol': hedge_symbol,
                'strike': hedge_strike,
                'option_type': option_type,
                'transaction_type': 'BUY',  # Buy for protection
                'expiry': expiry_date
            }
        
        return order_params
    
    def _get_option_type(self, signal: SignalResult) -> str:
        """
        Determine option type (CE/PE) based on signal
        
        Bearish signals (S3, S5, S6, S8) → Sell CALL
        Bullish signals (S1, S2, S4, S7) → Sell PUT
        """
        bearish_signals = ['S3', 'S5', 'S6', 'S8']
        return 'CE' if signal.signal_type in bearish_signals else 'PE'
    
    def _calculate_atm_strike(self, spot_price: float) -> int:
        """
        Calculate at-the-money strike price
        Rounds to nearest strike interval
        """
        return int(round(spot_price / self.strike_interval)) * self.strike_interval
    
    def _get_next_expiry(self) -> date:
        """
        Get next weekly expiry date
        NIFTY weekly options expire on Thursday (or Wednesday if Thursday is holiday)
        """
        today = datetime.now().date()
        
        # Find next Thursday
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0 and datetime.now().time() > datetime.strptime("15:30", "%H:%M").time():
            # If today is Thursday after 3:30 PM, get next Thursday
            days_until_thursday = 7
        
        next_thursday = today + timedelta(days=days_until_thursday)
        
        # Check if Thursday is a holiday
        if self.holiday_service.is_holiday(next_thursday):
            # If Thursday is holiday, expiry is on Wednesday
            next_thursday -= timedelta(days=1)
            
            # Double check Wednesday is not a holiday
            if self.holiday_service.is_holiday(next_thursday):
                logger.warning(f"Both Thursday and Wednesday are holidays for week of {next_thursday}")
        
        return next_thursday
    
    def calculate_strikes_for_spot(self, spot_price: float, signal_type: str) -> Dict[str, int]:
        """
        Calculate main and hedge strikes for given spot price
        
        Args:
            spot_price: Current NIFTY spot price
            signal_type: Signal type (S1-S8)
            
        Returns:
            Dictionary with 'main_strike' and 'hedge_strike'
        """
        main_strike = self._calculate_atm_strike(spot_price)
        
        # Determine if bearish or bullish signal
        bearish_signals = ['S3', 'S5', 'S6', 'S8']
        is_bearish = signal_type in bearish_signals
        
        # Calculate hedge strike
        if is_bearish:
            hedge_strike = main_strike + self.hedge_offset
        else:
            hedge_strike = main_strike - self.hedge_offset
        
        return {
            'main_strike': main_strike,
            'hedge_strike': hedge_strike
        }
    
    def get_stop_loss_price(self, main_strike: int, option_type: str) -> float:
        """
        Calculate stop loss price
        For our strategy, stop loss is when option reaches the main strike price
        """
        # In our strategy, we exit if the option goes in-the-money
        # So stop loss is essentially the strike price
        return float(main_strike)
    
    def validate_order_params(self, order_params: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate order parameters before placing order
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not order_params:
            return False, "No order parameters provided"
        
        if 'main_position' not in order_params:
            return False, "Main position missing"
        
        main_pos = order_params['main_position']
        
        # Validate main position
        required_fields = ['symbol', 'strike', 'option_type', 'transaction_type']
        for field in required_fields:
            if field not in main_pos:
                return False, f"Main position missing {field}"
        
        # Validate option type
        if main_pos['option_type'] not in ['CE', 'PE']:
            return False, f"Invalid option type: {main_pos['option_type']}"
        
        # Validate transaction type
        if main_pos['transaction_type'] != 'SELL':
            return False, "Main position must be SELL"
        
        # Validate hedge if present
        if 'hedge_position' in order_params:
            hedge_pos = order_params['hedge_position']
            
            for field in required_fields:
                if field not in hedge_pos:
                    return False, f"Hedge position missing {field}"
            
            if hedge_pos['transaction_type'] != 'BUY':
                return False, "Hedge position must be BUY"
            
            if hedge_pos['option_type'] != main_pos['option_type']:
                return False, "Hedge must be same option type as main"
        
        return True, None