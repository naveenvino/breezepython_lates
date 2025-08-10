"""
ML Exit Predictor Model
Predicts optimal exit timing using machine learning models trained on historical data
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import xgboost as xgb
import lightgbm as lgb
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

@dataclass
class ExitPrediction:
    """Exit prediction result"""
    action: str  # 'HOLD', 'PARTIAL_EXIT', 'FULL_EXIT'
    confidence: float  # 0-1 confidence score
    probability_distribution: Dict[str, float]  # Probabilities for each action
    optimal_exit_time: Optional[datetime]  # Predicted best exit time
    expected_profit: float  # Expected profit if following prediction
    risk_score: float  # Current risk level 0-1
    feature_importance: Dict[str, float]  # Top features driving prediction
    
    def to_dict(self) -> Dict:
        return {
            'action': self.action,
            'confidence': self.confidence,
            'probability_distribution': self.probability_distribution,
            'optimal_exit_time': self.optimal_exit_time.isoformat() if self.optimal_exit_time else None,
            'expected_profit': self.expected_profit,
            'risk_score': self.risk_score,
            'feature_importance': self.feature_importance
        }

class ExitPredictor:
    """ML model for predicting optimal trade exits"""
    
    def __init__(self, db_connection_string: str, model_dir: str = "models/exit_predictor"):
        """
        Initialize exit predictor
        
        Args:
            db_connection_string: Database connection
            model_dir: Directory to save/load models
        """
        self.engine = create_engine(db_connection_string)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.models = {}
        self.scalers = {}
        self.feature_columns = []
        
    def train_models(self, 
                    from_date: datetime,
                    to_date: datetime,
                    signal_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Train exit prediction models
        
        Args:
            from_date: Training data start date
            to_date: Training data end date
            signal_type: Specific signal to train for (None for all)
            
        Returns:
            Training results and metrics
        """
        logger.info(f"Training exit predictor models from {from_date} to {to_date}")
        
        # Get training data
        df = self._prepare_training_data(from_date, to_date, signal_type)
        
        if df.empty:
            logger.warning("No training data available")
            return {"error": "No training data"}
        
        # Engineer features
        X, y = self._engineer_features(df)
        
        if len(X) < 10:
            logger.warning("Insufficient training data")
            return {"error": "Insufficient data"}
        
        # Store feature columns as list (force conversion)
        feature_columns = list(X.columns.tolist()) if hasattr(X.columns, 'tolist') else list(X.columns)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train multiple models
        results = {}
        
        # 1. XGBoost
        xgb_model = self._train_xgboost(X_train_scaled, y_train, X_test_scaled, y_test)
        results['xgboost'] = xgb_model
        
        # 2. LightGBM
        lgb_model = self._train_lightgbm(X_train_scaled, y_train, X_test_scaled, y_test)
        results['lightgbm'] = lgb_model
        
        # 3. Random Forest
        rf_model = self._train_random_forest(X_train_scaled, y_train, X_test_scaled, y_test)
        results['random_forest'] = rf_model
        
        # 4. Skip ensemble for now due to label type mismatch
        # TODO: Fix ensemble with consistent label encoding
        # ensemble = self._create_ensemble(xgb_model['model'], lgb_model['model'], rf_model['model'])
        # ensemble_results = self._evaluate_model(ensemble, X_test_scaled, y_test, "Ensemble")
        # results['ensemble'] = ensemble_results
        
        # Save best model (only if we have valid models)
        valid_results = {k: v for k, v in results.items() if v['model'] is not None}
        if not valid_results:
            logger.error("No models trained successfully")
            return {"error": "All model training failed"}
        
        best_model_name = max(valid_results.keys(), key=lambda k: valid_results[k]['accuracy'])
        best_model = valid_results[best_model_name]['model']
        
        model_key = signal_type if signal_type else 'all'
        self.models[model_key] = best_model
        self.scalers[model_key] = scaler
        self.feature_columns = feature_columns
        
        # Save to disk
        self._save_models(model_key)
        
        logger.info(f"Training complete. Best model: {best_model_name} with accuracy: {results[best_model_name]['accuracy']:.2%}")
        
        # Prepare clean results without model objects
        clean_results = {}
        for model_name, model_result in results.items():
            clean_results[model_name] = {
                'accuracy': float(model_result.get('accuracy', 0)),
                'precision': float(model_result.get('precision', 0)),
                'recall': float(model_result.get('recall', 0)),
                'f1_score': float(model_result.get('f1_score', 0))
            }
        
        # Get feature importance (ensure feature_columns is a list)
        feature_importance = {}
        try:
            feature_importance = self._get_feature_importance(best_model, feature_columns)
        except Exception as e:
            logger.warning(f"Could not get feature importance: {e}")
        
        return {
            'best_model': best_model_name,
            'results': clean_results,
            'feature_importance': feature_importance,
            'training_samples': int(len(X_train)),
            'test_samples': int(len(X_test))
        }
    
    def predict_exit(self, 
                    signal_type: str,
                    current_state: Dict[str, Any]) -> ExitPrediction:
        """
        Predict optimal exit action for current trade
        
        Args:
            signal_type: Signal type of trade
            current_state: Current trade state and market conditions
            
        Returns:
            ExitPrediction with recommended action
        """
        # Load model if not in memory
        model_key = signal_type if signal_type in self.models else 'all'
        if model_key not in self.models:
            self._load_models(model_key)
            
        if model_key not in self.models:
            logger.warning(f"No model available for {signal_type}")
            return self._default_prediction()
        
        # Prepare features
        features = self._prepare_features(current_state)
        
        # Ensure feature alignment
        features_df = pd.DataFrame([features])
        features_df = features_df.reindex(columns=self.feature_columns, fill_value=0)
        
        # Scale features
        X_scaled = self.scalers[model_key].transform(features_df)
        
        # Get prediction
        model = self.models[model_key]
        
        # Get probabilities for each class
        if hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(X_scaled)[0]
            classes = model.classes_
        else:
            # For models without predict_proba
            prediction = model.predict(X_scaled)[0]
            probabilities = [1.0 if i == prediction else 0.0 for i in range(3)]
            classes = ['HOLD', 'PARTIAL_EXIT', 'FULL_EXIT']
        
        # Create probability distribution
        prob_dist = {cls: prob for cls, prob in zip(classes, probabilities)}
        
        # Get predicted action
        action_idx = np.argmax(probabilities)
        action = classes[action_idx]
        confidence = probabilities[action_idx]
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(current_state)
        
        # Get feature importance for this prediction
        feature_importance = self._get_prediction_feature_importance(model, X_scaled, features_df.columns)
        
        # Calculate expected profit
        expected_profit = self._calculate_expected_profit(action, current_state)
        
        # Determine optimal exit time
        optimal_exit_time = self._predict_optimal_exit_time(current_state, action)
        
        return ExitPrediction(
            action=action,
            confidence=confidence,
            probability_distribution=prob_dist,
            optimal_exit_time=optimal_exit_time,
            expected_profit=expected_profit,
            risk_score=risk_score,
            feature_importance=feature_importance
        )
    
    def _prepare_training_data(self, 
                              from_date: datetime,
                              to_date: datetime,
                              signal_type: Optional[str]) -> pd.DataFrame:
        """
        Prepare training data from historical trades
        
        Args:
            from_date: Start date
            to_date: End date
            signal_type: Optional signal filter
            
        Returns:
            DataFrame with training data
        """
        query = """
        SELECT 
            t.Id,
            t.SignalType,
            t.EntryTime,
            t.ExitTime,
            t.TotalPnL,
            t.IndexPriceAtEntry,
            t.IndexPriceAtExit,
            t.Direction,
            DATEDIFF(hour, t.EntryTime, t.ExitTime) as HoldingHours,
            DATEPART(hour, t.EntryTime) as EntryHour,
            DATEPART(dw, t.EntryTime) as EntryDayOfWeek,
            DATEPART(hour, t.ExitTime) as ExitHour,
            DATEPART(dw, t.ExitTime) as ExitDayOfWeek,
            -- Calculate lifecycle metrics from positions
            mp.EntryPrice as MainEntryPrice,
            mp.ExitPrice as MainExitPrice,
            hp.EntryPrice as HedgeEntryPrice,
            hp.ExitPrice as HedgeExitPrice,
            t.TotalPnL as MaxProfit,
            DATEDIFF(hour, t.EntryTime, t.ExitTime) as TimeToMaxProfitHours,
            CASE 
                WHEN t.TotalPnL > 0 THEN 1.0 
                ELSE 0.0 
            END as ProfitCaptureRatio
        FROM BacktestTrades t
        LEFT JOIN BacktestPositions mp ON t.Id = mp.TradeId AND mp.PositionType = 'Main'
        LEFT JOIN BacktestPositions hp ON t.Id = hp.TradeId AND hp.PositionType = 'Hedge'
        WHERE t.EntryTime >= :from_date
            AND t.EntryTime <= :to_date
            AND t.TotalPnL IS NOT NULL
        """
        
        params = {
            'from_date': from_date,
            'to_date': to_date
        }
        
        if signal_type:
            query += " AND t.SignalType = :signal_type"
            params['signal_type'] = signal_type
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        
        return df
    
    def _engineer_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Engineer features for ML model
        
        Args:
            df: Raw training data
            
        Returns:
            Features (X) and labels (y)
        """
        features = pd.DataFrame()
        
        # Time-based features
        features['holding_hours'] = df['HoldingHours']
        features['entry_hour'] = df['EntryHour']
        features['entry_day_of_week'] = df['EntryDayOfWeek']
        
        # One-hot encode signal type
        signal_dummies = pd.get_dummies(df['SignalType'], prefix='signal')
        features = pd.concat([features, signal_dummies], axis=1)
        
        # Direction encoding
        features['is_bearish'] = (df['Direction'] == 'BEARISH').astype(int)
        
        # Lifecycle features if available
        if 'MaxProfit' in df.columns:
            features['max_profit'] = df['MaxProfit'].fillna(0)
            features['time_to_max_profit'] = df['TimeToMaxProfitHours'].fillna(0)
            features['profit_capture_ratio'] = df['ProfitCaptureRatio'].fillna(0)
        
        # Option price features
        if 'MainEntryPrice' in df.columns:
            features['main_entry_price'] = df['MainEntryPrice'].fillna(0)
            features['main_exit_price'] = df['MainExitPrice'].fillna(0)
            features['hedge_entry_price'] = df['HedgeEntryPrice'].fillna(0)
            features['hedge_exit_price'] = df['HedgeExitPrice'].fillna(0)
        
        # Create labels based on exit performance
        # Multi-class: HOLD (bad exit), PARTIAL_EXIT (ok exit), FULL_EXIT (good exit)
        labels = []
        
        # Use P&L quantiles to create balanced classes
        pnl_75 = df['TotalPnL'].quantile(0.75)
        pnl_25 = df['TotalPnL'].quantile(0.25)
        
        for _, row in df.iterrows():
            # Use holding hours and P&L to determine exit quality
            holding_hours = row['HoldingHours']
            pnl = row['TotalPnL']
            
            # Quick profitable exits are FULL_EXIT
            if pnl > pnl_75 and holding_hours < 48:
                labels.append('FULL_EXIT')
            # Good profits but took longer
            elif pnl > pnl_75:
                labels.append('PARTIAL_EXIT')
            # Moderate profits
            elif pnl > pnl_25:
                labels.append('PARTIAL_EXIT')
            # Poor performance
            else:
                labels.append('HOLD')
        
        y = pd.Series(labels)
        
        # Remove any rows with NaN
        valid_idx = ~features.isna().any(axis=1)
        features = features[valid_idx]
        y = y[valid_idx]
        
        return features, y
    
    def _train_xgboost(self, X_train, y_train, X_test, y_test) -> Dict:
        """Train XGBoost model"""
        try:
            # Convert labels to numeric
            label_map = {'HOLD': 0, 'PARTIAL_EXIT': 1, 'FULL_EXIT': 2}
            y_train_numeric = pd.Series(y_train).map(label_map)
            y_test_numeric = pd.Series(y_test).map(label_map)
            
            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                objective='multi:softprob',
                num_class=3,
                random_state=42,
                use_label_encoder=False,
                eval_metric='mlogloss'
            )
            
            model.fit(X_train, y_train_numeric)
            
            # Store class mapping
            model._label_map = label_map
            model._reverse_map = {v: k for k, v in label_map.items()}
            
            return self._evaluate_model(model, X_test, y_test, "XGBoost")
        except Exception as e:
            logger.error(f"Error training XGBoost: {e}")
            # Return a simple result to continue
            return {'model': None, 'accuracy': 0, 'precision': 0, 'recall': 0, 'f1_score': 0}
    
    def _train_lightgbm(self, X_train, y_train, X_test, y_test) -> Dict:
        """Train LightGBM model"""
        try:
            # Convert labels to numeric
            label_map = {'HOLD': 0, 'PARTIAL_EXIT': 1, 'FULL_EXIT': 2}
            y_train_numeric = pd.Series(y_train).map(label_map)
            y_test_numeric = pd.Series(y_test).map(label_map)
            
            model = lgb.LGBMClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                num_class=3,
                objective='multiclass',
                random_state=42,
                verbosity=-1
            )
            
            model.fit(X_train, y_train_numeric)
            
            # Store class mapping
            model._label_map = label_map
            model._reverse_map = {v: k for k, v in label_map.items()}
            
            return self._evaluate_model(model, X_test, y_test, "LightGBM")
        except Exception as e:
            logger.error(f"Error training LightGBM: {e}")
            return {'model': None, 'accuracy': 0, 'precision': 0, 'recall': 0, 'f1_score': 0}
    
    def _train_random_forest(self, X_train, y_train, X_test, y_test) -> Dict:
        """Train Random Forest model"""
        try:
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=42,
                n_jobs=-1
            )
            
            model.fit(X_train, y_train)
            
            return self._evaluate_model(model, X_test, y_test, "Random Forest")
        except Exception as e:
            logger.error(f"Error training Random Forest: {e}")
            return {'model': None, 'accuracy': 0, 'precision': 0, 'recall': 0, 'f1_score': 0}
    
    def _create_ensemble(self, xgb_model, lgb_model, rf_model):
        """Create ensemble model"""
        from sklearn.ensemble import VotingClassifier
        
        # Wrap models to ensure they have consistent interfaces
        ensemble = VotingClassifier(
            estimators=[
                ('xgb', xgb_model),
                ('lgb', lgb_model),
                ('rf', rf_model)
            ],
            voting='soft'
        )
        
        return ensemble
    
    def _evaluate_model(self, model, X_test, y_test, model_name: str) -> Dict:
        """Evaluate model performance"""
        # Get predictions
        y_pred_numeric = model.predict(X_test)
        
        # Convert numeric predictions to labels if needed
        if hasattr(model, '_reverse_map'):
            # XGBoost/LightGBM with numeric labels
            y_pred = [model._reverse_map[pred] for pred in y_pred_numeric]
        else:
            # Random Forest with string labels
            y_pred = y_pred_numeric
        
        # Ensure y_test is in string format
        if isinstance(y_test, pd.Series):
            y_test_labels = y_test.values
        else:
            y_test_labels = y_test
        
        # Calculate metrics
        from sklearn.metrics import accuracy_score, precision_recall_fscore_support
        
        accuracy = accuracy_score(y_test_labels, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_test_labels, y_pred, average='weighted', zero_division=0
        )
        
        logger.info(f"{model_name} - Accuracy: {accuracy:.2%}, F1: {f1:.2%}")
        
        return {
            'model': model,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1
            # Don't include predictions array to avoid numpy serialization issues
        }
    
    def _prepare_features(self, current_state: Dict) -> Dict:
        """
        Prepare features from current trade state
        
        Args:
            current_state: Current trade state
            
        Returns:
            Feature dictionary
        """
        features = {}
        
        # Time features
        features['holding_hours'] = current_state.get('time_in_trade_hours', 0)
        features['entry_hour'] = current_state.get('entry_hour', 11)
        features['entry_day_of_week'] = current_state.get('entry_day_of_week', 2)  # Default Tuesday
        
        # Signal type (one-hot)
        signal_type = current_state.get('signal_type', 'S1')
        for signal in ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']:
            features[f'signal_{signal}'] = 1 if signal == signal_type else 0
        
        # Direction
        features['is_bearish'] = 1 if current_state.get('direction') == 'BEARISH' else 0
        
        # P&L features
        current_pnl = current_state.get('current_pnl', 0)
        max_pnl = current_state.get('max_pnl', current_pnl)
        features['max_profit'] = max_pnl
        features['profit_capture_ratio'] = current_pnl / max_pnl if max_pnl > 0 else 0
        
        # Greeks if available
        features['max_delta'] = current_state.get('delta', 0)
        features['avg_theta'] = current_state.get('theta', 0)
        
        # Time to max (estimate based on typical pattern)
        if max_pnl > current_pnl:
            features['time_to_max_profit'] = 0  # Already past peak
        else:
            features['time_to_max_profit'] = 48 - features['holding_hours']  # Estimate
        
        return features
    
    def _calculate_risk_score(self, current_state: Dict) -> float:
        """
        Calculate current risk score
        
        Args:
            current_state: Current trade state
            
        Returns:
            Risk score 0-1
        """
        risk_score = 0.0
        
        # Time risk (increases as expiry approaches)
        hours_to_expiry = max(0, 72 - current_state.get('time_in_trade_hours', 0))
        time_risk = 1 - (hours_to_expiry / 72)
        risk_score += time_risk * 0.3
        
        # Profit at risk (if past peak)
        current_pnl = current_state.get('current_pnl', 0)
        max_pnl = current_state.get('max_pnl', current_pnl)
        if max_pnl > 0 and current_pnl < max_pnl:
            profit_risk = (max_pnl - current_pnl) / max_pnl
            risk_score += profit_risk * 0.4
        
        # Delta risk (if available)
        delta = abs(current_state.get('delta', 0))
        if delta > 0.4:
            delta_risk = min(1.0, (delta - 0.4) / 0.4)
            risk_score += delta_risk * 0.3
        
        return min(1.0, risk_score)
    
    def _get_feature_importance(self, model, feature_names) -> Dict[str, float]:
        """Get feature importance from model"""
        importance_dict = {}
        
        try:
            # Ensure feature_names is a list
            if hasattr(feature_names, 'tolist'):
                feature_names = feature_names.tolist()
            elif not isinstance(feature_names, list):
                feature_names = list(feature_names)
            
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                for name, imp in zip(feature_names, importances):
                    # Convert numpy types to Python types
                    importance_dict[str(name)] = float(imp)
            
            # Sort and return top 10
            sorted_imp = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:10])
            return sorted_imp
        except Exception as e:
            logger.warning(f"Could not get feature importance: {e}")
            return {}
    
    def _get_prediction_feature_importance(self, model, X, feature_names) -> Dict[str, float]:
        """Get feature importance for specific prediction"""
        try:
            # Ensure feature_names is a list
            if hasattr(feature_names, 'tolist'):
                feature_names = feature_names.tolist()
            elif not isinstance(feature_names, list):
                feature_names = list(feature_names)
            
            # For tree-based models, we can use feature_importances_
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                importance_dict = {}
                for name, imp in zip(feature_names, importances):
                    if imp > 0:
                        importance_dict[str(name)] = float(imp)
                
                # Return top 5 features
                sorted_imp = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:5])
                return sorted_imp
        except Exception as e:
            logger.warning(f"Could not get prediction feature importance: {e}")
        
        return {}
    
    def _calculate_expected_profit(self, action: str, current_state: Dict) -> float:
        """
        Calculate expected profit for action
        
        Args:
            action: Predicted action
            current_state: Current state
            
        Returns:
            Expected profit
        """
        current_pnl = current_state.get('current_pnl', 0)
        max_pnl = current_state.get('max_pnl', current_pnl)
        
        if action == 'FULL_EXIT':
            return current_pnl  # Exit now with current profit
        elif action == 'PARTIAL_EXIT':
            # Exit half now, expect some additional profit
            return current_pnl * 0.5 + max_pnl * 0.3
        else:  # HOLD
            # Expect to capture more of max profit
            return max_pnl * 0.8
    
    def _predict_optimal_exit_time(self, current_state: Dict, action: str) -> Optional[datetime]:
        """
        Predict optimal exit time
        
        Args:
            current_state: Current state
            action: Predicted action
            
        Returns:
            Optimal exit time or None
        """
        if action == 'FULL_EXIT':
            return datetime.now()  # Exit immediately
        
        entry_time = current_state.get('entry_time')
        if not entry_time:
            return None
        
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)
        
        if action == 'PARTIAL_EXIT':
            # Exit in next few hours
            return datetime.now() + timedelta(hours=2)
        else:  # HOLD
            # Typical optimal exit on Wednesday
            days_to_wednesday = (2 - entry_time.weekday()) % 7
            if days_to_wednesday == 0:
                days_to_wednesday = 7  # Next Wednesday
            
            optimal_time = entry_time + timedelta(days=days_to_wednesday)
            optimal_time = optimal_time.replace(hour=11, minute=0, second=0)
            
            return optimal_time
    
    def _default_prediction(self) -> ExitPrediction:
        """Return default prediction when no model available"""
        return ExitPrediction(
            action='HOLD',
            confidence=0.5,
            probability_distribution={'HOLD': 0.5, 'PARTIAL_EXIT': 0.3, 'FULL_EXIT': 0.2},
            optimal_exit_time=None,
            expected_profit=0,
            risk_score=0.5,
            feature_importance={}
        )
    
    def _save_models(self, model_key: str):
        """Save models to disk"""
        try:
            # Save model
            model_path = self.model_dir / f"{model_key}_model.pkl"
            joblib.dump(self.models[model_key], model_path)
            
            # Save scaler
            scaler_path = self.model_dir / f"{model_key}_scaler.pkl"
            joblib.dump(self.scalers[model_key], scaler_path)
            
            # Save feature columns (ensure it's a list)
            features_path = self.model_dir / f"{model_key}_features.pkl"
            feature_list = self.feature_columns if isinstance(self.feature_columns, list) else list(self.feature_columns)
            joblib.dump(feature_list, features_path)
            
            logger.info(f"Models saved for {model_key}")
        except Exception as e:
            logger.warning(f"Could not save models to disk: {e}")
            # Don't fail training just because we can't save
    
    def _load_models(self, model_key: str):
        """Load models from disk"""
        try:
            # Load model
            model_path = self.model_dir / f"{model_key}_model.pkl"
            if model_path.exists():
                self.models[model_key] = joblib.load(model_path)
            
            # Load scaler
            scaler_path = self.model_dir / f"{model_key}_scaler.pkl"
            if scaler_path.exists():
                self.scalers[model_key] = joblib.load(scaler_path)
            
            # Load feature columns
            features_path = self.model_dir / f"{model_key}_features.pkl"
            if features_path.exists():
                self.feature_columns = joblib.load(features_path)
                
            logger.info(f"Models loaded for {model_key}")
        except Exception as e:
            logger.error(f"Error loading models: {e}")