"""
Kite Weekly Options Order Executor
Handles order placement for NIFTY weekly options with proper symbol formatting
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from kiteconnect import KiteConnect
import os

logger = logging.getLogger(__name__)

class KiteWeeklyOptionsExecutor:
    """Execute NIFTY weekly options trades on Zerodha Kite"""
    
    def __init__(self, api_key: str = None, access_token: str = None):
        """
        Initialize Kite connection
        
        Args:
            api_key: Kite Connect API key
            access_token: Access token from login
        """
        self.api_key = api_key or os.getenv('KITE_API_KEY')
        self.access_token = access_token or os.getenv('KITE_ACCESS_TOKEN')
        
        if not self.api_key or not self.access_token:
            logger.error("Kite API credentials not provided")
            raise ValueError("Kite API key and access token required")
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Month codes for weekly options
        self.month_codes = {
            1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6',
            7: '7', 8: '8', 9: '9', 10: 'O', 11: 'N', 12: 'D'
        }
        
    def format_weekly_symbol(self, expiry_date: datetime, strike: int, option_type: str) -> str:
        """
        Format symbol for NIFTY weekly options
        
        Args:
            expiry_date: Expiry date (Tuesday)
            strike: Strike price (e.g., 25000)
            option_type: 'PE' or 'CE'
        
        Returns:
            Formatted symbol like NIFTY2511425000PE
        """
        year = str(expiry_date.year)[-2:]  # Last 2 digits of year
        month = self.month_codes[expiry_date.month]
        day = f"{expiry_date.day:02d}"  # Two digit day
        
        symbol = f"NIFTY{year}{month}{day}{strike}{option_type}"
        logger.info(f"Generated Kite symbol: {symbol}")
        return symbol
    
    def format_monthly_symbol(self, expiry_date: datetime, strike: int, option_type: str) -> str:
        """
        Format symbol for NIFTY monthly options (last Thursday)
        
        Args:
            expiry_date: Monthly expiry date
            strike: Strike price
            option_type: 'PE' or 'CE'
        
        Returns:
            Formatted symbol like NIFTY25JAN25000PE
        """
        year = str(expiry_date.year)[-2:]
        month = expiry_date.strftime('%b').upper()  # JAN, FEB, etc.
        
        symbol = f"NIFTY{year}{month}{strike}{option_type}"
        logger.info(f"Generated monthly Kite symbol: {symbol}")
        return symbol
    
    def is_monthly_expiry(self, expiry_date: datetime) -> bool:
        """Check if the expiry is monthly (last Thursday of month)"""
        # Check if this is the last Thursday of the month
        # Add 7 days and see if we're in next month
        next_week = expiry_date + timedelta(days=7)
        return next_week.month != expiry_date.month
    
    def place_option_order(self, 
                          strike: int,
                          option_type: str,
                          transaction_type: str,
                          quantity: int,
                          expiry_date: datetime,
                          order_type: str = "MARKET",
                          price: float = None,
                          product: str = "MIS") -> str:
        """
        Place an option order on Kite
        
        Args:
            strike: Strike price
            option_type: 'PE' or 'CE'
            transaction_type: 'BUY' or 'SELL'
            quantity: Number of lots * lot size (e.g., 10 * 75 = 750)
            expiry_date: Expiry date for the option
            order_type: 'MARKET' or 'LIMIT'
            price: Price for limit orders
            product: 'MIS' (intraday) or 'NRML' (overnight)
        
        Returns:
            Order ID
        """
        try:
            # Format symbol based on expiry type
            if self.is_monthly_expiry(expiry_date):
                tradingsymbol = self.format_monthly_symbol(expiry_date, strike, option_type)
            else:
                tradingsymbol = self.format_weekly_symbol(expiry_date, strike, option_type)
            
            # Prepare order parameters
            order_params = {
                'tradingsymbol': tradingsymbol,
                'exchange': 'NFO',
                'transaction_type': transaction_type,
                'quantity': quantity,
                'order_type': order_type,
                'product': product,
                'variety': 'regular'
            }
            
            # Add price for limit orders
            if order_type == 'LIMIT' and price:
                order_params['price'] = price
            
            logger.info(f"Placing Kite order: {order_params}")
            
            # Place the order
            order_id = self.kite.place_order(**order_params)
            
            logger.info(f"Order placed successfully. Order ID: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            raise
    
    def execute_iron_condor(self,
                           main_strike: int,
                           hedge_strike: int,
                           option_type: str,
                           lots: int,
                           expiry_date: datetime) -> Dict:
        """
        Execute an iron condor strategy (main + hedge)
        
        Args:
            main_strike: Main leg strike price
            hedge_strike: Hedge leg strike price
            option_type: 'PE' or 'CE'
            lots: Number of lots
            expiry_date: Expiry date
        
        Returns:
            Dict with order IDs
        """
        try:
            lot_size = 75  # NIFTY lot size
            quantity = lots * lot_size
            
            results = {
                'main_order_id': None,
                'hedge_order_id': None,
                'status': 'pending'
            }
            
            # Place hedge order first (BUY) for margin benefit
            logger.info(f"Placing hedge order: BUY {hedge_strike} {option_type}")
            hedge_order_id = self.place_option_order(
                strike=hedge_strike,
                option_type=option_type,
                transaction_type='BUY',
                quantity=quantity,
                expiry_date=expiry_date,
                order_type='MARKET'
            )
            results['hedge_order_id'] = hedge_order_id
            
            # Then place main order (SELL)
            logger.info(f"Placing main order: SELL {main_strike} {option_type}")
            main_order_id = self.place_option_order(
                strike=main_strike,
                option_type=option_type,
                transaction_type='SELL',
                quantity=quantity,
                expiry_date=expiry_date,
                order_type='MARKET'
            )
            results['main_order_id'] = main_order_id
            
            results['status'] = 'executed'
            logger.info(f"Iron condor executed successfully: {results}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing iron condor: {str(e)}")
            results['status'] = 'failed'
            results['error'] = str(e)
            return results
    
    def process_webhook_signal(self, webhook_data: Dict) -> Dict:
        """
        Process webhook signal and place orders
        
        Args:
            webhook_data: Webhook payload with signal details
        
        Returns:
            Execution results
        """
        try:
            # Get expiry configuration
            from src.services.expiry_management_service import get_expiry_service
            expiry_service = get_expiry_service()
            
            # Load weekday config
            import json
            with open("expiry_weekday_config.json", "r") as f:
                weekday_config = json.load(f)
            
            # Get current day and expiry type
            current_day = datetime.now().strftime('%A').lower()
            expiry_type = weekday_config.get(current_day, 'next')
            
            # Get expiry date based on configuration
            if expiry_type == 'current':
                expiry_date = expiry_service.get_current_week_expiry()
            elif expiry_type == 'next':
                expiry_date = expiry_service.get_next_week_expiry()
            else:  # monthend
                expiry_date = expiry_service.get_month_end_expiry()
            
            logger.info(f"Using expiry: {expiry_date.strftime('%Y-%m-%d')} ({expiry_type})")
            
            # Extract order details from webhook
            main_strike = webhook_data['strike']
            option_type = webhook_data['option_type']  # PE or CE
            lots = webhook_data.get('lots', 10)
            
            # Calculate hedge strike (200 points away)
            if option_type == 'PE':
                hedge_strike = main_strike - 200  # Lower strike for PUT hedge
            else:
                hedge_strike = main_strike + 200  # Higher strike for CALL hedge
            
            # Execute the trade
            result = self.execute_iron_condor(
                main_strike=main_strike,
                hedge_strike=hedge_strike,
                option_type=option_type,
                lots=lots,
                expiry_date=expiry_date
            )
            
            # Add symbols to result for reference
            if self.is_monthly_expiry(expiry_date):
                main_symbol = self.format_monthly_symbol(expiry_date, main_strike, option_type)
                hedge_symbol = self.format_monthly_symbol(expiry_date, hedge_strike, option_type)
            else:
                main_symbol = self.format_weekly_symbol(expiry_date, main_strike, option_type)
                hedge_symbol = self.format_weekly_symbol(expiry_date, hedge_strike, option_type)
            
            result['main_symbol'] = main_symbol
            result['hedge_symbol'] = hedge_symbol
            result['expiry_date'] = expiry_date.strftime('%Y-%m-%d')
            result['expiry_type'] = expiry_type
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing webhook signal: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def check_order_status(self, order_id: str) -> Dict:
        """Check status of an order"""
        try:
            order_history = self.kite.order_history(order_id)
            if order_history:
                latest_status = order_history[-1]
                return {
                    'order_id': order_id,
                    'status': latest_status['status'],
                    'filled_quantity': latest_status.get('filled_quantity', 0),
                    'average_price': latest_status.get('average_price', 0)
                }
            return {'order_id': order_id, 'status': 'NOT_FOUND'}
        except Exception as e:
            logger.error(f"Error checking order status: {str(e)}")
            return {'order_id': order_id, 'status': 'ERROR', 'error': str(e)}
    
    def square_off_position(self, symbol: str, quantity: int, transaction_type: str) -> str:
        """
        Square off an existing position
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to square off
            transaction_type: 'BUY' to close short, 'SELL' to close long
        
        Returns:
            Order ID
        """
        try:
            order_params = {
                'tradingsymbol': symbol,
                'exchange': 'NFO',
                'transaction_type': transaction_type,
                'quantity': quantity,
                'order_type': 'MARKET',
                'product': 'MIS',
                'variety': 'regular'
            }
            
            order_id = self.kite.place_order(**order_params)
            logger.info(f"Square-off order placed: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"Error squaring off position: {str(e)}")
            raise


# Usage example
if __name__ == "__main__":
    from datetime import timedelta
    
    # Initialize executor (you need to set these in .env)
    executor = KiteWeeklyOptionsExecutor()
    
    # Example webhook data
    webhook_data = {
        'signal': 'S1',
        'strike': 25000,
        'option_type': 'PE',
        'lots': 10
    }
    
    # Process the webhook signal
    result = executor.process_webhook_signal(webhook_data)
    print(f"Execution result: {result}")
    
    # Check order status
    if result.get('main_order_id'):
        status = executor.check_order_status(result['main_order_id'])
        print(f"Main order status: {status}")