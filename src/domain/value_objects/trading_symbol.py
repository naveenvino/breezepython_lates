"""
Trading Symbol Value Object
Represents and validates trading symbols
"""
import re
from typing import Optional
from datetime import date
from ..entities.base import ValueObject


class TradingSymbol(ValueObject):
    """Value object representing a trading symbol"""
    
    def __init__(self, symbol: str):
        if not symbol:
            raise ValueError("Trading symbol cannot be empty")
        
        self._raw_symbol = symbol.upper().strip()
        self._parse_symbol()
    
    def _parse_symbol(self):
        """Parse the trading symbol to extract components"""
        # Pattern for options: NIFTY25JAN23500CE
        option_pattern = r'^([A-Z]+)(\d{2}[A-Z]{3}\d{2})(\d+)(CE|PE)$'
        
        # Pattern for futures: NIFTY25JAN
        future_pattern = r'^([A-Z]+)(\d{2}[A-Z]{3}\d{2})$'
        
        # Pattern for equity/index: NIFTY, RELIANCE
        equity_pattern = r'^([A-Z]+)$'
        
        # Try to match options pattern
        option_match = re.match(option_pattern, self._raw_symbol)
        if option_match:
            self._underlying = option_match.group(1)
            self._expiry_str = option_match.group(2)
            self._strike = int(option_match.group(3))
            self._option_type = option_match.group(4)
            self._instrument_type = "OPTION"
            return
        
        # Try to match futures pattern
        future_match = re.match(future_pattern, self._raw_symbol)
        if future_match:
            self._underlying = future_match.group(1)
            self._expiry_str = future_match.group(2)
            self._strike = None
            self._option_type = None
            self._instrument_type = "FUTURE"
            return
        
        # Try to match equity pattern
        equity_match = re.match(equity_pattern, self._raw_symbol)
        if equity_match:
            self._underlying = equity_match.group(1)
            self._expiry_str = None
            self._strike = None
            self._option_type = None
            self._instrument_type = "EQUITY"
            return
        
        raise ValueError(f"Invalid trading symbol format: {self._raw_symbol}")
    
    @property
    def raw_symbol(self) -> str:
        """Get the raw trading symbol"""
        return self._raw_symbol
    
    @property
    def underlying(self) -> str:
        """Get the underlying instrument"""
        return self._underlying
    
    @property
    def expiry_str(self) -> Optional[str]:
        """Get the expiry string (e.g., 25JAN24)"""
        return self._expiry_str
    
    @property
    def strike(self) -> Optional[int]:
        """Get the strike price"""
        return self._strike
    
    @property
    def option_type(self) -> Optional[str]:
        """Get the option type (CE/PE)"""
        return self._option_type
    
    @property
    def instrument_type(self) -> str:
        """Get the instrument type"""
        return self._instrument_type
    
    @property
    def is_option(self) -> bool:
        """Check if this is an option"""
        return self._instrument_type == "OPTION"
    
    @property
    def is_future(self) -> bool:
        """Check if this is a future"""
        return self._instrument_type == "FUTURE"
    
    @property
    def is_equity(self) -> bool:
        """Check if this is an equity/index"""
        return self._instrument_type == "EQUITY"
    
    @property
    def is_call(self) -> bool:
        """Check if this is a call option"""
        return self.is_option and self._option_type == "CE"
    
    @property
    def is_put(self) -> bool:
        """Check if this is a put option"""
        return self.is_option and self._option_type == "PE"
    
    @property
    def is_index(self) -> bool:
        """Check if this is an index"""
        return self._underlying in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
    
    def get_expiry_date(self) -> Optional[date]:
        """Parse and return expiry date"""
        if not self._expiry_str:
            return None
        
        # Parse format: 25JAN24 -> 2025-01-24
        try:
            year = 2000 + int(self._expiry_str[-2:])
            month_str = self._expiry_str[2:5]
            day = int(self._expiry_str[:2])
            
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
                'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
                'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            
            month = month_map.get(month_str)
            if not month:
                raise ValueError(f"Invalid month: {month_str}")
            
            return date(year, month, day)
        except Exception as e:
            raise ValueError(f"Cannot parse expiry date from {self._expiry_str}: {e}")
    
    @staticmethod
    def create_option_symbol(
        underlying: str,
        expiry_date: date,
        strike: int,
        option_type: str
    ) -> 'TradingSymbol':
        """Create an option trading symbol"""
        if option_type not in ["CE", "PE"]:
            raise ValueError("Option type must be CE or PE")
        
        expiry_str = expiry_date.strftime('%y%b%d').upper()
        symbol = f"{underlying.upper()}{expiry_str}{strike}{option_type}"
        return TradingSymbol(symbol)
    
    @staticmethod
    def create_future_symbol(underlying: str, expiry_date: date) -> 'TradingSymbol':
        """Create a future trading symbol"""
        expiry_str = expiry_date.strftime('%y%b%d').upper()
        symbol = f"{underlying.upper()}{expiry_str}"
        return TradingSymbol(symbol)
    
    def __str__(self) -> str:
        return self._raw_symbol
    
    def __repr__(self) -> str:
        return f"TradingSymbol('{self._raw_symbol}')"
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'symbol': self._raw_symbol,
            'underlying': self._underlying,
            'expiry_str': self._expiry_str,
            'strike': self._strike,
            'option_type': self._option_type,
            'instrument_type': self._instrument_type,
            'is_index': self.is_index
        }