"""Trading Holidays Model"""
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean
from datetime import datetime
from ..base import Base

class TradingHoliday(Base):
    """Trading holidays for exchanges"""
    __tablename__ = 'TradingHolidays'
    
    Id = Column(Integer, primary_key=True, autoincrement=True)
    Exchange = Column(String(10), nullable=False)  # NSE, BSE, MCX
    HolidayDate = Column(Date, nullable=False)
    HolidayName = Column(String(100), nullable=False)
    HolidayType = Column(String(50), nullable=True)  # Trading Holiday, Settlement Holiday
    IsTradingHoliday = Column(Boolean, default=True)
    IsSettlementHoliday = Column(Boolean, default=False)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    UpdatedAt = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<TradingHoliday({self.Exchange}, {self.HolidayDate}, {self.HolidayName})>"