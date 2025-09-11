"""
Hedge Selection Service - Proper percentage-based hedge selection
"""
import logging
from typing import Optional, Tuple
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class HedgeSelectionService:
    """Service for selecting optimal hedge strikes based on configuration"""
    
    def __init__(self):
        self.option_chain_service = None
        self._initialize_services()
        
    def _initialize_services(self):
        """Initialize required services"""
        try:
            from src.services.option_chain_service import OptionChainService
            self.option_chain_service = OptionChainService()
            logger.info("Option chain service initialized for hedge selection")
        except Exception as e:
            logger.warning(f"Could not initialize option chain service: {e}")
            self.option_chain_service = None
    
    def select_hedge_strike(
        self,
        main_strike: int,
        option_type: str,
        expiry_date,
        hedge_method: str,
        hedge_offset: int = 200,
        hedge_percent: float = 30.0
    ) -> Tuple[int, Optional[float]]:
        """
        Select optimal hedge strike based on configuration
        
        Args:
            main_strike: Main option strike
            option_type: PE or CE
            expiry_date: Expiry date object
            hedge_method: 'percentage' or 'offset'
            hedge_offset: Points offset for fixed method
            hedge_percent: Target percentage for percentage method
            
        Returns:
            Tuple of (hedge_strike, hedge_price)
        """
        
        if hedge_method == 'offset':
            # Simple fixed offset method
            if option_type == 'PE':
                hedge_strike = main_strike - hedge_offset
            else:
                hedge_strike = main_strike + hedge_offset
            logger.info(f"Offset-based hedge: {hedge_strike} ({hedge_offset} points away)")
            return hedge_strike, None
        
        # Percentage-based method - use efficient option chain fetching
        try:
            if not self.option_chain_service:
                logger.warning("Option chain service not available, using fallback")
                default_strike = main_strike - 250 if option_type == 'PE' else main_strike + 250
                return default_strike, None
            
            # Fetch option chain efficiently (cached, single call if possible)
            expiry_str = expiry_date.strftime('%Y-%m-%d')
            
            # Define search range
            if option_type == 'PE':
                # For PUT, OTM strikes are below main strike  
                start_strike = main_strike - 500
                end_strike = main_strike - 100
            else:
                # For CALL, OTM strikes are above main strike
                start_strike = main_strike + 100
                end_strike = main_strike + 500
            
            strikes_to_check = list(range(start_strike, end_strike + 1, 50))
            
            # Fetch option chain (will use cache if available)
            try:
                option_chain = self.option_chain_service.fetch_option_chain(
                    symbol='NIFTY',
                    expiry_date=expiry_str,
                    strike_count=15  # Get enough strikes
                )
                
                # Get main leg price from chain
                main_premium = None
                for row in option_chain['chain']:
                    if row['strike'] == main_strike:
                        if option_type == 'PE':
                            main_premium = row['put_ltp']
                        else:
                            main_premium = row['call_ltp']
                        break
                
                if not main_premium:
                    logger.warning(f"Main strike {main_strike} not found in chain")
                    main_premium = 100  # Fallback
                
                logger.info(f"Main leg {main_strike} {option_type} LTP: Rs. {main_premium}")
                
                # Calculate target price
                target_hedge_price = main_premium * (hedge_percent / 100)
                logger.info(f"Target hedge price: Rs. {target_hedge_price:.2f} ({hedge_percent}% of {main_premium})")
                
                # Find best match from chain
                best_hedge_strike = None
                best_price_diff = float('inf')
                best_hedge_price = None
                
                for row in option_chain['chain']:
                    strike = row['strike']
                    if strike not in strikes_to_check:
                        continue
                    
                    if option_type == 'PE':
                        strike_ltp = row['put_ltp']
                    else:
                        strike_ltp = row['call_ltp']
                    
                    if strike_ltp > 0:
                        price_diff = abs(strike_ltp - target_hedge_price)
                        price_percent = (strike_ltp / main_premium) * 100
                        
                        logger.debug(f"Strike {strike}: LTP={strike_ltp:.2f}, {price_percent:.1f}% of main")
                        
                        if price_diff < best_price_diff:
                            best_price_diff = price_diff
                            best_hedge_strike = strike
                            best_hedge_price = strike_ltp
                
                if best_hedge_strike:
                    actual_percent = (best_hedge_price / main_premium) * 100
                    logger.info(f"Selected hedge: {best_hedge_strike} {option_type} @ Rs. {best_hedge_price:.2f} ({actual_percent:.1f}% of main)")
                    return best_hedge_strike, best_hedge_price
                else:
                    logger.warning("No suitable hedge found in chain")
                    default_strike = main_strike - 250 if option_type == 'PE' else main_strike + 250
                    return default_strike, None
                    
            except Exception as e:
                logger.error(f"Error fetching option chain: {e}")
                # Fallback to simple offset
                default_strike = main_strike - 250 if option_type == 'PE' else main_strike + 250
                return default_strike, None
                
        except Exception as e:
            logger.error(f"Error in percentage-based hedge selection: {e}")
            # Fallback to simple offset
            default_strike = main_strike - 250 if option_type == 'PE' else main_strike + 250
            return default_strike, None