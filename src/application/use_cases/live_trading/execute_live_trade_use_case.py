"""
Execute Live Trade Use Case
Executes trades on Kite based on signals from the signal evaluator
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
from uuid import uuid4

from src.domain.value_objects.signal_types import SignalResult
from src.infrastructure.brokers.kite.kite_client import KiteClient
from src.infrastructure.brokers.kite.kite_order_service import KiteOrderService
from src.infrastructure.services.signal_to_kite_converter import SignalToKiteOrderConverter
from src.infrastructure.database.database_manager import DatabaseManager
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ExecuteLiveTradeUseCase:
    """
    Executes live trades based on signals
    """
    
    def __init__(self, kite_client: KiteClient, db_manager: DatabaseManager):
        self.kite_client = kite_client
        self.order_service = KiteOrderService(kite_client)
        self.signal_converter = SignalToKiteOrderConverter(kite_client)
        self.db_manager = db_manager
        
        # Trading configuration
        self.enabled = False  # Safety switch
        self.lot_size = 75
        self.num_lots = 10
        self.use_hedging = True
        self.max_positions = 1  # Max concurrent positions
        
    def execute(self, signal: SignalResult, current_spot: float) -> Dict[str, any]:
        """
        Execute a live trade based on signal
        
        Args:
            signal: Signal from evaluator
            current_spot: Current NIFTY spot price
            
        Returns:
            Trade execution result
        """
        result = {
            'success': False,
            'signal_type': signal.signal_type,
            'message': '',
            'trade_id': None,
            'orders': {}
        }
        
        # Safety checks
        if not self.enabled:
            result['message'] = "Live trading is disabled"
            return result
        
        if signal.signal_type == "NO_SIGNAL":
            result['message'] = "No signal to execute"
            return result
        
        # Check if we already have open positions
        if not self._can_take_new_position():
            result['message'] = "Maximum positions limit reached"
            return result
        
        # Check market hours
        if not self._is_market_open():
            result['message'] = "Market is closed"
            return result
        
        try:
            # Convert signal to order parameters
            order_params = self.signal_converter.convert_signal_to_order_params(
                signal=signal,
                current_spot=current_spot,
                use_hedging=self.use_hedging
            )
            
            # Validate order parameters
            is_valid, error_msg = self.signal_converter.validate_order_params(order_params)
            if not is_valid:
                result['message'] = f"Invalid order parameters: {error_msg}"
                return result
            
            # Create trade record in database
            trade_id = self._create_trade_record(signal, order_params)
            result['trade_id'] = trade_id
            
            # Execute the trade
            if self.use_hedging and 'hedge_position' in order_params:
                # Place spread order
                main_symbol = order_params['main_position']['symbol']
                hedge_symbol = order_params['hedge_position']['symbol']
                quantity = self.num_lots * self.lot_size
                
                main_order_id, hedge_order_id = self.order_service.place_option_spread(
                    main_symbol=main_symbol,
                    hedge_symbol=hedge_symbol,
                    quantity=quantity,
                    tag=signal.signal_type
                )
                
                result['orders'] = {
                    'main': main_order_id,
                    'hedge': hedge_order_id
                }
                
                # Update trade record with order IDs
                self._update_trade_orders(trade_id, main_order_id, hedge_order_id)
                
            else:
                # Place single order
                main_pos = order_params['main_position']
                quantity = self.num_lots * self.lot_size
                
                order_id = self.order_service.place_option_order(
                    symbol=main_pos['symbol'],
                    transaction_type=self.order_service.TransactionType.SELL,
                    quantity=quantity,
                    tag=signal.signal_type
                )
                
                result['orders'] = {'main': order_id}
                self._update_trade_orders(trade_id, order_id)
            
            result['success'] = True
            result['message'] = f"Trade executed successfully for signal {signal.signal_type}"
            
            logger.info(f"Live trade executed: {result}")
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            result['message'] = f"Trade execution failed: {str(e)}"
            
            # Mark trade as failed in database
            if result['trade_id']:
                self._mark_trade_failed(result['trade_id'], str(e))
        
        return result
    
    def _can_take_new_position(self) -> bool:
        """Check if we can take a new position"""
        try:
            positions = self.kite_client.get_positions()
            net_positions = positions.get('net', [])
            
            # Count open option positions
            open_positions = sum(1 for pos in net_positions 
                               if pos['exchange'] == 'NFO' and pos['quantity'] != 0)
            
            return open_positions < self.max_positions
        except Exception as e:
            logger.error(f"Error checking positions: {e}")
            return False
    
    def _is_market_open(self) -> bool:
        """Check if market is open for trading"""
        now = datetime.now()
        
        # Market hours: 9:15 AM to 3:30 PM
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        # Check weekday (Monday = 0, Friday = 4)
        if now.weekday() > 4:  # Weekend
            return False
        
        return market_open <= now <= market_close
    
    def _create_trade_record(self, signal: SignalResult, order_params: Dict) -> str:
        """Create a trade record in database"""
        trade_id = str(uuid4())
        
        with self.db_manager.get_session() as session:
            query = text("""
                INSERT INTO LiveTrades 
                (id, signal_type, entry_time, status, main_strike, hedge_strike, 
                 option_type, direction, created_at)
                VALUES 
                (:id, :signal_type, :entry_time, :status, :main_strike, :hedge_strike,
                 :option_type, :direction, GETDATE())
            """)
            
            main_pos = order_params['main_position']
            hedge_strike = order_params.get('hedge_position', {}).get('strike')
            
            session.execute(query, {
                'id': trade_id,
                'signal_type': signal.signal_type,
                'entry_time': datetime.now(),
                'status': 'PENDING',
                'main_strike': main_pos['strike'],
                'hedge_strike': hedge_strike,
                'option_type': main_pos['option_type'],
                'direction': signal.direction.value
            })
            session.commit()
        
        return trade_id
    
    def _update_trade_orders(self, trade_id: str, main_order_id: str, 
                           hedge_order_id: Optional[str] = None):
        """Update trade record with order IDs"""
        with self.db_manager.get_session() as session:
            query = text("""
                UPDATE LiveTrades 
                SET main_order_id = :main_order_id,
                    hedge_order_id = :hedge_order_id,
                    status = 'ACTIVE'
                WHERE id = :trade_id
            """)
            
            session.execute(query, {
                'trade_id': trade_id,
                'main_order_id': main_order_id,
                'hedge_order_id': hedge_order_id
            })
            session.commit()
    
    def _mark_trade_failed(self, trade_id: str, error_message: str):
        """Mark a trade as failed"""
        with self.db_manager.get_session() as session:
            query = text("""
                UPDATE LiveTrades 
                SET status = 'FAILED',
                    error_message = :error_message
                WHERE id = :trade_id
            """)
            
            session.execute(query, {
                'trade_id': trade_id,
                'error_message': error_message[:500]  # Limit error message length
            })
            session.commit()
    
    def enable_trading(self):
        """Enable live trading"""
        self.enabled = True
        logger.info("Live trading enabled")
    
    def disable_trading(self):
        """Disable live trading"""
        self.enabled = False
        logger.info("Live trading disabled")