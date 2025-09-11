from typing import Dict, List, Any, Optional
from datetime import datetime
import os
from breeze_connect import BreezeConnect
from .base_broker import (
    BaseBroker, Order, Position, Holdings, MarketQuote,
    OrderType, OrderSide, OrderStatus, ProductType
)

class BreezeBroker(BaseBroker):
    """Breeze/ICICI Direct broker implementation"""
    
    PRODUCT_TYPE_MAP = {
        ProductType.MIS: "margin",
        ProductType.CNC: "cash",
        ProductType.NRML: "futures"
    }
    
    ORDER_TYPE_MAP = {
        OrderType.MARKET: "market",
        OrderType.LIMIT: "limit",
        OrderType.STOP: "stoploss",
        OrderType.STOP_LIMIT: "stoploss"
    }
    
    def _validate_config(self):
        required_keys = ['api_key', 'api_secret', 'session_token']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config: {key}")
                
    def connect(self) -> bool:
        try:
            self.breeze = BreezeConnect(api_key=self.config['api_key'])
            self.breeze.generate_session(
                api_secret=self.config['api_secret'],
                session_token=self.config['session_token']
            )
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Breeze connection failed: {e}")
            return False
            
    def disconnect(self):
        self.is_connected = False
        
    def place_order(self, order: Order) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        is_valid, message = self.validate_order(order)
        if not is_valid:
            return {"status": "error", "message": message}
            
        try:
            response = self.breeze.place_order(
                stock_code=self._get_stock_code(order.symbol),
                exchange_code=self._get_exchange_code(order.symbol),
                product=self.PRODUCT_TYPE_MAP.get(order.product_type, "margin"),
                action="buy" if order.side == OrderSide.BUY else "sell",
                order_type=self.ORDER_TYPE_MAP.get(order.order_type, "market"),
                quantity=str(order.quantity),
                price=str(order.price) if order.price else "0",
                stoploss=str(order.trigger_price) if order.trigger_price else "0",
                validity="day",
                user_remark=order.tag or ""
            )
            
            if response.get('Status') == 200:
                return {
                    "status": "success",
                    "order_id": response.get('Success', {}).get('order_id'),
                    "message": response.get('Success', {}).get('message', 'Order placed')
                }
            else:
                return {
                    "status": "error",
                    "message": response.get('Error', 'Order placement failed')
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    def modify_order(self, order_id: str, order: Order) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.modify_order(
                order_id=order_id,
                quantity=str(order.quantity),
                price=str(order.price) if order.price else "0",
                stoploss=str(order.trigger_price) if order.trigger_price else "0"
            )
            
            if response.get('Status') == 200:
                return {"status": "success", "message": "Order modified"}
            else:
                return {"status": "error", "message": response.get('Error', 'Modification failed')}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.cancel_order(order_id=order_id)
            
            if response.get('Status') == 200:
                return {"status": "success", "message": "Order cancelled"}
            else:
                return {"status": "error", "message": response.get('Error', 'Cancellation failed')}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.get_order_detail(order_id=order_id)
            
            if response.get('Status') == 200:
                order_data = response.get('Success', [{}])[0]
                return {
                    "status": "success",
                    "order": self._parse_order(order_data)
                }
            else:
                return {"status": "error", "message": response.get('Error', 'Failed to get order')}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    def get_orders(self) -> List[Dict[str, Any]]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.get_order_list()
            
            if response.get('Status') == 200:
                orders = response.get('Success', [])
                return [self._parse_order(order) for order in orders]
            else:
                raise RuntimeError(f"Failed to get orders: {response.get('Error', 'Unknown error')}")
        except Exception as e:
            print(f"Error getting orders: {e}")
            raise RuntimeError(f"Failed to fetch orders: {str(e)}")
            
    def get_positions(self) -> List[Position]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.get_portfolio_positions()
            
            if response.get('Status') == 200:
                positions_data = response.get('Success', [])
                positions = []
                
                for pos in positions_data:
                    positions.append(Position(
                        symbol=pos.get('stock_code', ''),
                        quantity=int(pos.get('quantity', 0)),
                        product_type=self._map_product_type(pos.get('product', '')),
                        average_price=float(pos.get('average_price', 0)),
                        last_price=float(pos.get('ltp', 0)),
                        pnl=float(pos.get('realized_profit', 0)),
                        unrealized_pnl=float(pos.get('mtm', 0)),
                        realized_pnl=float(pos.get('realized_profit', 0))
                    ))
                    
                return positions
            else:
                raise RuntimeError(f"Failed to get positions: {response.get('Error', 'Unknown error')}")
        except Exception as e:
            print(f"Error getting positions: {e}")
            raise RuntimeError(f"Failed to fetch positions: {str(e)}")
            
    def get_holdings(self) -> List[Holdings]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.get_portfolio_holdings()
            
            if response.get('Status') == 200:
                holdings_data = response.get('Success', [])
                holdings = []
                
                for hold in holdings_data:
                    holdings.append(Holdings(
                        symbol=hold.get('stock_code', ''),
                        quantity=int(hold.get('quantity', 0)),
                        average_price=float(hold.get('average_price', 0)),
                        last_price=float(hold.get('ltp', 0)),
                        pnl=float(hold.get('gain_loss', 0)),
                        product=hold.get('product', '')
                    ))
                    
                return holdings
            else:
                raise RuntimeError(f"Failed to get holdings: {response.get('Error', 'Unknown error')}")
        except Exception as e:
            print(f"Error getting holdings: {e}")
            raise RuntimeError(f"Failed to fetch holdings: {str(e)}")
            
    def get_quote(self, symbol: str) -> MarketQuote:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.get_quotes(
                stock_code=self._get_stock_code(symbol),
                exchange_code=self._get_exchange_code(symbol)
            )
            
            if response.get('Status') == 200:
                quote_data = response.get('Success', [{}])[0]
                
                return MarketQuote(
                    symbol=symbol,
                    last_price=float(quote_data.get('ltp', 0)),
                    bid_price=float(quote_data.get('best_bid_price', 0)),
                    ask_price=float(quote_data.get('best_offer_price', 0)),
                    bid_quantity=int(quote_data.get('best_bid_quantity', 0)),
                    ask_quantity=int(quote_data.get('best_offer_quantity', 0)),
                    open=float(quote_data.get('open', 0)),
                    high=float(quote_data.get('high', 0)),
                    low=float(quote_data.get('low', 0)),
                    close=float(quote_data.get('close', 0)),
                    volume=int(quote_data.get('total_quantity_traded', 0)),
                    timestamp=datetime.now()
                )
            else:
                raise ValueError(f"Failed to get quote for {symbol}")
        except Exception as e:
            raise ValueError(f"Error getting quote: {e}")
            
    def get_historical_data(
        self, 
        symbol: str, 
        from_date: datetime, 
        to_date: datetime,
        interval: str = "5minute"
    ) -> List[Dict[str, Any]]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.get_historical_data_v2(
                interval=interval,
                from_date=from_date.strftime("%Y-%m-%d"),
                to_date=to_date.strftime("%Y-%m-%d"),
                stock_code=self._get_stock_code(symbol),
                exchange_code=self._get_exchange_code(symbol)
            )
            
            if response.get('Status') == 200:
                return response.get('Success', [])
            else:
                raise RuntimeError(f"Failed to get historical data: {response.get('Error', 'Unknown error')}")
        except Exception as e:
            print(f"Error getting historical data: {e}")
            raise RuntimeError(f"Failed to fetch historical data: {str(e)}")
            
    def get_margin(self) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.get_funds()
            
            if response.get('Status') == 200:
                funds = response.get('Success', {})
                return {
                    "available_margin": float(funds.get('available_balance', 0)),
                    "used_margin": float(funds.get('utilized_amount', 0)),
                    "total_margin": float(funds.get('limit_value', 0))
                }
            else:
                raise RuntimeError(f"Failed to get margin data: {response.get('Error', 'Unknown error')}")
        except Exception as e:
            print(f"Error getting margin: {e}")
            raise RuntimeError(f"Failed to fetch margin data: {str(e)}")
            
    def square_off_position(self, symbol: str, quantity: int = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Not connected to Breeze")
            
        try:
            response = self.breeze.square_off(
                stock_code=self._get_stock_code(symbol),
                exchange_code=self._get_exchange_code(symbol),
                quantity=str(quantity) if quantity else "0"
            )
            
            if response.get('Status') == 200:
                return {"status": "success", "message": "Position squared off"}
            else:
                return {"status": "error", "message": response.get('Error', 'Square off failed')}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    def convert_position(
        self, 
        symbol: str, 
        quantity: int,
        from_product: ProductType,
        to_product: ProductType
    ) -> Dict[str, Any]:
        return {"status": "error", "message": "Position conversion not supported in Breeze"}
        
    def _get_stock_code(self, symbol: str) -> str:
        parts = symbol.split(":")
        return parts[1] if len(parts) > 1 else symbol
        
    def _get_exchange_code(self, symbol: str) -> str:
        parts = symbol.split(":")
        if len(parts) > 1:
            exchange_map = {
                "NSE": "NSE",
                "NFO": "NFO",
                "BSE": "BSE"
            }
            return exchange_map.get(parts[0], "NSE")
        return "NSE"
        
    def _map_product_type(self, product: str) -> ProductType:
        product_map = {
            "margin": ProductType.MIS,
            "cash": ProductType.CNC,
            "futures": ProductType.NRML
        }
        return product_map.get(product.lower(), ProductType.MIS)
        
    def _parse_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "order_id": order_data.get('order_id', ''),
            "symbol": order_data.get('stock_code', ''),
            "quantity": int(order_data.get('quantity', 0)),
            "price": float(order_data.get('price', 0)),
            "status": order_data.get('status', ''),
            "order_type": order_data.get('order_type', ''),
            "product_type": order_data.get('product', ''),
            "side": order_data.get('action', ''),
            "timestamp": order_data.get('order_datetime', '')
        }