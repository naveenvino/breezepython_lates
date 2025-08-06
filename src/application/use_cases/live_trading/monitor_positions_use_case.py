"""
Monitor Positions Use Case
Monitors live positions and handles expiry day square-off
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, time
from src.infrastructure.brokers.kite.kite_client import KiteClient
from src.infrastructure.brokers.kite.kite_order_service import KiteOrderService
from src.infrastructure.database.database_manager import DatabaseManager
from sqlalchemy import text

logger = logging.getLogger(__name__)

class MonitorPositionsUseCase:
    """
    Monitors live positions and manages automatic square-offs
    """
    
    def __init__(self, kite_client: KiteClient, db_manager: DatabaseManager):
        self.kite_client = kite_client
        self.order_service = KiteOrderService(kite_client)
        self.db_manager = db_manager
        
        # Configuration
        self.expiry_square_off_time = time(15, 15)  # 3:15 PM
        self.last_entry_time = time(15, 0)  # No new positions after 3 PM on expiry
        
    def execute(self) -> Dict[str, any]:
        """
        Monitor positions and take necessary actions
        
        Returns:
            Monitoring result with actions taken
        """
        result = {
            'timestamp': datetime.now(),
            'positions': [],
            'actions_taken': [],
            'total_pnl': 0.0
        }
        
        try:
            # Get current positions
            positions_data = self.kite_client.get_positions()
            net_positions = positions_data.get('net', [])
            
            # Filter option positions
            option_positions = [
                pos for pos in net_positions 
                if pos['exchange'] == 'NFO' and pos['quantity'] != 0
            ]
            
            # Process each position
            for position in option_positions:
                pos_info = self._process_position(position)
                result['positions'].append(pos_info)
                result['total_pnl'] += pos_info['pnl']
            
            # Check for expiry day square-off
            if self._should_square_off_expiry():
                logger.info("Expiry day square-off time reached")
                square_off_result = self._execute_expiry_square_off()
                result['actions_taken'].append({
                    'action': 'EXPIRY_SQUARE_OFF',
                    'time': datetime.now(),
                    'orders': square_off_result
                })
            
            # Update database with current status
            self._update_position_status(result['positions'])
            
        except Exception as e:
            logger.error(f"Position monitoring failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def _process_position(self, position: Dict) -> Dict:
        """Process individual position data"""
        return {
            'symbol': position['tradingsymbol'],
            'quantity': position['quantity'],
            'average_price': position['average_price'],
            'last_price': position['last_price'],
            'pnl': position.get('pnl', 0.0),
            'unrealised_pnl': position.get('unrealised', 0.0),
            'realised_pnl': position.get('realised', 0.0),
            'is_buy': position['quantity'] > 0,
            'product': position['product']
        }
    
    def _should_square_off_expiry(self) -> bool:
        """Check if it's time for expiry day square-off"""
        now = datetime.now()
        
        # Check if today is Thursday (expiry day)
        if now.weekday() != 3:  # Not Thursday
            return False
        
        # Check if it's past square-off time
        return now.time() >= self.expiry_square_off_time
    
    def _execute_expiry_square_off(self) -> List[str]:
        """Execute expiry day square-off for all positions"""
        try:
            order_ids = self.order_service.square_off_all_positions()
            
            # Update trades in database
            with self.db_manager.get_session() as session:
                query = text("""
                    UPDATE LiveTrades 
                    SET exit_time = :exit_time,
                        exit_reason = 'EXPIRY_SQUAREOFF',
                        status = 'CLOSED'
                    WHERE status = 'ACTIVE'
                """)
                
                session.execute(query, {'exit_time': datetime.now()})
                session.commit()
            
            logger.info(f"Expiry square-off completed. Orders: {order_ids}")
            return order_ids
            
        except Exception as e:
            logger.error(f"Expiry square-off failed: {e}")
            raise
    
    def _update_position_status(self, positions: List[Dict]):
        """Update position status in database"""
        try:
            with self.db_manager.get_session() as session:
                # Clear existing positions
                session.execute(text("DELETE FROM LivePositions"))
                
                # Insert current positions
                for pos in positions:
                    query = text("""
                        INSERT INTO LivePositions 
                        (symbol, quantity, average_price, current_price, pnl, updated_at)
                        VALUES 
                        (:symbol, :quantity, :average_price, :current_price, :pnl, GETDATE())
                    """)
                    
                    session.execute(query, {
                        'symbol': pos['symbol'],
                        'quantity': pos['quantity'],
                        'average_price': pos['average_price'],
                        'current_price': pos['last_price'],
                        'pnl': pos['pnl']
                    })
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update position status: {e}")
    
    def can_take_new_positions(self) -> bool:
        """Check if new positions can be taken"""
        now = datetime.now()
        
        # No new positions after 3 PM on expiry day
        if now.weekday() == 3 and now.time() >= self.last_entry_time:
            return False
        
        return True
    
    def get_active_trades(self) -> List[Dict]:
        """Get all active trades from database"""
        with self.db_manager.get_session() as session:
            result = session.execute(text("""
                SELECT id, signal_type, entry_time, main_strike, hedge_strike,
                       option_type, direction, main_order_id, hedge_order_id
                FROM LiveTrades
                WHERE status = 'ACTIVE'
                ORDER BY entry_time DESC
            """))
            
            trades = []
            for row in result:
                trades.append({
                    'id': row[0],
                    'signal_type': row[1],
                    'entry_time': row[2],
                    'main_strike': row[3],
                    'hedge_strike': row[4],
                    'option_type': row[5],
                    'direction': row[6],
                    'main_order_id': row[7],
                    'hedge_order_id': row[8]
                })
            
            return trades