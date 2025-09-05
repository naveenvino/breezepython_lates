"""
TradingView Webhook Service - Complete webhook to trade execution
"""

import json
import logging
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import pyodbc

logger = logging.getLogger(__name__)

class SignalAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    CLOSE_ALL = "CLOSE_ALL"

@dataclass
class TradingViewSignal:
    """TradingView alert signal structure"""
    signal_type: str  # S1-S8
    action: SignalAction
    symbol: str
    strike: Optional[int]
    option_type: Optional[str]  # CE or PE
    quantity: int
    price: Optional[float]
    stop_loss: Optional[float]
    target: Optional[float]
    comment: str
    timestamp: datetime

class TradingViewWebhookService:
    """Handles TradingView webhook signals and converts to trades"""
    
    def __init__(self, trading_service=None, risk_service=None):
        self.trading_service = trading_service
        self.risk_service = risk_service
        self.webhook_secret = "your_webhook_secret_key"  # Should be in .env
        self.active_signals = {}
        self.signal_history = []
        self.conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=(localdb)\\mssqllocaldb;"
            "DATABASE=KiteConnectApi;"
            "Trusted_Connection=yes;"
        )
        
        # Signal to action mapping
        self.signal_config = {
            'S1': {'action': 'SELL', 'option': 'PE', 'name': 'Bear Trap'},
            'S2': {'action': 'SELL', 'option': 'PE', 'name': 'Support Hold'},
            'S3': {'action': 'SELL', 'option': 'CE', 'name': 'Resistance Hold'},
            'S4': {'action': 'SELL', 'option': 'PE', 'name': 'Bias Failure Bull'},
            'S5': {'action': 'SELL', 'option': 'CE', 'name': 'Bias Failure Bear'},
            'S6': {'action': 'SELL', 'option': 'CE', 'name': 'Weakness Confirmed'},
            'S7': {'action': 'SELL', 'option': 'PE', 'name': 'Breakout Confirmed'},
            'S8': {'action': 'SELL', 'option': 'CE', 'name': 'Breakdown Confirmed'}
        }
    
    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """Verify webhook signature for security"""
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def process_webhook(self, data: Dict, headers: Dict) -> Dict:
        """Process incoming TradingView webhook"""
        try:
            # Log webhook receipt
            self._log_webhook(data, headers)
            
            # Parse signal
            signal = self._parse_tradingview_alert(data)
            if not signal:
                return {'success': False, 'message': 'Invalid signal format'}
            
            # Save to database
            self._save_webhook_signal(signal)
            
            # Check risk limits before processing
            if self.risk_service:
                risk_check = self.risk_service.check_position_entry(
                    signal.signal_type,
                    signal.quantity,
                    signal.price or 100
                )
                
                if risk_check[0].value == 'block':
                    logger.warning(f"Signal blocked by risk management: {risk_check[1]}")
                    return {
                        'success': False,
                        'message': f'Risk check failed: {risk_check[1]}',
                        'signal': signal.signal_type
                    }
            
            # Execute trade based on signal
            result = await self._execute_signal_trade(signal)
            
            return result
            
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def _parse_tradingview_alert(self, data: Dict) -> Optional[TradingViewSignal]:
        """Parse TradingView alert into signal object"""
        try:
            # Expected format from TradingView:
            # {
            #   "signal": "S1",
            #   "action": "buy" or "sell",
            #   "symbol": "NIFTY",
            #   "price": "{{close}}",
            #   "volume": "{{volume}}",
            #   "comment": "{{strategy.order.comment}}"
            # }
            
            signal_type = data.get('signal', '').upper()
            
            # Validate signal type
            if signal_type not in self.signal_config:
                logger.warning(f"Unknown signal type: {signal_type}")
                return None
            
            # Get signal configuration
            config = self.signal_config[signal_type]
            
            # Determine action
            action_str = data.get('action', '').upper()
            if action_str in ['BUY', 'LONG']:
                action = SignalAction.BUY
            elif action_str in ['SELL', 'SHORT']:
                action = SignalAction.SELL
            elif action_str in ['CLOSE', 'EXIT']:
                action = SignalAction.CLOSE
            else:
                # Use configured action for signal
                action = SignalAction.SELL if config['action'] == 'SELL' else SignalAction.BUY
            
            # Parse symbol and price
            symbol = data.get('symbol', 'NIFTY').upper()
            try:
                price = float(data.get('price', 0))
            except:
                price = None
            
            # Calculate strike price (ATM)
            if price:
                strike = int(round(price / 50) * 50)
            else:
                strike = None
            
            # Default quantity (in lots)
            quantity = int(data.get('quantity', 10))
            
            # Create signal object
            signal = TradingViewSignal(
                signal_type=signal_type,
                action=action,
                symbol=symbol,
                strike=strike,
                option_type=config['option'],
                quantity=quantity,
                price=price,
                stop_loss=data.get('stop_loss'),
                target=data.get('target'),
                comment=data.get('comment', ''),
                timestamp=datetime.now()
            )
            
            logger.info(f"Parsed signal: {signal_type} - {config['name']} - {action.value}")
            return signal
            
        except Exception as e:
            logger.error(f"Error parsing TradingView alert: {e}")
            return None
    
    async def _execute_signal_trade(self, signal: TradingViewSignal) -> Dict:
        """Execute trade based on signal"""
        try:
            if not self.trading_service:
                return {
                    'success': False,
                    'message': 'Trading service not available'
                }
            
            # Check if closing position
            if signal.action == SignalAction.CLOSE:
                return await self._close_signal_position(signal)
            
            if signal.action == SignalAction.CLOSE_ALL:
                return await self._close_all_positions()
            
            # Build order request
            from src.services.trading_execution_service import OrderRequest, OrderSide, OrderType, ProductType
            
            # Create option symbol
            expiry = self._get_current_expiry()
            option_symbol = f"{signal.symbol}{expiry}{signal.strike}{signal.option_type}"
            
            # Determine order side (we're selling options)
            order_side = OrderSide.SELL
            
            # Calculate quantity (lots to quantity)
            total_quantity = signal.quantity * 75  # 75 qty per lot for NIFTY
            
            # Create order request
            order_request = OrderRequest(
                symbol=option_symbol,
                side=order_side,
                quantity=total_quantity,
                order_type=OrderType.MARKET,
                product_type=ProductType.OPTIONS,
                stop_loss=signal.strike,  # Use strike as stop loss
                target=signal.target or 100,  # Default 100 points target
                trailing_stop=0
            )
            
            # Place order
            response = await self.trading_service.place_order(order_request)
            
            if response.status == 'SUCCESS':
                # Track active signal
                self.active_signals[signal.signal_type] = {
                    'signal': signal,
                    'order_id': response.order_id,
                    'timestamp': datetime.now()
                }
                
                # Place hedge order (30% quantity)
                await self.trading_service.place_hedge_order(
                    response.order_id,
                    hedge_percentage=30
                )
                
                # Update risk management
                if self.risk_service:
                    self.risk_service.add_position(
                        position_id=response.order_id,
                        signal_type=signal.signal_type,
                        quantity=signal.quantity,
                        price=signal.price or 100
                    )
                
                logger.info(f"Signal trade executed: {signal.signal_type} - Order ID: {response.order_id}")
                
                return {
                    'success': True,
                    'message': f'Trade executed for signal {signal.signal_type}',
                    'order_id': response.order_id,
                    'signal': signal.signal_type
                }
            else:
                return {
                    'success': False,
                    'message': response.message,
                    'signal': signal.signal_type
                }
                
        except Exception as e:
            logger.error(f"Error executing signal trade: {e}")
            return {
                'success': False,
                'message': str(e),
                'signal': signal.signal_type
            }
    
    async def _close_signal_position(self, signal: TradingViewSignal) -> Dict:
        """Close position for specific signal"""
        try:
            if signal.signal_type not in self.active_signals:
                return {
                    'success': False,
                    'message': f'No active position for signal {signal.signal_type}'
                }
            
            active = self.active_signals[signal.signal_type]
            order_id = active['order_id']
            
            # Square off position
            from src.services.trading_execution_service import OrderRequest, OrderSide, OrderType, ProductType
            
            # Create opposite order to square off
            square_off_request = OrderRequest(
                symbol=active['signal'].symbol,
                side=OrderSide.BUY,  # Opposite of original SELL
                quantity=active['signal'].quantity * 75,
                order_type=OrderType.MARKET,
                product_type=ProductType.OPTIONS
            )
            
            response = await self.trading_service.place_order(square_off_request)
            
            if response.status == 'SUCCESS':
                # Remove from active signals
                del self.active_signals[signal.signal_type]
                
                return {
                    'success': True,
                    'message': f'Position closed for signal {signal.signal_type}',
                    'order_id': response.order_id
                }
            
            return {
                'success': False,
                'message': response.message
            }
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    async def _close_all_positions(self) -> Dict:
        """Close all active positions"""
        try:
            if self.trading_service:
                responses = await self.trading_service.square_off_all()
                
                # Clear active signals
                self.active_signals.clear()
                
                return {
                    'success': True,
                    'message': f'Closed {len(responses)} positions',
                    'closed_count': len(responses)
                }
            
            return {
                'success': False,
                'message': 'Trading service not available'
            }
            
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def _get_current_expiry(self) -> str:
        """Get current weekly expiry date"""
        from datetime import datetime, timedelta
        
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        
        if days_until_thursday == 0 and today.hour >= 15:
            days_until_thursday = 7
        
        expiry = today + timedelta(days=days_until_thursday)
        return expiry.strftime("%d%b%y").upper()
    
    def _save_webhook_signal(self, signal: TradingViewSignal):
        """Save webhook signal to database"""
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO WebhookSignals 
                (source, signal_type, symbol, action, price, quantity, raw_data, processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'TradingView',
                signal.signal_type,
                signal.symbol,
                signal.action.value,
                signal.price,
                signal.quantity,
                json.dumps({
                    'strike': signal.strike,
                    'option_type': signal.option_type,
                    'comment': signal.comment
                }),
                False
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving webhook signal: {e}")
    
    def _log_webhook(self, data: Dict, headers: Dict):
        """Log webhook for audit trail"""
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO TradingLogs (log_type, message, details)
                VALUES (?, ?, ?)
            """, (
                'WEBHOOK_RECEIVED',
                f"TradingView webhook: {data.get('signal', 'Unknown')}",
                json.dumps({
                    'data': data,
                    'headers': dict(headers)
                })
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging webhook: {e}")
    
    def get_active_signals(self) -> Dict:
        """Get all active signal positions"""
        return self.active_signals
    
    def get_signal_history(self, limit: int = 50) -> list:
        """Get webhook signal history from database"""
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT TOP (?) 
                    signal_id, source, signal_type, symbol, action, 
                    price, quantity, processed, received_at
                FROM WebhookSignals
                ORDER BY received_at DESC
            """, (limit,))
            
            signals = []
            for row in cursor.fetchall():
                signals.append({
                    'id': row[0],
                    'source': row[1],
                    'signal': row[2],
                    'symbol': row[3],
                    'action': row[4],
                    'price': row[5],
                    'quantity': row[6],
                    'processed': row[7],
                    'timestamp': row[8]
                })
            
            conn.close()
            return signals
            
        except Exception as e:
            logger.error(f"Error fetching signal history: {e}")
            return []

# Singleton instance
_webhook_service = None

def get_webhook_service(trading_service=None, risk_service=None):
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = TradingViewWebhookService(trading_service, risk_service)
    return _webhook_service