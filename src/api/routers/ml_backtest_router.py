"""
ML Backtest Router
API endpoints for running ML-enhanced backtests with 5-minute granularity
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict
import logging

from ...application.use_cases.run_backtest_ml import RunMLBacktestUseCase, MLBacktestParameters
from ...infrastructure.services.data_collection_service import DataCollectionService
from ...infrastructure.services.option_pricing_service import OptionPricingService
from ...config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml/backtest", tags=["ML Backtest"])

# Request Models
class RunMLBacktestRequest(BaseModel):
    from_date: date
    to_date: date
    initial_capital: float = 500000
    lots_to_trade: int = 10
    signals_to_test: List[str] = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
    use_hedging: bool = True
    hedge_offset: int = 200
    # ML Features
    use_ml_exits: bool = True
    use_trailing_stops: bool = True
    use_profit_targets: bool = True
    use_position_adjustments: bool = True
    use_regime_filter: bool = True
    granularity_minutes: int = 5
    ml_confidence_threshold: float = 0.7
    partial_exit_enabled: bool = True
    wednesday_exit_enabled: bool = True
    breakeven_enabled: bool = True

class CompareBacktestRequest(BaseModel):
    from_date: date
    to_date: date
    signals_to_test: List[str] = ["S1", "S3", "S7"]

# Initialize services
settings = get_settings()
db_connection = settings.database.connection_string
data_collection = DataCollectionService(db_connection)
option_pricing = OptionPricingService(db_connection)

@router.post("/run", summary="Run ML-Enhanced Backtest")
async def run_ml_backtest(
    request: RunMLBacktestRequest,
    background_tasks: BackgroundTasks
):
    """
    Run backtest with ML exit optimization and 5-minute granularity
    
    Features:
    - ML-powered exit predictions
    - Dynamic trailing stops
    - Profit target optimization
    - Position adjustments
    - Market regime filtering
    - 5-minute bar processing
    
    Returns backtest ID for tracking
    """
    try:
        # Create ML backtest parameters
        params = MLBacktestParameters(
            from_date=datetime.combine(request.from_date, datetime.min.time()),
            to_date=datetime.combine(request.to_date, datetime.max.time()),
            initial_capital=request.initial_capital,
            lots_to_trade=request.lots_to_trade,
            signals_to_test=request.signals_to_test,
            use_hedging=request.use_hedging,
            hedge_offset=request.hedge_offset,
            use_ml_exits=request.use_ml_exits,
            use_trailing_stops=request.use_trailing_stops,
            use_profit_targets=request.use_profit_targets,
            use_position_adjustments=request.use_position_adjustments,
            use_regime_filter=request.use_regime_filter,
            granularity_minutes=request.granularity_minutes,
            ml_confidence_threshold=request.ml_confidence_threshold,
            partial_exit_enabled=request.partial_exit_enabled,
            wednesday_exit_enabled=request.wednesday_exit_enabled,
            breakeven_enabled=request.breakeven_enabled
        )
        
        # Initialize use case
        use_case = RunMLBacktestUseCase(
            data_collection_service=data_collection,
            option_pricing_service=option_pricing,
            db_connection_string=db_connection
        )
        
        # Run backtest in background
        background_tasks.add_task(
            use_case.execute,
            params
        )
        
        return {
            "status": "started",
            "message": "ML-enhanced backtest started in background",
            "parameters": {
                "period": f"{request.from_date} to {request.to_date}",
                "signals": request.signals_to_test,
                "ml_features": {
                    "exits": request.use_ml_exits,
                    "trailing_stops": request.use_trailing_stops,
                    "profit_targets": request.use_profit_targets,
                    "adjustments": request.use_position_adjustments,
                    "regime_filter": request.use_regime_filter
                },
                "granularity": f"{request.granularity_minutes} minutes"
            }
        }
        
    except Exception as e:
        logger.error(f"Error starting ML backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compare", summary="Compare Standard vs ML Backtest")
async def compare_backtests(
    request: CompareBacktestRequest,
    background_tasks: BackgroundTasks
):
    """
    Run both standard and ML-enhanced backtests for comparison
    
    Returns performance comparison metrics
    """
    try:
        from_dt = datetime.combine(request.from_date, datetime.min.time())
        to_dt = datetime.combine(request.to_date, datetime.max.time())
        
        # Run standard backtest (hourly, no ML)
        standard_params = MLBacktestParameters(
            from_date=from_dt,
            to_date=to_dt,
            signals_to_test=request.signals_to_test,
            use_ml_exits=False,
            use_trailing_stops=False,
            use_profit_targets=False,
            use_position_adjustments=False,
            use_regime_filter=False,
            granularity_minutes=60  # Hourly
        )
        
        # Run ML-enhanced backtest (5-min, all features)
        ml_params = MLBacktestParameters(
            from_date=from_dt,
            to_date=to_dt,
            signals_to_test=request.signals_to_test,
            use_ml_exits=True,
            use_trailing_stops=True,
            use_profit_targets=True,
            use_position_adjustments=True,
            use_regime_filter=True,
            granularity_minutes=5  # 5-minute
        )
        
        # Initialize use case
        use_case = RunMLBacktestUseCase(
            data_collection_service=data_collection,
            option_pricing_service=option_pricing,
            db_connection_string=db_connection
        )
        
        # Run both backtests
        logger.info("Starting standard backtest...")
        standard_id = await use_case.execute(standard_params)
        
        logger.info("Starting ML-enhanced backtest...")
        ml_id = await use_case.execute(ml_params)
        
        # Get results for comparison
        comparison = await _compare_results(standard_id, ml_id)
        
        return {
            "standard_backtest_id": standard_id,
            "ml_backtest_id": ml_id,
            "comparison": comparison,
            "summary": {
                "improvement_pnl": f"{comparison['pnl_improvement']:.1%}",
                "improvement_win_rate": f"{comparison['win_rate_improvement']:.1%}",
                "improvement_profit_capture": f"{comparison['profit_capture_improvement']:.1%}",
                "recommendation": comparison['recommendation']
            }
        }
        
    except Exception as e:
        logger.error(f"Error comparing backtests: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/{backtest_id}", summary="Get ML Backtest Results")
async def get_ml_backtest_results(backtest_id: str):
    """
    Get detailed results of ML-enhanced backtest
    
    Returns comprehensive metrics including ML-specific performance
    """
    try:
        from ...infrastructure.database.database_manager import get_db_manager
        from ...infrastructure.database.models import BacktestRun, BacktestTrade
        
        db_manager = get_db_manager()
        
        with db_manager.get_session() as session:
            # Get backtest run
            backtest = session.query(BacktestRun).filter_by(id=backtest_id).first()
            
            if not backtest:
                raise HTTPException(status_code=404, detail="Backtest not found")
            
            # Get trades
            trades = session.query(BacktestTrade).filter_by(
                backtest_run_id=backtest_id
            ).all()
            
            # Calculate ML-specific metrics
            ml_exits = [t for t in trades if 'ML Exit' in (t.exit_reason or '')]
            trailing_stops = [t for t in trades if 'Trailing' in (t.exit_reason or '')]
            target_hits = [t for t in trades if 'Target' in (t.exit_reason or '')]
            wednesday_exits = [t for t in trades if t.exit_time and t.exit_time.weekday() == 2]
            
            # Get metadata if available
            metadata = backtest.metadata if hasattr(backtest, 'metadata') else {}
            
            return {
                "backtest_id": backtest_id,
                "status": backtest.status.value if backtest.status else "unknown",
                "period": {
                    "from": backtest.from_date.isoformat(),
                    "to": backtest.to_date.isoformat()
                },
                "performance": {
                    "total_trades": backtest.total_trades,
                    "winning_trades": backtest.winning_trades,
                    "losing_trades": backtest.losing_trades,
                    "win_rate": float(backtest.win_rate) if backtest.win_rate else 0,
                    "total_pnl": float(backtest.total_pnl) if backtest.total_pnl else 0,
                    "total_return": float(backtest.total_return_percent) if backtest.total_return_percent else 0,
                    "max_drawdown": float(backtest.max_drawdown_percent) if backtest.max_drawdown_percent else 0
                },
                "ml_metrics": {
                    "ml_exit_trades": len(ml_exits),
                    "ml_exit_success_rate": len([t for t in ml_exits if t.outcome.value == 'WIN']) / len(ml_exits) if ml_exits else 0,
                    "trailing_stop_trades": len(trailing_stops),
                    "profit_target_hits": len(target_hits),
                    "wednesday_exits": len(wednesday_exits),
                    "avg_profit_capture": metadata.get('avg_profit_capture', 0),
                    "partial_exits_count": metadata.get('partial_exits_count', 0)
                },
                "exit_analysis": {
                    "ml_exits": f"{len(ml_exits)/len(trades)*100:.1f}%" if trades else "0%",
                    "trailing_stops": f"{len(trailing_stops)/len(trades)*100:.1f}%" if trades else "0%",
                    "profit_targets": f"{len(target_hits)/len(trades)*100:.1f}%" if trades else "0%",
                    "stop_losses": f"{len([t for t in trades if t.outcome.value == 'STOPPED'])/len(trades)*100:.1f}%" if trades else "0%",
                    "expiry": f"{len([t for t in trades if t.outcome.value == 'EXPIRED'])/len(trades)*100:.1f}%" if trades else "0%"
                },
                "configuration": {
                    "ml_exits": metadata.get('ml_exits', False),
                    "trailing_stops": metadata.get('trailing_stops', False),
                    "profit_targets": metadata.get('profit_targets', False),
                    "position_adjustments": metadata.get('position_adjustments', False),
                    "regime_filter": metadata.get('regime_filter', False),
                    "granularity_minutes": metadata.get('granularity_minutes', 60)
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ML backtest results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _compare_results(standard_id: str, ml_id: str) -> Dict:
    """Compare standard vs ML backtest results"""
    from ...infrastructure.database.database_manager import get_db_manager
    from ...infrastructure.database.models import BacktestRun
    
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        standard = session.query(BacktestRun).filter_by(id=standard_id).first()
        ml = session.query(BacktestRun).filter_by(id=ml_id).first()
        
        if not standard or not ml:
            return {}
        
        # Calculate improvements
        pnl_improvement = (float(ml.total_pnl) - float(standard.total_pnl)) / abs(float(standard.total_pnl)) if standard.total_pnl else 0
        win_rate_improvement = (float(ml.win_rate) - float(standard.win_rate)) / float(standard.win_rate) if standard.win_rate else 0
        
        # Profit capture improvement (from metadata)
        ml_capture = ml.metadata.get('avg_profit_capture', 0) if hasattr(ml, 'metadata') else 0
        standard_capture = 0.6  # Assume 60% for standard
        profit_capture_improvement = (ml_capture - standard_capture) / standard_capture if standard_capture else 0
        
        # Generate recommendation
        if pnl_improvement > 0.2 and win_rate_improvement > 0.1:
            recommendation = "Strong improvement with ML - Recommended for live trading"
        elif pnl_improvement > 0.1:
            recommendation = "Moderate improvement with ML - Consider for specific signals"
        else:
            recommendation = "Marginal improvement - Further optimization needed"
        
        return {
            'pnl_improvement': pnl_improvement,
            'win_rate_improvement': win_rate_improvement,
            'profit_capture_improvement': profit_capture_improvement,
            'standard_metrics': {
                'total_pnl': float(standard.total_pnl) if standard.total_pnl else 0,
                'win_rate': float(standard.win_rate) if standard.win_rate else 0,
                'max_drawdown': float(standard.max_drawdown_percent) if standard.max_drawdown_percent else 0
            },
            'ml_metrics': {
                'total_pnl': float(ml.total_pnl) if ml.total_pnl else 0,
                'win_rate': float(ml.win_rate) if ml.win_rate else 0,
                'max_drawdown': float(ml.max_drawdown_percent) if ml.max_drawdown_percent else 0
            },
            'recommendation': recommendation
        }

@router.get("/live-signals", summary="Get Live ML Trading Signals")
async def get_live_ml_signals():
    """
    Get current ML-powered trading recommendations
    
    Returns signals with ML confidence scores and exit strategies
    """
    try:
        from ...ml.market_regime_classifier import MarketRegimeClassifier
        from ...ml.profit_target_optimizer import ProfitTargetOptimizer
        
        # Initialize ML components
        regime_classifier = MarketRegimeClassifier(db_connection)
        profit_optimizer = ProfitTargetOptimizer(db_connection)
        
        # Get current market regime
        regime = regime_classifier.classify_current_regime("NIFTY", 20)
        
        # Get optimal targets for today
        today = datetime.now().date()
        targets = profit_optimizer.optimize_targets(
            datetime.combine(today - timedelta(days=30), datetime.min.time()),
            datetime.combine(today, datetime.max.time())
        )
        
        # Build recommendations
        recommendations = []
        for signal in regime.recommended_strategies[:3]:  # Top 3 signals
            if signal in targets:
                target = targets[signal]
                recommendations.append({
                    'signal': signal,
                    'confidence': regime.confidence,
                    'profit_target': target.primary_target,
                    'stop_loss': target.minimum_target,
                    'expected_success_rate': target.expected_achievement_rate,
                    'exit_strategy': {
                        'partial_exit_1': f"{target.first_exit_level:.0f} ({target.first_exit_percentage*100:.0f}%)",
                        'partial_exit_2': f"{target.second_exit_level:.0f} ({target.second_exit_percentage*100:.0f}%)",
                        'final_exit': f"{target.final_exit_level:.0f}"
                    }
                })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "market_regime": regime.current_regime.value,
            "regime_confidence": f"{regime.confidence:.1%}",
            "recommended_signals": recommendations,
            "risk_management": {
                "position_size": f"{regime.position_size_adjustment*100:.0f}% of normal",
                "stop_loss_adjustment": f"{regime.stop_loss_adjustment*100:.0f}% of normal",
                "max_positions": 2 if regime.current_regime.value in ['CHOPPY', 'HIGH_VOLATILITY'] else 3
            },
            "avoid_signals": regime.avoid_strategies
        }
        
    except Exception as e:
        logger.error(f"Error getting live ML signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))