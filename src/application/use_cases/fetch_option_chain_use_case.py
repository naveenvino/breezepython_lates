"""
Fetch Option Chain Use Case
Application use case for fetching and analyzing option chains
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from ..dto.requests import CollectOptionChainRequest, AnalyzeOptionChainRequest
from ..dto.responses import (
    CollectOptionChainResponse,
    AnalyzeOptionChainResponse,
    OptionChainStrike,
    OptionGreeks,
    BaseResponse,
    ResponseStatus
)
from ..interfaces.idata_collector import IDataCollector
from ...domain.repositories.imarket_data_repository import IMarketDataRepository
from ...domain.repositories.ioptions_repository import IOptionsRepository
from ...domain.services.iprice_calculator import IPriceCalculator
from ...domain.entities.option import Option, OptionType
from ...domain.value_objects.strike_price import StrikePrice
from ...domain.entities.market_data import TimeInterval

logger = logging.getLogger(__name__)


class FetchOptionChainUseCase:
    """Use case for fetching option chain data"""
    
    def __init__(
        self,
        data_collector: IDataCollector,
        options_repo: IOptionsRepository,
        market_data_repo: IMarketDataRepository
    ):
        self.data_collector = data_collector
        self.options_repo = options_repo
        self.market_data_repo = market_data_repo
    
    async def execute(
        self,
        request: CollectOptionChainRequest
    ) -> BaseResponse[CollectOptionChainResponse]:
        """Execute the use case to fetch option chain"""
        try:
            start_time = datetime.now()
            
            # Get current expiry if not provided
            expiry_date = request.expiry_date
            if not expiry_date:
                expiry_date = await self._get_current_expiry(request.symbol)
            
            logger.info(f"Fetching option chain for {request.symbol} expiry {expiry_date}")
            
            # Fetch option chain from data collector
            result = await self.data_collector.collect_option_chain(
                symbol=request.symbol,
                expiry_date=expiry_date,
                save_to_db=request.save_to_db
            )
            
            if not result or "error" in result:
                return BaseResponse(
                    status=ResponseStatus.ERROR,
                    message=f"Failed to fetch option chain: {result.get('error', 'Unknown error')}",
                    errors=[result.get('error', 'Unknown error')]
                )
            
            # Extract chain data
            chain_data = result.get("chain_data", {})
            records_saved = 0
            
            if request.save_to_db and chain_data:
                records_saved = await self._save_chain_to_db(
                    chain_data, request.symbol, expiry_date
                )
            
            # Calculate strikes count
            strikes_count = len(chain_data.get("strikes", []))
            
            response_data = CollectOptionChainResponse(
                symbol=request.symbol,
                expiry_date=expiry_date,
                timestamp=datetime.now(),
                strikes_count=strikes_count,
                records_saved=records_saved,
                chain_data=chain_data if not request.save_to_db else None
            )
            
            return BaseResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Successfully fetched option chain with {strikes_count} strikes",
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"Error in FetchOptionChainUseCase: {e}", exc_info=True)
            return BaseResponse(
                status=ResponseStatus.ERROR,
                message=f"Failed to fetch option chain: {str(e)}",
                errors=[str(e)]
            )
    
    async def _get_current_expiry(self, symbol: str) -> date:
        """Get current/nearest expiry for the symbol"""
        # For NIFTY, weekly expiry is Thursday
        today = date.today()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0 and datetime.now().hour >= 15:  # Past 3:30 PM
            days_until_thursday = 7
        
        return today + timedelta(days=days_until_thursday)
    
    async def _save_chain_to_db(
        self,
        chain_data: Dict[str, Any],
        symbol: str,
        expiry_date: date
    ) -> int:
        """Save option chain data to database"""
        records_saved = 0
        
        for strike_data in chain_data.get("strikes", []):
            strike_price = strike_data.get("strike_price")
            
            # Save call option
            if strike_data.get("call_data"):
                call_option = self._create_option_entity(
                    symbol, strike_price, expiry_date, 
                    OptionType.CALL, strike_data["call_data"]
                )
                await self.options_repo.save(call_option)
                records_saved += 1
            
            # Save put option
            if strike_data.get("put_data"):
                put_option = self._create_option_entity(
                    symbol, strike_price, expiry_date,
                    OptionType.PUT, strike_data["put_data"]
                )
                await self.options_repo.save(put_option)
                records_saved += 1
        
        return records_saved
    
    def _create_option_entity(
        self,
        symbol: str,
        strike: float,
        expiry: date,
        option_type: OptionType,
        data: Dict[str, Any]
    ) -> Option:
        """Create option entity from chain data"""
        return Option(
            symbol=f"{symbol}{expiry.strftime('%y%b').upper()}{int(strike)}{option_type.value}",
            underlying=symbol,
            strike_price=StrikePrice(Decimal(str(strike)), symbol),
            expiry_date=expiry,
            option_type=option_type,
            last_price=Decimal(str(data.get("last_price", 0))),
            volume=data.get("volume", 0),
            open_interest=data.get("open_interest", 0),
            bid_price=Decimal(str(data.get("bid_price", 0))),
            ask_price=Decimal(str(data.get("ask_price", 0))),
            implied_volatility=Decimal(str(data.get("iv", 0))) if data.get("iv") else None
        )


class AnalyzeOptionChainUseCase:
    """Use case for analyzing option chain"""
    
    def __init__(
        self,
        options_repo: IOptionsRepository,
        market_data_repo: IMarketDataRepository,
        price_calculator: IPriceCalculator
    ):
        self.options_repo = options_repo
        self.market_data_repo = market_data_repo
        self.price_calculator = price_calculator
    
    async def execute(
        self,
        request: AnalyzeOptionChainRequest
    ) -> BaseResponse[AnalyzeOptionChainResponse]:
        """Execute the use case to analyze option chain"""
        try:
            # Get spot price if not provided
            spot_price = request.spot_price
            if not spot_price:
                spot_price = await self._get_spot_price(request.symbol)
            
            if not spot_price:
                return BaseResponse(
                    status=ResponseStatus.ERROR,
                    message="Unable to get spot price",
                    errors=["Spot price not available"]
                )
            
            # Get expiry if not provided
            expiry_date = request.expiry_date
            if not expiry_date:
                expiry_date = await self._get_current_expiry(request.symbol)
            
            # Get option chain data
            options = await self.options_repo.get_option_chain(
                underlying=request.symbol,
                expiry_date=expiry_date
            )
            
            if not options:
                return BaseResponse(
                    status=ResponseStatus.ERROR,
                    message="No option chain data available",
                    errors=["Option chain not found"]
                )
            
            # Analyze chain
            strikes = await self._analyze_strikes(
                options, spot_price, request.strike_range, request.include_greeks
            )
            
            # Calculate key metrics
            max_call_oi_strike = self._find_max_oi_strike(options, OptionType.CALL)
            max_put_oi_strike = self._find_max_oi_strike(options, OptionType.PUT)
            put_call_ratio = self._calculate_pcr(options)
            
            # Find support/resistance levels
            support_levels = self._find_support_levels(options, spot_price)
            resistance_levels = self._find_resistance_levels(options, spot_price)
            
            # Calculate IV skew
            iv_skew = self._calculate_iv_skew(options, spot_price)
            
            response_data = AnalyzeOptionChainResponse(
                symbol=request.symbol,
                expiry_date=expiry_date,
                spot_price=spot_price,
                analysis_time=datetime.now(),
                strikes=strikes,
                max_call_oi_strike=max_call_oi_strike,
                max_put_oi_strike=max_put_oi_strike,
                put_call_ratio=put_call_ratio,
                support_levels=support_levels,
                resistance_levels=resistance_levels,
                iv_skew=iv_skew
            )
            
            return BaseResponse(
                status=ResponseStatus.SUCCESS,
                message="Option chain analysis completed",
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"Error in AnalyzeOptionChainUseCase: {e}", exc_info=True)
            return BaseResponse(
                status=ResponseStatus.ERROR,
                message=f"Failed to analyze option chain: {str(e)}",
                errors=[str(e)]
            )
    
    async def _get_spot_price(self, symbol: str) -> Optional[Decimal]:
        """Get current spot price"""
        try:
            # Get latest market data
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=1)
            
            data = await self.market_data_repo.get_by_symbol_and_date_range(
                symbol=f"{symbol} 50",
                start_date=start_time,
                end_date=end_time,
                interval=TimeInterval.ONE_MINUTE
            )
            
            if data:
                return data[-1].close  # Latest close price
            
            return None
        except Exception as e:
            logger.error(f"Error getting spot price: {e}")
            return None
    
    async def _get_current_expiry(self, symbol: str) -> date:
        """Get current/nearest expiry"""
        from datetime import timedelta
        today = date.today()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0 and datetime.now().hour >= 15:
            days_until_thursday = 7
        
        return today + timedelta(days=days_until_thursday)
    
    async def _analyze_strikes(
        self,
        options: List[Option],
        spot_price: Decimal,
        strike_range: Optional[int],
        include_greeks: bool
    ) -> List[OptionChainStrike]:
        """Analyze individual strikes"""
        strikes_dict = {}
        
        for option in options:
            strike = float(option.strike_price.price)
            
            # Filter by strike range if provided
            if strike_range and abs(strike - float(spot_price)) > strike_range:
                continue
            
            if strike not in strikes_dict:
                strikes_dict[strike] = OptionChainStrike(
                    strike=Decimal(str(strike)),
                    call_data=None,
                    put_data=None,
                    call_greeks=None,
                    put_greeks=None
                )
            
            # Prepare option data
            option_data = {
                "last_price": float(option.last_price),
                "volume": option.volume,
                "open_interest": option.open_interest,
                "bid": float(option.bid_price),
                "ask": float(option.ask_price),
                "iv": float(option.implied_volatility) if option.implied_volatility else None
            }
            
            if option.option_type == OptionType.CALL:
                strikes_dict[strike].call_data = option_data
                if include_greeks and option.delta is not None:
                    strikes_dict[strike].call_greeks = OptionGreeks(
                        delta=option.delta,
                        gamma=option.gamma,
                        theta=option.theta,
                        vega=option.vega,
                        rho=option.rho
                    )
            else:
                strikes_dict[strike].put_data = option_data
                if include_greeks and option.delta is not None:
                    strikes_dict[strike].put_greeks = OptionGreeks(
                        delta=option.delta,
                        gamma=option.gamma,
                        theta=option.theta,
                        vega=option.vega,
                        rho=option.rho
                    )
        
        # Sort by strike price
        return sorted(strikes_dict.values(), key=lambda x: x.strike)
    
    def _find_max_oi_strike(
        self,
        options: List[Option],
        option_type: OptionType
    ) -> Optional[Decimal]:
        """Find strike with maximum open interest"""
        filtered_options = [o for o in options if o.option_type == option_type]
        if not filtered_options:
            return None
        
        max_oi_option = max(filtered_options, key=lambda x: x.open_interest)
        return max_oi_option.strike_price.price
    
    def _calculate_pcr(self, options: List[Option]) -> Optional[Decimal]:
        """Calculate Put-Call Ratio"""
        call_oi = sum(o.open_interest for o in options if o.option_type == OptionType.CALL)
        put_oi = sum(o.open_interest for o in options if o.option_type == OptionType.PUT)
        
        if call_oi > 0:
            return Decimal(str(put_oi)) / Decimal(str(call_oi))
        return None
    
    def _find_support_levels(
        self,
        options: List[Option],
        spot_price: Decimal
    ) -> List[Decimal]:
        """Find support levels based on put OI"""
        put_options = [o for o in options if o.option_type == OptionType.PUT]
        put_options = [o for o in put_options if o.strike_price.price < spot_price]
        
        # Sort by OI descending
        put_options.sort(key=lambda x: x.open_interest, reverse=True)
        
        # Return top 3 strikes as support levels
        return [o.strike_price.price for o in put_options[:3]]
    
    def _find_resistance_levels(
        self,
        options: List[Option],
        spot_price: Decimal
    ) -> List[Decimal]:
        """Find resistance levels based on call OI"""
        call_options = [o for o in options if o.option_type == OptionType.CALL]
        call_options = [o for o in call_options if o.strike_price.price > spot_price]
        
        # Sort by OI descending
        call_options.sort(key=lambda x: x.open_interest, reverse=True)
        
        # Return top 3 strikes as resistance levels
        return [o.strike_price.price for o in call_options[:3]]
    
    def _calculate_iv_skew(
        self,
        options: List[Option],
        spot_price: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Calculate implied volatility skew"""
        try:
            # Get ATM strike
            atm_strike = self._find_atm_strike(options, spot_price)
            
            # Get IV for different strikes
            otm_put_ivs = []
            atm_ivs = []
            otm_call_ivs = []
            
            for option in options:
                if option.implied_volatility is None:
                    continue
                    
                strike = float(option.strike_price.price)
                iv = float(option.implied_volatility)
                
                if abs(strike - float(atm_strike)) < 50:  # ATM
                    atm_ivs.append(iv)
                elif strike < float(atm_strike) - 100 and option.option_type == OptionType.PUT:  # OTM Put
                    otm_put_ivs.append(iv)
                elif strike > float(atm_strike) + 100 and option.option_type == OptionType.CALL:  # OTM Call
                    otm_call_ivs.append(iv)
            
            if not atm_ivs:
                return None
            
            avg_atm_iv = sum(atm_ivs) / len(atm_ivs)
            
            skew_data = {
                "atm_iv": avg_atm_iv,
                "skew_type": "neutral"
            }
            
            if otm_put_ivs and otm_call_ivs:
                avg_put_iv = sum(otm_put_ivs) / len(otm_put_ivs)
                avg_call_iv = sum(otm_call_ivs) / len(otm_call_ivs)
                
                if avg_put_iv > avg_call_iv * 1.1:
                    skew_data["skew_type"] = "negative"  # Put skew
                elif avg_call_iv > avg_put_iv * 1.1:
                    skew_data["skew_type"] = "positive"  # Call skew
                
                skew_data["put_iv"] = avg_put_iv
                skew_data["call_iv"] = avg_call_iv
            
            return skew_data
            
        except Exception as e:
            logger.error(f"Error calculating IV skew: {e}")
            return None
    
    def _find_atm_strike(self, options: List[Option], spot_price: Decimal) -> Decimal:
        """Find at-the-money strike"""
        strikes = list(set(o.strike_price.price for o in options))
        strikes.sort(key=lambda x: abs(x - spot_price))
        return strikes[0] if strikes else spot_price