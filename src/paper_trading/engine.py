"""
Paper Trading Engine
Simulates live trading with real-time data for risk-free strategy testing
"""
import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
import json
import uuid
from sqlalchemy import create_engine, text
from decimal import Decimal
import threading
from queue import Queue

logger = logging.getLogger(__name__)

@dataclass
class PaperPosition:
    """Paper trading position"""
    position_id: str
    trade_id: str
    symbol: str
    signal_type: str
    direction: str
    entry_price: float
    current_price: float
    quantity: int
    stop_loss: float
    target: Optional[float] = None
    entry_time: datetime = field(default_factory=datetime.now)
    status: str = 'OPEN'
    unrealized_pnl: float = 0.0
    ml_prediction: float = 0.0

@dataclass
class PaperTrade:
    """Paper trade record"""
    trade_id: str
    signal_type: str
    direction: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    status: str = 'PENDING'
    exit_reason: str = ''
    ml_prediction: float = 0.0
    slippage: float = 0.0
    commission: float = 0.0

class PaperTradingEngine:
    """Paper trading engine for risk-free strategy testing"""
    
    def __init__(self,
                 db_connection_string: str,
                 initial_capital: float = 500000,
                 commission_per_lot: float = 40,
                 slippage_percent: float = 0.05):
        """
        Initialize paper trading engine
        
        Args:
            db_connection_string: Database connection
            initial_capital: Starting virtual capital
            commission_per_lot: Commission per lot traded
            slippage_percent: Slippage percentage for realistic execution
        """
        self.engine = create_engine(db_connection_string)
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.commission_per_lot = commission_per_lot
        self.slippage_percent = slippage_percent / 100
        
        # Trading state
        self.positions: Dict[str, PaperPosition] = {}
        self.trades: List[PaperTrade] = []
        self.order_queue = Queue()
        self.is_running = False
        
        # Signal evaluator and ML models
        self.signal_evaluator = None
        self.ml_classifier = None
        self.stop_loss_optimizer = None
        
        # Performance tracking
        self.equity_curve = []
        self.daily_pnl = []
        self.trade_log = []
        
    def start(self, signal_evaluator=None, ml_models: Dict = None):
        """
        Start paper trading engine
        
        Args:
            signal_evaluator: Signal evaluation logic
            ml_models: Dictionary of ML models
        """
        self.is_running = True
        self.signal_evaluator = signal_evaluator
        
        if ml_models:
            self.ml_classifier = ml_models.get('classifier')
            self.stop_loss_optimizer = ml_models.get('stop_loss')
            
        # Start order processing thread
        self.order_thread = threading.Thread(target=self._process_orders)
        self.order_thread.start()
        
        logger.info("Paper trading engine started")
        
    def stop(self):
        """Stop paper trading engine"""
        self.is_running = False
        
        # Close all open positions
        self._close_all_positions('ENGINE_STOP')
        
        # Save final results
        self._save_trading_session()
        
        logger.info("Paper trading engine stopped")
        
    def process_market_data(self, market_data: Dict):
        """
        Process incoming market data and check for signals
        
        Args:
            market_data: Dictionary with OHLCV data
        """
        if not self.is_running:
            return
            
        timestamp = market_data.get('timestamp', datetime.now())
        
        # Update current prices for open positions
        self._update_position_prices(market_data)
        
        # Check stop losses
        self._check_stop_losses(market_data)
        
        # Check for expiry day square-off (3:15 PM on Tuesday)
        if timestamp.weekday() == 1 and timestamp.hour == 15 and timestamp.minute >= 15:
            self._square_off_expiry_positions()
            
        # Evaluate signals if evaluator is available
        if self.signal_evaluator:
            signals = self._evaluate_signals(market_data)
            
            for signal in signals:
                # Apply ML filter if available
                if self.ml_classifier:
                    ml_score = self._get_ml_prediction(signal, market_data)
                    if ml_score < 0.6:  # Threshold
                        logger.info(f"Signal {signal['type']} filtered by ML (score: {ml_score:.2f})")
                        continue
                else:
                    ml_score = 0.5
                    
                # Create paper trade
                self._create_paper_trade(signal, market_data, ml_score)
                
        # Update equity curve
        self._update_equity_curve(timestamp)
        
    def _evaluate_signals(self, market_data: Dict) -> List[Dict]:
        """
        Evaluate market data for trading signals
        
        Args:
            market_data: Market data
            
        Returns:
            List of detected signals
        """
        # Simplified signal evaluation
        # In production, would use actual signal evaluator
        signals = []
        
        # Example signal detection
        if market_data.get('rsi', 50) < 30:
            signals.append({
                'type': 'S1',
                'direction': 'BULLISH',
                'strength': 0.7
            })
        elif market_data.get('rsi', 50) > 70:
            signals.append({
                'type': 'S3',
                'direction': 'BEARISH', 
                'strength': 0.7
            })
            
        return signals
    
    def _get_ml_prediction(self, signal: Dict, market_data: Dict) -> float:
        """
        Get ML prediction for signal profitability
        
        Args:
            signal: Signal information
            market_data: Current market data
            
        Returns:
            ML prediction score (0-1)
        """
        if not self.ml_classifier:
            return 0.5
            
        # Prepare features for ML model
        features = pd.DataFrame([market_data])
        
        try:
            prediction = self.ml_classifier.predict(features, return_proba=True)
            return float(prediction[0])
        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            return 0.5
    
    def _create_paper_trade(self, 
                          signal: Dict,
                          market_data: Dict,
                          ml_score: float):
        """
        Create a paper trade based on signal
        
        Args:
            signal: Trading signal
            market_data: Current market data
            ml_score: ML prediction score
        """
        trade_id = str(uuid.uuid4())
        current_price = market_data.get('close', 0)
        
        # Calculate position size (simplified)
        position_size = self._calculate_position_size(signal, self.current_capital)
        
        # Apply slippage
        if signal['direction'] == 'BULLISH':
            entry_price = current_price * (1 + self.slippage_percent)
        else:
            entry_price = current_price * (1 - self.slippage_percent)
            
        # Optimize stop loss if model available
        if self.stop_loss_optimizer:
            stop_loss = self._optimize_stop_loss(signal, market_data)
        else:
            # Default stop loss (2% from entry)
            if signal['direction'] == 'BULLISH':
                stop_loss = entry_price * 0.98
            else:
                stop_loss = entry_price * 1.02
                
        # Create trade
        trade = PaperTrade(
            trade_id=trade_id,
            signal_type=signal['type'],
            direction=signal['direction'],
            entry_time=datetime.now(),
            entry_price=entry_price,
            quantity=position_size,
            status='PENDING',
            ml_prediction=ml_score
        )
        
        # Create position
        position = PaperPosition(
            position_id=str(uuid.uuid4()),
            trade_id=trade_id,
            symbol='NIFTY',  # Simplified
            signal_type=signal['type'],
            direction=signal['direction'],
            entry_price=entry_price,
            current_price=entry_price,
            quantity=position_size,
            stop_loss=stop_loss,
            ml_prediction=ml_score
        )
        
        # Add to queue for processing
        self.order_queue.put(('OPEN', trade, position))
        
        logger.info(f"Paper trade created: {signal['type']} {signal['direction']} at {entry_price}")
        
    def _calculate_position_size(self, signal: Dict, capital: float) -> int:
        """
        Calculate position size based on signal and capital
        
        Args:
            signal: Trading signal
            capital: Available capital
            
        Returns:
            Position size in lots
        """
        # Risk 2% of capital per trade
        risk_amount = capital * 0.02
        
        # Calculate lots (NIFTY lot size = 75)
        lot_size = 75
        max_lots = 10  # Maximum 10 lots
        
        # Simple sizing based on signal strength
        base_lots = 5
        if signal.get('strength', 0.5) > 0.7:
            lots = min(base_lots * 1.5, max_lots)
        else:
            lots = base_lots
            
        return int(lots) * lot_size
    
    def _optimize_stop_loss(self, signal: Dict, market_data: Dict) -> float:
        """
        Optimize stop loss using ML model
        
        Args:
            signal: Trading signal
            market_data: Market data
            
        Returns:
            Optimized stop loss price
        """
        if not self.stop_loss_optimizer:
            return 0
            
        try:
            result = self.stop_loss_optimizer.optimize_stop_loss(
                signal_type=signal['type'],
                entry_price=market_data['close'],
                market_features=market_data,
                direction=signal['direction']
            )
            return result.recommended_stop
        except Exception as e:
            logger.error(f"Stop loss optimization failed: {e}")
            # Return default stop loss
            if signal['direction'] == 'BULLISH':
                return market_data['close'] * 0.98
            else:
                return market_data['close'] * 1.02
    
    def _process_orders(self):
        """Process orders from queue (runs in separate thread)"""
        while self.is_running:
            try:
                if not self.order_queue.empty():
                    action, trade, position = self.order_queue.get(timeout=1)
                    
                    if action == 'OPEN':
                        self._execute_paper_trade(trade, position)
                    elif action == 'CLOSE':
                        self._close_paper_position(position, trade)
                        
            except Exception as e:
                if self.is_running:
                    logger.error(f"Order processing error: {e}")
                    
    def _execute_paper_trade(self, trade: PaperTrade, position: PaperPosition):
        """
        Execute paper trade
        
        Args:
            trade: Paper trade
            position: Paper position
        """
        # Calculate commission
        lots = position.quantity / 75  # NIFTY lot size
        commission = lots * self.commission_per_lot
        
        # Update capital
        trade_value = position.entry_price * position.quantity
        self.current_capital -= (trade_value + commission)
        
        # Update trade status
        trade.status = 'OPEN'
        trade.commission = commission
        
        # Store position and trade
        self.positions[position.position_id] = position
        self.trades.append(trade)
        
        # Save to database
        self._save_paper_trade(trade)
        self._save_paper_position(position)
        
        logger.info(f"Paper trade executed: {trade.trade_id}")
        
    def _update_position_prices(self, market_data: Dict):
        """Update current prices and P&L for open positions"""
        current_price = market_data.get('close', 0)
        
        for position in self.positions.values():
            if position.status == 'OPEN':
                position.current_price = current_price
                
                # Calculate unrealized P&L
                if position.direction == 'BULLISH':
                    position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
                else:
                    position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
                    
    def _check_stop_losses(self, market_data: Dict):
        """Check and trigger stop losses"""
        current_price = market_data.get('close', 0)
        
        for position in list(self.positions.values()):
            if position.status != 'OPEN':
                continue
                
            hit_stop = False
            
            if position.direction == 'BULLISH' and current_price <= position.stop_loss:
                hit_stop = True
            elif position.direction == 'BEARISH' and current_price >= position.stop_loss:
                hit_stop = True
                
            if hit_stop:
                logger.warning(f"Stop loss hit for position {position.position_id}")
                self._close_position(position.position_id, 'STOP_LOSS', current_price)
                
    def _square_off_expiry_positions(self):
        """Square off all positions on expiry day at 3:15 PM"""
        logger.info("Expiry day square-off initiated")
        
        for position in list(self.positions.values()):
            if position.status == 'OPEN':
                self._close_position(position.position_id, 'EXPIRY_SQUARE_OFF')
                
    def _close_position(self, 
                       position_id: str,
                       reason: str,
                       exit_price: Optional[float] = None):
        """
        Close a paper position
        
        Args:
            position_id: Position ID
            reason: Reason for closing
            exit_price: Exit price (if not provided, uses current price)
        """
        if position_id not in self.positions:
            return
            
        position = self.positions[position_id]
        if position.status != 'OPEN':
            return
            
        # Get corresponding trade
        trade = next((t for t in self.trades if t.trade_id == position.trade_id), None)
        if not trade:
            return
            
        # Calculate exit price with slippage
        if exit_price is None:
            exit_price = position.current_price
            
        if position.direction == 'BULLISH':
            exit_price *= (1 - self.slippage_percent)  # Sell at lower price
        else:
            exit_price *= (1 + self.slippage_percent)  # Buy back at higher price
            
        # Calculate P&L
        if position.direction == 'BULLISH':
            pnl = (exit_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exit_price) * position.quantity
            
        # Add commission
        lots = position.quantity / 75
        commission = lots * self.commission_per_lot
        pnl -= commission
        
        # Update trade
        trade.exit_time = datetime.now()
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.pnl_percent = (pnl / (position.entry_price * position.quantity)) * 100
        trade.status = 'CLOSED'
        trade.exit_reason = reason
        
        # Update position
        position.status = 'CLOSED'
        
        # Update capital
        self.current_capital += (exit_price * position.quantity - commission)
        
        # Save to database
        self._update_paper_trade(trade)
        self._update_paper_position(position)
        
        # Log trade
        self.trade_log.append({
            'trade_id': trade.trade_id,
            'signal': trade.signal_type,
            'direction': trade.direction,
            'entry': trade.entry_price,
            'exit': trade.exit_price,
            'pnl': trade.pnl,
            'reason': reason,
            'ml_score': trade.ml_prediction
        })
        
        logger.info(f"Position closed: {position_id}, PnL: {pnl:.2f}, Reason: {reason}")
        
    def _close_all_positions(self, reason: str):
        """Close all open positions"""
        for position_id in list(self.positions.keys()):
            self._close_position(position_id, reason)
            
    def _update_equity_curve(self, timestamp: datetime):
        """Update equity curve with current portfolio value"""
        # Calculate total value
        total_value = self.current_capital
        
        for position in self.positions.values():
            if position.status == 'OPEN':
                total_value += position.unrealized_pnl
                
        self.equity_curve.append({
            'timestamp': timestamp,
            'value': total_value,
            'cash': self.current_capital,
            'positions': len([p for p in self.positions.values() if p.status == 'OPEN'])
        })
        
        # Calculate daily P&L
        if len(self.equity_curve) > 1:
            daily_pnl = total_value - self.equity_curve[-2]['value']
            self.daily_pnl.append({
                'date': timestamp.date(),
                'pnl': daily_pnl,
                'return': daily_pnl / self.equity_curve[-2]['value']
            })
            
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get current performance summary
        
        Returns:
            Dictionary with performance metrics
        """
        if not self.trades:
            return {'message': 'No trades executed yet'}
            
        closed_trades = [t for t in self.trades if t.status == 'CLOSED']
        
        if not closed_trades:
            return {'message': 'No closed trades yet'}
            
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0
        
        # Calculate profit factor
        gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
        gross_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Calculate returns
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital
        
        # Calculate max drawdown
        if self.equity_curve:
            values = [e['value'] for e in self.equity_curve]
            cummax = pd.Series(values).expanding().max()
            drawdown = (pd.Series(values) - cummax) / cummax
            max_drawdown = abs(drawdown.min())
        else:
            max_drawdown = 0
            
        return {
            'total_trades': len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate * 100,
            'total_pnl': total_pnl,
            'total_return': total_return * 100,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown * 100,
            'current_capital': self.current_capital,
            'open_positions': len([p for p in self.positions.values() if p.status == 'OPEN']),
            'avg_win': np.mean([t.pnl for t in winning_trades]) if winning_trades else 0,
            'avg_loss': np.mean([t.pnl for t in losing_trades]) if losing_trades else 0,
            'best_trade': max(t.pnl for t in closed_trades) if closed_trades else 0,
            'worst_trade': min(t.pnl for t in closed_trades) if closed_trades else 0,
            'ml_accuracy': self._calculate_ml_accuracy()
        }
    
    def _calculate_ml_accuracy(self) -> float:
        """Calculate ML prediction accuracy"""
        accurate_predictions = 0
        total_predictions = 0
        
        for trade in self.trades:
            if trade.status == 'CLOSED' and trade.ml_prediction > 0:
                total_predictions += 1
                # Check if ML prediction was correct
                if (trade.ml_prediction > 0.5 and trade.pnl > 0) or \
                   (trade.ml_prediction <= 0.5 and trade.pnl <= 0):
                    accurate_predictions += 1
                    
        return (accurate_predictions / total_predictions * 100) if total_predictions > 0 else 0
    
    def _save_paper_trade(self, trade: PaperTrade):
        """Save paper trade to database"""
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO PaperTrades (
                    TradeId, SignalType, Direction, EntryTime, EntryPrice,
                    Quantity, Status, MLPrediction, CreatedAt
                ) VALUES (
                    :trade_id, :signal_type, :direction, :entry_time, :entry_price,
                    :quantity, :status, :ml_prediction, GETDATE()
                )
            """), {
                'trade_id': trade.trade_id,
                'signal_type': trade.signal_type,
                'direction': trade.direction,
                'entry_time': trade.entry_time,
                'entry_price': trade.entry_price,
                'quantity': trade.quantity,
                'status': trade.status,
                'ml_prediction': trade.ml_prediction
            })
            
    def _save_paper_position(self, position: PaperPosition):
        """Save paper position to database"""
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO PaperPositions (
                    PositionId, TradeId, Symbol, PositionType, Direction,
                    Quantity, EntryPrice, CurrentPrice, StopLoss, Status,
                    OpenedAt, UpdatedAt
                ) VALUES (
                    :position_id, :trade_id, :symbol, 'MAIN', :direction,
                    :quantity, :entry_price, :current_price, :stop_loss, :status,
                    :opened_at, GETDATE()
                )
            """), {
                'position_id': position.position_id,
                'trade_id': position.trade_id,
                'symbol': position.symbol,
                'direction': position.direction,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'stop_loss': position.stop_loss,
                'status': position.status,
                'opened_at': position.entry_time
            })
            
    def _update_paper_trade(self, trade: PaperTrade):
        """Update paper trade in database"""
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE PaperTrades
                SET ExitTime = :exit_time,
                    ExitPrice = :exit_price,
                    PnL = :pnl,
                    PnLPercent = :pnl_percent,
                    Status = :status,
                    ExitReason = :exit_reason
                WHERE TradeId = :trade_id
            """), {
                'trade_id': trade.trade_id,
                'exit_time': trade.exit_time,
                'exit_price': trade.exit_price,
                'pnl': trade.pnl,
                'pnl_percent': trade.pnl_percent,
                'status': trade.status,
                'exit_reason': trade.exit_reason
            })
            
    def _update_paper_position(self, position: PaperPosition):
        """Update paper position in database"""
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE PaperPositions
                SET CurrentPrice = :current_price,
                    UnrealizedPnL = :unrealized_pnl,
                    Status = :status,
                    UpdatedAt = GETDATE()
                WHERE PositionId = :position_id
            """), {
                'position_id': position.position_id,
                'current_price': position.current_price,
                'unrealized_pnl': position.unrealized_pnl,
                'status': position.status
            })
            
    def _save_trading_session(self):
        """Save complete trading session summary"""
        summary = self.get_performance_summary()
        
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO PaperTradingSessions (
                    SessionId, StartTime, EndTime, InitialCapital,
                    FinalCapital, TotalTrades, WinRate, TotalPnL,
                    MaxDrawdown, Summary, CreatedAt
                ) VALUES (
                    :session_id, :start_time, :end_time, :initial_capital,
                    :final_capital, :total_trades, :win_rate, :total_pnl,
                    :max_drawdown, :summary, GETDATE()
                )
            """), {
                'session_id': str(uuid.uuid4()),
                'start_time': self.equity_curve[0]['timestamp'] if self.equity_curve else datetime.now(),
                'end_time': datetime.now(),
                'initial_capital': self.initial_capital,
                'final_capital': self.current_capital,
                'total_trades': summary.get('total_trades', 0),
                'win_rate': summary.get('win_rate', 0),
                'total_pnl': summary.get('total_pnl', 0),
                'max_drawdown': summary.get('max_drawdown', 0),
                'summary': json.dumps(summary, default=str)
            })
            
        logger.info("Trading session saved to database")