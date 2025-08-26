"""
Live Trading Execution Engine
Handles real-time strategy execution with complete order and position management
"""
import asyncio
import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json
import os
from dataclasses import dataclass, asdict
from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from decimal import Decimal

from src.infrastructure.database.strategy_models import (
    TradingStrategy, StrategyExecution, StrategyStatus, StrategyType
)
from src.domain.value_objects import SignalType
from src.services.breeze_websocket_live import get_breeze_websocket
from src.infrastructure.brokers.breeze.breeze_adapter import BreezeAdapter
from breeze_connect import BreezeConnect
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    PENDING = "pending"
    PLACED = "placed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXECUTED = "executed"
    PARTIAL = "partial"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    SL = "stoploss"
    SL_MARKET = "stoploss-market"

@dataclass
class Position:
    strategy_id: int
    execution_id: int
    symbol: str
    strike: int
    quantity: int
    entry_price: float
    current_price: float
    pnl: float
    is_hedge: bool
    order_id: Optional[str] = None
    entry_time: Optional[datetime] = None
    
    @property
    def mtm(self) -> float:
        """Mark to Market calculation"""
        return (self.current_price - self.entry_price) * self.quantity

@dataclass
class OrderRequest:
    strategy_id: int
    symbol: str
    strike: int
    order_type: str
    quantity: int
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    is_hedge: bool = False
    tag: Optional[str] = None

class LiveTradingExecutor:
    def __init__(self):
        self.engine = create_engine(
            f"mssql+pyodbc://{os.getenv('DB_SERVER')}/{os.getenv('DB_NAME')}?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes"
        )
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Initialize Breeze connection
        self.breeze = BreezeConnect(api_key=os.getenv('BREEZE_API_KEY'))
        self.breeze.generate_session(
            api_secret=os.getenv('BREEZE_API_SECRET'),
            session_token=os.getenv('BREEZE_API_SESSION')
        )
        
        # WebSocket for real-time data
        self.websocket = get_breeze_websocket()
        
        # Active positions and orders
        self.positions: Dict[int, List[Position]] = {}  # strategy_id -> positions
        self.open_orders: Dict[str, OrderRequest] = {}  # order_id -> order
        self.active_strategies: Dict[int, TradingStrategy] = {}
        self.signal_subscriptions: Dict[str, List[int]] = {}  # signal -> strategy_ids
        
        # Market timings
        self.market_open = time(9, 15)
        self.market_close = time(15, 30)
        self.square_off_time = time(15, 15)
        
        # Monitoring flags
        self.is_running = False
        self.monitoring_task = None
        
        # Audit log
        self.audit_logs = []
        
    async def start(self):
        """Start the live trading engine"""
        if self.is_running:
            logger.warning("Trading engine already running")
            return
            
        self.is_running = True
        logger.info("Starting Live Trading Execution Engine")
        
        # Load deployed strategies
        await self.load_deployed_strategies()
        
        # Start monitoring tasks
        self.monitoring_task = asyncio.create_task(self.monitor_loop())
        
        # Subscribe to market data
        await self.subscribe_market_data()
        
        self.audit_log("SYSTEM", "Live Trading Engine started")
        return {"status": "started", "strategies": len(self.active_strategies)}
    
    async def stop(self):
        """Stop the trading engine"""
        self.is_running = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            
        # Square off all positions if market is open
        if self.is_market_open():
            await self.square_off_all_positions("ENGINE_STOP")
            
        self.audit_log("SYSTEM", "Live Trading Engine stopped")
        return {"status": "stopped"}
    
    async def load_deployed_strategies(self):
        """Load all deployed strategies from database"""
        try:
            strategies = self.session.query(TradingStrategy).filter(
                TradingStrategy.status == StrategyStatus.DEPLOYED
            ).all()
            
            for strategy in strategies:
                self.active_strategies[strategy.id] = strategy
                
                # Subscribe to signals
                for signal in strategy.signals:
                    if signal not in self.signal_subscriptions:
                        self.signal_subscriptions[signal] = []
                    self.signal_subscriptions[signal].append(strategy.id)
                    
            logger.info(f"Loaded {len(strategies)} deployed strategies")
            
        except Exception as e:
            logger.error(f"Error loading strategies: {e}")
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                # Check for signals
                await self.check_signals()
                
                # Update positions
                await self.update_positions()
                
                # Check risk management
                await self.check_risk_management()
                
                # Check market timing
                await self.check_market_timing()
                
                # Save performance metrics
                await self.update_performance_metrics()
                
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)
    
    async def check_signals(self):
        """Check for trading signals"""
        try:
            # Get current signals from signal detector
            from src.domain.services.signal_evaluator import SignalEvaluator
            evaluator = SignalEvaluator()
            
            # Get latest market data
            spot_price = self.websocket.get_spot_price()
            if not spot_price:
                return
                
            # Evaluate all signals
            current_time = datetime.now()
            
            # Check each signal type
            for signal_type in SignalType:
                signal_code = signal_type.value
                
                if signal_code not in self.signal_subscriptions:
                    continue
                    
                # Check if signal is triggered (you'd implement actual logic here)
                is_triggered = await self.evaluate_signal(signal_type, spot_price)
                
                if is_triggered:
                    # Execute for all subscribed strategies
                    for strategy_id in self.signal_subscriptions[signal_code]:
                        if strategy_id not in self.positions:
                            await self.execute_signal(strategy_id, signal_code, spot_price)
                            
        except Exception as e:
            logger.error(f"Error checking signals: {e}")
    
    async def evaluate_signal(self, signal_type: SignalType, spot_price: float) -> bool:
        """Evaluate if a signal is triggered"""
        # This would contain actual signal logic
        # For now, returning False to prevent automatic execution
        return False
    
    async def execute_signal(self, strategy_id: int, signal: str, spot_price: float):
        """Execute a trade based on signal"""
        try:
            strategy = self.active_strategies.get(strategy_id)
            if not strategy:
                return
                
            logger.info(f"Executing signal {signal} for strategy {strategy_id}")
            
            # Determine strike and option type
            strike, option_type = self.calculate_strike(signal, spot_price)
            
            # Create execution record
            execution = StrategyExecution(
                strategy_id=strategy_id,
                signal=signal,
                entry_time=datetime.now(),
                main_strike=strike,
                main_quantity=strategy.main_lots * 75,  # Lot size
                status="pending"
            )
            self.session.add(execution)
            self.session.commit()
            
            # Place main position order
            main_order = await self.place_order(
                OrderRequest(
                    strategy_id=strategy_id,
                    symbol=f"{strategy.instrument}{strike}{option_type}",
                    strike=strike,
                    order_type="MARKET",
                    quantity=strategy.main_lots * 75,
                    is_hedge=False,
                    tag=f"MAIN_{signal}_{strategy_id}"
                )
            )
            
            if main_order and main_order.get('status') == 'success':
                execution.main_entry_price = main_order.get('price', 0)
                
                # Place hedge if configured
                if strategy.hedge_lots > 0:
                    hedge_strike = strike + (strategy.hedge_strike_distance if option_type == 'CE' else -strategy.hedge_strike_distance)
                    hedge_type = 'PE' if option_type == 'CE' else 'CE'
                    
                    hedge_order = await self.place_order(
                        OrderRequest(
                            strategy_id=strategy_id,
                            symbol=f"{strategy.instrument}{hedge_strike}{hedge_type}",
                            strike=hedge_strike,
                            order_type="MARKET",
                            quantity=strategy.hedge_lots * 75,
                            is_hedge=True,
                            tag=f"HEDGE_{signal}_{strategy_id}"
                        )
                    )
                    
                    if hedge_order and hedge_order.get('status') == 'success':
                        execution.hedge_strike = hedge_strike
                        execution.hedge_entry_price = hedge_order.get('price', 0)
                        execution.hedge_quantity = strategy.hedge_lots * 75
                
                execution.status = "open"
                self.session.commit()
                
                # Add to positions
                self.add_position(strategy_id, execution, main_order.get('price', 0))
                
                self.audit_log("TRADE", f"Executed {signal} for strategy {strategy_id}", {
                    "strike": strike,
                    "quantity": strategy.main_lots * 75,
                    "price": main_order.get('price', 0)
                })
                
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            self.audit_log("ERROR", f"Failed to execute signal {signal}", {"error": str(e)})
    
    def calculate_strike(self, signal: str, spot_price: float) -> Tuple[int, str]:
        """Calculate strike price and option type based on signal"""
        # Round to nearest 50
        atm_strike = round(spot_price / 50) * 50
        
        # Determine option type based on signal
        bullish_signals = ['S1', 'S2', 'S4', 'S7']
        bearish_signals = ['S3', 'S5', 'S6', 'S8']
        
        if signal in bullish_signals:
            return atm_strike, 'PE'  # Sell PUT for bullish
        else:
            return atm_strike, 'CE'  # Sell CALL for bearish
    
    async def place_order(self, order_request: OrderRequest) -> Dict:
        """Place order with broker"""
        try:
            # Extract option details from symbol
            symbol = order_request.symbol
            
            # Determine exchange and other parameters
            exchange = "NFO"
            product = "options"
            action = "sell"  # We're option sellers
            
            response = self.breeze.place_order(
                stock_code=symbol,
                exchange_code=exchange,
                product=product,
                action=action,
                order_type=order_request.order_type.lower(),
                quantity=str(order_request.quantity),
                price="" if order_request.order_type == "MARKET" else str(order_request.price),
                validity="day",
                stoploss="" if not order_request.trigger_price else str(order_request.trigger_price),
                user_remark=order_request.tag
            )
            
            if response.get('Success'):
                order_id = response.get('Success', {}).get('order_id')
                self.open_orders[order_id] = order_request
                
                # Get fill price (in real scenario, would check order status)
                fill_price = self.get_current_price(symbol)
                
                return {
                    'status': 'success',
                    'order_id': order_id,
                    'price': fill_price
                }
            else:
                logger.error(f"Order placement failed: {response}")
                return {'status': 'failed', 'error': response.get('Error', 'Unknown error')}
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        try:
            # Try WebSocket first
            price = self.websocket.get_option_price(symbol)
            if price:
                return price
                
            # Fallback to API
            response = self.breeze.get_option_chain(
                stock_code=symbol[:5],  # Extract underlying
                exchange_code="NFO",
                product_type="options"
            )
            
            # Parse response to get price
            return 100.0  # Default fallback
            
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return 100.0
    
    def add_position(self, strategy_id: int, execution: StrategyExecution, entry_price: float):
        """Add position to tracking"""
        if strategy_id not in self.positions:
            self.positions[strategy_id] = []
            
        position = Position(
            strategy_id=strategy_id,
            execution_id=execution.id,
            symbol=f"{self.active_strategies[strategy_id].instrument}{execution.main_strike}",
            strike=execution.main_strike,
            quantity=execution.main_quantity,
            entry_price=entry_price,
            current_price=entry_price,
            pnl=0,
            is_hedge=False,
            entry_time=execution.entry_time
        )
        
        self.positions[strategy_id].append(position)
    
    async def update_positions(self):
        """Update all position prices and P&L"""
        try:
            for strategy_id, positions in self.positions.items():
                for position in positions:
                    # Get current price
                    current_price = self.get_current_price(position.symbol)
                    position.current_price = current_price
                    
                    # Calculate P&L (negative because we're sellers)
                    position.pnl = -(current_price - position.entry_price) * position.quantity
                    
        except Exception as e:
            logger.error(f"Error updating positions: {e}")
    
    async def check_risk_management(self):
        """Check stop loss and target profit for all strategies"""
        try:
            for strategy_id, strategy in self.active_strategies.items():
                if strategy_id not in self.positions:
                    continue
                    
                positions = self.positions[strategy_id]
                total_pnl = sum(p.pnl for p in positions)
                
                # Check stop loss
                if strategy.stop_loss_enabled and strategy.stop_loss_value:
                    if total_pnl <= -abs(strategy.stop_loss_value):
                        logger.warning(f"Stop loss triggered for strategy {strategy_id}")
                        await self.close_positions(strategy_id, "STOP_LOSS")
                        
                # Check target profit
                if strategy.target_profit_enabled and strategy.target_profit_value:
                    if total_pnl >= abs(strategy.target_profit_value):
                        logger.info(f"Target profit reached for strategy {strategy_id}")
                        await self.close_positions(strategy_id, "TARGET_PROFIT")
                        
                # Check trailing stop loss
                if strategy.trailing_enabled and strategy.trailing_value:
                    await self.check_trailing_stop(strategy_id, total_pnl)
                    
        except Exception as e:
            logger.error(f"Error in risk management: {e}")
    
    async def check_trailing_stop(self, strategy_id: int, current_pnl: float):
        """Implement trailing stop loss"""
        strategy = self.active_strategies[strategy_id]
        
        # Track highest P&L for trailing
        if not hasattr(strategy, '_max_pnl'):
            strategy._max_pnl = current_pnl
        else:
            strategy._max_pnl = max(strategy._max_pnl, current_pnl)
            
        # Check if trailing stop hit
        if strategy.trailing_type.value == "points":
            if current_pnl < strategy._max_pnl - strategy.trailing_value:
                await self.close_positions(strategy_id, "TRAILING_STOP")
                
        elif strategy.trailing_type.value == "percentage":
            if current_pnl < strategy._max_pnl * (1 - strategy.trailing_value / 100):
                await self.close_positions(strategy_id, "TRAILING_STOP")
    
    async def close_positions(self, strategy_id: int, reason: str):
        """Close all positions for a strategy"""
        try:
            if strategy_id not in self.positions:
                return
                
            positions = self.positions[strategy_id]
            
            for position in positions:
                # Place exit order
                exit_order = await self.place_order(
                    OrderRequest(
                        strategy_id=strategy_id,
                        symbol=position.symbol,
                        strike=position.strike,
                        order_type="MARKET",
                        quantity=position.quantity,
                        is_hedge=position.is_hedge,
                        tag=f"EXIT_{reason}_{strategy_id}"
                    )
                )
                
                if exit_order.get('status') == 'success':
                    # Update execution record
                    execution = self.session.query(StrategyExecution).filter_by(
                        id=position.execution_id
                    ).first()
                    
                    if execution:
                        execution.exit_time = datetime.now()
                        execution.main_exit_price = exit_order.get('price', 0)
                        execution.pnl = position.pnl
                        execution.status = "closed"
                        execution.exit_reason = reason
                        self.session.commit()
            
            # Remove from active positions
            del self.positions[strategy_id]
            
            # Update strategy P&L
            strategy = self.active_strategies[strategy_id]
            strategy.current_pnl += sum(p.pnl for p in positions)
            self.session.commit()
            
            self.audit_log("POSITION", f"Closed positions for strategy {strategy_id}", {
                "reason": reason,
                "pnl": sum(p.pnl for p in positions)
            })
            
        except Exception as e:
            logger.error(f"Error closing positions: {e}")
    
    async def check_market_timing(self):
        """Check market timing for square off"""
        current_time = datetime.now().time()
        
        # Square off all intraday positions at 3:15 PM
        if current_time >= self.square_off_time and current_time < self.market_close:
            for strategy_id, strategy in self.active_strategies.items():
                if strategy.strategy_type == StrategyType.INTRADAY:
                    if strategy_id in self.positions:
                        await self.close_positions(strategy_id, "SQUARE_OFF")
    
    async def square_off_all_positions(self, reason: str = "MANUAL"):
        """Square off all open positions"""
        for strategy_id in list(self.positions.keys()):
            await self.close_positions(strategy_id, reason)
    
    async def update_performance_metrics(self):
        """Update performance metrics for all strategies"""
        try:
            for strategy_id, strategy in self.active_strategies.items():
                # Calculate metrics
                executions = self.session.query(StrategyExecution).filter_by(
                    strategy_id=strategy_id
                ).all()
                
                total_trades = len(executions)
                winning_trades = len([e for e in executions if e.pnl > 0])
                losing_trades = len([e for e in executions if e.pnl < 0])
                total_pnl = sum(e.pnl for e in executions if e.pnl)
                
                # Update strategy
                strategy.total_trades = total_trades
                strategy.winning_trades = winning_trades
                strategy.losing_trades = losing_trades
                strategy.current_pnl = total_pnl
                
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    async def subscribe_market_data(self):
        """Subscribe to required market data feeds"""
        try:
            # Subscribe to NIFTY spot
            self.websocket.subscribe_spot("NIFTY")
            
            # Subscribe to option chains for active strikes
            strikes = set()
            for positions in self.positions.values():
                for position in positions:
                    strikes.add(position.strike)
                    
            for strike in strikes:
                self.websocket.subscribe_option_chain("NIFTY", strike)
                
        except Exception as e:
            logger.error(f"Error subscribing to market data: {e}")
    
    def is_market_open(self) -> bool:
        """Check if market is open"""
        current_time = datetime.now().time()
        return self.market_open <= current_time <= self.market_close
    
    def audit_log(self, category: str, message: str, details: Dict = None):
        """Add audit log entry"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "message": message,
            "details": details or {}
        }
        self.audit_logs.append(log_entry)
        
        # Also save to database
        try:
            from sqlalchemy import text
            query = text("""
                INSERT INTO AuditLogs (Category, Message, Details, CreatedAt)
                VALUES (:category, :message, :details, :created_at)
            """)
            self.session.execute(query, {
                "category": category,
                "message": message,
                "details": json.dumps(details or {}),
                "created_at": datetime.now()
            })
            self.session.commit()
        except Exception as e:
            logger.error(f"Error saving audit log: {e}")
    
    def get_audit_logs(self, limit: int = 100) -> List[Dict]:
        """Get recent audit logs"""
        return self.audit_logs[-limit:]
    
    def get_positions_summary(self) -> Dict:
        """Get summary of all positions"""
        summary = {
            "total_strategies": len(self.active_strategies),
            "strategies_with_positions": len(self.positions),
            "total_positions": sum(len(p) for p in self.positions.values()),
            "total_pnl": 0,
            "positions": []
        }
        
        for strategy_id, positions in self.positions.items():
            strategy = self.active_strategies.get(strategy_id)
            strategy_pnl = sum(p.pnl for p in positions)
            summary["total_pnl"] += strategy_pnl
            
            summary["positions"].append({
                "strategy_id": strategy_id,
                "strategy_name": strategy.name if strategy else "Unknown",
                "position_count": len(positions),
                "pnl": strategy_pnl,
                "positions": [asdict(p) for p in positions]
            })
            
        return summary
    
    async def deploy_strategy(self, strategy_id: int) -> Dict:
        """Deploy a strategy for live trading"""
        try:
            strategy = self.session.query(TradingStrategy).filter_by(id=strategy_id).first()
            if not strategy:
                return {"status": "error", "message": "Strategy not found"}
                
            if strategy.status == StrategyStatus.DEPLOYED:
                return {"status": "error", "message": "Strategy already deployed"}
                
            # Update status
            strategy.status = StrategyStatus.DEPLOYED
            strategy.deployed_at = datetime.now()
            self.session.commit()
            
            # Add to active strategies
            self.active_strategies[strategy_id] = strategy
            
            # Subscribe to signals
            for signal in strategy.signals:
                if signal not in self.signal_subscriptions:
                    self.signal_subscriptions[signal] = []
                self.signal_subscriptions[signal].append(strategy_id)
                
            self.audit_log("STRATEGY", f"Deployed strategy {strategy_id}", {
                "name": strategy.name,
                "signals": strategy.signals
            })
            
            return {"status": "success", "message": "Strategy deployed successfully"}
            
        except Exception as e:
            logger.error(f"Error deploying strategy: {e}")
            return {"status": "error", "message": str(e)}
    
    async def pause_strategy(self, strategy_id: int) -> Dict:
        """Pause a running strategy"""
        try:
            strategy = self.session.query(TradingStrategy).filter_by(id=strategy_id).first()
            if not strategy:
                return {"status": "error", "message": "Strategy not found"}
                
            strategy.status = StrategyStatus.PAUSED
            self.session.commit()
            
            # Remove from active but keep positions
            if strategy_id in self.active_strategies:
                del self.active_strategies[strategy_id]
                
            # Remove from signal subscriptions
            for signal in strategy.signals:
                if signal in self.signal_subscriptions:
                    self.signal_subscriptions[signal] = [
                        sid for sid in self.signal_subscriptions[signal] if sid != strategy_id
                    ]
                    
            self.audit_log("STRATEGY", f"Paused strategy {strategy_id}")
            
            return {"status": "success", "message": "Strategy paused"}
            
        except Exception as e:
            logger.error(f"Error pausing strategy: {e}")
            return {"status": "error", "message": str(e)}
    
    async def stop_strategy(self, strategy_id: int) -> Dict:
        """Stop a strategy and close positions"""
        try:
            # Close positions if any
            if strategy_id in self.positions:
                await self.close_positions(strategy_id, "STRATEGY_STOP")
                
            # Update database
            strategy = self.session.query(TradingStrategy).filter_by(id=strategy_id).first()
            if strategy:
                strategy.status = StrategyStatus.STOPPED
                strategy.stopped_at = datetime.now()
                self.session.commit()
                
            # Remove from active
            if strategy_id in self.active_strategies:
                del self.active_strategies[strategy_id]
                
            self.audit_log("STRATEGY", f"Stopped strategy {strategy_id}")
            
            return {"status": "success", "message": "Strategy stopped"}
            
        except Exception as e:
            logger.error(f"Error stopping strategy: {e}")
            return {"status": "error", "message": str(e)}

# Global instance
_executor_instance = None

def get_live_executor() -> LiveTradingExecutor:
    """Get or create live trading executor instance"""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = LiveTradingExecutor()
    return _executor_instance