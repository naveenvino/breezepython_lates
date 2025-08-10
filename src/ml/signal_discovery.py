"""
Signal Combination Discovery Module
Discovers new profitable signal combinations using pattern mining and genetic algorithms
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
from itertools import combinations, product
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
import random
from deap import base, creator, tools, algorithms
from sqlalchemy import create_engine, text
import json

logger = logging.getLogger(__name__)

@dataclass
class SignalCombination:
    """Discovered signal combination"""
    combination_id: str
    signals: List[str]
    rules: Dict[str, Any]
    backtest_results: Dict[str, float]
    confidence_score: float
    discovery_method: str
    validation_periods: int
    
    def to_dict(self) -> Dict:
        return {
            'combination_id': self.combination_id,
            'signals': self.signals,
            'rules': self.rules,
            'backtest_results': self.backtest_results,
            'confidence_score': self.confidence_score,
            'discovery_method': self.discovery_method,
            'validation_periods': self.validation_periods
        }

@dataclass
class TradingRule:
    """Trading rule for signal combination"""
    entry_conditions: List[str]
    exit_conditions: List[str]
    position_sizing: str
    stop_loss_method: str
    time_filters: Dict[str, Any]
    market_regime_filter: str

class SignalCombinationDiscovery:
    """Discovers profitable signal combinations"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize discovery module
        
        Args:
            db_connection_string: Database connection
        """
        self.engine = create_engine(db_connection_string)
        self.signal_types = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
        self.discovered_combinations = []
        self.genetic_population = None
        
    def discover_combinations(self,
                            from_date: datetime,
                            to_date: datetime,
                            methods: List[str] = ['correlation', 'sequential', 'genetic']) -> List[SignalCombination]:
        """
        Discover profitable signal combinations using multiple methods
        
        Args:
            from_date: Start date for analysis
            to_date: End date for analysis
            methods: Discovery methods to use
            
        Returns:
            List of discovered combinations
        """
        all_combinations = []
        
        if 'correlation' in methods:
            logger.info("Discovering correlation-based combinations...")
            corr_combinations = self._discover_correlation_combinations(from_date, to_date)
            all_combinations.extend(corr_combinations)
            
        if 'sequential' in methods:
            logger.info("Discovering sequential pattern combinations...")
            seq_combinations = self._discover_sequential_patterns(from_date, to_date)
            all_combinations.extend(seq_combinations)
            
        if 'genetic' in methods:
            logger.info("Discovering combinations using genetic algorithm...")
            genetic_combinations = self._discover_genetic_combinations(from_date, to_date)
            all_combinations.extend(genetic_combinations)
            
        if 'decision_tree' in methods:
            logger.info("Discovering rule-based combinations...")
            rule_combinations = self._discover_rule_based_combinations(from_date, to_date)
            all_combinations.extend(rule_combinations)
            
        # Validate and rank combinations
        validated_combinations = self._validate_combinations(all_combinations, from_date, to_date)
        
        # Store discoveries
        self._save_discoveries(validated_combinations)
        
        return validated_combinations
    
    def _discover_correlation_combinations(self,
                                         from_date: datetime,
                                         to_date: datetime) -> List[SignalCombination]:
        """
        Discover combinations based on signal correlations
        
        Args:
            from_date: Start date
            to_date: End date
            
        Returns:
            List of correlation-based combinations
        """
        # Get signal occurrences
        signal_data = self._get_signal_data(from_date, to_date)
        
        if signal_data.empty:
            return []
            
        combinations_found = []
        
        # Calculate correlation matrix
        signal_matrix = pd.get_dummies(signal_data['SignalType'])
        correlation = signal_matrix.corr()
        
        # Find negatively correlated signals (good for diversification)
        for signal1 in self.signal_types:
            for signal2 in self.signal_types:
                if signal1 >= signal2:
                    continue
                    
                if signal1 in correlation.columns and signal2 in correlation.columns:
                    corr_value = correlation.loc[signal1, signal2]
                    
                    # Negative correlation indicates diversification benefit
                    if corr_value < -0.3:
                        combination = self._create_combination(
                            signals=[signal1, signal2],
                            rules={
                                'type': 'diversification',
                                'correlation': corr_value,
                                'entry': f"Either {signal1} OR {signal2}",
                                'position_split': '50/50'
                            },
                            method='correlation'
                        )
                        
                        # Backtest combination
                        results = self._backtest_combination(combination, from_date, to_date)
                        combination.backtest_results = results
                        
                        if results.get('sharpe_ratio', 0) > 1.0:
                            combinations_found.append(combination)
                            
        # Find complementary signals (work well together)
        for size in [2, 3]:
            for combo in combinations(self.signal_types, size):
                if self._are_complementary_signals(combo, signal_data):
                    combination = self._create_combination(
                        signals=list(combo),
                        rules={
                            'type': 'complementary',
                            'entry': f"ALL of {combo} within 2 days",
                            'confidence_threshold': 0.7
                        },
                        method='correlation'
                    )
                    
                    results = self._backtest_combination(combination, from_date, to_date)
                    combination.backtest_results = results
                    
                    if results.get('win_rate', 0) > 0.6:
                        combinations_found.append(combination)
                        
        return combinations_found
    
    def _discover_sequential_patterns(self,
                                     from_date: datetime,
                                     to_date: datetime) -> List[SignalCombination]:
        """
        Discover sequential signal patterns
        
        Args:
            from_date: Start date
            to_date: End date
            
        Returns:
            List of sequential pattern combinations
        """
        signal_data = self._get_signal_data(from_date, to_date)
        
        if signal_data.empty:
            return []
            
        combinations_found = []
        
        # Group by week to find sequences
        signal_data['Week'] = pd.to_datetime(signal_data['EntryTime']).dt.to_period('W')
        
        # Find common sequences
        sequences = self._find_signal_sequences(signal_data)
        
        for sequence in sequences:
            if len(sequence) >= 2:
                # Check if sequence is profitable
                sequence_performance = self._evaluate_sequence_performance(sequence, signal_data)
                
                if sequence_performance['success_rate'] > 0.65:
                    combination = self._create_combination(
                        signals=sequence,
                        rules={
                            'type': 'sequential',
                            'sequence': ' -> '.join(sequence),
                            'max_gap_days': 3,
                            'entry': f"Wait for {sequence[0]}, then {sequence[1]}",
                            'success_rate': sequence_performance['success_rate']
                        },
                        method='sequential'
                    )
                    
                    results = self._backtest_combination(combination, from_date, to_date)
                    combination.backtest_results = results
                    
                    if results.get('profit_factor', 0) > 1.5:
                        combinations_found.append(combination)
                        
        # Find reversal patterns
        reversal_patterns = self._find_reversal_patterns(signal_data)
        
        for pattern in reversal_patterns:
            combination = self._create_combination(
                signals=pattern['signals'],
                rules={
                    'type': 'reversal',
                    'pattern': pattern['name'],
                    'entry': pattern['entry_rule'],
                    'confidence': pattern['confidence']
                },
                method='sequential'
            )
            
            results = self._backtest_combination(combination, from_date, to_date)
            combination.backtest_results = results
            
            if results.get('win_rate', 0) > 0.55:
                combinations_found.append(combination)
                
        return combinations_found
    
    def _discover_genetic_combinations(self,
                                      from_date: datetime,
                                      to_date: datetime,
                                      population_size: int = 50,
                                      generations: int = 20) -> List[SignalCombination]:
        """
        Use genetic algorithm to discover optimal signal combinations
        
        Args:
            from_date: Start date
            to_date: End date
            population_size: GA population size
            generations: Number of generations
            
        Returns:
            List of genetically optimized combinations
        """
        # Setup DEAP genetic algorithm
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
            creator.create("Individual", list, fitness=creator.FitnessMax)
            
        toolbox = base.Toolbox()
        
        # Gene: [signal_combination, entry_rule, exit_rule, position_size]
        toolbox.register("signal", random.choice, self.signal_types)
        toolbox.register("rule", random.choice, ['AND', 'OR', 'XOR', 'THEN'])
        toolbox.register("position", random.uniform, 0.1, 0.3)
        
        # Individual: combination of 2-4 signals with rules
        def create_individual():
            num_signals = random.randint(2, 4)
            signals = random.sample(self.signal_types, num_signals)
            rule = random.choice(['AND', 'OR', 'SEQUENTIAL'])
            position_size = random.uniform(0.1, 0.3)
            time_filter = random.choice(['ALL', 'MORNING', 'AFTERNOON'])
            
            return [signals, rule, position_size, time_filter]
            
        toolbox.register("individual", tools.initIterate, creator.Individual, create_individual)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        
        # Fitness function
        def evaluate_combination(individual):
            signals, rule, position_size, time_filter = individual
            
            # Create combination
            combination = self._create_combination(
                signals=signals,
                rules={
                    'type': 'genetic',
                    'combination_rule': rule,
                    'position_size': position_size,
                    'time_filter': time_filter
                },
                method='genetic'
            )
            
            # Backtest
            results = self._backtest_combination(combination, from_date, to_date)
            
            # Fitness is combination of Sharpe ratio and win rate
            fitness = results.get('sharpe_ratio', 0) * 0.5 + results.get('win_rate', 0) * 0.5
            
            return (fitness,)
            
        toolbox.register("evaluate", evaluate_combination)
        
        # Genetic operators
        toolbox.register("mate", tools.cxTwoPoint)
        toolbox.register("mutate", self._mutate_combination, indpb=0.2)
        toolbox.register("select", tools.selTournament, tournsize=3)
        
        # Create population
        population = toolbox.population(n=population_size)
        
        # Statistics
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("max", np.max)
        
        # Run genetic algorithm
        population, logbook = algorithms.eaSimple(
            population, toolbox,
            cxpb=0.5,  # Crossover probability
            mutpb=0.2,  # Mutation probability
            ngen=generations,
            stats=stats,
            verbose=False
        )
        
        # Get best individuals
        best_individuals = tools.selBest(population, k=5)
        
        combinations_found = []
        for individual in best_individuals:
            signals, rule, position_size, time_filter = individual
            
            combination = self._create_combination(
                signals=signals,
                rules={
                    'type': 'genetic_optimized',
                    'combination_rule': rule,
                    'position_size': position_size,
                    'time_filter': time_filter,
                    'fitness': individual.fitness.values[0]
                },
                method='genetic'
            )
            
            results = self._backtest_combination(combination, from_date, to_date)
            combination.backtest_results = results
            
            combinations_found.append(combination)
            
        return combinations_found
    
    def _discover_rule_based_combinations(self,
                                         from_date: datetime,
                                         to_date: datetime) -> List[SignalCombination]:
        """
        Discover combinations using decision tree rules
        
        Args:
            from_date: Start date
            to_date: End date
            
        Returns:
            List of rule-based combinations
        """
        # Get historical data with features
        data = self._prepare_ml_data(from_date, to_date)
        
        if data.empty:
            return []
            
        combinations_found = []
        
        # Train decision tree to find rules
        features = ['volatility', 'trend', 'volume_ratio', 'time_of_day', 'day_of_week']
        X = data[features]
        
        # For each signal, find when it works best
        for signal in self.signal_types:
            y = (data['SignalType'] == signal) & (data['PnL'] > 0)
            
            if y.sum() < 10:  # Not enough positive samples
                continue
                
            # Train decision tree
            clf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=5)
            clf.fit(X, y)
            
            # Extract rules
            rules = self._extract_decision_rules(clf, features)
            
            if rules:
                # Find complementary signal for these conditions
                complement = self._find_best_complement(signal, data, rules)
                
                if complement:
                    combination = self._create_combination(
                        signals=[signal, complement],
                        rules={
                            'type': 'rule_based',
                            'primary_signal': signal,
                            'complement_signal': complement,
                            'conditions': rules,
                            'entry': f"When {rules[0]}, use {signal} + {complement}"
                        },
                        method='decision_tree'
                    )
                    
                    results = self._backtest_combination(combination, from_date, to_date)
                    combination.backtest_results = results
                    
                    if results.get('sharpe_ratio', 0) > 1.2:
                        combinations_found.append(combination)
                        
        return combinations_found
    
    def _get_signal_data(self, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        """Get historical signal data"""
        query = """
        SELECT 
            SignalType,
            EntryTime,
            ExitTime,
            PnL,
            Direction,
            StopLoss
        FROM BacktestTrades
        WHERE EntryTime >= :from_date 
            AND EntryTime <= :to_date
        ORDER BY EntryTime
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text(query),
                {'from_date': from_date, 'to_date': to_date}
            )
            return pd.DataFrame(result.fetchall())
    
    def _are_complementary_signals(self, 
                                  signals: Tuple[str],
                                  data: pd.DataFrame) -> bool:
        """Check if signals are complementary"""
        # Simplified logic - check if signals don't overlap much
        signal_days = {}
        
        for signal in signals:
            signal_data = data[data['SignalType'] == signal]
            signal_days[signal] = set(pd.to_datetime(signal_data['EntryTime']).dt.date)
            
        # Check overlap
        if len(signals) == 2:
            overlap = len(signal_days[signals[0]] & signal_days[signals[1]])
            total = len(signal_days[signals[0]] | signal_days[signals[1]])
            
            # Low overlap means complementary
            return (overlap / total < 0.2) if total > 0 else False
            
        return False
    
    def _find_signal_sequences(self, data: pd.DataFrame) -> List[List[str]]:
        """Find common signal sequences"""
        sequences = []
        
        # Group by week and find patterns
        for week, group in data.groupby('Week'):
            week_signals = group.sort_values('EntryTime')['SignalType'].tolist()
            
            # Look for 2-signal and 3-signal sequences
            for length in [2, 3]:
                if len(week_signals) >= length:
                    for i in range(len(week_signals) - length + 1):
                        sequence = week_signals[i:i+length]
                        sequences.append(sequence)
                        
        # Count frequency
        from collections import Counter
        sequence_counts = Counter(tuple(s) for s in sequences)
        
        # Return common sequences (appearing at least 3 times)
        common_sequences = [list(seq) for seq, count in sequence_counts.items() if count >= 3]
        
        return common_sequences
    
    def _evaluate_sequence_performance(self,
                                      sequence: List[str],
                                      data: pd.DataFrame) -> Dict[str, float]:
        """Evaluate performance of a signal sequence"""
        performance = {'success_rate': 0, 'avg_return': 0}
        
        # Find occurrences of the sequence
        successes = 0
        total = 0
        returns = []
        
        for week, group in data.groupby('Week'):
            week_signals = group.sort_values('EntryTime')['SignalType'].tolist()
            week_pnls = group.sort_values('EntryTime')['PnL'].tolist()
            
            # Check if sequence appears
            for i in range(len(week_signals) - len(sequence) + 1):
                if week_signals[i:i+len(sequence)] == sequence:
                    total += 1
                    sequence_pnl = sum(week_pnls[i:i+len(sequence)])
                    returns.append(sequence_pnl)
                    if sequence_pnl > 0:
                        successes += 1
                        
        if total > 0:
            performance['success_rate'] = successes / total
            performance['avg_return'] = np.mean(returns) if returns else 0
            
        return performance
    
    def _find_reversal_patterns(self, data: pd.DataFrame) -> List[Dict]:
        """Find reversal patterns in signals"""
        patterns = []
        
        # Bullish reversal: Bearish signal followed by strong bullish signal
        bearish_signals = ['S3', 'S5', 'S6', 'S8']
        bullish_signals = ['S1', 'S2', 'S4', 'S7']
        
        for bear in bearish_signals:
            for bull in bullish_signals:
                pattern = {
                    'name': f"{bear}_to_{bull}_reversal",
                    'signals': [bear, bull],
                    'entry_rule': f"After {bear} failure, enter on {bull}",
                    'confidence': 0.7
                }
                patterns.append(pattern)
                
        return patterns
    
    def _create_combination(self,
                          signals: List[str],
                          rules: Dict[str, Any],
                          method: str) -> SignalCombination:
        """Create a signal combination"""
        import uuid
        
        return SignalCombination(
            combination_id=str(uuid.uuid4()),
            signals=signals,
            rules=rules,
            backtest_results={},
            confidence_score=0.5,
            discovery_method=method,
            validation_periods=0
        )
    
    def _backtest_combination(self,
                            combination: SignalCombination,
                            from_date: datetime,
                            to_date: datetime) -> Dict[str, float]:
        """Backtest a signal combination"""
        # Simplified backtest - would use actual backtest engine
        results = {
            'total_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'total_return': 0
        }
        
        # Get trades for combination signals
        signal_data = self._get_signal_data(from_date, to_date)
        
        if signal_data.empty:
            return results
            
        # Filter for combination signals
        combo_data = signal_data[signal_data['SignalType'].isin(combination.signals)]
        
        if combo_data.empty:
            return results
            
        # Calculate metrics
        results['total_trades'] = len(combo_data)
        
        winning_trades = combo_data[combo_data['PnL'] > 0]
        results['win_rate'] = len(winning_trades) / len(combo_data) if len(combo_data) > 0 else 0
        
        gross_profit = winning_trades['PnL'].sum() if len(winning_trades) > 0 else 0
        gross_loss = abs(combo_data[combo_data['PnL'] <= 0]['PnL'].sum())
        results['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Simplified Sharpe (would calculate properly with returns)
        returns = combo_data['PnL'].values
        if len(returns) > 1:
            results['sharpe_ratio'] = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
            
        results['total_return'] = combo_data['PnL'].sum()
        
        return results
    
    def _mutate_combination(self, individual, indpb):
        """Mutate combination for genetic algorithm"""
        for i in range(len(individual)):
            if random.random() < indpb:
                if i == 0:  # Signals
                    # Add or remove a signal
                    if random.random() < 0.5 and len(individual[0]) > 2:
                        individual[0].pop(random.randint(0, len(individual[0])-1))
                    elif len(individual[0]) < 4:
                        new_signal = random.choice(self.signal_types)
                        if new_signal not in individual[0]:
                            individual[0].append(new_signal)
                elif i == 1:  # Rule
                    individual[1] = random.choice(['AND', 'OR', 'SEQUENTIAL'])
                elif i == 2:  # Position size
                    individual[2] = random.uniform(0.1, 0.3)
                elif i == 3:  # Time filter
                    individual[3] = random.choice(['ALL', 'MORNING', 'AFTERNOON'])
                    
        return individual,
    
    def _prepare_ml_data(self, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        """Prepare data for ML analysis"""
        # Get market data with features
        query = """
        SELECT 
            t.*,
            n.Close as NIFTY_Close,
            n.Volume,
            n.High - n.Low as Range,
            DATEPART(hour, t.EntryTime) as TimeOfDay,
            DATEPART(weekday, t.EntryTime) as DayOfWeek
        FROM BacktestTrades t
        JOIN NIFTYData_5Min n ON 
            ABS(DATEDIFF(minute, t.EntryTime, n.Timestamp)) < 30
        WHERE t.EntryTime >= :from_date 
            AND t.EntryTime <= :to_date
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text(query),
                {'from_date': from_date, 'to_date': to_date}
            )
            df = pd.DataFrame(result.fetchall())
            
        if not df.empty:
            # Calculate additional features
            df['volatility'] = df['Range'] / df['NIFTY_Close']
            df['volume_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
            df['trend'] = df['NIFTY_Close'].pct_change(5)
            
        return df
    
    def _extract_decision_rules(self, 
                               tree: DecisionTreeClassifier,
                               feature_names: List[str]) -> List[str]:
        """Extract human-readable rules from decision tree"""
        rules = []
        
        # Simplified rule extraction
        # In production, would properly traverse the tree
        
        # Get feature importances
        importances = tree.feature_importances_
        important_features = [f for f, imp in zip(feature_names, importances) if imp > 0.1]
        
        if important_features:
            rules.append(f"High importance on {', '.join(important_features)}")
            
        return rules
    
    def _find_best_complement(self,
                             primary_signal: str,
                             data: pd.DataFrame,
                             rules: List[str]) -> Optional[str]:
        """Find best complementary signal for given conditions"""
        best_complement = None
        best_score = 0
        
        primary_data = data[data['SignalType'] == primary_signal]
        
        for signal in self.signal_types:
            if signal == primary_signal:
                continue
                
            # Check performance when both signals present
            signal_data = data[data['SignalType'] == signal]
            
            # Simple scoring based on non-overlap and performance
            overlap_dates = set(pd.to_datetime(primary_data['EntryTime']).dt.date) & \
                          set(pd.to_datetime(signal_data['EntryTime']).dt.date)
                          
            if len(overlap_dates) < 5:  # Low overlap
                score = signal_data['PnL'].mean() if len(signal_data) > 0 else 0
                
                if score > best_score:
                    best_score = score
                    best_complement = signal
                    
        return best_complement
    
    def _validate_combinations(self,
                              combinations: List[SignalCombination],
                              from_date: datetime,
                              to_date: datetime) -> List[SignalCombination]:
        """Validate and rank discovered combinations"""
        validated = []
        
        for combination in combinations:
            # Walk-forward validation
            validation_score = self._walk_forward_validation(combination, from_date, to_date)
            
            combination.confidence_score = validation_score
            combination.validation_periods = 3  # Number of validation periods
            
            # Only keep combinations with good validation score
            if validation_score > 0.6:
                validated.append(combination)
                
        # Sort by confidence score
        validated.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return validated[:20]  # Return top 20
    
    def _walk_forward_validation(self,
                                combination: SignalCombination,
                                from_date: datetime,
                                to_date: datetime,
                                num_folds: int = 3) -> float:
        """Perform walk-forward validation"""
        total_days = (to_date - from_date).days
        fold_days = total_days // (num_folds + 1)
        
        scores = []
        
        for i in range(num_folds):
            # Training period
            train_start = from_date + timedelta(days=i * fold_days)
            train_end = train_start + timedelta(days=fold_days)
            
            # Validation period
            val_start = train_end
            val_end = val_start + timedelta(days=fold_days // 2)
            
            # Backtest on validation period
            val_results = self._backtest_combination(combination, val_start, val_end)
            
            # Score based on Sharpe ratio and consistency
            score = val_results.get('sharpe_ratio', 0) * 0.7 + \
                   val_results.get('win_rate', 0) * 0.3
                   
            scores.append(score)
            
        return np.mean(scores) if scores else 0
    
    def _save_discoveries(self, combinations: List[SignalCombination]):
        """Save discovered combinations to database"""
        with self.engine.begin() as conn:
            for combination in combinations:
                conn.execute(text("""
                    INSERT INTO SignalCombinations (
                        CombinationId, Signals, Rules, BacktestResults,
                        WinRate, ProfitFactor, SharpeRatio,
                        DiscoveredAt, Status
                    ) VALUES (
                        :combination_id, :signals, :rules, :backtest_results,
                        :win_rate, :profit_factor, :sharpe_ratio,
                        GETDATE(), 'DISCOVERED'
                    )
                """), {
                    'combination_id': combination.combination_id,
                    'signals': ','.join(combination.signals),
                    'rules': json.dumps(combination.rules),
                    'backtest_results': json.dumps(combination.backtest_results),
                    'win_rate': combination.backtest_results.get('win_rate', 0) * 100,
                    'profit_factor': combination.backtest_results.get('profit_factor', 0),
                    'sharpe_ratio': combination.backtest_results.get('sharpe_ratio', 0)
                })
                
        logger.info(f"Saved {len(combinations)} discovered combinations to database")