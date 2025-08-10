"""
ML Router
API endpoints for machine learning predictions and model management
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel, Field
import logging
import json
import pandas as pd
import numpy as np
from pathlib import Path

# Import ML modules
from ...ml.signal_analyzer import SignalPerformanceAnalyzer
from ...ml.feature_engineering import FeatureEngineer
from ...ml.models.signal_classifier import SignalClassifier, EnsembleSignalClassifier
from ...ml.models.stoploss_optimizer import StopLossOptimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["Machine Learning"])

# Request/Response Models
class TrainModelRequest(BaseModel):
    """Request for training ML model"""
    model_type: str = Field(default="xgboost", description="Model type: xgboost, lightgbm, random_forest, ensemble")
    signal_type: Optional[str] = Field(default=None, description="Specific signal type (S1-S8) or None for all")
    from_date: date = Field(description="Start date for training data")
    to_date: date = Field(description="End date for training data")
    feature_set: str = Field(default="all", description="Feature set to use: all, technical, market_structure")
    optimize_hyperparameters: bool = Field(default=False, description="Whether to optimize hyperparameters")

class PredictSignalRequest(BaseModel):
    """Request for signal prediction"""
    signal_type: str = Field(description="Signal type (S1-S8)")
    market_data: Dict[str, float] = Field(description="Current market data features")
    use_ensemble: bool = Field(default=False, description="Use ensemble model")

class OptimizeStopLossRequest(BaseModel):
    """Request for stop loss optimization"""
    signal_type: str = Field(description="Signal type")
    entry_price: float = Field(description="Entry price")
    direction: str = Field(description="Trade direction: BULLISH or BEARISH")
    market_features: Dict[str, float] = Field(description="Current market features")

class AnalyzeSignalsRequest(BaseModel):
    """Request for signal performance analysis"""
    from_date: date = Field(description="Start date")
    to_date: date = Field(description="End date")
    signals: Optional[List[str]] = Field(default=None, description="Specific signals to analyze")

class PortfolioBacktestRequest(BaseModel):
    """Request for portfolio backtest"""
    from_date: date = Field(description="Start date")
    to_date: date = Field(description="End date")
    strategies: List[Dict[str, Any]] = Field(description="List of strategy configurations")
    initial_capital: float = Field(default=500000, description="Initial capital")
    allocation_method: str = Field(default="equal_weight", description="Allocation method")
    rebalance_frequency: str = Field(default="weekly", description="Rebalance frequency")

class PaperTradingRequest(BaseModel):
    """Request for paper trading control"""
    action: str = Field(description="Action: start, stop, status")
    use_ml: bool = Field(default=True, description="Use ML models for filtering")
    ml_threshold: float = Field(default=0.6, description="ML confidence threshold")

# Global instances (in production, use dependency injection)
signal_analyzer = None
feature_engineer = None
ml_models = {}
paper_trading_engine = None
portfolio_backtester = None

def get_db_connection():
    """Get database connection string"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    server = os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')
    database = os.getenv('DB_NAME', 'KiteConnectApi')
    return f"mssql+pyodbc://{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"

@router.post("/train")
async def train_ml_model(
    request: TrainModelRequest,
    background_tasks: BackgroundTasks
):
    """
    Train ML model for signal prediction
    """
    try:
        # Train in background
        background_tasks.add_task(
            train_model_task,
            request.model_type,
            request.signal_type,
            request.from_date,
            request.to_date,
            request.feature_set,
            request.optimize_hyperparameters
        )
        
        return {
            "status": "training_started",
            "message": f"Training {request.model_type} model for {request.signal_type or 'all signals'}",
            "estimated_time": "5-10 minutes"
        }
        
    except Exception as e:
        logger.error(f"Training initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def train_model_task(
    model_type: str,
    signal_type: Optional[str],
    from_date: date,
    to_date: date,
    feature_set: str,
    optimize_hyperparameters: bool
):
    """Background task for model training"""
    global ml_models
    
    try:
        # Get training data
        db_conn = get_db_connection()
        
        # Initialize feature engineer
        engineer = FeatureEngineer()
        
        # Load market data
        query = f"""
        SELECT * FROM NIFTYData_5Min
        WHERE Timestamp >= '{from_date}' AND Timestamp <= '{to_date}'
        ORDER BY Timestamp
        """
        
        df = pd.read_sql(query, db_conn)
        
        # Generate features
        df = engineer.generate_features(
            df,
            include_ta=(feature_set in ['all', 'technical']),
            include_market_structure=(feature_set in ['all', 'market_structure']),
            include_temporal=True
        )
        
        # Create target variable (simplified - would use actual trade outcomes)
        df = engineer.create_target_variables(df, forward_periods=[5, 10])
        
        # Prepare dataset
        train_df, val_df, test_df = engineer.prepare_ml_dataset(
            df,
            target_col='target_up_5',
            test_size=0.2,
            val_size=0.1
        )
        
        # Train model
        if model_type == 'ensemble':
            classifier = EnsembleSignalClassifier(signal_type)
            classifier.add_model('xgboost', 'xgboost', weight=1.0)
            classifier.add_model('lightgbm', 'lightgbm', weight=0.8)
            classifier.add_model('random_forest', 'random_forest', weight=0.6)
        else:
            classifier = SignalClassifier(model_type, signal_type)
            
        # Train
        X_train = train_df[engineer.feature_columns]
        y_train = train_df['target_up_5']
        X_val = val_df[engineer.feature_columns]
        y_val = val_df['target_up_5']
        
        metrics = classifier.train(X_train, y_train, X_val, y_val)
        
        # Evaluate on test set
        X_test = test_df[engineer.feature_columns]
        y_test = test_df['target_up_5']
        test_metrics = classifier.evaluate(X_test, y_test)
        
        # Save model
        model_path = Path("models") / f"{signal_type or 'all'}_{model_type}"
        model_path.mkdir(parents=True, exist_ok=True)
        classifier.save_model(str(model_path))
        
        # Store in global dict
        ml_models[f"{signal_type or 'all'}_{model_type}"] = classifier
        
        # Log training results
        logger.info(f"Model trained successfully: {test_metrics}")
        
        # Save training history to database
        save_training_history(
            model_type, signal_type, metrics, test_metrics, str(model_path)
        )
        
    except Exception as e:
        logger.error(f"Training failed: {e}")

def save_training_history(
    model_type: str,
    signal_type: Optional[str],
    train_metrics: Dict,
    test_metrics: Dict,
    model_path: str
):
    """Save training history to database"""
    db_conn = get_db_connection()
    
    query = """
    INSERT INTO MLTrainingHistory (
        ModelId, ModelType, SignalType, TrainingDate,
        TrainAccuracy, ValAccuracy, TrainF1Score, ValF1Score,
        TrainAUC, ValAUC, ModelPath, Status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    # Execute insert (simplified)
    pass

@router.post("/predict/{signal_type}")
async def predict_signal(
    signal_type: str,
    request: PredictSignalRequest
):
    """
    Get ML prediction for a signal
    """
    try:
        model_key = f"{signal_type}_{request.use_ensemble and 'ensemble' or 'xgboost'}"
        
        if model_key not in ml_models:
            # Try to load model
            model_path = Path("models") / f"{signal_type}_xgboost"
            if model_path.exists():
                classifier = SignalClassifier('xgboost', signal_type)
                classifier.load_model(str(model_path))
                ml_models[model_key] = classifier
            else:
                raise HTTPException(status_code=404, detail=f"Model not found for {signal_type}")
                
        classifier = ml_models[model_key]
        
        # Prepare features
        features_df = pd.DataFrame([request.market_data])
        
        # Get prediction
        prediction = classifier.predict(features_df, return_proba=True)
        
        # Get feature importance if available
        feature_importance = []
        if hasattr(classifier.model, 'feature_importances_'):
            importance_df = pd.DataFrame({
                'feature': classifier.feature_columns,
                'importance': classifier.model.feature_importances_
            }).sort_values('importance', ascending=False).head(10)
            feature_importance = importance_df.to_dict('records')
            
        return {
            "signal_type": signal_type,
            "prediction_probability": float(prediction[0]),
            "recommendation": "TAKE" if prediction[0] > 0.6 else "SKIP",
            "confidence": "HIGH" if prediction[0] > 0.8 or prediction[0] < 0.2 else "MEDIUM",
            "top_features": feature_importance,
            "model_type": classifier.model_type
        }
        
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimize-stop-loss")
async def optimize_stop_loss(request: OptimizeStopLossRequest):
    """
    Optimize stop loss using ML
    """
    try:
        global ml_models
        
        # Get or load stop loss optimizer
        if 'stop_loss_optimizer' not in ml_models:
            optimizer = StopLossOptimizer()
            # Load if exists
            model_path = Path("models") / "stop_loss"
            if model_path.exists():
                optimizer.load_model(str(model_path))
            ml_models['stop_loss_optimizer'] = optimizer
            
        optimizer = ml_models['stop_loss_optimizer']
        
        # Optimize stop loss
        result = optimizer.optimize_stop_loss(
            signal_type=request.signal_type,
            entry_price=request.entry_price,
            market_features=request.market_features,
            direction=request.direction
        )
        
        return {
            "signal_type": request.signal_type,
            "entry_price": request.entry_price,
            "recommended_stop": result.recommended_stop,
            "stop_distance_pct": result.stop_distance_pct,
            "confidence_score": result.confidence_score,
            "expected_risk_reward": result.expected_risk_reward,
            "direction": request.direction
        }
        
    except Exception as e:
        logger.error(f"Stop loss optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze-signals")
async def analyze_signals(request: AnalyzeSignalsRequest):
    """
    Analyze historical signal performance
    """
    try:
        global signal_analyzer
        
        if signal_analyzer is None:
            signal_analyzer = SignalPerformanceAnalyzer(get_db_connection())
            
        # Analyze signals
        metrics = signal_analyzer.analyze_all_signals(
            datetime.combine(request.from_date, datetime.min.time()),
            datetime.combine(request.to_date, datetime.max.time())
        )
        
        # Get best conditions
        conditions = signal_analyzer.identify_best_conditions(metrics)
        
        # Format response
        response = {
            "analysis_period": {
                "from": request.from_date.isoformat(),
                "to": request.to_date.isoformat()
            },
            "signals": {}
        }
        
        for signal_type, signal_metrics in metrics.items():
            if request.signals and signal_type not in request.signals:
                continue
                
            # Handle infinity values for JSON serialization
            profit_factor = signal_metrics.profit_factor
            if profit_factor == float('inf'):
                profit_factor = "INF"
            elif profit_factor == float('-inf'):
                profit_factor = "-INF"
            elif profit_factor != profit_factor:  # Check for NaN
                profit_factor = 0
            
            response["signals"][signal_type] = {
                "total_trades": signal_metrics.total_trades,
                "win_rate": round(signal_metrics.win_rate * 100, 1),
                "profit_factor": profit_factor,
                "avg_profit": round(signal_metrics.avg_profit, 2),
                "avg_loss": round(signal_metrics.avg_loss, 2),
                "best_time": signal_metrics.best_time_of_day,
                "best_day": signal_metrics.best_day_of_week,
                "trending_performance": {
                    "win_rate": round(signal_metrics.trending_performance.get('win_rate', 0) * 100, 1),
                    "avg_pnl": round(signal_metrics.trending_performance.get('avg_pnl', 0), 2),
                    "trade_count": signal_metrics.trending_performance.get('trade_count', 0)
                },
                "sideways_performance": {
                    "win_rate": round(signal_metrics.sideways_performance.get('win_rate', 0) * 100, 1),
                    "avg_pnl": round(signal_metrics.sideways_performance.get('avg_pnl', 0), 2),
                    "trade_count": signal_metrics.sideways_performance.get('trade_count', 0)
                },
                "recommendation": conditions[signal_type]['recommendation']
            }
            
        return response
        
    except Exception as e:
        logger.error(f"Signal analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/portfolio/backtest")
async def run_portfolio_backtest(
    request: PortfolioBacktestRequest,
    background_tasks: BackgroundTasks
):
    """
    Run portfolio-level backtest
    """
    try:
        # Run in background
        background_tasks.add_task(
            portfolio_backtest_task,
            request.from_date,
            request.to_date,
            request.strategies,
            request.initial_capital,
            request.allocation_method,
            request.rebalance_frequency
        )
        
        return {
            "status": "backtest_started",
            "message": "Portfolio backtest started in background",
            "estimated_time": "10-15 minutes"
        }
        
    except Exception as e:
        logger.error(f"Portfolio backtest initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def portfolio_backtest_task(
    from_date: date,
    to_date: date,
    strategies: List[Dict],
    initial_capital: float,
    allocation_method: str,
    rebalance_frequency: str
):
    """Background task for portfolio backtest"""
    from ...portfolio.portfolio_backtester import PortfolioBacktester, StrategyConfig
    
    try:
        backtester = PortfolioBacktester(get_db_connection(), initial_capital)
        
        # Add strategies
        for strategy_dict in strategies:
            config = StrategyConfig(**strategy_dict)
            backtester.add_strategy(config)
            
        # Run backtest
        metrics = backtester.run_backtest(
            datetime.combine(from_date, datetime.min.time()),
            datetime.combine(to_date, datetime.max.time()),
            allocation_method,
            rebalance_frequency
        )
        
        logger.info(f"Portfolio backtest completed: {metrics}")
        
    except Exception as e:
        logger.error(f"Portfolio backtest failed: {e}")

@router.post("/paper-trading")
async def control_paper_trading(request: PaperTradingRequest):
    """
    Control paper trading engine
    """
    try:
        global paper_trading_engine
        
        if request.action == "start":
            if paper_trading_engine is None:
                from ...paper_trading.engine import PaperTradingEngine
                paper_trading_engine = PaperTradingEngine(
                    get_db_connection(),
                    initial_capital=500000
                )
                
            # Load ML models if requested
            ml_models_dict = {}
            if request.use_ml:
                # Load classifier
                if 'signal_classifier' in ml_models:
                    ml_models_dict['classifier'] = ml_models['signal_classifier']
                # Load stop loss optimizer
                if 'stop_loss_optimizer' in ml_models:
                    ml_models_dict['stop_loss'] = ml_models['stop_loss_optimizer']
                    
            paper_trading_engine.start(ml_models=ml_models_dict)
            
            return {
                "status": "started",
                "message": "Paper trading engine started",
                "use_ml": request.use_ml,
                "ml_threshold": request.ml_threshold
            }
            
        elif request.action == "stop":
            if paper_trading_engine:
                paper_trading_engine.stop()
                summary = paper_trading_engine.get_performance_summary()
                return {
                    "status": "stopped",
                    "message": "Paper trading engine stopped",
                    "summary": summary
                }
            else:
                return {"status": "not_running", "message": "Paper trading engine is not running"}
                
        elif request.action == "status":
            if paper_trading_engine and paper_trading_engine.is_running:
                summary = paper_trading_engine.get_performance_summary()
                return {
                    "status": "running",
                    "performance": summary
                }
            else:
                return {"status": "not_running", "message": "Paper trading engine is not running"}
                
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")
            
    except Exception as e:
        logger.error(f"Paper trading control failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
async def list_models():
    """
    List available ML models
    """
    try:
        models_dir = Path("models")
        available_models = []
        
        if models_dir.exists():
            for model_dir in models_dir.iterdir():
                if model_dir.is_dir():
                    metadata_file = model_dir / "metadata_all.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            available_models.append({
                                "name": model_dir.name,
                                "type": metadata.get('model_type'),
                                "signal": metadata.get('signal_type'),
                                "trained_at": metadata.get('trained_at'),
                                "performance": metadata.get('performance_metrics', {})
                            })
                            
        # Add loaded models
        for key, model in ml_models.items():
            available_models.append({
                "name": key,
                "type": getattr(model, 'model_type', 'unknown'),
                "loaded": True
            })
            
        return {
            "total_models": len(available_models),
            "models": available_models
        }
        
    except Exception as e:
        logger.error(f"Model listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/ml")
async def get_ml_performance():
    """
    Get ML model performance metrics
    """
    try:
        db_conn = get_db_connection()
        
        # Query ML prediction accuracy
        query = """
        SELECT 
            ModelType,
            SignalType,
            COUNT(*) as TotalPredictions,
            SUM(CASE WHEN PredictedProbability > 0.5 AND ActualOutcome = 'WIN' THEN 1
                     WHEN PredictedProbability <= 0.5 AND ActualOutcome = 'LOSS' THEN 1
                     ELSE 0 END) as CorrectPredictions,
            AVG(PredictedProbability) as AvgConfidence
        FROM MLPredictions
        WHERE CreatedAt >= DATEADD(day, -30, GETDATE())
        GROUP BY ModelType, SignalType
        """
        
        df = pd.read_sql(query, db_conn)
        
        if df.empty:
            return {"message": "No ML predictions found"}
            
        # Calculate accuracy
        df['accuracy'] = (df['CorrectPredictions'] / df['TotalPredictions'] * 100).round(2)
        
        return {
            "overall_accuracy": df['accuracy'].mean(),
            "by_model": df.to_dict('records'),
            "period": "Last 30 days"
        }
        
    except Exception as e:
        logger.error(f"ML performance retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))