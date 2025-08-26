"""
Kite Order Manager for Live Trading
Uses Kite Personal API (FREE) for order placement only
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from kiteconnect import KiteConnect
import os
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()
logger = logging.getLogger(__name__)

class KiteOrderManager:
    """Manages order placement via Kite Personal API"""
    
    def __init__(self):
        """Initialize Kite connection"""
        self.kite = None
        self.is_connected = False
        self.api_key = os.getenv('KITE_API_KEY')
        self.access_token = None
        
        # Trading parameters
        self.lot_size = 75  # NIFTY lot size
        self.default_lots = 10
        self.hedge_distance = 200  # Points away for hedge
        
        # Order tracking
        self.active_orders = {}
        self.positions = {}
        
    def connect(self, access_token: str = None):
        """Connect to Kite API"""
        try:
            if not self.api_key:
                logger.error("Kite API key not found in environment")
                return False
            
            self.kite = KiteConnect(api_key=self.api_key)
            
            # Use provided token or from environment
            self.access_token = access_token or os.getenv('KITE_ACCESS_TOKEN')
            
            if not self.access_token:
                logger.error("Kite access token not provided")
                return False
            
            self.kite.set_access_token(self.access_token)
            
            # Verify connection
            profile = self.kite.profile()
            logger.info(f"Connected to Kite as {profile['user_name']}")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Kite: {e}")
            self.is_connected = False
            return False
    
    def place_hedge_basket(
        self,
        signal_type: str,
        strike: int,
        option_type: str,
        lots: int = None
    ) -> Dict[str, Any]:
        """
        Place hedge basket order (main + hedge)
        
        Args:
            signal_type: Signal that triggered (S1-S8)
            strike: Strike price for main leg
            option_type: CE or PE
            lots: Number of lots (default 10)
        
        Returns:
            Order response with order IDs
        """
        if not self.is_connected:
            return {'status': 'error', 'message': 'Not connected to Kite'}
        
        try:
            lots = lots or self.default_lots
            quantity = lots * self.lot_size
            
            # Get expiry
            expiry = self._get_current_expiry()
            
            # Prepare main leg (SELL)
            main_symbol = f"NIFTY{expiry}{strike}{option_type}"
            main_order = {
                'tradingsymbol': main_symbol,
                'exchange': 'NFO',
                'transaction_type': 'SELL',
                'quantity': quantity,
                'product': 'MIS',  # Intraday
                'order_type': 'MARKET',  # Market order for quick execution
                'variety': 'regular'
            }
            
            # Prepare hedge leg (BUY)
            hedge_strike = self._calculate_hedge_strike(strike, option_type)
            hedge_symbol = f"NIFTY{expiry}{hedge_strike}{option_type}"
            hedge_order = {
                'tradingsymbol': hedge_symbol,
                'exchange': 'NFO',
                'transaction_type': 'BUY',
                'quantity': quantity,
                'product': 'MIS',
                'order_type': 'MARKET',
                'variety': 'regular'
            }
            
            # Place orders
            order_ids = []
            
            # Place hedge first (BUY) for safety
            hedge_id = self.kite.place_order(**hedge_order)
            order_ids.append(hedge_id)
            logger.info(f"Hedge order placed: {hedge_symbol} BUY {quantity} @ MARKET")
            
            # Then place main leg (SELL)
            main_id = self.kite.place_order(**main_order)
            order_ids.append(main_id)
            logger.info(f"Main order placed: {main_symbol} SELL {quantity} @ MARKET")
            
            # Store order info
            order_info = {
                'signal_type': signal_type,
                'main_order_id': main_id,
                'hedge_order_id': hedge_id,
                'main_symbol': main_symbol,
                'hedge_symbol': hedge_symbol,
                'strike': strike,
                'option_type': option_type,
                'quantity': quantity,
                'timestamp': datetime.now()
            }
            
            self.active_orders[signal_type] = order_info
            
            return {
                'status': 'success',
                'order_ids': order_ids,
                'order_info': order_info
            }
            
        except Exception as e:
            logger.error(f"Failed to place hedge basket: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def square_off_position(self, signal_type: str) -> Dict[str, Any]:
        """
        Square off a position (close both main and hedge)
        
        Args:
            signal_type: Signal identifier
        
        Returns:
            Square off response
        """
        if signal_type not in self.active_orders:
            return {'status': 'error', 'message': 'Position not found'}
        
        try:
            order_info = self.active_orders[signal_type]
            quantity = order_info['quantity']
            
            # Square off main leg (BUY to close SELL)
            main_square = {
                'tradingsymbol': order_info['main_symbol'],
                'exchange': 'NFO',
                'transaction_type': 'BUY',
                'quantity': quantity,
                'product': 'MIS',
                'order_type': 'MARKET',
                'variety': 'regular'
            }
            
            # Square off hedge leg (SELL to close BUY)
            hedge_square = {
                'tradingsymbol': order_info['hedge_symbol'],
                'exchange': 'NFO',
                'transaction_type': 'SELL',
                'quantity': quantity,
                'product': 'MIS',
                'order_type': 'MARKET',
                'variety': 'regular'
            }
            
            # Place square off orders
            square_ids = []
            
            # Square off main first
            main_sq_id = self.kite.place_order(**main_square)
            square_ids.append(main_sq_id)
            logger.info(f"Main squared off: {order_info['main_symbol']}")
            
            # Square off hedge
            hedge_sq_id = self.kite.place_order(**hedge_square)
            square_ids.append(hedge_sq_id)
            logger.info(f"Hedge squared off: {order_info['hedge_symbol']}")
            
            # Remove from active orders
            del self.active_orders[signal_type]
            
            return {
                'status': 'success',
                'square_off_ids': square_ids,
                'signal_type': signal_type
            }
            
        except Exception as e:
            logger.error(f"Failed to square off position: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def square_off_all(self) -> Dict[str, Any]:
        """Square off all open positions"""
        results = []
        
        for signal_type in list(self.active_orders.keys()):
            result = self.square_off_position(signal_type)
            results.append(result)
        
        return {
            'status': 'success',
            'squared_off': len(results),
            'results': results
        }
    
    def get_positions(self) -> List[Dict]:
        """Get current positions from Kite"""
        try:
            if not self.is_connected:
                return []
            
            positions = self.kite.positions()
            
            # Filter for NIFTY options
            nifty_positions = []
            for pos in positions['net']:
                if 'NIFTY' in pos['tradingsymbol']:
                    nifty_positions.append({
                        'symbol': pos['tradingsymbol'],
                        'quantity': pos['quantity'],
                        'average_price': pos['average_price'],
                        'last_price': pos['last_price'],
                        'pnl': pos['pnl'],
                        'unrealised': pos['unrealised'],
                        'realised': pos['realised']
                    })
            
            return nifty_positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def get_orders(self) -> List[Dict]:
        """Get today's orders"""
        try:
            if not self.is_connected:
                return []
            
            orders = self.kite.orders()
            
            # Filter for today's NIFTY orders
            today = datetime.now().date()
            nifty_orders = []
            
            for order in orders:
                if 'NIFTY' in order['tradingsymbol']:
                    order_date = datetime.strptime(
                        order['order_timestamp'],
                        '%Y-%m-%d %H:%M:%S'
                    ).date()
                    
                    if order_date == today:
                        nifty_orders.append({
                            'order_id': order['order_id'],
                            'symbol': order['tradingsymbol'],
                            'transaction_type': order['transaction_type'],
                            'quantity': order['quantity'],
                            'price': order['price'],
                            'status': order['status'],
                            'timestamp': order['order_timestamp']
                        })
            
            return nifty_orders
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    def get_margins(self) -> Dict[str, float]:
        """Get account margins"""
        try:
            if not self.is_connected:
                return {}
            
            margins = self.kite.margins()
            
            return {
                'available': margins['equity']['available']['live_balance'],
                'used': margins['equity']['utilised']['debits'],
                'total': margins['equity']['net']
            }
            
        except Exception as e:
            logger.error(f"Failed to get margins: {e}")
            return {}
    
    def _calculate_hedge_strike(self, main_strike: int, option_type: str) -> int:
        """Calculate hedge strike price"""
        if option_type == 'PE':
            # For PUT, hedge is further OTM (lower strike)
            return main_strike - self.hedge_distance
        else:
            # For CALL, hedge is further OTM (higher strike)
            return main_strike + self.hedge_distance
    
    def _get_current_expiry(self) -> str:
        """Get current week expiry format for Kite"""
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        
        # If today is Thursday after 3:30 PM, get next Thursday
        if days_until_thursday == 0:
            if today.hour >= 15 and today.minute >= 30:
                days_until_thursday = 7
        
        expiry = today + timedelta(days=days_until_thursday)
        
        # Format for Kite: 25AUG (day + month)
        day = expiry.strftime("%d").lstrip("0")  # Remove leading zero
        month = expiry.strftime("%b").upper()
        
        # Special formatting for Kite
        month_map = {
            'JAN': '1', 'FEB': '2', 'MAR': '3', 'APR': '4',
            'MAY': '5', 'JUN': '6', 'JUL': '7', 'AUG': '8',
            'SEP': '9', 'OCT': 'O', 'NOV': 'N', 'DEC': 'D'
        }
        
        # Return format: 25AUG for normal months, 25O for October
        if month in ['OCT', 'NOV', 'DEC']:
            return f"{day}{month_map[month]}"
        else:
            return f"{day}{month}"
    
    def place_stop_loss_order(
        self,
        signal_type: str,
        trigger_price: float
    ) -> Dict[str, Any]:
        """Place stop-loss order for a position"""
        if signal_type not in self.active_orders:
            return {'status': 'error', 'message': 'Position not found'}
        
        try:
            order_info = self.active_orders[signal_type]
            
            # Place SL-M order for main leg
            sl_order = {
                'tradingsymbol': order_info['main_symbol'],
                'exchange': 'NFO',
                'transaction_type': 'BUY',  # To close SELL position
                'quantity': order_info['quantity'],
                'product': 'MIS',
                'order_type': 'SL-M',  # Stop-loss market
                'trigger_price': trigger_price,
                'variety': 'regular'
            }
            
            sl_id = self.kite.place_order(**sl_order)
            
            logger.info(f"Stop-loss placed for {signal_type} at {trigger_price}")
            
            return {
                'status': 'success',
                'sl_order_id': sl_id,
                'trigger_price': trigger_price
            }
            
        except Exception as e:
            logger.error(f"Failed to place stop-loss: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_connection_status(self) -> Dict:
        """Get connection status"""
        return {
            'connected': self.is_connected,
            'api_key': bool(self.api_key),
            'access_token': bool(self.access_token),
            'active_orders': len(self.active_orders),
            'positions': len(self.get_positions())
        }

# Global instance
_kite_manager = None

def get_kite_manager() -> KiteOrderManager:
    """Get or create Kite order manager instance"""
    global _kite_manager
    if _kite_manager is None:
        _kite_manager = KiteOrderManager()
    return _kite_manager

def connect_kite(access_token: str = None) -> bool:
    """Connect to Kite API"""
    manager = get_kite_manager()
    return manager.connect(access_token)

def place_trade(signal_type: str, strike: int, option_type: str, lots: int = None):
    """Place a hedge basket trade"""
    manager = get_kite_manager()
    return manager.place_hedge_basket(signal_type, strike, option_type, lots)

def square_off_all_positions():
    """Square off all open positions"""
    manager = get_kite_manager()
    return manager.square_off_all()

if __name__ == "__main__":
    # Test the order manager
    logging.basicConfig(level=logging.INFO)
    
    manager = get_kite_manager()
    
    # You need to provide access token
    # This would come from the auto-login process
    if manager.connect():
        print("Connected to Kite!")
        
        # Get margins
        margins = manager.get_margins()
        print(f"Available margin: {margins.get('available', 0)}")
        
        # Get positions
        positions = manager.get_positions()
        print(f"Current positions: {len(positions)}")
        
    else:
        print("Failed to connect to Kite")