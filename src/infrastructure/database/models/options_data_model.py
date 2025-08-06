"""
Options Historical Data Model
SQLAlchemy model for storing options historical data
"""
from sqlalchemy import Column, String, DateTime, DECIMAL, BigInteger, Integer, Index
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from ..base import Base


class OptionsHistoricalData(Base):
    """
    Model for options historical data
    Matches the SQL Server table structure
    """
    __tablename__ = 'OptionsHistoricalData'
    
    # Primary key (GUID)
    id = Column('Id', String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Option identification
    trading_symbol = Column('TradingSymbol', String(50), nullable=False)
    timestamp = Column('Timestamp', DateTime, nullable=False)
    exchange = Column('Exchange', String(10), nullable=False, default='NFO')
    underlying = Column('Underlying', String(10), nullable=False, default='NIFTY')
    strike = Column('Strike', Integer, nullable=False)
    option_type = Column('OptionType', String(2), nullable=False)  # CE or PE
    expiry_date = Column('ExpiryDate', DateTime, nullable=False)
    
    # OHLC data
    open = Column('Open', DECIMAL(18, 2), nullable=False)
    high = Column('High', DECIMAL(18, 2), nullable=False)
    low = Column('Low', DECIMAL(18, 2), nullable=False)
    close = Column('Close', DECIMAL(18, 2), nullable=False)
    last_price = Column('LastPrice', DECIMAL(18, 2), nullable=False)
    
    # Volume data
    volume = Column('Volume', BigInteger, nullable=False)
    open_interest = Column('OpenInterest', BigInteger, nullable=False)
    
    # Greeks
    delta = Column('Delta', DECIMAL(8, 4), nullable=True)
    gamma = Column('Gamma', DECIMAL(8, 4), nullable=True)
    theta = Column('Theta', DECIMAL(8, 4), nullable=True)
    vega = Column('Vega', DECIMAL(8, 4), nullable=True)
    implied_volatility = Column('ImpliedVolatility', DECIMAL(8, 4), nullable=True)
    
    # Bid/Ask
    bid_price = Column('BidPrice', DECIMAL(18, 2), nullable=True)
    ask_price = Column('AskPrice', DECIMAL(18, 2), nullable=True)
    bid_ask_spread = Column('BidAskSpread', DECIMAL(18, 2), nullable=True)
    
    # Metadata
    created_at = Column('CreatedAt', DateTime, nullable=False, server_default=func.now())
    data_source = Column('DataSource', String(50), nullable=False, default='BreezeConnect')
    interval = Column('Interval', String(20), nullable=False, default='1minute')
    
    # Indexes
    __table_args__ = (
        Index('IX_OptionsData_Symbol_Timestamp', 'TradingSymbol', 'Timestamp'),
        Index('IX_OptionsData_Expiry_Strike', 'ExpiryDate', 'Strike', 'OptionType'),
        Index('IX_OptionsData_Underlying_Timestamp', 'Underlying', 'Timestamp'),
    )
    
    def __repr__(self):
        return f"<OptionsData({self.trading_symbol} @ {self.timestamp}: {self.last_price})>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'trading_symbol': self.trading_symbol,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'strike': self.strike,
            'option_type': self.option_type,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'open': float(self.open),
            'high': float(self.high),
            'low': float(self.low),
            'close': float(self.close),
            'last_price': float(self.last_price),
            'volume': self.volume,
            'open_interest': self.open_interest,
            'delta': float(self.delta) if self.delta else None,
            'gamma': float(self.gamma) if self.gamma else None,
            'theta': float(self.theta) if self.theta else None,
            'vega': float(self.vega) if self.vega else None,
            'implied_volatility': float(self.implied_volatility) if self.implied_volatility else None,
            'bid_price': float(self.bid_price) if self.bid_price else None,
            'ask_price': float(self.ask_price) if self.ask_price else None,
            'bid_ask_spread': float(self.bid_ask_spread) if self.bid_ask_spread else None
        }
    
    @classmethod
    def from_breeze_data(cls, breeze_data: dict):
        """Create instance from Breeze API response"""
        import pytz
        from ....utils.market_hours import is_within_market_hours
        IST = pytz.timezone('Asia/Kolkata')
        
        # Parse datetime - handle multiple formats
        datetime_str = breeze_data['datetime']
        # Check for ISO format more precisely (must have 'T' between date and time)
        if 'T' in datetime_str and ':' in datetime_str and datetime_str.count('-') >= 2:
            # ISO format with timezone (e.g., 2024-03-01T09:15:00Z)
            try:
                utc_timestamp = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                timestamp = utc_timestamp.astimezone(IST).replace(tzinfo=None)
            except ValueError:
                # Fallback to other formats if ISO parsing fails
                if ' ' in datetime_str:
                    timestamp = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                else:
                    timestamp = datetime.strptime(datetime_str, '%d-%b-%Y')
        elif ' ' in datetime_str and ':' in datetime_str:
            # YYYY-MM-DD HH:MM:SS format from Breeze (already in IST)
            timestamp = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        else:
            # DD-MON-YYYY format from Breeze (e.g., 10-OCT-2024)
            timestamp = datetime.strptime(datetime_str, '%d-%b-%Y')
        
        # Filter out data outside market hours (9:15 AM - 3:30 PM IST)
        # For Breeze 5-minute data, use is_breeze_data=True (regular hours 9:15-15:30)
        if not is_within_market_hours(timestamp, include_pre_market=False, is_breeze_data=True, extended_hours=False):
            return None  # This record will be skipped
        
        # Parse expiry date - handle both ISO format and DD-MON-YYYY format
        expiry_str = breeze_data['expiry_date']
        # Check for ISO format more precisely
        if 'T' in expiry_str and ':' in expiry_str and expiry_str.count('-') >= 2:
            # ISO format (e.g., 2024-03-01T15:30:00Z)
            try:
                utc_expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                expiry = utc_expiry.astimezone(IST).replace(tzinfo=None)
            except ValueError:
                # Fallback to DD-MON-YYYY format
                expiry = datetime.strptime(expiry_str, '%d-%b-%Y')
        elif expiry_str.count('-') == 2 and any(month in expiry_str.upper() for month in ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']):
            # DD-MON-YYYY format from Breeze (e.g., 10-OCT-2024)
            expiry = datetime.strptime(expiry_str, '%d-%b-%Y')
        else:
            # Try other formats or default
            try:
                expiry = datetime.strptime(expiry_str, '%Y-%m-%d')
            except ValueError:
                expiry = datetime.strptime(expiry_str, '%d-%b-%Y')
        
        # Calculate bid-ask spread if both are available
        bid_ask_spread = None
        if breeze_data.get('best_bid_price') and breeze_data.get('best_offer_price'):
            bid_ask_spread = float(breeze_data['best_offer_price']) - float(breeze_data['best_bid_price'])
        
        # Construct trading symbol from components if not provided
        strike = int(breeze_data.get('strike_price', 0))
        option_type = 'PE' if breeze_data.get('right', '').lower() == 'put' else 'CE'
        
        # If trading_symbol not in data, construct it
        if 'trading_symbol' not in breeze_data:
            # Format: NIFTY25JAN23300CE
            month_map = {'JAN': 'JAN', 'FEB': 'FEB', 'MAR': 'MAR', 'APR': 'APR', 'MAY': 'MAY', 'JUN': 'JUN',
                        'JUL': 'JUL', 'AUG': 'AUG', 'SEP': 'SEP', 'OCT': 'OCT', 'NOV': 'NOV', 'DEC': 'DEC'}
            # Get month from expiry date
            month = expiry.strftime('%b').upper()
            year = expiry.strftime('%y')
            trading_symbol = f"NIFTY{year}{month}{strike}{option_type}"
        else:
            trading_symbol = breeze_data['trading_symbol']
        
        return cls(
            trading_symbol=trading_symbol,
            timestamp=timestamp,
            exchange=breeze_data.get('exchange_code', 'NFO'),
            underlying=breeze_data.get('underlying', 'NIFTY'),
            strike=strike,
            option_type=option_type,
            expiry_date=expiry,
            open=float(breeze_data['open']),
            high=float(breeze_data['high']),
            low=float(breeze_data['low']),
            close=float(breeze_data['close']),
            last_price=float(breeze_data['close']),
            volume=int(breeze_data.get('volume', 0)) if breeze_data.get('volume') else 0,
            open_interest=int(breeze_data.get('open_interest', 0)) if breeze_data.get('open_interest') else 0,
            bid_price=float(breeze_data['best_bid_price']) if breeze_data.get('best_bid_price') else None,
            ask_price=float(breeze_data['best_offer_price']) if breeze_data.get('best_offer_price') else None,
            bid_ask_spread=bid_ask_spread,
            data_source="BreezeConnect"
        )