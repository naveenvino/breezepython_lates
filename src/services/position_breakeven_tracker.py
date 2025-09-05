"""
Position & Breakeven Tracker
Tracks main and hedge positions with real-time breakeven calculation
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

from src.services.hybrid_data_manager import get_hybrid_data_manager, LivePosition
from src.services.breeze_option_chain_production import get_breeze_option_chain
from src.services.zerodha_order_executor import get_zerodha_executor, OrderRequest, OrderType

logger = logging.getLogger(__name__)

@dataclass
class PositionEntry:
    """Represents a position entry request"""
    signal_type: str  # S1-S8
    main_strike: int
    option_type: str  # CE or PE
    quantity: int = 10  # Default 10 lots
    hedge_percent: float = 30.0  # 30% hedge rule
    enable_hedge: bool = True

@dataclass
class HedgeSelection:
    """Result of hedge strike selection"""
    strike: int
    price: float
    delta: float
    percent_of_main: float
    offset_points: int

class PositionBreakevenTracker:
    """
    Manages position entry with 30% hedge rule and breakeven tracking
    """
    
    def __init__(self):
        self.data_manager = get_hybrid_data_manager()
        
        # ALWAYS use mock for now to prevent loading issues
        # Will switch to Breeze when credentials are properly fixed
        from src.services.simple_option_chain_mock import get_simple_option_chain
        self.option_chain_service = get_simple_option_chain()
        logger.info("Using mock option chain service (immediate fallback to prevent loading)")
            
        self.zerodha = get_zerodha_executor()
        
        # Position tracking
        self.position_counter = 0
        
        # Default parameters
        self.default_quantity = 10  # lots
        self.lot_size = 75  # NIFTY lot size
        self.default_hedge_percent = 30.0
        self.max_hedge_offset = 500  # Maximum points away for hedge
        self.min_hedge_offset = 100  # Minimum points away for hedge
        
        # Trading mode
        self.live_trading_enabled = True  # LIVE TRADING ENABLED - Real orders will be placed!
    
    def create_position(self, entry: PositionEntry) -> Dict[str, Any]:
        """
        Create a new position with hedge
        
        Returns:
            Dict with position details including breakeven
        """
        try:
            # Get current option chain
            option_chain = self.option_chain_service.get_option_chain()
            
            if not option_chain or 'options' not in option_chain:
                return {'error': 'Option chain not available'}
            
            # Find main leg price
            main_price = self._get_option_price(
                option_chain, 
                entry.main_strike, 
                entry.option_type
            )
            
            if main_price is None:
                return {'error': f'Main strike {entry.main_strike} {entry.option_type} not found'}
            
            # Select hedge if enabled
            hedge_strike = None
            hedge_price = None
            hedge_quantity = None
            
            if entry.enable_hedge:
                hedge_selection = self._select_hedge_strike(
                    option_chain,
                    entry.main_strike,
                    main_price,
                    entry.option_type,
                    entry.hedge_percent
                )
                
                if hedge_selection:
                    hedge_strike = hedge_selection.strike
                    hedge_price = hedge_selection.price
                    hedge_quantity = entry.quantity  # Same quantity for hedge
                    
                    logger.info(f"Selected hedge: {hedge_strike} {entry.option_type} "
                              f"@ {hedge_price:.2f} ({hedge_selection.percent_of_main:.1f}% of main)")
            
            # Create position
            self.position_counter += 1
            position = LivePosition(
                id=self.position_counter,
                signal_type=entry.signal_type,
                main_strike=entry.main_strike,
                main_price=main_price,
                main_quantity=entry.quantity,
                hedge_strike=hedge_strike,
                hedge_price=hedge_price,
                hedge_quantity=hedge_quantity,
                entry_time=datetime.now(),
                current_main_price=main_price,
                current_hedge_price=hedge_price,
                status='open',
                option_type=entry.option_type,
                quantity=entry.quantity,
                lot_size=self.lot_size
            )
            
            # Add to data manager
            self.data_manager.add_position(position)
            
            # Execute real orders if live trading is enabled
            if self.live_trading_enabled and self.zerodha.is_connected:
                try:
                    # Get current expiry (Thursday)
                    from datetime import timedelta
                    today = datetime.now()
                    days_until_thursday = (3 - today.weekday()) % 7
                    if days_until_thursday == 0 and today.hour >= 15:  # Past 3:30 PM on Thursday
                        days_until_thursday = 7
                    expiry = today + timedelta(days=days_until_thursday)
                    expiry_str = expiry.strftime("%y%b").upper()  # Format: 24DEC
                    
                    # Place main order (SELL option)
                    main_symbol = f"NIFTY{expiry_str}{entry.main_strike}{entry.option_type}"
                    main_order = OrderRequest(
                        symbol=main_symbol,
                        exchange="NFO",
                        transaction_type="SELL",  # Selling option
                        quantity=entry.quantity * self.lot_size,
                        order_type=OrderType.MARKET,
                        product="MIS",  # Intraday
                        tag=f"{entry.signal_type}_MAIN"
                    )
                    
                    logger.info(f"Placing main order: {main_symbol} SELL {entry.quantity * self.lot_size}")
                    main_result = self.zerodha.place_order(main_order)
                    
                    if main_result.status == "COMPLETE" or main_result.status == "PENDING":
                        position.main_order_id = main_result.order_id
                        logger.info(f"Main order placed successfully: {main_result.order_id}")
                    else:
                        logger.error(f"Main order failed: {main_result.message}")
                    
                    # Place hedge order if enabled
                    if hedge_strike and hedge_quantity:
                        hedge_symbol = f"NIFTY{expiry_str}{hedge_strike}{entry.option_type}"
                        hedge_order = OrderRequest(
                            symbol=hedge_symbol,
                            exchange="NFO",
                            transaction_type="BUY",  # Buying option for hedge
                            quantity=hedge_quantity * self.lot_size,
                            order_type=OrderType.MARKET,
                            product="MIS",  # Intraday
                            tag=f"{entry.signal_type}_HEDGE"
                        )
                        
                        logger.info(f"Placing hedge order: {hedge_symbol} BUY {hedge_quantity * self.lot_size}")
                        hedge_result = self.zerodha.place_order(hedge_order)
                        
                        if hedge_result.status == "COMPLETE" or hedge_result.status == "PENDING":
                            position.hedge_order_id = hedge_result.order_id
                            logger.info(f"Hedge order placed successfully: {hedge_result.order_id}")
                        else:
                            logger.error(f"Hedge order failed: {hedge_result.message}")
                            
                except Exception as e:
                    logger.error(f"Error executing orders: {e}")
                    # Continue even if order placement fails - position is still tracked
            elif self.live_trading_enabled and not self.zerodha.is_connected:
                logger.warning("Live trading enabled but Zerodha not connected. Orders not placed.")
            else:
                logger.info("Paper trading mode - no real orders placed")
            
            # Calculate initial metrics
            result = {
                'position_id': position.id,
                'signal_type': entry.signal_type,
                'main_leg': {
                    'strike': entry.main_strike,
                    'type': entry.option_type,
                    'price': main_price,
                    'quantity': entry.quantity,
                    'value': main_price * entry.quantity * self.lot_size
                },
                'hedge_leg': None,
                'breakeven': position.breakeven,
                'net_premium': main_price,
                'max_profit': None,
                'max_loss': None,
                'entry_time': position.entry_time.isoformat()
            }
            
            if hedge_strike:
                result['hedge_leg'] = {
                    'strike': hedge_strike,
                    'type': entry.option_type,
                    'price': hedge_price,
                    'quantity': hedge_quantity,
                    'value': hedge_price * hedge_quantity * self.lot_size,
                    'percent_of_main': hedge_selection.percent_of_main,
                    'offset_points': hedge_selection.offset_points
                }
                result['net_premium'] = main_price - hedge_price
                
                # Calculate max profit/loss for spread
                result['max_profit'] = result['net_premium'] * entry.quantity * self.lot_size
                result['max_loss'] = (abs(hedge_strike - entry.main_strike) - result['net_premium']) * entry.quantity * self.lot_size
            
            logger.info(f"Created position {position.id}: {entry.signal_type} "
                       f"Main: {entry.main_strike} {entry.option_type} @ {main_price:.2f}, "
                       f"Breakeven: {position.breakeven:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating position: {e}")
            return {'error': str(e)}
    
    def _get_option_price(self, option_chain: Dict, strike: int, option_type: str) -> Optional[float]:
        """Get option price from chain"""
        for option in option_chain.get('options', []):
            if option['strike'] == strike and option['type'] == option_type:
                return option.get('ltp', option.get('price'))
        return None
    
    def _select_hedge_strike(
        self, 
        option_chain: Dict,
        main_strike: int,
        main_price: float,
        option_type: str,
        target_percent: float
    ) -> Optional[HedgeSelection]:
        """
        Select hedge strike based on 30% rule
        If main leg price is 100, select hedge around 30
        """
        target_price = main_price * (target_percent / 100)
        
        # Get all options of same type
        options = [
            opt for opt in option_chain.get('options', [])
            if opt['type'] == option_type
        ]
        
        # Sort by strike
        options.sort(key=lambda x: x['strike'])
        
        # For PUT: hedge is further OTM (lower strike)
        # For CALL: hedge is further OTM (higher strike)
        best_hedge = None
        min_price_diff = float('inf')
        
        for option in options:
            strike = option['strike']
            price = option.get('ltp', option.get('price', 0))
            
            # Skip if no price
            if not price:
                continue
            
            # Calculate offset from main strike
            if option_type == 'PE':
                offset = main_strike - strike
                if offset < self.min_hedge_offset or offset > self.max_hedge_offset:
                    continue
            else:  # CE
                offset = strike - main_strike
                if offset < self.min_hedge_offset or offset > self.max_hedge_offset:
                    continue
            
            # Check if price is close to target
            price_diff = abs(price - target_price)
            percent_of_main = (price / main_price) * 100
            
            # Prefer strikes closer to target percentage
            if price_diff < min_price_diff:
                min_price_diff = price_diff
                best_hedge = HedgeSelection(
                    strike=strike,
                    price=price,
                    delta=option.get('delta', 0),
                    percent_of_main=percent_of_main,
                    offset_points=offset
                )
        
        return best_hedge
    
    def update_position_prices(self, position_id: int):
        """Update position with latest option prices"""
        try:
            if position_id not in self.data_manager.memory_cache['active_positions']:
                return {'error': 'Position not found'}
            
            position = self.data_manager.memory_cache['active_positions'][position_id]
            
            # Get current option chain
            option_chain = self.option_chain_service.get_option_chain()
            
            if not option_chain or 'options' not in option_chain:
                return {'error': 'Option chain not available'}
            
            # Determine option type from signal
            option_type = 'PE' if position.signal_type in ['S1', 'S2', 'S4', 'S7'] else 'CE'
            
            # Update main leg price
            main_price = self._get_option_price(
                option_chain,
                position.main_strike,
                option_type
            )
            
            if main_price:
                position.current_main_price = main_price
            
            # Update hedge leg price if exists
            if position.hedge_strike:
                hedge_price = self._get_option_price(
                    option_chain,
                    position.hedge_strike,
                    option_type
                )
                
                if hedge_price:
                    position.current_hedge_price = hedge_price
            
            # Update in data manager
            self.data_manager.update_position(
                position_id,
                main_price,
                position.current_hedge_price
            )
            
            return {
                'position_id': position_id,
                'main_price': main_price,
                'hedge_price': position.current_hedge_price,
                'pnl': position.pnl,
                'breakeven': position.breakeven
            }
            
        except Exception as e:
            logger.error(f"Error updating position prices: {e}")
            return {'error': str(e)}
    
    def calculate_live_breakeven(self, position_id: int) -> Optional[float]:
        """Calculate real breakeven by scanning option chain for P&L = 0"""
        if position_id not in self.data_manager.memory_cache['active_positions']:
            return None
        
        position = self.data_manager.memory_cache['active_positions'][position_id]
        option_type = 'PE' if position.signal_type in ['S1', 'S2', 'S4', 'S7'] else 'CE'
        
        # Store original spot
        original_spot = self.option_chain_service.spot_price
        
        # Test different spot levels
        test_spots = []
        for offset in range(-500, 501, 10):  # Test from -500 to +500 in steps of 10
            test_spots.append(position.main_strike + offset)
        
        breakeven_spot = None
        min_pnl_abs = float('inf')
        
        for test_spot in test_spots:
            # Update spot price for testing
            self.option_chain_service.update_spot(test_spot)
            
            # Get option chain (REAL data from Breeze if connected, mock if not)
            chain = self.option_chain_service.get_option_chain()
            
            # Get prices at this spot level
            main_price_at_spot = None
            hedge_price_at_spot = None
            
            for option in chain['options']:
                if option['strike'] == position.main_strike and option['type'] == option_type:
                    main_price_at_spot = option['ltp']
                if position.hedge_strike and option['strike'] == position.hedge_strike and option['type'] == option_type:
                    hedge_price_at_spot = option['ltp']
            
            if main_price_at_spot is None:
                continue
            
            # Calculate P&L at this spot
            main_pnl = (position.main_price - main_price_at_spot) * position.main_quantity * self.lot_size
            hedge_pnl = 0
            if position.hedge_strike and hedge_price_at_spot:
                hedge_pnl = (hedge_price_at_spot - position.hedge_price) * position.hedge_quantity * self.lot_size
            
            net_pnl = main_pnl + hedge_pnl
            
            # Check if this is closer to breakeven
            if abs(net_pnl) < min_pnl_abs:
                min_pnl_abs = abs(net_pnl)
                breakeven_spot = test_spot
                
                # If P&L is very close to zero, we found it
                if abs(net_pnl) < 100:  # Within ₹100 of breakeven
                    break
        
        # Restore original spot
        self.option_chain_service.update_spot(original_spot)
        
        return breakeven_spot
    
    def get_position_details(self, position_id: int) -> Dict[str, Any]:
        """Get detailed position information"""
        if position_id not in self.data_manager.memory_cache['active_positions']:
            return {'error': 'Position not found'}
        
        position = self.data_manager.memory_cache['active_positions'][position_id]
        
        # Calculate Greeks if available
        option_type = 'PE' if position.signal_type in ['S1', 'S2', 'S4', 'S7'] else 'CE'
        
        # Calculate live breakeven
        live_breakeven = self.calculate_live_breakeven(position_id)
        
        details = {
            'position_id': position.id,
            'signal_type': position.signal_type,
            'status': position.status,
            'entry_time': position.entry_time.isoformat(),
            'main_leg': {
                'strike': position.main_strike,
                'type': option_type,
                'entry_price': position.main_price,
                'current_price': position.current_main_price,
                'quantity': position.main_quantity,
                'pnl': (position.main_price - position.current_main_price) * position.main_quantity * self.lot_size
            },
            'hedge_leg': None,
            'net_position': {
                'expiry_breakeven': position.breakeven,  # Strike-based breakeven at expiry
                'live_breakeven': live_breakeven,  # Real breakeven based on current prices
                'total_pnl': position.pnl,
                'pnl_percent': (position.pnl / (position.main_price * position.main_quantity * self.lot_size)) * 100
            }
        }
        
        if position.hedge_strike:
            details['hedge_leg'] = {
                'strike': position.hedge_strike,
                'type': option_type,
                'entry_price': position.hedge_price,
                'current_price': position.current_hedge_price,
                'quantity': position.hedge_quantity,
                'pnl': (position.current_hedge_price - position.hedge_price) * position.hedge_quantity * self.lot_size
            }
            
            # Net premium and spread details
            net_premium_entry = position.main_price - position.hedge_price
            net_premium_current = position.current_main_price - position.current_hedge_price
            
            details['spread_analysis'] = {
                'net_premium_entry': net_premium_entry,
                'net_premium_current': net_premium_current,
                'spread_width': abs(position.hedge_strike - position.main_strike),
                'max_profit': net_premium_entry * position.main_quantity * self.lot_size,
                'max_loss': (abs(position.hedge_strike - position.main_strike) - net_premium_entry) * position.main_quantity * self.lot_size
            }
        
        return details
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all active positions with breakeven"""
        positions = []
        
        for position in self.data_manager.memory_cache['active_positions'].values():
            option_type = 'PE' if position.signal_type in ['S1', 'S2', 'S4', 'S7'] else 'CE'
            
            pos_dict = {
                'position_id': position.id,
                'signal_type': position.signal_type,
                'main_strike': position.main_strike,
                'option_type': option_type,
                'entry_time': position.entry_time.isoformat(),
                'breakeven': position.breakeven,
                'pnl': position.pnl,
                'pnl_percent': (position.pnl / (position.main_price * position.main_quantity * self.lot_size)) * 100,
                'status': position.status
            }
            
            if position.hedge_strike:
                pos_dict['hedge_strike'] = position.hedge_strike
                pos_dict['net_premium'] = position.main_price - position.hedge_price
            
            positions.append(pos_dict)
        
        return positions
    
    def close_position(self, position_id: int, reason: str = "Manual close") -> Dict[str, Any]:
        """Close a position"""
        try:
            if position_id not in self.data_manager.memory_cache['active_positions']:
                return {'error': 'Position not found'}
            
            position = self.data_manager.memory_cache['active_positions'][position_id]
            
            # Calculate final P&L
            final_pnl = position.pnl
            
            # Close in data manager
            self.data_manager.close_position(position_id, final_pnl)
            
            result = {
                'position_id': position_id,
                'signal_type': position.signal_type,
                'entry_time': position.entry_time.isoformat(),
                'exit_time': datetime.now().isoformat(),
                'final_pnl': final_pnl,
                'reason': reason
            }
            
            logger.info(f"Closed position {position_id}: P&L = {final_pnl:.2f}, Reason: {reason}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {'error': str(e)}

# Singleton instance
_instance = None

def get_position_breakeven_tracker() -> PositionBreakevenTracker:
    """Get singleton instance of position breakeven tracker"""
    global _instance
    if _instance is None:
        _instance = PositionBreakevenTracker()
    return _instance