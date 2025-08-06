"""
Trade Entity - Core domain entity representing a trade
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from .base import AggregateRoot, DomainEvent


class TradeType(Enum):
    """Trade type enumeration"""
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(Enum):
    """Trade status enumeration"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class InstrumentType(Enum):
    """Instrument type enumeration"""
    EQUITY = "EQUITY"
    OPTION = "OPTION"
    FUTURE = "FUTURE"
    INDEX = "INDEX"


# Domain Events
class TradeOpenedEvent(DomainEvent):
    """Event raised when a trade is opened"""
    def __init__(self, trade_id: str, symbol: str, quantity: int, price: Decimal):
        super().__init__()
        self.trade_id = trade_id
        self.symbol = symbol
        self.quantity = quantity
        self.price = price


class TradeClosedEvent(DomainEvent):
    """Event raised when a trade is closed"""
    def __init__(self, trade_id: str, exit_price: Decimal, pnl: Decimal, reason: str):
        super().__init__()
        self.trade_id = trade_id
        self.exit_price = exit_price
        self.pnl = pnl
        self.reason = reason


class StopLossUpdatedEvent(DomainEvent):
    """Event raised when stop loss is updated"""
    def __init__(self, trade_id: str, old_stop_loss: Optional[Decimal], new_stop_loss: Decimal):
        super().__init__()
        self.trade_id = trade_id
        self.old_stop_loss = old_stop_loss
        self.new_stop_loss = new_stop_loss


class Trade(AggregateRoot):
    """Trade aggregate root"""
    
    def __init__(
        self,
        id: Optional[str] = None,
        symbol: str = None,
        trade_type: TradeType = None,
        instrument_type: InstrumentType = None,
        quantity: int = None,
        entry_price: Decimal = None,
        strategy_name: Optional[str] = None
    ):
        super().__init__(id)
        self._symbol = symbol
        self._trade_type = trade_type
        self._instrument_type = instrument_type
        self._quantity = quantity
        self._entry_price = entry_price
        self._exit_price: Optional[Decimal] = None
        self._status = TradeStatus.PENDING
        self._strategy_name = strategy_name
        
        # Risk management
        self._stop_loss: Optional[Decimal] = None
        self._take_profit: Optional[Decimal] = None
        
        # Timestamps
        self._entry_time: Optional[datetime] = None
        self._exit_time: Optional[datetime] = None
        
        # Performance
        self._pnl: Optional[Decimal] = None
        self._pnl_percentage: Optional[Decimal] = None
        
        # Additional metadata
        self._tags: List[str] = []
        self._notes: str = ""
    
    # Properties
    @property
    def symbol(self) -> str:
        return self._symbol
    
    @property
    def trade_type(self) -> TradeType:
        return self._trade_type
    
    @property
    def instrument_type(self) -> InstrumentType:
        return self._instrument_type
    
    @property
    def quantity(self) -> int:
        return self._quantity
    
    @property
    def entry_price(self) -> Decimal:
        return self._entry_price
    
    @property
    def exit_price(self) -> Optional[Decimal]:
        return self._exit_price
    
    @property
    def status(self) -> TradeStatus:
        return self._status
    
    @property
    def stop_loss(self) -> Optional[Decimal]:
        return self._stop_loss
    
    @property
    def take_profit(self) -> Optional[Decimal]:
        return self._take_profit
    
    @property
    def pnl(self) -> Optional[Decimal]:
        return self._pnl
    
    @property
    def pnl_percentage(self) -> Optional[Decimal]:
        return self._pnl_percentage
    
    @property
    def is_open(self) -> bool:
        return self._status == TradeStatus.OPEN
    
    @property
    def is_closed(self) -> bool:
        return self._status == TradeStatus.CLOSED
    
    @property
    def is_profitable(self) -> bool:
        return self._pnl is not None and self._pnl > 0
    
    # Business Methods
    def open(self, entry_time: Optional[datetime] = None) -> 'Trade':
        """Open the trade"""
        if self._status != TradeStatus.PENDING:
            raise ValueError(f"Cannot open trade in {self._status} status")
        
        self._status = TradeStatus.OPEN
        self._entry_time = entry_time or datetime.utcnow()
        self.mark_updated()
        
        # Raise domain event
        self.add_domain_event(
            TradeOpenedEvent(
                trade_id=self.id,
                symbol=self._symbol,
                quantity=self._quantity,
                price=self._entry_price
            )
        )
        
        return self
    
    def close(self, exit_price: Decimal, exit_time: Optional[datetime] = None, 
              reason: str = "Manual") -> 'Trade':
        """Close the trade"""
        if self._status != TradeStatus.OPEN:
            raise ValueError(f"Cannot close trade in {self._status} status")
        
        self._exit_price = exit_price
        self._exit_time = exit_time or datetime.utcnow()
        self._status = TradeStatus.CLOSED
        
        # Calculate P&L
        self._calculate_pnl()
        
        self.mark_updated()
        
        # Raise domain event
        self.add_domain_event(
            TradeClosedEvent(
                trade_id=self.id,
                exit_price=exit_price,
                pnl=self._pnl,
                reason=reason
            )
        )
        
        return self
    
    def cancel(self, reason: str = "Manual") -> 'Trade':
        """Cancel the trade"""
        if self._status not in [TradeStatus.PENDING, TradeStatus.OPEN]:
            raise ValueError(f"Cannot cancel trade in {self._status} status")
        
        self._status = TradeStatus.CANCELLED
        self.mark_updated()
        
        return self
    
    def set_stop_loss(self, stop_loss: Decimal) -> 'Trade':
        """Set or update stop loss"""
        if stop_loss <= 0:
            raise ValueError("Stop loss must be positive")
        
        # Validate stop loss based on trade type
        if self._trade_type == TradeType.BUY and stop_loss >= self._entry_price:
            raise ValueError("Stop loss for BUY trade must be below entry price")
        elif self._trade_type == TradeType.SELL and stop_loss <= self._entry_price:
            raise ValueError("Stop loss for SELL trade must be above entry price")
        
        old_stop_loss = self._stop_loss
        self._stop_loss = stop_loss
        self.mark_updated()
        
        # Raise domain event
        self.add_domain_event(
            StopLossUpdatedEvent(
                trade_id=self.id,
                old_stop_loss=old_stop_loss,
                new_stop_loss=stop_loss
            )
        )
        
        return self
    
    def set_take_profit(self, take_profit: Decimal) -> 'Trade':
        """Set or update take profit"""
        if take_profit <= 0:
            raise ValueError("Take profit must be positive")
        
        # Validate take profit based on trade type
        if self._trade_type == TradeType.BUY and take_profit <= self._entry_price:
            raise ValueError("Take profit for BUY trade must be above entry price")
        elif self._trade_type == TradeType.SELL and take_profit >= self._entry_price:
            raise ValueError("Take profit for SELL trade must be below entry price")
        
        self._take_profit = take_profit
        self.mark_updated()
        
        return self
    
    def add_tag(self, tag: str) -> 'Trade':
        """Add a tag to the trade"""
        if tag and tag not in self._tags:
            self._tags.append(tag)
            self.mark_updated()
        return self
    
    def add_note(self, note: str) -> 'Trade':
        """Add or update trade notes"""
        self._notes = note
        self.mark_updated()
        return self
    
    def _calculate_pnl(self):
        """Calculate P&L for the trade"""
        if self._exit_price is None:
            return
        
        if self._trade_type == TradeType.BUY:
            # For BUY: PnL = (Exit Price - Entry Price) * Quantity
            price_diff = self._exit_price - self._entry_price
        else:  # SELL
            # For SELL: PnL = (Entry Price - Exit Price) * Quantity
            price_diff = self._entry_price - self._exit_price
        
        self._pnl = price_diff * self._quantity
        
        # Calculate percentage
        if self._entry_price != 0:
            self._pnl_percentage = (price_diff / self._entry_price) * 100
    
    def to_dict(self) -> dict:
        """Convert trade to dictionary"""
        return {
            'id': self.id,
            'symbol': self._symbol,
            'trade_type': self._trade_type.value if self._trade_type else None,
            'instrument_type': self._instrument_type.value if self._instrument_type else None,
            'quantity': self._quantity,
            'entry_price': float(self._entry_price) if self._entry_price else None,
            'exit_price': float(self._exit_price) if self._exit_price else None,
            'status': self._status.value if self._status else None,
            'stop_loss': float(self._stop_loss) if self._stop_loss else None,
            'take_profit': float(self._take_profit) if self._take_profit else None,
            'pnl': float(self._pnl) if self._pnl else None,
            'pnl_percentage': float(self._pnl_percentage) if self._pnl_percentage else None,
            'entry_time': self._entry_time.isoformat() if self._entry_time else None,
            'exit_time': self._exit_time.isoformat() if self._exit_time else None,
            'strategy_name': self._strategy_name,
            'tags': self._tags,
            'notes': self._notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }