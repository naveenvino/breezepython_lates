"""
Manage Stop Loss Use Case
Monitors positions for stop loss hits and executes exits
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from src.infrastructure.brokers.kite.kite_client import KiteClient
from src.infrastructure.brokers.kite.kite_order_service import KiteOrderService
from src.infrastructure.database.database_manager import DatabaseManager
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ManageStopLossUseCase:
    """
    Manages stop loss monitoring and execution
    """
    
    def __init__(self, kite_client: KiteClient, db_manager: DatabaseManager):
        self.kite_client = kite_client
        self.order_service = KiteOrderService(kite_client)
        self.db_manager = db_manager
        
    def execute(self) -> Dict[str, any]:
        """
        Check all positions for stop loss hits
        
        Returns:
            Result with stop loss actions taken
        """
        result = {
            'timestamp': datetime.now(),
            'positions_checked': 0,
            'stop_losses_hit': [],
            'errors': []
        }
        
        try:
            # Get active trades with their stop loss levels
            active_trades = self._get_active_trades_with_sl()
            result['positions_checked'] = len(active_trades)
            
            # Get current market prices
            symbols = []
            for trade in active_trades:
                if trade['main_symbol']:
                    symbols.append(f"NFO:{trade['main_symbol']}")
                if trade['hedge_symbol']:
                    symbols.append(f"NFO:{trade['hedge_symbol']}")
            
            if not symbols:
                return result
            
            # Get quotes for all symbols
            quotes = self.kite_client.get_quote(symbols)
            
            # Check each trade for stop loss
            for trade in active_trades:
                sl_hit, details = self._check_stop_loss(trade, quotes)
                
                if sl_hit:
                    logger.info(f"Stop loss hit for trade {trade['id']}: {details}")
                    
                    # Execute stop loss exit
                    exit_result = self._execute_stop_loss_exit(trade)
                    
                    result['stop_losses_hit'].append({
                        'trade_id': trade['id'],
                        'signal_type': trade['signal_type'],
                        'details': details,
                        'exit_orders': exit_result
                    })
                    
        except Exception as e:
            logger.error(f"Stop loss monitoring failed: {e}")
            result['errors'].append(str(e))
        
        return result
    
    def _get_active_trades_with_sl(self) -> List[Dict]:
        """Get active trades with stop loss information"""
        with self.db_manager.get_session() as session:
            result = session.execute(text("""
                SELECT 
                    t.id,
                    t.signal_type,
                    t.main_strike,
                    t.option_type,
                    t.direction,
                    t.main_order_id,
                    t.hedge_order_id,
                    p1.symbol as main_symbol,
                    p2.symbol as hedge_symbol
                FROM LiveTrades t
                LEFT JOIN LivePositions p1 ON p1.order_id = t.main_order_id
                LEFT JOIN LivePositions p2 ON p2.order_id = t.hedge_order_id
                WHERE t.status = 'ACTIVE'
            """))
            
            trades = []
            for row in result:
                trades.append({
                    'id': row[0],
                    'signal_type': row[1],
                    'main_strike': row[2],
                    'option_type': row[3],
                    'direction': row[4],
                    'main_order_id': row[5],
                    'hedge_order_id': row[6],
                    'main_symbol': row[7],
                    'hedge_symbol': row[8]
                })
            
            return trades
    
    def _check_stop_loss(self, trade: Dict, quotes: Dict) -> Tuple[bool, str]:
        """
        Check if stop loss is hit for a trade
        
        Stop loss is hit when the sold option reaches the strike price
        (i.e., when it goes in-the-money)
        
        Returns:
            Tuple of (is_hit, details)
        """
        main_symbol = trade['main_symbol']
        if not main_symbol:
            return False, "No main position found"
        
        quote_key = f"NFO:{main_symbol}"
        if quote_key not in quotes:
            return False, f"No quote found for {main_symbol}"
        
        quote = quotes[quote_key]
        last_price = quote.get('last_price', 0)
        
        # Get NIFTY spot price to check if option is ITM
        # For simplicity, we'll use a price-based stop loss
        # In practice, you might want to check actual NIFTY spot
        
        # For our strategy, stop loss is the main strike price
        stop_loss_price = float(trade['main_strike'])
        
        # Since we're selling options, we lose when price goes up
        # So we check if option price has reached a certain level
        # A rough approximation: if option price > 2% of strike, it's likely ITM
        stop_loss_threshold = stop_loss_price * 0.02  # 2% of strike
        
        if last_price > stop_loss_threshold:
            return True, f"Option price {last_price} exceeded threshold {stop_loss_threshold}"
        
        return False, f"Option price {last_price} below threshold {stop_loss_threshold}"
    
    def _execute_stop_loss_exit(self, trade: Dict) -> Dict[str, str]:
        """Execute stop loss exit for a trade"""
        exit_orders = {}
        
        try:
            # Get current positions
            positions = self.kite_client.get_positions()
            net_positions = {pos['tradingsymbol']: pos for pos in positions.get('net', [])}
            
            # Square off main position
            if trade['main_symbol'] in net_positions:
                pos = net_positions[trade['main_symbol']]
                if pos['quantity'] != 0:
                    order_id = self.order_service.square_off_position(
                        symbol=trade['main_symbol'],
                        quantity=abs(pos['quantity']),
                        is_buy_position=pos['quantity'] > 0
                    )
                    exit_orders['main'] = order_id
            
            # Square off hedge position
            if trade['hedge_symbol'] and trade['hedge_symbol'] in net_positions:
                pos = net_positions[trade['hedge_symbol']]
                if pos['quantity'] != 0:
                    order_id = self.order_service.square_off_position(
                        symbol=trade['hedge_symbol'],
                        quantity=abs(pos['quantity']),
                        is_buy_position=pos['quantity'] > 0
                    )
                    exit_orders['hedge'] = order_id
            
            # Update trade status in database
            self._update_trade_exit(trade['id'], 'STOPLOSS', exit_orders)
            
            logger.info(f"Stop loss exit completed for trade {trade['id']}: {exit_orders}")
            
        except Exception as e:
            logger.error(f"Stop loss exit failed for trade {trade['id']}: {e}")
            raise
        
        return exit_orders
    
    def _update_trade_exit(self, trade_id: str, exit_reason: str, exit_orders: Dict):
        """Update trade record with exit information"""
        with self.db_manager.get_session() as session:
            # Get final P&L from positions before updating
            pnl = self._calculate_trade_pnl(trade_id)
            
            query = text("""
                UPDATE LiveTrades 
                SET exit_time = :exit_time,
                    exit_reason = :exit_reason,
                    status = 'CLOSED',
                    pnl = :pnl,
                    exit_main_order_id = :exit_main_order,
                    exit_hedge_order_id = :exit_hedge_order
                WHERE id = :trade_id
            """)
            
            session.execute(query, {
                'trade_id': trade_id,
                'exit_time': datetime.now(),
                'exit_reason': exit_reason,
                'pnl': pnl,
                'exit_main_order': exit_orders.get('main'),
                'exit_hedge_order': exit_orders.get('hedge')
            })
            session.commit()
    
    def _calculate_trade_pnl(self, trade_id: str) -> float:
        """Calculate total P&L for a trade"""
        try:
            # Get position P&L from Kite
            positions = self.order_service.get_position_pnl()
            return positions.get('total_pnl', 0.0)
        except:
            return 0.0
    
    def get_stop_loss_summary(self) -> Dict[str, any]:
        """Get summary of stop losses hit today"""
        with self.db_manager.get_session() as session:
            result = session.execute(text("""
                SELECT 
                    COUNT(*) as total_sl_hits,
                    SUM(pnl) as total_sl_loss
                FROM LiveTrades
                WHERE exit_reason = 'STOPLOSS'
                AND CAST(exit_time AS DATE) = CAST(GETDATE() AS DATE)
            """))
            
            row = result.fetchone()
            
            return {
                'stop_losses_hit_today': row[0] or 0,
                'total_stop_loss_amount': row[1] or 0.0
            }