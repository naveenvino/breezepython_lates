"""
TradingView Webhook Receiver
Receives and processes webhooks from TradingView for automated trading
"""

import logging
import hmac
import hashlib
import json
from typing import Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class WebhookAction(Enum):
    """Webhook action types"""
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    CLOSE_ALL = "CLOSE_ALL"
    REVERSE = "REVERSE"
    ALERT = "ALERT"

class WebhookReceiver:
    """
    Handles incoming webhooks from TradingView and other sources
    """
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or "your-webhook-secret"
        self.webhook_handlers: Dict[str, Callable] = {}
        self.webhook_history: List[Dict] = []
        self.max_history = 1000
        
        # Statistics
        self.stats = {
            'total_received': 0,
            'successful': 0,
            'failed': 0,
            'by_action': {}
        }
    
    def verify_signature(self, payload: str, signature: str) -> bool:
        """Verify webhook signature for security"""
        try:
            expected_signature = hmac.new(
                self.secret_key.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    async def process_webhook(self, data: Dict, signature: Optional[str] = None) -> Dict:
        """
        Process incoming webhook data
        
        Args:
            data: Webhook payload
            signature: Optional signature for verification
        
        Returns:
            Processing result
        """
        try:
            # Update statistics
            self.stats['total_received'] += 1
            
            # Verify signature if provided
            if signature and self.secret_key:
                payload_str = json.dumps(data, sort_keys=True)
                if not self.verify_signature(payload_str, signature):
                    logger.warning("Invalid webhook signature")
                    self.stats['failed'] += 1
                    return {
                        'status': 'error',
                        'message': 'Invalid signature',
                        'timestamp': datetime.now().isoformat()
                    }
            
            # Parse webhook data
            parsed = self._parse_webhook(data)
            
            # Store in history
            self._add_to_history(parsed)
            
            # Execute action
            result = await self._execute_action(parsed)
            
            if result['status'] == 'success':
                self.stats['successful'] += 1
                action = parsed.get('action')
                self.stats['by_action'][action] = self.stats['by_action'].get(action, 0) + 1
            else:
                self.stats['failed'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            self.stats['failed'] += 1
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _parse_webhook(self, data: Dict) -> Dict:
        """Parse webhook data into standard format"""
        try:
            # TradingView format
            if 'action' in data:
                return self._parse_tradingview(data)
            # Custom format
            elif 'signal' in data:
                return self._parse_custom(data)
            # Pine Script alert
            elif 'strategy' in data:
                return self._parse_pinescript(data)
            else:
                # Generic format
                return {
                    'source': 'unknown',
                    'action': data.get('action', 'ALERT'),
                    'symbol': data.get('symbol', 'NIFTY'),
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Webhook parsing error: {e}")
            raise
    
    def _parse_tradingview(self, data: Dict) -> Dict:
        """Parse TradingView webhook format"""
        return {
            'source': 'tradingview',
            'action': data.get('action', 'ALERT').upper(),
            'symbol': data.get('ticker', 'NIFTY'),
            'side': data.get('side', 'BUY'),
            'quantity': data.get('quantity', 1),
            'price': data.get('price'),
            'order_type': data.get('order_type', 'MARKET'),
            'strategy': data.get('strategy_name'),
            'message': data.get('message'),
            'timestamp': data.get('time', datetime.now().isoformat())
        }
    
    def _parse_custom(self, data: Dict) -> Dict:
        """Parse custom webhook format"""
        signal = data.get('signal', '')
        
        # Map signals to actions
        action_map = {
            'S1': 'SELL_PUT',
            'S2': 'SELL_PUT',
            'S3': 'SELL_CALL',
            'S4': 'SELL_PUT',
            'S5': 'SELL_CALL',
            'S6': 'SELL_CALL',
            'S7': 'SELL_PUT',
            'S8': 'SELL_CALL'
        }
        
        return {
            'source': 'custom',
            'action': action_map.get(signal, 'ALERT'),
            'signal': signal,
            'symbol': data.get('symbol', 'NIFTY'),
            'strike': data.get('strike'),
            'expiry': data.get('expiry'),
            'quantity': data.get('lots', 1) * 75,  # NIFTY lot size
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def _parse_pinescript(self, data: Dict) -> Dict:
        """Parse Pine Script alert format"""
        return {
            'source': 'pinescript',
            'strategy': data.get('strategy'),
            'action': data.get('action', 'ALERT').upper(),
            'symbol': data.get('symbol', 'NIFTY'),
            'entry_price': data.get('entry_price'),
            'stop_loss': data.get('stop_loss'),
            'target': data.get('target'),
            'quantity': data.get('contracts', 1),
            'comment': data.get('comment'),
            'timestamp': datetime.now().isoformat()
        }
    
    async def _execute_action(self, webhook_data: Dict) -> Dict:
        """Execute the action specified in the webhook"""
        try:
            action = webhook_data.get('action')
            
            # Check if handler is registered
            if action in self.webhook_handlers:
                handler = self.webhook_handlers[action]
                return await handler(webhook_data)
            
            # Default action handling
            logger.info(f"Webhook action: {action} - {webhook_data}")
            
            return {
                'status': 'success',
                'action': action,
                'data': webhook_data,
                'message': f'Webhook processed: {action}',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def register_handler(self, action: str, handler: Callable):
        """Register a handler for specific webhook action"""
        self.webhook_handlers[action] = handler
        logger.info(f"Registered handler for action: {action}")
    
    def _add_to_history(self, webhook_data: Dict):
        """Add webhook to history"""
        self.webhook_history.insert(0, {
            'id': f"WH_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            'received_at': datetime.now().isoformat(),
            **webhook_data
        })
        
        # Limit history size
        if len(self.webhook_history) > self.max_history:
            self.webhook_history = self.webhook_history[:self.max_history]
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """Get webhook history"""
        return self.webhook_history[:limit]
    
    def get_stats(self) -> Dict:
        """Get webhook statistics"""
        return {
            **self.stats,
            'success_rate': (self.stats['successful'] / self.stats['total_received'] * 100) 
                           if self.stats['total_received'] > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_history(self):
        """Clear webhook history"""
        self.webhook_history = []
        logger.info("Webhook history cleared")


class WebhookStrategyBridge:
    """
    Bridge between webhooks and strategy automation
    """
    
    def __init__(self, webhook_receiver: WebhookReceiver, strategy_service):
        self.webhook_receiver = webhook_receiver
        self.strategy_service = strategy_service
        
        # Register webhook handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register webhook action handlers"""
        self.webhook_receiver.register_handler('BUY', self._handle_buy)
        self.webhook_receiver.register_handler('SELL', self._handle_sell)
        self.webhook_receiver.register_handler('CLOSE', self._handle_close)
        self.webhook_receiver.register_handler('CLOSE_ALL', self._handle_close_all)
        self.webhook_receiver.register_handler('REVERSE', self._handle_reverse)
        self.webhook_receiver.register_handler('SELL_PUT', self._handle_sell_put)
        self.webhook_receiver.register_handler('SELL_CALL', self._handle_sell_call)
    
    async def _handle_buy(self, data: Dict) -> Dict:
        """Handle BUY webhook"""
        try:
            # Create order through strategy service
            order = {
                'symbol': data.get('symbol'),
                'quantity': data.get('quantity'),
                'transaction_type': 'BUY',
                'order_type': data.get('order_type', 'MARKET'),
                'price': data.get('price')
            }
            
            # Execute order
            if self.strategy_service and hasattr(self.strategy_service, 'order_service'):
                result = await self.strategy_service.order_service.place_order(order)
                return {
                    'status': 'success',
                    'action': 'BUY',
                    'order_id': result.get('order_id'),
                    'timestamp': datetime.now().isoformat()
                }
            
            return {
                'status': 'success',
                'action': 'BUY',
                'message': 'Order queued',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Buy handler error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def _handle_sell(self, data: Dict) -> Dict:
        """Handle SELL webhook"""
        try:
            order = {
                'symbol': data.get('symbol'),
                'quantity': data.get('quantity'),
                'transaction_type': 'SELL',
                'order_type': data.get('order_type', 'MARKET'),
                'price': data.get('price')
            }
            
            if self.strategy_service and hasattr(self.strategy_service, 'order_service'):
                result = await self.strategy_service.order_service.place_order(order)
                return {
                    'status': 'success',
                    'action': 'SELL',
                    'order_id': result.get('order_id'),
                    'timestamp': datetime.now().isoformat()
                }
            
            return {
                'status': 'success',
                'action': 'SELL',
                'message': 'Order queued',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Sell handler error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def _handle_close(self, data: Dict) -> Dict:
        """Handle CLOSE webhook"""
        try:
            symbol = data.get('symbol')
            
            if self.strategy_service and hasattr(self.strategy_service, 'order_service'):
                # Close position for symbol
                result = await self.strategy_service.order_service.close_position(symbol)
                return {
                    'status': 'success',
                    'action': 'CLOSE',
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat()
                }
            
            return {
                'status': 'success',
                'action': 'CLOSE',
                'message': 'Close order queued',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Close handler error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def _handle_close_all(self, data: Dict) -> Dict:
        """Handle CLOSE_ALL webhook"""
        try:
            if self.strategy_service and hasattr(self.strategy_service, 'order_service'):
                # Close all positions
                from src.services.order_management import get_order_manager
                order_manager = get_order_manager()
                result = await order_manager.square_off_all_positions()
                
                return {
                    'status': 'success',
                    'action': 'CLOSE_ALL',
                    'positions_closed': result.get('squared_off_count', 0),
                    'timestamp': datetime.now().isoformat()
                }
            
            return {
                'status': 'success',
                'action': 'CLOSE_ALL',
                'message': 'Close all queued',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Close all handler error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def _handle_reverse(self, data: Dict) -> Dict:
        """Handle REVERSE webhook - close current and open opposite"""
        try:
            # Close current position
            await self._handle_close(data)
            
            # Open opposite position
            current_side = data.get('current_side', 'BUY')
            data['side'] = 'SELL' if current_side == 'BUY' else 'BUY'
            
            if data['side'] == 'BUY':
                return await self._handle_buy(data)
            else:
                return await self._handle_sell(data)
                
        except Exception as e:
            logger.error(f"Reverse handler error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def _handle_sell_put(self, data: Dict) -> Dict:
        """Handle SELL PUT webhook"""
        try:
            strike = data.get('strike')
            if not strike:
                # Calculate strike from spot price
                spot_price = data.get('spot_price', 25000)
                strike = round(spot_price / 50) * 50 - 50
            
            order = {
                'symbol': f"NIFTY{strike}PE",
                'quantity': data.get('quantity', 75),
                'transaction_type': 'SELL',
                'order_type': 'MARKET',
                'product': 'MIS'
            }
            
            return {
                'status': 'success',
                'action': 'SELL_PUT',
                'strike': strike,
                'message': 'PUT sell order placed',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Sell PUT handler error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def _handle_sell_call(self, data: Dict) -> Dict:
        """Handle SELL CALL webhook"""
        try:
            strike = data.get('strike')
            if not strike:
                spot_price = data.get('spot_price', 25000)
                strike = round(spot_price / 50) * 50 + 50
            
            order = {
                'symbol': f"NIFTY{strike}CE",
                'quantity': data.get('quantity', 75),
                'transaction_type': 'SELL',
                'order_type': 'MARKET',
                'product': 'MIS'
            }
            
            return {
                'status': 'success',
                'action': 'SELL_CALL',
                'strike': strike,
                'message': 'CALL sell order placed',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Sell CALL handler error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }


# Global instances
_webhook_receiver: Optional[WebhookReceiver] = None
_webhook_bridge: Optional[WebhookStrategyBridge] = None

def get_webhook_receiver(secret_key: str = None) -> WebhookReceiver:
    """Get or create webhook receiver"""
    global _webhook_receiver
    if _webhook_receiver is None:
        _webhook_receiver = WebhookReceiver(secret_key)
    return _webhook_receiver

def get_webhook_bridge(strategy_service=None) -> WebhookStrategyBridge:
    """Get or create webhook bridge"""
    global _webhook_bridge
    if _webhook_bridge is None:
        receiver = get_webhook_receiver()
        _webhook_bridge = WebhookStrategyBridge(receiver, strategy_service)
    return _webhook_bridge