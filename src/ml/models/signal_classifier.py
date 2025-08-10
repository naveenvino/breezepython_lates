"""
Signal Classifier Model
ML models to predict signal profitability and filter trades
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import joblib
import json
from pathlib import Path

from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
import xgboost as xgb
import lightgbm as lgb

logger = logging.getLogger(__name__)

class SignalClassifier:
    """ML classifier for trading signal profitability prediction"""
    
    def __init__(self, 
                 model_type: str = 'xgboost',
                 signal_type: str = None):
        """
        Initialize signal classifier
        
        Args:
            model_type: Type of model ('xgboost', 'lightgbm', 'random_forest', 'ensemble')
            signal_type: Specific signal type (S1-S8) or None for all signals
        """
        self.model_type = model_type
        self.signal_type = signal_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.model_params = {}
        self.performance_metrics = {}
        
    def create_model(self, **kwargs) -> Any:
        """
        Create ML model based on type
        
        Args:
            **kwargs: Model-specific parameters
            
        Returns:
            Model instance
        """
        if self.model_type == 'xgboost':
            default_params = {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'objective': 'binary:logistic',
                'use_label_encoder': False,
                'eval_metric': 'logloss',
                'random_state': 42
            }
            default_params.update(kwargs)
            model = xgb.XGBClassifier(**default_params)
            
        elif self.model_type == 'lightgbm':
            default_params = {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'objective': 'binary',
                'metric': 'binary_logloss',
                'random_state': 42,
                'verbose': -1
            }
            default_params.update(kwargs)
            model = lgb.LGBMClassifier(**default_params)
            
        elif self.model_type == 'random_forest':
            default_params = {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'random_state': 42
            }
            default_params.update(kwargs)
            model = RandomForestClassifier(**default_params)
            
        elif self.model_type == 'logistic':
            default_params = {
                'C': 1.0,
                'max_iter': 1000,
                'random_state': 42
            }
            default_params.update(kwargs)
            model = LogisticRegression(**default_params)
            
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
            
        self.model_params = default_params
        return model
    
    def train(self,
             X_train: pd.DataFrame,
             y_train: pd.Series,
             X_val: pd.DataFrame = None,
             y_val: pd.Series = None,
             feature_columns: List[str] = None) -> Dict[str, float]:
        """
        Train the classifier model
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            feature_columns: List of feature column names
            
        Returns:
            Dictionary of training metrics
        """
        if feature_columns:
            self.feature_columns = feature_columns
            X_train = X_train[feature_columns]
            if X_val is not None:
                X_val = X_val[feature_columns]
        else:
            self.feature_columns = X_train.columns.tolist()
            
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        # Create and train model
        self.model = self.create_model()
        
        # Train with validation if provided
        if X_val is not None and y_val is not None:
            X_val_scaled = self.scaler.transform(X_val)
            
            if self.model_type in ['xgboost', 'lightgbm']:
                eval_set = [(X_train_scaled, y_train), (X_val_scaled, y_val)]
                self.model.fit(
                    X_train_scaled, y_train,
                    eval_set=eval_set,
                    early_stopping_rounds=10,
                    verbose=False
                )
            else:
                self.model.fit(X_train_scaled, y_train)
        else:
            self.model.fit(X_train_scaled, y_train)
            
        # Calculate training metrics
        train_pred = self.model.predict(X_train_scaled)
        train_pred_proba = self.model.predict_proba(X_train_scaled)[:, 1]
        
        metrics = {
            'train_accuracy': accuracy_score(y_train, train_pred),
            'train_precision': precision_score(y_train, train_pred, zero_division=0),
            'train_recall': recall_score(y_train, train_pred, zero_division=0),
            'train_f1': f1_score(y_train, train_pred, zero_division=0),
            'train_auc': roc_auc_score(y_train, train_pred_proba) if len(np.unique(y_train)) > 1 else 0
        }
        
        # Add validation metrics if available
        if X_val is not None and y_val is not None:
            val_pred = self.model.predict(X_val_scaled)
            val_pred_proba = self.model.predict_proba(X_val_scaled)[:, 1]
            
            metrics.update({
                'val_accuracy': accuracy_score(y_val, val_pred),
                'val_precision': precision_score(y_val, val_pred, zero_division=0),
                'val_recall': recall_score(y_val, val_pred, zero_division=0),
                'val_f1': f1_score(y_val, val_pred, zero_division=0),
                'val_auc': roc_auc_score(y_val, val_pred_proba) if len(np.unique(y_val)) > 1 else 0
            })
            
        self.performance_metrics = metrics
        logger.info(f"Model trained - Accuracy: {metrics.get('val_accuracy', metrics['train_accuracy']):.4f}")
        
        return metrics
    
    def predict(self, 
               X: pd.DataFrame,
               return_proba: bool = True) -> np.ndarray:
        """
        Make predictions on new data
        
        Args:
            X: Features for prediction
            return_proba: Return probability scores instead of binary predictions
            
        Returns:
            Predictions or probability scores
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
            
        # Use only trained features
        X = X[self.feature_columns]
        X_scaled = self.scaler.transform(X)
        
        if return_proba:
            return self.model.predict_proba(X_scaled)[:, 1]
        else:
            return self.model.predict(X_scaled)
    
    def evaluate(self,
                X_test: pd.DataFrame,
                y_test: pd.Series) -> Dict[str, Any]:
        """
        Evaluate model performance on test set
        
        Args:
            X_test: Test features
            y_test: Test labels
            
        Returns:
            Dictionary of evaluation metrics
        """
        X_test = X_test[self.feature_columns]
        X_test_scaled = self.scaler.transform(X_test)
        
        # Predictions
        y_pred = self.model.predict(X_test_scaled)
        y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]
        
        # Calculate metrics
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'auc': roc_auc_score(y_test, y_pred_proba) if len(np.unique(y_test)) > 1 else 0,
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'classification_report': classification_report(y_test, y_pred, output_dict=True)
        }
        
        # Feature importance
        if hasattr(self.model, 'feature_importances_'):
            feature_importance = pd.DataFrame({
                'feature': self.feature_columns,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            metrics['feature_importance'] = feature_importance.to_dict('records')
            
        return metrics
    
    def optimize_threshold(self,
                          X_val: pd.DataFrame,
                          y_val: pd.Series,
                          metric: str = 'f1') -> float:
        """
        Find optimal probability threshold for classification
        
        Args:
            X_val: Validation features
            y_val: Validation labels
            metric: Metric to optimize ('f1', 'precision', 'recall')
            
        Returns:
            Optimal threshold
        """
        X_val = X_val[self.feature_columns]
        X_val_scaled = self.scaler.transform(X_val)
        y_pred_proba = self.model.predict_proba(X_val_scaled)[:, 1]
        
        best_threshold = 0.5
        best_score = 0
        
        for threshold in np.arange(0.1, 0.9, 0.05):
            y_pred = (y_pred_proba >= threshold).astype(int)
            
            if metric == 'f1':
                score = f1_score(y_val, y_pred, zero_division=0)
            elif metric == 'precision':
                score = precision_score(y_val, y_pred, zero_division=0)
            elif metric == 'recall':
                score = recall_score(y_val, y_pred, zero_division=0)
            else:
                raise ValueError(f"Unknown metric: {metric}")
                
            if score > best_score:
                best_score = score
                best_threshold = threshold
                
        logger.info(f"Optimal threshold: {best_threshold:.2f} with {metric}: {best_score:.4f}")
        return best_threshold
    
    def save_model(self, path: str):
        """
        Save trained model and metadata
        
        Args:
            path: Directory path to save model
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = path / f"model_{self.signal_type or 'all'}_{self.model_type}.pkl"
        joblib.dump(self.model, model_path)
        
        # Save scaler
        scaler_path = path / f"scaler_{self.signal_type or 'all'}.pkl"
        joblib.dump(self.scaler, scaler_path)
        
        # Save metadata
        metadata = {
            'model_type': self.model_type,
            'signal_type': self.signal_type,
            'feature_columns': self.feature_columns,
            'model_params': self.model_params,
            'performance_metrics': self.performance_metrics,
            'trained_at': datetime.now().isoformat()
        }
        
        metadata_path = path / f"metadata_{self.signal_type or 'all'}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
            
        logger.info(f"Model saved to {path}")
    
    def load_model(self, path: str):
        """
        Load trained model and metadata
        
        Args:
            path: Directory path containing saved model
        """
        path = Path(path)
        
        # Load model
        model_path = path / f"model_{self.signal_type or 'all'}_{self.model_type}.pkl"
        self.model = joblib.load(model_path)
        
        # Load scaler
        scaler_path = path / f"scaler_{self.signal_type or 'all'}.pkl"
        self.scaler = joblib.load(scaler_path)
        
        # Load metadata
        metadata_path = path / f"metadata_{self.signal_type or 'all'}.json"
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            
        self.feature_columns = metadata['feature_columns']
        self.model_params = metadata['model_params']
        self.performance_metrics = metadata['performance_metrics']
        
        logger.info(f"Model loaded from {path}")

class EnsembleSignalClassifier:
    """Ensemble of multiple classifiers for robust predictions"""
    
    def __init__(self, signal_type: str = None):
        """
        Initialize ensemble classifier
        
        Args:
            signal_type: Specific signal type or None for all
        """
        self.signal_type = signal_type
        self.models = {}
        self.weights = {}
        self.feature_columns = []
        
    def add_model(self, 
                 name: str,
                 model_type: str,
                 weight: float = 1.0):
        """
        Add a model to the ensemble
        
        Args:
            name: Name for the model
            model_type: Type of model
            weight: Weight for ensemble voting
        """
        self.models[name] = SignalClassifier(model_type, self.signal_type)
        self.weights[name] = weight
        
    def train(self,
             X_train: pd.DataFrame,
             y_train: pd.Series,
             X_val: pd.DataFrame = None,
             y_val: pd.Series = None,
             feature_columns: List[str] = None) -> Dict[str, Dict[str, float]]:
        """
        Train all models in the ensemble
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            feature_columns: Feature column names
            
        Returns:
            Dictionary of metrics for each model
        """
        if feature_columns:
            self.feature_columns = feature_columns
        else:
            self.feature_columns = X_train.columns.tolist()
            
        all_metrics = {}
        
        for name, model in self.models.items():
            logger.info(f"Training {name} model...")
            metrics = model.train(X_train, y_train, X_val, y_val, self.feature_columns)
            all_metrics[name] = metrics
            
        return all_metrics
    
    def predict(self,
               X: pd.DataFrame,
               return_proba: bool = True,
               voting: str = 'weighted') -> np.ndarray:
        """
        Make ensemble predictions
        
        Args:
            X: Features for prediction
            return_proba: Return probabilities
            voting: Voting method ('weighted' or 'average')
            
        Returns:
            Ensemble predictions
        """
        predictions = []
        weights = []
        
        for name, model in self.models.items():
            pred = model.predict(X, return_proba=True)
            predictions.append(pred)
            weights.append(self.weights[name])
            
        predictions = np.array(predictions)
        weights = np.array(weights) / np.sum(weights)
        
        if voting == 'weighted':
            ensemble_pred = np.average(predictions, axis=0, weights=weights)
        else:
            ensemble_pred = np.mean(predictions, axis=0)
            
        if not return_proba:
            ensemble_pred = (ensemble_pred >= 0.5).astype(int)
            
        return ensemble_pred
    
    def evaluate(self,
                X_test: pd.DataFrame,
                y_test: pd.Series) -> Dict[str, Any]:
        """
        Evaluate ensemble performance
        
        Args:
            X_test: Test features
            y_test: Test labels
            
        Returns:
            Dictionary of evaluation metrics
        """
        # Individual model metrics
        individual_metrics = {}
        for name, model in self.models.items():
            individual_metrics[name] = model.evaluate(X_test, y_test)
            
        # Ensemble metrics
        y_pred_proba = self.predict(X_test, return_proba=True)
        y_pred = (y_pred_proba >= 0.5).astype(int)
        
        ensemble_metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'auc': roc_auc_score(y_test, y_pred_proba) if len(np.unique(y_test)) > 1 else 0,
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist()
        }
        
        return {
            'ensemble': ensemble_metrics,
            'individual': individual_metrics
        }