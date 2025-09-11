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
        Format symbol for NIFTY monthly options (last Tuesday)
        
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
        """Check if the expiry is monthly (last Tuesday of month)"""
        # Check if this is the last Tuesday of the month
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
                          product: str = "NRML",
                          use_iceberg: bool = True,
                          use_amo: bool = False) -> str:
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
            use_amo: Whether to place as AMO order (for after market hours)
        
        Returns:
            Order ID
        """
        try:
            # Format symbol based on expiry type
            if self.is_monthly_expiry(expiry_date):
                tradingsymbol = self.format_monthly_symbol(expiry_date, strike, option_type)
            else:
                tradingsymbol = self.format_weekly_symbol(expiry_date, strike, option_type)
            
            # Check if we need to split the order (iceberg)
            MAX_QUANTITY = 1800  # 24 lots * 75
            
            if use_iceberg and quantity > MAX_QUANTITY:
                # Split into multiple orders
                logger.info(f"Order quantity {quantity} exceeds max {MAX_QUANTITY}, using iceberg orders")
                order_ids = []
                remaining_qty = quantity
                
                while remaining_qty > 0:
                    chunk_qty = min(remaining_qty, MAX_QUANTITY)
                    
                    # Prepare order parameters for this chunk
                    order_params = {
                        'tradingsymbol': tradingsymbol,
                        'exchange': 'NFO',
                        'transaction_type': transaction_type,
                        'quantity': chunk_qty,
                        'order_type': order_type,
                        'product': product,
                        'variety': 'amo' if use_amo else 'regular'
                    }
                    
                    # Add price for limit orders
                    if order_type == 'LIMIT' and price:
                        order_params['price'] = price
                    
                    logger.info(f"Placing iceberg chunk: {chunk_qty}/{quantity} - {order_params}")
                    
                    # Place the order chunk
                    order_id = self.kite.place_order(**order_params)
                    order_ids.append(order_id)
                    logger.info(f"Iceberg chunk placed. Order ID: {order_id}")
                    
                    remaining_qty -= chunk_qty
                    
                    # Small delay between orders to avoid rate limiting
                    if remaining_qty > 0:
                        import time
                        time.sleep(0.5)
                
                logger.info(f"All iceberg orders placed successfully. Order IDs: {order_ids}")
                return ','.join(map(str, order_ids))  # Return comma-separated order IDs
            else:
                # Single order within limit
                order_params = {
                    'tradingsymbol': tradingsymbol,
                    'exchange': 'NFO',
                    'transaction_type': transaction_type,
                    'quantity': quantity,
                    'order_type': order_type,
                    'product': product,
                    'variety': 'amo' if use_amo else 'regular'
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
                           expiry_date: datetime,
                           use_amo: bool = False) -> Dict:
        """
        Execute an iron condor strategy (main + hedge)
        
        Args:
            main_strike: Main leg strike price
            hedge_strike: Hedge leg strike price
            option_type: 'PE' or 'CE'
            lots: Number of lots
            expiry_date: Expiry date
            use_amo: Whether to place as AMO order
        
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
            
            # Determine order type based on AMO or market hours
            # Check if market is closed (after 3:30 PM or before 9:15 AM)
            current_time = datetime.now().time()
            market_open = datetime.strptime("09:15", "%H:%M").time()
            market_close = datetime.strptime("15:30", "%H:%M").time()
            
            is_market_closed = current_time < market_open or current_time > market_close
            
            # Use LIMIT orders if AMO is enabled OR if market is closed
            # (Market orders can't be placed after hours)
            order_type = 'LIMIT' if (use_amo or is_market_closed) else 'MARKET'
            
            if is_market_closed and not use_amo:
                logger.warning("Market is closed. Automatically using LIMIT orders for after-market placement.")
            
            # Get option prices if using LIMIT orders (AMO or after-market)
            hedge_price = None
            main_price = None
            
            if order_type == 'LIMIT':
                # Get current option prices for LIMIT orders using Kite API (works better for AMO)
                try:
                    # Generate Kite symbols
                    hedge_symbol = self.format_weekly_symbol(expiry_date, hedge_strike, option_type)
                    main_symbol = self.format_weekly_symbol(expiry_date, main_strike, option_type)
                    
                    # Get LTP from Kite API using quotes
                    try:
                        # Fetch quotes for both symbols
                        symbols = [f"NFO:{hedge_symbol}", f"NFO:{main_symbol}"]
                        quotes = self.kite.quote(symbols)
                        
                        # Extract hedge price
                        hedge_key = f"NFO:{hedge_symbol}"
                        if hedge_key in quotes:
                            hedge_ltp = quotes[hedge_key].get('last_price', 0)
                            if hedge_ltp > 0:
                                # For BUY orders, add 3% buffer to ensure execution in AMO
                                hedge_price = round(hedge_ltp * 1.03, 1)
                                logger.info(f"Kite Hedge LTP: {hedge_ltp}, AMO Limit Price: {hedge_price}")
                            else:
                                # FAIL LOUDLY - No dummy data
                                logger.error(f"CRITICAL: Hedge option LTP is 0 for {hedge_symbol}")
                                raise ValueError(f"Cannot place order: No price available for {hedge_symbol}")
                        else:
                            logger.error(f"CRITICAL: Could not get hedge quote from Kite for {hedge_symbol}")
                            raise ValueError(f"Cannot place order: Failed to fetch price for {hedge_symbol}")
                        
                        # Extract main price
                        main_key = f"NFO:{main_symbol}"
                        if main_key in quotes:
                            main_ltp = quotes[main_key].get('last_price', 0)
                            if main_ltp > 0:
                                # For SELL orders, reduce 2% buffer to ensure execution in AMO
                                main_price = round(main_ltp * 0.98, 1)
                                logger.info(f"Kite Main LTP: {main_ltp}, AMO Limit Price: {main_price}")
                            else:
                                # FAIL LOUDLY - No dummy data
                                logger.error(f"CRITICAL: Main option LTP is 0 for {main_symbol}")
                                raise ValueError(f"Cannot place order: No price available for {main_symbol}")
                        else:
                            logger.error(f"CRITICAL: Could not get main quote from Kite for {main_symbol}")
                            raise ValueError(f"Cannot place order: Failed to fetch price for {main_symbol}")
                            
                    except Exception as e:
                        logger.error(f"CRITICAL: Error getting quotes from Kite: {str(e)}")
                        # FAIL LOUDLY - No dummy data allowed
                        raise ValueError(f"Cannot place AMO order: Failed to fetch option prices from Kite API - {str(e)}")
                        
                except Exception as e:
                    logger.error(f"CRITICAL: Error fetching Kite quotes for AMO: {str(e)}")
                    # FAIL LOUDLY - No dummy data allowed
                    raise ValueError(f"Cannot place AMO order: Failed to initialize price fetching - {str(e)}")
            
            # Place hedge order first (BUY) for margin benefit
            logger.info(f"Placing hedge order: BUY {hedge_strike} {option_type} (AMO: {use_amo}, Type: {order_type})")
            hedge_order_id = self.place_option_order(
                strike=hedge_strike,
                option_type=option_type,
                transaction_type='BUY',
                quantity=quantity,
                expiry_date=expiry_date,
                order_type=order_type,
                price=hedge_price,
                use_amo=use_amo
            )
            results['hedge_order_id'] = hedge_order_id
            
            # Then place main order (SELL)
            logger.info(f"Placing main order: SELL {main_strike} {option_type} (AMO: {use_amo}, Type: {order_type})")
            main_order_id = self.place_option_order(
                strike=main_strike,
                option_type=option_type,
                transaction_type='SELL',
                quantity=quantity,
                expiry_date=expiry_date,
                order_type=order_type,
                price=main_price,
                use_amo=use_amo
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
            use_amo = webhook_data.get('use_amo', False)  # AMO flag from webhook
            
            # Load hedge configuration from user settings and select optimal hedge
            hedge_strike = None
            hedge_price = None
            try:
                import sqlite3
                conn = sqlite3.connect('data/trading_settings.db')
                cursor = conn.cursor()
                cursor.execute("SELECT hedge_method, hedge_offset, hedge_percent FROM TradeConfiguration WHERE user_id='default' AND config_name='default'")
                result = cursor.fetchone()
                
                hedge_method = 'offset'  # Default
                hedge_offset = 200
                hedge_percent = 30.0
                
                if result:
                    hedge_method = result[0]  # 'percentage' or 'offset'
                    hedge_offset = int(result[1])  # Points offset
                    hedge_percent = float(result[2])  # Percentage for hedge
                    
                logger.info(f"Hedge config: method={hedge_method}, offset={hedge_offset}, percent={hedge_percent}%")
                conn.close()
                
                # Use the hedge selection service for proper implementation
                from src.services.hedge_selection_service import HedgeSelectionService
                hedge_service = HedgeSelectionService()
                
                hedge_strike, hedge_price = hedge_service.select_hedge_strike(
                    main_strike=main_strike,
                    option_type=option_type,
                    expiry_date=expiry_date,
                    hedge_method=hedge_method,
                    hedge_offset=hedge_offset,
                    hedge_percent=hedge_percent
                )
                
            except Exception as e:
                logger.warning(f"Could not use hedge selection service: {e}, using fallback")
                # Simple fallback
                hedge_offset = 200
                if option_type == 'PE':
                    hedge_strike = main_strike - hedge_offset
                else:
                    hedge_strike = main_strike + hedge_offset
                hedge_price = None
            
            logger.info(f"Final hedge selection: Main={main_strike}, Hedge={hedge_strike}" + 
                       (f" @ Rs. {hedge_price}" if hedge_price else ""))
            
            # Execute the trade
            result = self.execute_iron_condor(
                main_strike=main_strike,
                hedge_strike=hedge_strike,
                option_type=option_type,
                lots=lots,
                expiry_date=expiry_date,
                use_amo=use_amo
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