"""
ML Training Pipeline Script
Automated pipeline for training and evaluating all ML models
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import logging
import json
import argparse
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

from src.ml.signal_analyzer import SignalPerformanceAnalyzer
from src.ml.feature_engineering import FeatureEngineer  
from src.ml.models.signal_classifier import SignalClassifier, EnsembleSignalClassifier
from src.ml.models.stoploss_optimizer import StopLossOptimizer
from src.ml.signal_discovery import SignalCombinationDiscovery
from src.portfolio.portfolio_backtester import PortfolioBacktester, StrategyConfig

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ml_training_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MLTrainingPipeline:
    """Automated ML training pipeline"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize training pipeline
        
        Args:
            config_path: Path to configuration file
        """
        load_dotenv()
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Database connection
        self.db_connection = self._get_db_connection()
        self.engine = create_engine(self.db_connection)
        
        # Initialize components
        self.signal_analyzer = SignalPerformanceAnalyzer(self.db_connection)
        self.feature_engineer = FeatureEngineer()
        self.signal_discovery = SignalCombinationDiscovery(self.db_connection)
        
        # Model storage
        self.models = {}
        self.model_path = Path(self.config.get('model_path', 'models'))
        self.model_path.mkdir(parents=True, exist_ok=True)
        
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from file or use defaults"""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            return {
                'training_period_days': 365,
                'validation_split': 0.2,
                'test_split': 0.1,
                'signal_types': ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'],
                'model_types': ['xgboost', 'lightgbm', 'random_forest'],
                'ensemble_enabled': True,
                'hyperparameter_tuning': False,
                'feature_sets': ['all'],
                'ml_threshold': 0.6,
                'model_path': 'models',
                'results_path': 'results'
            }
    
    def _get_db_connection(self) -> str:
        """Get database connection string"""
        server = os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')
        database = os.getenv('DB_NAME', 'KiteConnectApi')
        return f"mssql+pyodbc://{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
    
    def run_full_pipeline(self, 
                         from_date: datetime = None,
                         to_date: datetime = None):
        """
        Run complete ML training pipeline
        
        Args:
            from_date: Start date for training data
            to_date: End date for training data
        """
        logger.info("="*50)
        logger.info("Starting ML Training Pipeline")
        logger.info("="*50)
        
        # Set dates if not provided
        if not to_date:
            to_date = datetime.now() - timedelta(days=1)
        if not from_date:
            from_date = to_date - timedelta(days=self.config['training_period_days'])
            
        # Step 1: Analyze Signal Performance
        logger.info("\n[Step 1/7] Analyzing Signal Performance...")
        signal_metrics = self._analyze_signals(from_date, to_date)
        
        # Step 2: Prepare Training Data
        logger.info("\n[Step 2/7] Preparing Training Data...")
        training_data = self._prepare_training_data(from_date, to_date)
        
        # Step 3: Train Signal Classifiers
        logger.info("\n[Step 3/7] Training Signal Classifiers...")
        classifier_results = self._train_signal_classifiers(training_data)
        
        # Step 4: Train Stop Loss Optimizer
        logger.info("\n[Step 4/7] Training Stop Loss Optimizer...")
        stoploss_results = self._train_stoploss_optimizer(training_data)
        
        # Step 5: Discover Signal Combinations
        logger.info("\n[Step 5/7] Discovering Signal Combinations...")
        combinations = self._discover_combinations(from_date, to_date)
        
        # Step 6: Portfolio Optimization
        logger.info("\n[Step 6/7] Running Portfolio Optimization...")
        portfolio_results = self._optimize_portfolio(from_date, to_date)
        
        # Step 7: Generate Report
        logger.info("\n[Step 7/7] Generating Training Report...")
        report = self._generate_report(
            signal_metrics,
            classifier_results,
            stoploss_results,
            combinations,
            portfolio_results
        )
        
        # Save report
        self._save_report(report)
        
        logger.info("\n" + "="*50)
        logger.info("ML Training Pipeline Completed Successfully!")
        logger.info("="*50)
        
        return report
    
    def _analyze_signals(self, from_date: datetime, to_date: datetime) -> dict:
        """Analyze historical signal performance"""
        logger.info("Analyzing performance for all signals...")
        
        metrics = self.signal_analyzer.analyze_all_signals(from_date, to_date)
        
        # Identify best conditions
        conditions = self.signal_analyzer.identify_best_conditions(metrics)
        
        # Save analysis
        self.signal_analyzer.save_analysis_results(
            metrics,
            output_path=self.model_path / "signal_analysis.json"
        )
        
        # Log summary
        for signal_type, signal_metrics in metrics.items():
            logger.info(f"  {signal_type}: Win Rate={signal_metrics.win_rate:.2%}, "
                       f"Profit Factor={signal_metrics.profit_factor:.2f}")
            
        return {'metrics': metrics, 'conditions': conditions}
    
    def _prepare_training_data(self, from_date: datetime, to_date: datetime) -> dict:
        """Prepare data for ML training"""
        logger.info("Loading market data...")
        
        # Load NIFTY data
        query = """
        SELECT 
            Timestamp,
            Open, High, Low, Close, Volume
        FROM NIFTYData_5Min
        WHERE Timestamp >= :from_date AND Timestamp <= :to_date
        ORDER BY Timestamp
        """
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={
                'from_date': from_date,
                'to_date': to_date
            })
            
        if df.empty:
            logger.error("No market data found for the specified period")
            return {}
            
        logger.info(f"Loaded {len(df)} data points")
        
        # Generate features
        logger.info("Generating features...")
        for feature_set in self.config['feature_sets']:
            df = self.feature_engineer.generate_features(
                df,
                include_ta=(feature_set in ['all', 'technical']),
                include_market_structure=(feature_set in ['all', 'market']),
                include_temporal=True
            )
            
        # Create targets
        logger.info("Creating target variables...")
        df = self.feature_engineer.create_target_variables(df, forward_periods=[1, 5, 10])
        
        # Split data
        train_df, val_df, test_df = self.feature_engineer.prepare_ml_dataset(
            df,
            target_col='target_up_5',
            test_size=self.config['test_split'],
            val_size=self.config['validation_split']
        )
        
        logger.info(f"Data split - Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")
        
        return {
            'full': df,
            'train': train_df,
            'validation': val_df,
            'test': test_df,
            'features': self.feature_engineer.feature_columns
        }
    
    def _train_signal_classifiers(self, training_data: dict) -> dict:
        """Train classifiers for each signal type"""
        if not training_data:
            return {}
            
        results = {}
        
        for signal_type in self.config['signal_types']:
            logger.info(f"Training classifier for {signal_type}...")
            
            # Add signal-specific features
            train_df = self.feature_engineer.create_signal_features(
                training_data['train'].copy(), signal_type
            )
            val_df = self.feature_engineer.create_signal_features(
                training_data['validation'].copy(), signal_type
            )
            test_df = self.feature_engineer.create_signal_features(
                training_data['test'].copy(), signal_type
            )
            
            # Train individual models
            model_results = {}
            
            for model_type in self.config['model_types']:
                logger.info(f"  Training {model_type} model...")
                
                classifier = SignalClassifier(model_type, signal_type)
                
                # Prepare features
                feature_cols = [col for col in train_df.columns 
                              if col not in ['target_up_5', 'Timestamp']]
                
                X_train = train_df[feature_cols]
                y_train = train_df['target_up_5']
                X_val = val_df[feature_cols]
                y_val = val_df['target_up_5']
                
                # Train
                metrics = classifier.train(X_train, y_train, X_val, y_val, feature_cols)
                
                # Evaluate on test set
                X_test = test_df[feature_cols]
                y_test = test_df['target_up_5']
                test_metrics = classifier.evaluate(X_test, y_test)
                
                # Save model
                model_dir = self.model_path / f"{signal_type}_{model_type}"
                classifier.save_model(str(model_dir))
                
                model_results[model_type] = {
                    'train_metrics': metrics,
                    'test_metrics': test_metrics
                }
                
                logger.info(f"    Test Accuracy: {test_metrics['accuracy']:.4f}, "
                           f"F1: {test_metrics['f1']:.4f}")
                
            # Train ensemble if enabled
            if self.config['ensemble_enabled']:
                logger.info(f"  Training ensemble model for {signal_type}...")
                
                ensemble = EnsembleSignalClassifier(signal_type)
                for model_type in self.config['model_types']:
                    ensemble.add_model(model_type, model_type)
                    
                ensemble_metrics = ensemble.train(
                    X_train, y_train, X_val, y_val, feature_cols
                )
                
                ensemble_test = ensemble.evaluate(X_test, y_test)
                
                model_results['ensemble'] = {
                    'train_metrics': ensemble_metrics,
                    'test_metrics': ensemble_test
                }
                
                logger.info(f"    Ensemble Test Accuracy: {ensemble_test['ensemble']['accuracy']:.4f}")
                
            results[signal_type] = model_results
            
        return results
    
    def _train_stoploss_optimizer(self, training_data: dict) -> dict:
        """Train stop loss optimization model"""
        if not training_data:
            return {}
            
        logger.info("Preparing stop loss training data...")
        
        # Get historical trades
        query = """
        SELECT * FROM BacktestTrades
        WHERE EntryTime >= :from_date AND EntryTime <= :to_date
        """
        
        with self.engine.connect() as conn:
            trades_df = pd.read_sql(text(query), conn, params={
                'from_date': training_data['train'].index[0],
                'to_date': training_data['test'].index[-1]
            })
            
        if trades_df.empty:
            logger.warning("No trades found for stop loss training")
            return {}
            
        # Initialize optimizer
        optimizer = StopLossOptimizer('xgboost')
        
        # Prepare training data
        sl_training_data = optimizer.prepare_training_data(
            trades_df,
            training_data['full']
        )
        
        if sl_training_data.empty:
            logger.warning("Could not prepare stop loss training data")
            return {}
            
        # Split features and target
        feature_cols = [col for col in sl_training_data.columns 
                       if col != 'optimal_stop_distance']
        
        X = sl_training_data[feature_cols]
        y = sl_training_data['optimal_stop_distance']
        
        # Split data
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # Train
        logger.info("Training stop loss optimizer...")
        metrics = optimizer.train(X_train, y_train, X_val, y_val)
        
        # Save model
        optimizer.save_model(str(self.model_path / "stop_loss"))
        
        logger.info(f"Stop Loss Optimizer - Val MAE: {metrics.get('val_mae', 0):.4f}")
        
        # Analyze effectiveness
        effectiveness = optimizer.analyze_stop_effectiveness(trades_df)
        
        return {
            'metrics': metrics,
            'effectiveness': effectiveness
        }
    
    def _discover_combinations(self, from_date: datetime, to_date: datetime) -> list:
        """Discover profitable signal combinations"""
        logger.info("Starting signal combination discovery...")
        
        methods = ['correlation', 'sequential']
        
        if self.config.get('use_genetic_discovery', True):
            methods.append('genetic')
            
        combinations = self.signal_discovery.discover_combinations(
            from_date,
            to_date,
            methods=methods
        )
        
        logger.info(f"Discovered {len(combinations)} profitable combinations")
        
        # Log top combinations
        for i, combo in enumerate(combinations[:5]):
            logger.info(f"  Top {i+1}: {combo.signals} - "
                       f"Sharpe: {combo.backtest_results.get('sharpe_ratio', 0):.2f}, "
                       f"Win Rate: {combo.backtest_results.get('win_rate', 0):.2%}")
            
        return combinations
    
    def _optimize_portfolio(self, from_date: datetime, to_date: datetime) -> dict:
        """Run portfolio optimization"""
        logger.info("Running portfolio optimization...")
        
        # Initialize portfolio backtester
        backtester = PortfolioBacktester(self.db_connection, initial_capital=500000)
        
        # Add strategies based on best signals
        strategies = []
        
        # Top individual signals
        for signal in ['S1', 'S2', 'S4', 'S7']:  # Best performing signals
            config = StrategyConfig(
                name=f"Strategy_{signal}",
                signal_types=[signal],
                weight=0.25,
                max_positions=3,
                use_ml_filter=True,
                ml_threshold=self.config['ml_threshold']
            )
            backtester.add_strategy(config)
            strategies.append(config)
            
        # Run backtest with different allocation methods
        allocation_methods = ['equal_weight', 'risk_parity', 'ml_weighted']
        results = {}
        
        for method in allocation_methods:
            logger.info(f"  Testing {method} allocation...")
            
            metrics = backtester.run_backtest(
                from_date,
                to_date,
                allocation_method=method,
                rebalance_frequency='weekly'
            )
            
            results[method] = {
                'total_return': metrics.total_return,
                'sharpe_ratio': metrics.sharpe_ratio,
                'max_drawdown': metrics.max_drawdown,
                'win_rate': metrics.win_rate
            }
            
            logger.info(f"    Return: {metrics.total_return:.2%}, "
                       f"Sharpe: {metrics.sharpe_ratio:.2f}, "
                       f"Max DD: {metrics.max_drawdown:.2%}")
            
        return results
    
    def _generate_report(self, *args) -> dict:
        """Generate comprehensive training report"""
        signal_metrics, classifier_results, stoploss_results, combinations, portfolio_results = args
        
        report = {
            'training_date': datetime.now().isoformat(),
            'configuration': self.config,
            'signal_analysis': signal_metrics,
            'classifier_performance': classifier_results,
            'stop_loss_optimization': stoploss_results,
            'discovered_combinations': [c.to_dict() for c in combinations[:10]],
            'portfolio_optimization': portfolio_results,
            'summary': self._generate_summary(args)
        }
        
        return report
    
    def _generate_summary(self, results) -> dict:
        """Generate executive summary"""
        signal_metrics, classifier_results, stoploss_results, combinations, portfolio_results = results
        
        # Best performing signals
        best_signals = []
        if signal_metrics and 'metrics' in signal_metrics:
            for signal, metrics in signal_metrics['metrics'].items():
                if metrics.win_rate > 0.55:
                    best_signals.append({
                        'signal': signal,
                        'win_rate': metrics.win_rate,
                        'profit_factor': metrics.profit_factor
                    })
                    
        # Average model performance
        avg_accuracy = []
        for signal_results in classifier_results.values():
            for model_results in signal_results.values():
                if 'test_metrics' in model_results:
                    avg_accuracy.append(model_results['test_metrics'].get('accuracy', 0))
                    
        # Best portfolio allocation
        best_allocation = None
        best_sharpe = 0
        for method, results in portfolio_results.items():
            if results['sharpe_ratio'] > best_sharpe:
                best_sharpe = results['sharpe_ratio']
                best_allocation = method
                
        summary = {
            'best_signals': sorted(best_signals, 
                                  key=lambda x: x['profit_factor'], 
                                  reverse=True)[:3],
            'average_model_accuracy': np.mean(avg_accuracy) if avg_accuracy else 0,
            'stop_loss_improvement': stoploss_results.get('effectiveness', {}).get('pnl_improvement', 0),
            'best_combinations': len(combinations),
            'best_portfolio_method': best_allocation,
            'best_portfolio_sharpe': best_sharpe
        }
        
        return summary
    
    def _save_report(self, report: dict):
        """Save training report"""
        # Create results directory
        results_path = Path(self.config.get('results_path', 'results'))
        results_path.mkdir(parents=True, exist_ok=True)
        
        # Save JSON report
        report_file = results_path / f"training_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
            
        logger.info(f"Report saved to {report_file}")
        
        # Save summary to database
        self._save_to_database(report)
        
    def _save_to_database(self, report: dict):
        """Save training results to database"""
        summary = report['summary']
        
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO MLTrainingHistory (
                    ModelId, ModelType, TrainingDate,
                    TrainAccuracy, ValAccuracy,
                    Status, CreatedAt
                ) VALUES (
                    :model_id, 'PIPELINE', GETDATE(),
                    :accuracy, :accuracy,
                    'COMPLETED', GETDATE()
                )
            """), {
                'model_id': f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'accuracy': summary['average_model_accuracy']
            })

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='ML Training Pipeline')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--from-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--quick', action='store_true', help='Quick training mode')
    
    args = parser.parse_args()
    
    # Parse dates
    from_date = datetime.strptime(args.from_date, '%Y-%m-%d') if args.from_date else None
    to_date = datetime.strptime(args.to_date, '%Y-%m-%d') if args.to_date else None
    
    # Initialize pipeline
    pipeline = MLTrainingPipeline(args.config)
    
    # Modify config for quick mode
    if args.quick:
        pipeline.config['training_period_days'] = 90
        pipeline.config['model_types'] = ['xgboost']
        pipeline.config['ensemble_enabled'] = False
        pipeline.config['use_genetic_discovery'] = False
        
    # Run pipeline
    try:
        report = pipeline.run_full_pipeline(from_date, to_date)
        
        # Print summary
        print("\n" + "="*50)
        print("TRAINING SUMMARY")
        print("="*50)
        
        summary = report['summary']
        print(f"Average Model Accuracy: {summary['average_model_accuracy']:.2%}")
        print(f"Stop Loss Improvement: {summary.get('stop_loss_improvement', 0):.2%}")
        print(f"Discovered Combinations: {summary['best_combinations']}")
        print(f"Best Portfolio Method: {summary['best_portfolio_method']}")
        print(f"Best Portfolio Sharpe: {summary['best_portfolio_sharpe']:.2f}")
        
        print("\nTop Signals:")
        for signal in summary['best_signals'][:3]:
            print(f"  {signal['signal']}: Win Rate={signal['win_rate']:.2%}, "
                  f"PF={signal['profit_factor']:.2f}")
            
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()