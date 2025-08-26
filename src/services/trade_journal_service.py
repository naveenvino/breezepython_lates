"""
Trade Journal Service
Manages trade recording, performance tracking, and analytics
"""

import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import pyodbc
import json
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

@dataclass
class Trade:
    trade_id: str
    symbol: str
    trade_type: str  # BUY or SELL
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None
    commission: float = 0
    strategy_name: Optional[str] = None
    signal_type: Optional[str] = None
    notes: Optional[str] = None
    status: str = 'OPEN'

class TradeJournalService:
    """Service for managing trade journal and analytics"""
    
    def __init__(self, connection_string: Optional[str] = None):
        if not connection_string:
            connection_string = (
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=(localdb)\\mssqllocaldb;"
                "DATABASE=KiteConnectApi;"
                "Trusted_Connection=yes;"
            )
        self.connection_string = connection_string
        
    def _get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.connection_string)
        
    def record_trade_entry(self, trade: Trade) -> Dict:
        """Record a new trade entry"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Generate trade ID if not provided
            if not trade.trade_id:
                trade.trade_id = f"TRD_{uuid.uuid4().hex[:8]}"
            
            # Set entry time if not provided
            if not trade.entry_time:
                trade.entry_time = datetime.now()
            
            cursor.execute("""
                EXEC sp_InsertTrade 
                    @trade_id = ?,
                    @symbol = ?,
                    @trade_type = ?,
                    @quantity = ?,
                    @entry_price = ?,
                    @strategy_name = ?,
                    @signal_type = ?
            """, (
                trade.trade_id,
                trade.symbol,
                trade.trade_type,
                trade.quantity,
                trade.entry_price,
                trade.strategy_name,
                trade.signal_type
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Trade entry recorded: {trade.trade_id}")
            
            return {
                "status": "success",
                "trade_id": trade.trade_id,
                "message": "Trade entry recorded successfully"
            }
            
        except Exception as e:
            logger.error(f"Error recording trade entry: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
            
    def record_trade_exit(self, trade_id: str, exit_price: float, 
                         commission: float = 0, notes: Optional[str] = None) -> Dict:
        """Record trade exit"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Execute stored procedure
            cursor.execute("""
                EXEC sp_CloseTrade 
                    @trade_id = ?,
                    @exit_price = ?,
                    @commission = ?
            """, (trade_id, exit_price, commission))
            
            # Update notes if provided
            if notes:
                cursor.execute("""
                    UPDATE TradeJournal 
                    SET notes = ? 
                    WHERE trade_id = ?
                """, (notes, trade_id))
            
            conn.commit()
            
            # Get updated trade details
            cursor.execute("""
                SELECT pnl, pnl_percentage 
                FROM TradeJournal 
                WHERE trade_id = ?
            """, (trade_id,))
            
            row = cursor.fetchone()
            pnl = row[0] if row else 0
            pnl_percentage = row[1] if row else 0
            
            cursor.close()
            conn.close()
            
            logger.info(f"Trade exit recorded: {trade_id}, PnL: {pnl:.2f}")
            
            return {
                "status": "success",
                "trade_id": trade_id,
                "pnl": float(pnl),
                "pnl_percentage": float(pnl_percentage),
                "message": "Trade exit recorded successfully"
            }
            
        except Exception as e:
            logger.error(f"Error recording trade exit: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
            
    def get_open_trades(self) -> List[Dict]:
        """Get all open trades"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT trade_id, symbol, trade_type, quantity, 
                       entry_price, entry_time, strategy_name, signal_type
                FROM TradeJournal
                WHERE status = 'OPEN'
                ORDER BY entry_time DESC
            """)
            
            trades = []
            for row in cursor.fetchall():
                trades.append({
                    "trade_id": row[0],
                    "symbol": row[1],
                    "trade_type": row[2],
                    "quantity": row[3],
                    "entry_price": float(row[4]),
                    "entry_time": row[5].isoformat() if row[5] else None,
                    "strategy_name": row[6],
                    "signal_type": row[7]
                })
            
            cursor.close()
            conn.close()
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting open trades: {e}")
            return []
            
    def get_trade_history(self, from_date: Optional[date] = None, 
                         to_date: Optional[date] = None,
                         symbol: Optional[str] = None) -> List[Dict]:
        """Get trade history with filters"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT trade_id, symbol, trade_type, quantity,
                       entry_price, exit_price, entry_time, exit_time,
                       pnl, pnl_percentage, commission, strategy_name,
                       signal_type, status
                FROM TradeJournal
                WHERE 1=1
            """
            params = []
            
            if from_date:
                query += " AND entry_time >= ?"
                params.append(from_date)
                
            if to_date:
                query += " AND entry_time <= ?"
                params.append(to_date)
                
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
                
            query += " ORDER BY entry_time DESC"
            
            cursor.execute(query, params)
            
            trades = []
            for row in cursor.fetchall():
                trades.append({
                    "trade_id": row[0],
                    "symbol": row[1],
                    "trade_type": row[2],
                    "quantity": row[3],
                    "entry_price": float(row[4]),
                    "exit_price": float(row[5]) if row[5] else None,
                    "entry_time": row[6].isoformat() if row[6] else None,
                    "exit_time": row[7].isoformat() if row[7] else None,
                    "pnl": float(row[8]) if row[8] else None,
                    "pnl_percentage": float(row[9]) if row[9] else None,
                    "commission": float(row[10]) if row[10] else 0,
                    "strategy_name": row[11],
                    "signal_type": row[12],
                    "status": row[13]
                })
            
            cursor.close()
            conn.close()
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            return []
            
    def get_performance_summary(self, from_date: Optional[date] = None,
                               to_date: Optional[date] = None) -> Dict:
        """Get performance summary"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Use stored procedure
            cursor.execute("""
                EXEC sp_GetPerformanceSummary 
                    @from_date = ?,
                    @to_date = ?
            """, (from_date, to_date))
            
            row = cursor.fetchone()
            
            if row:
                summary = {
                    "total_trades": row[0] or 0,
                    "winning_trades": row[1] or 0,
                    "losing_trades": row[2] or 0,
                    "total_pnl": float(row[3]) if row[3] else 0,
                    "avg_pnl": float(row[4]) if row[4] else 0,
                    "best_trade": float(row[5]) if row[5] else 0,
                    "worst_trade": float(row[6]) if row[6] else 0,
                    "avg_return": float(row[7]) if row[7] else 0,
                    "win_rate": float(row[8]) if row[8] else 0
                }
            else:
                summary = {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                    "best_trade": 0,
                    "worst_trade": 0,
                    "avg_return": 0,
                    "win_rate": 0
                }
            
            cursor.close()
            conn.close()
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
            
    def get_daily_performance(self, date: Optional[date] = None) -> Dict:
        """Get daily performance metrics"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if not date:
                date = datetime.now().date()
            
            cursor.execute("""
                SELECT total_trades, winning_trades, losing_trades,
                       gross_pnl, net_pnl, commission_paid,
                       max_drawdown, win_rate
                FROM DailyPerformance
                WHERE date = ?
            """, (date,))
            
            row = cursor.fetchone()
            
            if row:
                performance = {
                    "date": date.isoformat(),
                    "total_trades": row[0] or 0,
                    "winning_trades": row[1] or 0,
                    "losing_trades": row[2] or 0,
                    "gross_pnl": float(row[3]) if row[3] else 0,
                    "net_pnl": float(row[4]) if row[4] else 0,
                    "commission_paid": float(row[5]) if row[5] else 0,
                    "max_drawdown": float(row[6]) if row[6] else 0,
                    "win_rate": float(row[7]) if row[7] else 0
                }
            else:
                performance = {
                    "date": date.isoformat(),
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "gross_pnl": 0,
                    "net_pnl": 0,
                    "commission_paid": 0,
                    "max_drawdown": 0,
                    "win_rate": 0
                }
            
            cursor.close()
            conn.close()
            
            return performance
            
        except Exception as e:
            logger.error(f"Error getting daily performance: {e}")
            return {}
            
    def get_strategy_performance(self) -> List[Dict]:
        """Get performance by strategy"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT strategy_name, signal_type, total_trades,
                       winning_trades, total_pnl, win_rate,
                       avg_pnl_per_trade, max_consecutive_wins,
                       max_consecutive_losses
                FROM StrategyPerformance
                ORDER BY total_pnl DESC
            """)
            
            strategies = []
            for row in cursor.fetchall():
                strategies.append({
                    "strategy_name": row[0],
                    "signal_type": row[1],
                    "total_trades": row[2] or 0,
                    "winning_trades": row[3] or 0,
                    "total_pnl": float(row[4]) if row[4] else 0,
                    "win_rate": float(row[5]) if row[5] else 0,
                    "avg_pnl_per_trade": float(row[6]) if row[6] else 0,
                    "max_consecutive_wins": row[7] or 0,
                    "max_consecutive_losses": row[8] or 0
                })
            
            cursor.close()
            conn.close()
            
            return strategies
            
        except Exception as e:
            logger.error(f"Error getting strategy performance: {e}")
            return []
            
    def record_signal(self, signal_type: str, spot_price: float,
                     strike_price: Optional[int] = None,
                     option_type: Optional[str] = None,
                     confidence: float = 0.5,
                     reason: Optional[str] = None) -> Dict:
        """Record a trading signal"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO SignalHistory 
                (signal_type, signal_time, spot_price, strike_price,
                 option_type, confidence, reason)
                VALUES (?, GETDATE(), ?, ?, ?, ?, ?)
            """, (signal_type, spot_price, strike_price, 
                 option_type, confidence, reason))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Signal recorded: {signal_type} at {spot_price}")
            
            return {
                "status": "success",
                "message": "Signal recorded successfully"
            }
            
        except Exception as e:
            logger.error(f"Error recording signal: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
            
    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """Get recent signals"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT TOP (?) signal_type, signal_time, spot_price,
                       strike_price, option_type, confidence,
                       executed, reason
                FROM SignalHistory
                ORDER BY signal_time DESC
            """, (limit,))
            
            signals = []
            for row in cursor.fetchall():
                signals.append({
                    "signal_type": row[0],
                    "signal_time": row[1].isoformat() if row[1] else None,
                    "spot_price": float(row[2]) if row[2] else None,
                    "strike_price": row[3],
                    "option_type": row[4],
                    "confidence": float(row[5]) if row[5] else None,
                    "executed": bool(row[6]),
                    "reason": row[7]
                })
            
            cursor.close()
            conn.close()
            
            return signals
            
        except Exception as e:
            logger.error(f"Error getting recent signals: {e}")
            return []
            
    def calculate_risk_metrics(self, portfolio_value: float) -> Dict:
        """Calculate and store risk metrics"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get recent trades for risk calculation
            cursor.execute("""
                SELECT pnl FROM TradeJournal
                WHERE status = 'CLOSED'
                AND exit_time >= DATEADD(day, -30, GETDATE())
                ORDER BY exit_time DESC
            """)
            
            pnls = [float(row[0]) for row in cursor.fetchall() if row[0]]
            
            if pnls:
                import numpy as np
                
                # Calculate VaR
                var_95 = np.percentile(pnls, 5)
                var_99 = np.percentile(pnls, 1)
                
                # Get current exposure
                cursor.execute("""
                    SELECT SUM(quantity * entry_price) as total_exposure
                    FROM TradeJournal
                    WHERE status = 'OPEN'
                """)
                
                row = cursor.fetchone()
                total_exposure = float(row[0]) if row and row[0] else 0
                
                leverage_ratio = total_exposure / portfolio_value if portfolio_value > 0 else 0
                
                # Store metrics
                cursor.execute("""
                    INSERT INTO RiskMetrics
                    (date, portfolio_value, var_95, var_99,
                     total_exposure, leverage_ratio)
                    VALUES (CAST(GETDATE() AS DATE), ?, ?, ?, ?, ?)
                """, (portfolio_value, var_95, var_99, 
                     total_exposure, leverage_ratio))
                
                conn.commit()
                
                metrics = {
                    "portfolio_value": portfolio_value,
                    "var_95": var_95,
                    "var_99": var_99,
                    "total_exposure": total_exposure,
                    "leverage_ratio": leverage_ratio
                }
            else:
                metrics = {
                    "portfolio_value": portfolio_value,
                    "var_95": 0,
                    "var_99": 0,
                    "total_exposure": 0,
                    "leverage_ratio": 0
                }
            
            cursor.close()
            conn.close()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {}
            
    def export_trades(self, filepath: str, from_date: Optional[date] = None,
                     to_date: Optional[date] = None):
        """Export trades to JSON file"""
        try:
            trades = self.get_trade_history(from_date, to_date)
            performance = self.get_performance_summary(from_date, to_date)
            strategies = self.get_strategy_performance()
            
            export_data = {
                "export_date": datetime.now().isoformat(),
                "period": {
                    "from": from_date.isoformat() if from_date else None,
                    "to": to_date.isoformat() if to_date else None
                },
                "performance_summary": performance,
                "strategy_performance": strategies,
                "trades": trades
            }
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
                
            logger.info(f"Trades exported to {filepath}")
            
            return {
                "status": "success",
                "message": f"Exported {len(trades)} trades to {filepath}"
            }
            
        except Exception as e:
            logger.error(f"Error exporting trades: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

# Singleton instance
_trade_journal_service = None

def get_trade_journal_service() -> TradeJournalService:
    """Get or create trade journal service instance"""
    global _trade_journal_service
    if _trade_journal_service is None:
        _trade_journal_service = TradeJournalService()
    return _trade_journal_service