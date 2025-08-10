"""
Machine Learning Module for Trading System
Provides ML-based signal optimization, feature engineering, and predictive models
"""

from .signal_analyzer import SignalPerformanceAnalyzer
from .feature_engineering import FeatureEngineer

__all__ = [
    'SignalPerformanceAnalyzer',
    'FeatureEngineer'
]