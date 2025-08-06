"""
Analyze Data Availability Use Case
Application use case for analyzing data availability and gaps
"""
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

from ..dto.requests import AnalyzeDataAvailabilityRequest
from ..dto.responses import (
    AnalyzeDataAvailabilityResponse, 
    DataAvailabilitySummary,
    BaseResponse, 
    ResponseStatus
)
from ...domain.repositories.imarket_data_repository import IMarketDataRepository
from ...domain.repositories.ioptions_repository import IOptionsHistoricalDataRepository
from ...domain.entities.market_data import TimeInterval

logger = logging.getLogger(__name__)


class AnalyzeDataAvailabilityUseCase:
    """Use case for analyzing data availability"""
    
    def __init__(
        self,
        market_data_repo: IMarketDataRepository,
        options_data_repo: IOptionsHistoricalDataRepository
    ):
        self.market_data_repo = market_data_repo
        self.options_data_repo = options_data_repo
    
    async def execute(
        self, 
        request: AnalyzeDataAvailabilityRequest
    ) -> BaseResponse[AnalyzeDataAvailabilityResponse]:
        """Execute the use case"""
        try:
            # Set default date range if not provided
            from_date = request.from_date or date(2024, 1, 1)
            to_date = request.to_date or date.today()
            
            nifty_summary = None
            options_summary = None
            recommendations = []
            detailed_gaps = {}
            
            # Analyze based on data type
            if request.data_type in ["all", "nifty"]:
                nifty_summary = await self._analyze_nifty_data(
                    from_date, to_date, request.include_gaps
                )
                if nifty_summary and request.include_gaps:
                    detailed_gaps["nifty"] = self._get_detailed_gaps(
                        nifty_summary.missing_dates, "NIFTY"
                    )
                    
            if request.data_type in ["all", "options"]:
                options_summary = await self._analyze_options_data(
                    from_date, to_date, request.symbol, request.include_gaps
                )
                if options_summary and request.include_gaps:
                    detailed_gaps["options"] = self._get_detailed_gaps(
                        options_summary.missing_dates, "Options"
                    )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                nifty_summary, options_summary, detailed_gaps
            )
            
            response_data = AnalyzeDataAvailabilityResponse(
                nifty_summary=nifty_summary,
                options_summary=options_summary,
                recommendations=recommendations,
                detailed_gaps=detailed_gaps if request.include_gaps else None
            )
            
            return BaseResponse(
                status=ResponseStatus.SUCCESS,
                message="Data availability analysis completed",
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"Error in AnalyzeDataAvailabilityUseCase: {e}", exc_info=True)
            return BaseResponse(
                status=ResponseStatus.ERROR,
                message=f"Failed to analyze data availability: {str(e)}",
                errors=[str(e)]
            )
    
    async def _analyze_nifty_data(
        self,
        from_date: date,
        to_date: date,
        include_gaps: bool
    ) -> Optional[DataAvailabilitySummary]:
        """Analyze NIFTY index data availability"""
        try:
            # Get all NIFTY data in range
            start_datetime = datetime.combine(from_date, datetime.min.time())
            end_datetime = datetime.combine(to_date, datetime.max.time())
            
            data = await self.market_data_repo.get_by_symbol_and_date_range(
                symbol="NIFTY 50",
                start_date=start_datetime,
                end_date=end_datetime,
                interval=TimeInterval.ONE_HOUR
            )
            
            if not data:
                return DataAvailabilitySummary(
                    total_records=0,
                    date_range={"start": None, "end": None},
                    unique_days=0,
                    completeness_percentage=0.0,
                    gaps_found=0,
                    missing_dates=[]
                )
            
            # Extract unique dates
            unique_dates = {d.timestamp.date() for d in data}
            
            # Calculate expected trading days
            expected_days = self._get_expected_trading_days(from_date, to_date)
            missing_dates = sorted(expected_days - unique_dates)
            
            # Create summary
            summary = DataAvailabilitySummary(
                total_records=len(data),
                date_range={
                    "start": min(d.timestamp for d in data),
                    "end": max(d.timestamp for d in data)
                },
                unique_days=len(unique_dates),
                completeness_percentage=(len(unique_dates) / len(expected_days) * 100) if expected_days else 0,
                gaps_found=len(missing_dates),
                missing_dates=missing_dates if include_gaps else []
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Error analyzing NIFTY data: {e}")
            return None
    
    async def _analyze_options_data(
        self,
        from_date: date,
        to_date: date,
        symbol: Optional[str],
        include_gaps: bool
    ) -> Optional[DataAvailabilitySummary]:
        """Analyze options data availability"""
        try:
            # Get options data count and date range
            stats = await self.options_data_repo.get_data_statistics(
                underlying=symbol or "NIFTY",
                from_date=from_date,
                to_date=to_date
            )
            
            if not stats or stats.get("total_records", 0) == 0:
                return DataAvailabilitySummary(
                    total_records=0,
                    date_range={"start": None, "end": None},
                    unique_days=0,
                    completeness_percentage=0.0,
                    gaps_found=0,
                    missing_dates=[]
                )
            
            # Get unique dates
            unique_dates = await self.options_data_repo.get_unique_dates(
                underlying=symbol or "NIFTY",
                from_date=from_date,
                to_date=to_date
            )
            
            unique_date_set = set(unique_dates)
            expected_days = self._get_expected_trading_days(from_date, to_date)
            missing_dates = sorted(expected_days - unique_date_set)
            
            # Create summary
            summary = DataAvailabilitySummary(
                total_records=stats["total_records"],
                date_range={
                    "start": stats.get("min_date"),
                    "end": stats.get("max_date")
                },
                unique_days=len(unique_dates),
                completeness_percentage=(len(unique_dates) / len(expected_days) * 100) if expected_days else 0,
                gaps_found=len(missing_dates),
                missing_dates=missing_dates if include_gaps else []
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Error analyzing options data: {e}")
            return None
    
    def _get_expected_trading_days(self, from_date: date, to_date: date) -> Set[date]:
        """Get expected trading days (excluding weekends and holidays)"""
        expected_days = set()
        current = from_date
        
        while current <= to_date:
            # Skip weekends
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                # TODO: Add holiday calendar check
                expected_days.add(current)
            current += timedelta(days=1)
        
        return expected_days
    
    def _get_detailed_gaps(
        self, 
        missing_dates: List[date], 
        data_type: str
    ) -> Dict[str, Any]:
        """Get detailed gap analysis"""
        if not missing_dates:
            return {"message": "No gaps found"}
        
        # Group consecutive dates
        gap_groups = []
        current_group = [missing_dates[0]]
        
        for i in range(1, len(missing_dates)):
            if (missing_dates[i] - missing_dates[i-1]).days == 1:
                current_group.append(missing_dates[i])
            else:
                gap_groups.append(current_group)
                current_group = [missing_dates[i]]
        
        if current_group:
            gap_groups.append(current_group)
        
        # Create gap summary
        gaps = []
        for group in gap_groups:
            gaps.append({
                "start_date": group[0].isoformat(),
                "end_date": group[-1].isoformat(),
                "days": len(group),
                "type": "consecutive" if len(group) > 1 else "single"
            })
        
        return {
            "total_missing_days": len(missing_dates),
            "gap_count": len(gaps),
            "gaps": gaps,
            "longest_gap": max(gaps, key=lambda x: x["days"]) if gaps else None
        }
    
    def _generate_recommendations(
        self,
        nifty_summary: Optional[DataAvailabilitySummary],
        options_summary: Optional[DataAvailabilitySummary],
        detailed_gaps: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # NIFTY data recommendations
        if nifty_summary:
            if nifty_summary.completeness_percentage < 80:
                recommendations.append(
                    f"NIFTY data is only {nifty_summary.completeness_percentage:.1f}% complete. "
                    "Consider collecting missing historical data."
                )
            
            if nifty_summary.gaps_found > 10:
                recommendations.append(
                    f"Found {nifty_summary.gaps_found} gaps in NIFTY data. "
                    "Run data collection for specific gap periods."
                )
        
        # Options data recommendations
        if options_summary:
            if options_summary.completeness_percentage < 70:
                recommendations.append(
                    f"Options data is only {options_summary.completeness_percentage:.1f}% complete. "
                    "This may affect backtest accuracy."
                )
            
            if options_summary.total_records < 1000:
                recommendations.append(
                    "Limited options data available. Consider expanding date range or strikes."
                )
        
        # Gap-based recommendations
        if detailed_gaps:
            for data_type, gap_info in detailed_gaps.items():
                if isinstance(gap_info, dict) and gap_info.get("longest_gap"):
                    longest = gap_info["longest_gap"]
                    if longest["days"] > 5:
                        recommendations.append(
                            f"{data_type.upper()}: Long gap of {longest['days']} days "
                            f"from {longest['start_date']} to {longest['end_date']}"
                        )
        
        # General recommendations
        if not recommendations:
            recommendations.append("Data availability looks good. Ready for analysis and backtesting.")
        
        return recommendations