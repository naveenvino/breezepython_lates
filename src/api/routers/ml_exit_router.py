"""
ML Exit Strategy Router
API endpoints for ML-powered exit optimization and dynamic risk management
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import logging

from ...ml.trade_lifecycle_analyzer import TradeLifecycleAnalyzer
from ...ml.exit_pattern_analyzer import ExitPatternAnalyzer
from ...ml.stoploss_optimizer import StopLossOptimizer
from ...ml.models.exit_predictor import ExitPredictor
from ...ml.trailing_stop_engine import TrailingStopEngine, TrailingStopType
from ...ml.market_regime_classifier import MarketRegimeClassifier
from ...config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml/exit", tags=["ML Exit Strategies"])

# Request/Response Models
class LifecycleAnalysisRequest(BaseModel):
    trade_id: Optional[int] = None
    from_date: date = date(2025, 1, 1)
    to_date: date = date(2025, 8, 6)
    granularity_minutes: int = 5

class ExitPatternRequest(BaseModel):
    from_date: date = date(2025, 1, 1)
    to_date: date = date(2025, 8, 6)
    min_pattern_occurrences: int = 2

class StopLossOptimizationRequest(BaseModel):
    from_date: date = date(2025, 1, 1)
    to_date: date = date(2025, 8, 6)
    signal_types: Optional[List[str]] = None

class CurrentTradeState(BaseModel):
    signal_type: str
    entry_time: datetime
    entry_price: float
    current_price: float
    current_pnl: float
    max_pnl: float
    time_in_trade_hours: float
    day_of_week: str
    hour: int
    quantity: int = 750
    volatility: Optional[float] = None
    delta: Optional[float] = None

class OptimalExitRequest(BaseModel):
    trade_id: int

# Initialize analyzers
settings = get_settings()
db_connection = settings.database.connection_string

lifecycle_analyzer = TradeLifecycleAnalyzer(db_connection)
pattern_analyzer = ExitPatternAnalyzer(db_connection)
stoploss_optimizer = StopLossOptimizer(db_connection)
exit_predictor = ExitPredictor(db_connection)
trailing_stop_engine = TrailingStopEngine(db_connection)
regime_classifier = MarketRegimeClassifier(db_connection)

@router.post("/analyze-lifecycle", summary="Analyze Trade Lifecycle")
async def analyze_trade_lifecycle(request: LifecycleAnalysisRequest):
    """
    Analyze complete lifecycle of trades to identify profit patterns
    
    Returns:
    - Maximum profit points
    - Time to peak profit
    - Profit decay patterns
    - Optimal exit timing
    """
    try:
        if request.trade_id:
            # Analyze single trade
            metrics = lifecycle_analyzer.analyze_trade_lifecycle(
                request.trade_id,
                request.granularity_minutes
            )
            
            if not metrics:
                raise HTTPException(status_code=404, detail=f"Trade {request.trade_id} not found")
            
            return {
                "trade_id": request.trade_id,
                "metrics": metrics.to_dict(),
                "analysis_summary": {
                    "profit_capture_efficiency": f"{metrics.profit_capture_ratio:.1%}",
                    "time_to_max_profit": f"{metrics.time_to_max_profit_hours:.1f} hours",
                    "best_exit_time": f"{metrics.best_exit_day} {metrics.best_exit_hour}:00",
                    "profit_left_on_table": metrics.max_profit - metrics.final_pnl
                }
            }
        else:
            # Analyze all trades in date range
            df_metrics = lifecycle_analyzer.analyze_all_trades(
                datetime.combine(request.from_date, datetime.min.time()),
                datetime.combine(request.to_date, datetime.max.time())
            )
            
            if df_metrics.empty:
                return {
                    "message": "No trades found in the specified date range",
                    "trades_analyzed": 0
                }
            
            # Summary statistics
            summary = {
                "trades_analyzed": len(df_metrics),
                "avg_profit_capture": f"{df_metrics['profit_capture_ratio'].mean():.1%}",
                "avg_time_to_max_profit": f"{df_metrics['time_to_max_profit_hours'].mean():.1f} hours",
                "best_exit_days": df_metrics['best_exit_day'].value_counts().to_dict(),
                "avg_profit_decay": f"{df_metrics['profit_decay_from_peak'].mean():.1%}"
            }
            
            # Signal-specific insights
            signal_insights = {}
            for signal in df_metrics['signal_type'].unique():
                signal_df = df_metrics[df_metrics['signal_type'] == signal]
                signal_insights[signal] = {
                    "trades": len(signal_df),
                    "avg_capture_ratio": f"{signal_df['profit_capture_ratio'].mean():.1%}",
                    "best_exit_day": signal_df['best_exit_day'].mode()[0] if not signal_df['best_exit_day'].mode().empty else "N/A",
                    "best_exit_hour": int(signal_df['best_exit_hour'].mode()[0]) if not signal_df['best_exit_hour'].mode().empty else 0
                }
            
            return {
                "analysis_period": {
                    "from": request.from_date.isoformat(),
                    "to": request.to_date.isoformat()
                },
                "summary": summary,
                "signal_insights": signal_insights,
                "trades": df_metrics.to_dict('records')[:10]  # Return first 10 for brevity
            }
            
    except Exception as e:
        logger.error(f"Error in lifecycle analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/discover-patterns", summary="Discover Exit Patterns")
async def discover_exit_patterns(request: ExitPatternRequest):
    """
    Discover optimal exit patterns from historical data
    
    Returns:
    - Time-based patterns (best exit times)
    - Day-specific patterns (Wednesday morning, Thursday expiry)
    - Profit-based patterns (exit at X% of max profit)
    - Volatility patterns (exit during high volatility)
    """
    try:
        patterns = pattern_analyzer.discover_patterns(
            datetime.combine(request.from_date, datetime.min.time()),
            datetime.combine(request.to_date, datetime.max.time()),
            request.min_pattern_occurrences
        )
        
        if not patterns:
            return {
                "message": "No significant patterns discovered",
                "patterns": []
            }
        
        # Group patterns by type
        patterns_by_type = {}
        for pattern in patterns:
            pattern_type = pattern.pattern_type
            if pattern_type not in patterns_by_type:
                patterns_by_type[pattern_type] = []
            patterns_by_type[pattern_type].append(pattern.to_dict())
        
        # Key insights
        insights = []
        
        # Wednesday morning pattern
        wed_patterns = [p for p in patterns if p.day_of_week == 'Wednesday' and p.hour_of_day and p.hour_of_day <= 12]
        if wed_patterns:
            best_wed = max(wed_patterns, key=lambda x: x.avg_profit_captured)
            insights.append(f"Wednesday morning exit captures {best_wed.avg_profit_captured:.0f} average profit")
        
        # Thursday expiry pattern
        thu_patterns = [p for p in patterns if p.day_of_week == 'Thursday']
        if thu_patterns:
            insights.append(f"Thursday exits are mandatory (expiry day) - {len(thu_patterns)} patterns found")
        
        # Best profit threshold
        profit_patterns = [p for p in patterns if p.pattern_type == 'profit_based']
        if profit_patterns:
            best_profit = max(profit_patterns, key=lambda x: x.confidence_score)
            insights.append(f"Exit at {best_profit.profit_threshold_pct:.0f}% of max profit is optimal")
        
        return {
            "analysis_period": {
                "from": request.from_date.isoformat(),
                "to": request.to_date.isoformat()
            },
            "total_patterns": len(patterns),
            "patterns_by_type": patterns_by_type,
            "key_insights": insights,
            "top_patterns": [p.to_dict() for p in patterns[:5]]  # Top 5 by confidence
        }
        
    except Exception as e:
        logger.error(f"Error discovering patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimize-stoploss", summary="Optimize Stop-Loss Strategies")
async def optimize_stop_loss(request: StopLossOptimizationRequest):
    """
    Test and optimize multiple stop-loss strategies
    
    Returns:
    - Optimal stop-loss strategy for each signal
    - Comparison of different strategies
    - False stop analysis
    - Risk-reward optimization
    """
    try:
        optimal_strategies = stoploss_optimizer.optimize_all_strategies(
            datetime.combine(request.from_date, datetime.min.time()),
            datetime.combine(request.to_date, datetime.max.time())
        )
        
        if not optimal_strategies:
            return {
                "message": "No optimal strategies found",
                "strategies": {}
            }
        
        # Format results
        results = {}
        for signal_type, strategy in optimal_strategies.items():
            if request.signal_types and signal_type not in request.signal_types:
                continue
                
            results[signal_type] = {
                "optimal_strategy": strategy.stop_type.value,
                "configuration": {
                    "initial_stop_multiplier": strategy.initial_stop_multiplier,
                    "trail_percentage": strategy.trail_percentage,
                    "breakeven_threshold": strategy.breakeven_profit_threshold
                },
                "performance": {
                    "backtest_trades": strategy.backtest_trades,
                    "stops_hit": strategy.stops_hit,
                    "stop_hit_rate": f"{strategy.stop_hit_rate:.1%}",
                    "false_stops": strategy.false_stops,
                    "false_stop_rate": f"{strategy.false_stops/strategy.stops_hit:.1%}" if strategy.stops_hit > 0 else "0%",
                    "avg_profit_saved": strategy.avg_profit_saved
                },
                "recommendation": _get_stoploss_recommendation(strategy)
            }
        
        return {
            "analysis_period": {
                "from": request.from_date.isoformat(),
                "to": request.to_date.isoformat()
            },
            "optimized_strategies": results,
            "summary": {
                "signals_optimized": len(results),
                "most_common_strategy": _most_common_strategy(optimal_strategies),
                "avg_stop_hit_rate": f"{sum(s.stop_hit_rate for s in optimal_strategies.values())/len(optimal_strategies):.1%}",
                "recommendation": "Use signal-specific optimized strategies for best results"
            }
        }
        
    except Exception as e:
        logger.error(f"Error optimizing stop-loss: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/get-exit-recommendation", summary="Get Real-Time Exit Recommendation")
async def get_exit_recommendation(state: CurrentTradeState):
    """
    Get real-time exit recommendation for an active trade
    
    Based on:
    - Current P&L and time in trade
    - Discovered exit patterns
    - Market conditions
    
    Returns:
    - Action: hold, partial_exit, full_exit, trail_stop
    - Exit percentage
    - Confidence score
    - Reasoning
    """
    try:
        # Get recommendation from pattern analyzer
        pattern_rec = pattern_analyzer.get_exit_recommendation(
            state.signal_type,
            {
                'day_of_week': state.day_of_week,
                'hour': state.hour,
                'time_in_trade_hours': state.time_in_trade_hours,
                'current_pnl': state.current_pnl,
                'max_pnl': state.max_pnl
            }
        )
        
        # Get stop-loss recommendation
        sl_rec = stoploss_optimizer.get_recommendation(
            state.signal_type,
            {
                'entry_price': state.entry_price,
                'current_pnl': state.current_pnl,
                'max_pnl': state.max_pnl,
                'quantity': state.quantity
            }
        )
        
        # Combine recommendations
        final_action = pattern_rec['action']
        final_confidence = pattern_rec['confidence']
        
        # Special cases
        if state.day_of_week == 'Thursday' and state.hour >= 14:
            final_action = 'full_exit'
            final_confidence = 1.0
            reason = "Thursday expiry approaching - mandatory exit"
        elif state.day_of_week == 'Wednesday' and state.hour <= 12 and state.current_pnl > 0:
            if final_action == 'hold':
                final_action = 'partial_exit'
            reason = "Wednesday morning profit booking opportunity"
        else:
            reason = pattern_rec.get('reason', 'Based on historical patterns')
        
        # Check if stop-loss should trigger
        if sl_rec['stop_price'] and state.current_price >= sl_rec['stop_price']:
            final_action = 'full_exit'
            reason = f"Stop-loss triggered ({sl_rec['stop_type']})"
            final_confidence = 1.0
        
        return {
            "recommendation": {
                "action": final_action,
                "exit_percentage": pattern_rec['exit_percentage'],
                "confidence": final_confidence,
                "reason": reason
            },
            "stop_loss": {
                "type": sl_rec['stop_type'],
                "price": sl_rec['stop_price'],
                "distance_from_current": abs(state.current_price - sl_rec['stop_price']) if sl_rec['stop_price'] else None
            },
            "pattern_analysis": {
                "expected_profit": pattern_rec.get('expected_profit'),
                "pattern_matched": pattern_rec.get('pattern_details', {}).get('pattern_id') if pattern_rec.get('pattern_details') else None
            },
            "market_context": {
                "day": state.day_of_week,
                "hour": state.hour,
                "time_in_trade": f"{state.time_in_trade_hours:.1f} hours",
                "profit_capture": f"{state.current_pnl/state.max_pnl:.1%}" if state.max_pnl > 0 else "0%"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting exit recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimal-exit/{trade_id}", summary="Get Optimal Exit for Specific Trade")
async def get_optimal_exit(trade_id: int):
    """
    Analyze a specific trade and determine optimal exit point
    
    Returns:
    - When the trade should have been exited
    - How much profit was left on table
    - Recommended exit strategy for similar trades
    """
    try:
        # Analyze trade lifecycle
        metrics = lifecycle_analyzer.analyze_trade_lifecycle(trade_id)
        
        if not metrics:
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
        
        # Get optimal exit rules
        optimal_rules = lifecycle_analyzer.get_optimal_exit_rules(metrics.signal_type)
        
        return {
            "trade_id": trade_id,
            "signal_type": metrics.signal_type,
            "actual_performance": {
                "entry_time": metrics.entry_time.isoformat() if metrics.entry_time else None,
                "exit_time": metrics.exit_time.isoformat() if metrics.exit_time else None,
                "final_pnl": metrics.final_pnl,
                "max_profit": metrics.max_profit,
                "profit_captured": f"{metrics.profit_capture_ratio:.1%}"
            },
            "optimal_exit": {
                "best_exit_time": f"{metrics.best_exit_day} {metrics.best_exit_hour}:00",
                "time_to_exit": f"{metrics.time_to_max_profit_hours:.1f} hours from entry",
                "profit_at_optimal": metrics.max_profit,
                "profit_missed": metrics.max_profit - metrics.final_pnl
            },
            "recommendations": {
                "exit_rule": f"Exit on {metrics.best_exit_day} around {metrics.best_exit_hour}:00",
                "stop_loss": f"Set stop at {optimal_rules[metrics.signal_type]['stop_loss_multiplier']}x premium",
                "trailing_stop": f"Trail by {optimal_rules[metrics.signal_type]['trailing_stop_pct']*100:.0f}% after profit",
                "wednesday_rule": f"Book {optimal_rules[metrics.signal_type]['wednesday_exit_threshold']*100:.0f}% on Wednesday if profitable"
            },
            "risk_metrics": {
                "times_near_stop": metrics.times_near_stop_loss,
                "min_distance_to_stop": f"{metrics.min_distance_to_stop_pct:.1%}",
                "max_drawdown": metrics.max_drawdown
            }
        }
        
    except Exception as e:
        logger.error(f"Error analyzing optimal exit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exit-rules", summary="Get Current Exit Rules")
async def get_exit_rules():
    """
    Get current exit rules for all signals
    
    Returns configured exit strategies and patterns
    """
    try:
        rules = {}
        
        # Get optimal rules for each signal
        for signal in ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']:
            rules[signal] = lifecycle_analyzer.get_optimal_exit_rules(signal).get(signal, {})
        
        return {
            "exit_rules": rules,
            "general_guidelines": {
                "monday": "Hold all positions - fresh weekly levels",
                "tuesday": "Consider partial exit (25-50%) if trending strongly",
                "wednesday_morning": "Prime profit booking time - exit 50-75% if profitable",
                "wednesday_afternoon": "Trail stops tightly",
                "thursday_morning": "Final exit opportunity before expiry",
                "thursday_afternoon": "Mandatory exit by 3:00 PM"
            },
            "risk_management": {
                "initial_stop": "1.5x premium received (default)",
                "trailing_activation": "After 50% of target profit",
                "trailing_percentage": "25% of maximum profit",
                "breakeven_threshold": "Move to breakeven after 50% profit"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting exit rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _get_stoploss_recommendation(strategy) -> str:
    """Generate recommendation text for stop-loss strategy"""
    if strategy.stop_type.value == 'fixed_premium':
        return f"Use {strategy.initial_stop_multiplier}x premium as stop-loss"
    elif strategy.stop_type.value == 'percentage_trail':
        return f"Trail stop by {strategy.trail_percentage*100:.0f}% of profit"
    elif strategy.stop_type.value == 'breakeven':
        return f"Move to breakeven after {strategy.breakeven_profit_threshold*100:.0f}% profit"
    else:
        return "Use adaptive stop-loss based on market conditions"

def _most_common_strategy(strategies) -> str:
    """Find most common strategy type"""
    from collections import Counter
    strategy_types = [s.stop_type.value for s in strategies.values()]
    if strategy_types:
        return Counter(strategy_types).most_common(1)[0][0]
    return "None"

@router.post("/train-exit-predictor", summary="Train ML Exit Predictor")
async def train_exit_predictor(
    from_date: date = date(2025, 1, 1),
    to_date: date = date(2025, 8, 6),
    signal_type: Optional[str] = None
):
    """
    Train ML models to predict optimal exit timing
    
    Models trained:
    - XGBoost
    - LightGBM  
    - Random Forest
    - Ensemble
    
    Returns best performing model and feature importance
    """
    try:
        results = exit_predictor.train_models(
            datetime.combine(from_date, datetime.min.time()),
            datetime.combine(to_date, datetime.max.time()),
            signal_type
        )
        
        # Ensure results are JSON serializable
        if isinstance(results, dict):
            if 'error' in results:
                return {
                    "status": "error",
                    "message": results['error'],
                    "training_period": {
                        "from": from_date.isoformat(),
                        "to": to_date.isoformat()
                    }
                }
            else:
                # Clean up results for JSON serialization
                clean_results = {
                    "best_model": results.get('best_model', 'unknown'),
                    "training_samples": results.get('training_samples', 0),
                    "test_samples": results.get('test_samples', 0)
                }
                
                # Add model metrics if available
                if 'results' in results and isinstance(results['results'], dict):
                    clean_results['model_performance'] = results['results']
                
                # Add feature importance if available
                if 'feature_importance' in results and isinstance(results['feature_importance'], dict):
                    clean_results['top_features'] = list(results['feature_importance'].keys())[:5]
                
                return {
                    "status": "success",
                    "training_period": {
                        "from": from_date.isoformat(),
                        "to": to_date.isoformat()
                    },
                    "signal_type": signal_type or "all",
                    "results": clean_results
                }
        else:
            return {
                "status": "success",
                "message": "Training completed",
                "training_period": {
                    "from": from_date.isoformat(),
                    "to": to_date.isoformat()
                }
            }
    except Exception as e:
        logger.error(f"Error training exit predictor: {e}")
        # Return a more user-friendly error
        return {
            "status": "error",
            "message": f"Training failed: {str(e)[:100]}",
            "training_period": {
                "from": from_date.isoformat(),
                "to": to_date.isoformat()
            }
        }

@router.post("/predict-exit", summary="Get ML Exit Prediction")
async def predict_exit(state: CurrentTradeState):
    """
    Get ML prediction for optimal exit action
    
    Returns:
    - Action: HOLD, PARTIAL_EXIT, FULL_EXIT
    - Confidence score
    - Risk assessment
    - Expected profit
    """
    try:
        # Convert state to dict for predictor
        state_dict = {
            'signal_type': state.signal_type,
            'entry_time': state.entry_time,
            'entry_hour': state.entry_time.hour,
            'entry_day_of_week': state.entry_time.weekday(),
            'time_in_trade_hours': state.time_in_trade_hours,
            'current_pnl': state.current_pnl,
            'max_pnl': state.max_pnl,
            'direction': 'BEARISH' if state.signal_type in ['S3', 'S5', 'S6', 'S8'] else 'BULLISH',
            'delta': state.delta,
            'theta': 100  # Default theta
        }
        
        prediction = exit_predictor.predict_exit(state.signal_type, state_dict)
        
        return {
            "prediction": prediction.to_dict(),
            "recommendation": {
                "action": prediction.action,
                "confidence": f"{prediction.confidence:.1%}",
                "risk_level": "HIGH" if prediction.risk_score > 0.7 else "MEDIUM" if prediction.risk_score > 0.4 else "LOW"
            }
        }
    except Exception as e:
        logger.error(f"Error predicting exit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update-trailing-stop", summary="Update Trailing Stop")
async def update_trailing_stop(
    trade_id: int,
    signal_type: str,
    current_pnl: float,
    max_pnl: float,
    current_price: float,
    entry_price: float,
    entry_time: datetime,
    current_volatility: Optional[float] = None
):
    """
    Update trailing stop for active trade
    
    Returns current stop level and distance
    """
    try:
        stop_level = trailing_stop_engine.update_trailing_stop(
            trade_id=trade_id,
            signal_type=signal_type,
            current_pnl=current_pnl,
            max_pnl=max_pnl,
            current_price=current_price,
            entry_price=entry_price,
            entry_time=entry_time,
            current_volatility=current_volatility
        )
        
        # Check if stop triggered
        triggered, reason = trailing_stop_engine.check_stop_triggered(
            trade_id, current_pnl, current_price
        )
        
        return {
            "trade_id": trade_id,
            "stop_level": stop_level.to_dict(),
            "triggered": triggered,
            "trigger_reason": reason,
            "recommendation": "EXIT NOW" if triggered else "CONTINUE HOLDING"
        }
    except Exception as e:
        logger.error(f"Error updating trailing stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trailing-stop-config/{signal_type}", summary="Get Trailing Stop Config")
async def get_trailing_stop_config(signal_type: str):
    """Get optimal trailing stop configuration for signal"""
    try:
        config = trailing_stop_engine.get_optimal_config(signal_type)
        return {
            "signal_type": signal_type,
            "configuration": config.to_dict()
        }
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/classify-regime", summary="Classify Market Regime")
async def classify_market_regime(
    symbol: str = "NIFTY",
    lookback_days: int = 20
):
    """
    Classify current market regime
    
    Returns:
    - Current regime (trending, range-bound, volatile, etc.)
    - Trading recommendations
    - Position size adjustments
    """
    try:
        regime = regime_classifier.classify_current_regime(symbol, lookback_days)
        
        return {
            "market_analysis": regime.to_dict(),
            "trading_guidance": {
                "current_regime": regime.current_regime.value,
                "confidence": f"{regime.confidence:.1%}",
                "recommended_signals": regime.recommended_strategies,
                "avoid_signals": regime.avoid_strategies,
                "position_size": f"{regime.position_size_adjustment*100:.0f}% of normal",
                "stop_loss": f"{regime.stop_loss_adjustment*100:.0f}% of normal"
            },
            "forecast": {
                "change_probability": f"{regime.regime_change_probability:.1%}",
                "expected_next": regime.expected_next_regime.value if regime.expected_next_regime else "Unknown"
            }
        }
    except Exception as e:
        logger.error(f"Error classifying regime: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/train-regime-classifier", summary="Train Regime Classifier")
async def train_regime_classifier(
    from_date: date = date(2024, 1, 1),
    to_date: date = date(2025, 8, 6)
):
    """Train market regime classifier on historical data"""
    try:
        regime_classifier.train_classifier(
            datetime.combine(from_date, datetime.min.time()),
            datetime.combine(to_date, datetime.max.time())
        )
        
        return {
            "status": "success",
            "message": "Regime classifier trained successfully",
            "training_period": {
                "from": from_date.isoformat(),
                "to": to_date.isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error training regime classifier: {e}")
        raise HTTPException(status_code=500, detail=str(e))