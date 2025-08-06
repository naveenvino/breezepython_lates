"""
Trade Repository Implementation
Concrete implementation of ITradeRepository
"""
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy import create_engine, select, and_, or_, func
from sqlalchemy.orm import sessionmaker, Session

from ...domain.repositories.itrade_repository import ITradeRepository
from ...domain.entities.trade import Trade, TradeType, TradeStatus
from ..database.models.trade_model import TradeModel, TradeLogModel
from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class TradeRepository(ITradeRepository):
    """SQL Server implementation of trade repository"""
    
    def __init__(self):
        self.settings = get_settings()
        self.engine = create_engine(self.settings.database.connection_string)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    async def get_by_id(self, id: str) -> Optional[Trade]:
        """Get trade by ID"""
        try:
            with self.SessionLocal() as session:
                result = session.query(TradeModel).filter_by(Id=int(id)).first()
                if result:
                    return self._map_to_domain(result)
                return None
        except Exception as e:
            logger.error(f"Error getting trade by ID {id}: {e}")
            return None
    
    async def get_active_trades(self) -> List[Trade]:
        """Get all active trades"""
        try:
            with self.SessionLocal() as session:
                results = session.query(TradeModel).filter(
                    TradeModel.Status == TradeStatus.OPEN.value
                ).order_by(TradeModel.EntryTime.desc()).all()
                
                return [self._map_to_domain(r) for r in results]
        except Exception as e:
            logger.error(f"Error getting active trades: {e}")
            return []
    
    async def get_active_trade_by_symbol(self, symbol: str) -> Optional[Trade]:
        """Get active trade for symbol"""
        try:
            with self.SessionLocal() as session:
                result = session.query(TradeModel).filter(
                    and_(
                        TradeModel.Symbol == symbol,
                        TradeModel.Status == TradeStatus.OPEN.value
                    )
                ).first()
                
                if result:
                    return self._map_to_domain(result)
                return None
        except Exception as e:
            logger.error(f"Error getting active trade for {symbol}: {e}")
            return None
    
    async def get_trades_by_date_range(
        self,
        from_date: datetime,
        to_date: datetime
    ) -> List[Trade]:
        """Get trades within date range"""
        try:
            with self.SessionLocal() as session:
                results = session.query(TradeModel).filter(
                    and_(
                        TradeModel.EntryTime >= from_date,
                        TradeModel.EntryTime <= to_date
                    )
                ).order_by(TradeModel.EntryTime.desc()).all()
                
                return [self._map_to_domain(r) for r in results]
        except Exception as e:
            logger.error(f"Error getting trades by date range: {e}")
            return []
    
    async def get_trades_by_status(self, status: TradeStatus) -> List[Trade]:
        """Get trades by status"""
        try:
            with self.SessionLocal() as session:
                results = session.query(TradeModel).filter(
                    TradeModel.Status == status.value
                ).order_by(TradeModel.EntryTime.desc()).all()
                
                return [self._map_to_domain(r) for r in results]
        except Exception as e:
            logger.error(f"Error getting trades by status {status}: {e}")
            return []
    
    async def save(self, entity: Trade) -> Trade:
        """Save trade"""
        try:
            with self.SessionLocal() as session:
                if entity.id:
                    # Update existing
                    model = session.query(TradeModel).filter_by(Id=int(entity.id)).first()
                    if model:
                        model.ExitPrice = float(entity.exit_price) if entity.exit_price else None
                        model.ExitTime = entity.exit_time
                        model.Status = entity.status.value
                        model.PnL = float(entity.calculate_pnl()) if entity.exit_price else None
                        model.ExitReason = entity.exit_reason
                        model.UpdatedAt = datetime.utcnow()
                else:
                    # Create new
                    model = TradeModel(
                        Symbol=entity.symbol,
                        TradeType=entity.trade_type.value,
                        EntryPrice=float(entity.entry_price),
                        Quantity=entity.quantity,
                        Status=entity.status.value,
                        SignalId=entity.signal_id,
                        EntryTime=entity.entry_time,
                        StopLoss=float(entity.stop_loss) if entity.stop_loss else None,
                        Target=float(entity.target) if entity.target else None,
                        CreatedAt=datetime.utcnow()
                    )
                    session.add(model)
                
                session.commit()
                
                if not entity.id:
                    session.refresh(model)
                    entity.id = str(model.Id)
                
                return entity
                
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
            raise
    
    async def delete(self, id: str) -> bool:
        """Delete trade by ID"""
        try:
            with self.SessionLocal() as session:
                result = session.query(TradeModel).filter_by(Id=int(id)).first()
                if result:
                    session.delete(result)
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting trade {id}: {e}")
            return False
    
    async def get_trade_statistics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get trade statistics"""
        try:
            with self.SessionLocal() as session:
                query = session.query(TradeModel).filter(
                    TradeModel.Status == TradeStatus.CLOSED.value
                )
                
                if from_date:
                    query = query.filter(TradeModel.EntryTime >= from_date)
                if to_date:
                    query = query.filter(TradeModel.EntryTime <= to_date)
                
                trades = query.all()
                
                if not trades:
                    return {
                        "total_trades": 0,
                        "winning_trades": 0,
                        "losing_trades": 0,
                        "win_rate": 0.0,
                        "total_pnl": 0.0,
                        "average_win": 0.0,
                        "average_loss": 0.0,
                        "profit_factor": 0.0
                    }
                
                winning_trades = [t for t in trades if t.PnL and t.PnL > 0]
                losing_trades = [t for t in trades if t.PnL and t.PnL <= 0]
                
                total_wins = sum(t.PnL for t in winning_trades)
                total_losses = abs(sum(t.PnL for t in losing_trades))
                
                return {
                    "total_trades": len(trades),
                    "winning_trades": len(winning_trades),
                    "losing_trades": len(losing_trades),
                    "win_rate": (len(winning_trades) / len(trades) * 100) if trades else 0,
                    "total_pnl": sum(t.PnL for t in trades if t.PnL),
                    "average_win": (total_wins / len(winning_trades)) if winning_trades else 0,
                    "average_loss": (total_losses / len(losing_trades)) if losing_trades else 0,
                    "profit_factor": (total_wins / total_losses) if total_losses > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"Error getting trade statistics: {e}")
            return {}
    
    async def add_trade_log(
        self,
        trade_id: str,
        action: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add log entry for trade"""
        try:
            with self.SessionLocal() as session:
                log = TradeLogModel(
                    TradeId=int(trade_id),
                    Action=action,
                    Message=message,
                    Details=str(details) if details else None,
                    Timestamp=datetime.utcnow()
                )
                
                session.add(log)
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding trade log: {e}")
            return False
    
    def _map_to_domain(self, model: TradeModel) -> Trade:
        """Map database model to domain entity"""
        trade = Trade(
            symbol=model.Symbol,
            trade_type=TradeType(model.TradeType),
            entry_price=Decimal(str(model.EntryPrice)),
            quantity=model.Quantity,
            entry_time=model.EntryTime,
            status=TradeStatus(model.Status)
        )
        
        # Set optional fields
        trade.id = str(model.Id)
        trade.signal_id = model.SignalId
        
        if model.ExitPrice:
            trade.exit_price = Decimal(str(model.ExitPrice))
        if model.ExitTime:
            trade.exit_time = model.ExitTime
        if model.StopLoss:
            trade.stop_loss = Decimal(str(model.StopLoss))
        if model.Target:
            trade.target = Decimal(str(model.Target))
        if model.ExitReason:
            trade.exit_reason = model.ExitReason
        
        return trade