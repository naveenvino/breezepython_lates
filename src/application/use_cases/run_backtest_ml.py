"""
Run Backtest with ML Integration
Enhanced backtesting with 5-minute granularity and ML-powered exit optimization
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import asyncio
import pandas as pd

from ...domain.value_objects.signal_types import SignalType, BarData
from ...domain.services.signal_evaluator import SignalEvaluator
from ...domain.services.weekly_context_manager import WeeklyContextManager
from ...domain.services.margin_calculator import MarginCalculator
from ...domain.services.risk_manager import RiskManager
from ...domain.services.market_calendar import MarketCalendar
from ...infrastructure.services.data_collection_service import DataCollectionService
from ...infrastructure.services.option_pricing_service import OptionPricingService
from ...infrastructure.services.holiday_service import HolidayService
from ...infrastructure.validation.market_data_validator import MarketDataValidator
from ...infrastructure.database.models import (
    BacktestRun, BacktestTrade, BacktestPosition, BacktestDailyResult,
    BacktestStatus, NiftyIndexData, NiftyIndexDataHourly, TradeOutcome
)
from ...infrastructure.database.database_manager import get_db_manager
from ...domain.services.progressive_sl_manager import ProgressiveSLManager, PositionData

# ML Components
from ...ml.trade_lifecycle_analyzer import TradeLifecycleAnalyzer
from ...ml.models.exit_predictor import ExitPredictor
from ...ml.trailing_stop_engine import TrailingStopEngine
from ...ml.market_regime_classifier import MarketRegimeClassifier
from ...ml.profit_target_optimizer import ProfitTargetOptimizer
from ...ml.position_adjustment_engine import PositionAdjustmentEngine, PositionState
from ...ml.greeks_analyzer import GreeksAnalyzer

logger = logging.getLogger(__name__)


class MLBacktestParameters:
    """Enhanced parameters for ML-powered backtesting"""
    def __init__(
        self,
        from_date: datetime,
        to_date: datetime,
        initial_capital: float = 500000,
        lot_size: int = 75,
        lots_to_trade: int = 10,
        lots_per_signal: Dict[str, int] = None,
        signals_to_test: List[str] = None,
        use_hedging: bool = True,
        hedge_offset: int = 200,
        commission_per_lot: float = 40,
        slippage_percent: float = 0.001,
        # ML Parameters
        use_ml_exits: bool = True,
        use_trailing_stops: bool = True,
        use_profit_targets: bool = True,
        use_position_adjustments: bool = True,
        use_regime_filter: bool = True,
        granularity_minutes: int = 5,  # 5-minute bars
        ml_confidence_threshold: float = 0.7,  # Min confidence for ML decisions
        partial_exit_enabled: bool = True,
        wednesday_exit_enabled: bool = True,
        breakeven_enabled: bool = True,
        # Progressive P&L Stop-Loss Parameters
        use_progressive_sl: bool = False,
        initial_sl_per_lot: float = 6000,
        profit_trigger_percent: float = 40,
        day2_sl_factor: float = 0.5,
        day3_breakeven: bool = True,
        day4_profit_lock_percent: float = 5,
        track_5min_pnl: bool = True,
        # ML-Enhanced Progressive SL
        ml_optimize_sl_rules: bool = False,
        adaptive_sl_enabled: bool = False,
        signal_specific_sl: bool = False
    ):
        self.from_date = from_date
        self.to_date = to_date
        self.initial_capital = initial_capital
        self.lot_size = lot_size
        self.lots_to_trade = lots_to_trade
        self.lots_per_signal = lots_per_signal or {}
        self.signals_to_test = signals_to_test or ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
        self.use_hedging = use_hedging
        self.hedge_offset = hedge_offset
        self.commission_per_lot = commission_per_lot
        self.slippage_percent = slippage_percent
        # ML settings
        self.use_ml_exits = use_ml_exits
        self.use_trailing_stops = use_trailing_stops
        self.use_profit_targets = use_profit_targets
        self.use_position_adjustments = use_position_adjustments
        self.use_regime_filter = use_regime_filter
        self.granularity_minutes = granularity_minutes
        self.ml_confidence_threshold = ml_confidence_threshold
        self.partial_exit_enabled = partial_exit_enabled
        self.wednesday_exit_enabled = wednesday_exit_enabled
        self.breakeven_enabled = breakeven_enabled
        # Progressive P&L Stop-Loss
        self.use_progressive_sl = use_progressive_sl
        self.initial_sl_per_lot = initial_sl_per_lot
        self.profit_trigger_percent = profit_trigger_percent
        self.day2_sl_factor = day2_sl_factor
        self.day3_breakeven = day3_breakeven
        self.day4_profit_lock_percent = day4_profit_lock_percent
        self.track_5min_pnl = track_5min_pnl
        # ML-Enhanced Progressive SL
        self.ml_optimize_sl_rules = ml_optimize_sl_rules
        self.adaptive_sl_enabled = adaptive_sl_enabled
        self.signal_specific_sl = signal_specific_sl


class RunMLBacktestUseCase:
    """
    Enhanced backtest with ML integration and 5-minute granularity
    """
    
    def __init__(
        self,
        data_collection_service: DataCollectionService,
        option_pricing_service: OptionPricingService,
        db_connection_string: str
    ):
        self.data_collection = data_collection_service
        self.option_pricing = option_pricing_service
        self.signal_evaluator = SignalEvaluator()
        self.context_manager = WeeklyContextManager()
        self.holiday_service = HolidayService()
        self.db_manager = get_db_manager()
        
        # Initialize ML components
        self.lifecycle_analyzer = TradeLifecycleAnalyzer(db_connection_string)
        self.exit_predictor = ExitPredictor(db_connection_string)
        self.trailing_stop_engine = TrailingStopEngine(db_connection_string)
        self.regime_classifier = MarketRegimeClassifier(db_connection_string)
        self.profit_target_optimizer = ProfitTargetOptimizer(db_connection_string)
        self.position_adjustment_engine = PositionAdjustmentEngine(db_connection_string)
        self.greeks_analyzer = GreeksAnalyzer(db_connection_string)
        
        # Track trade lifecycle data
        self.trade_lifecycle_data = {}  # trade_id -> lifecycle metrics
        self.trade_max_pnl = {}  # trade_id -> max P&L reached
        self.trade_entry_times = {}  # trade_id -> entry time
        
        # Progressive P&L Stop-Loss tracking
        self.progressive_sl_managers = {}  # trade_id -> ProgressiveSLManager
        self.pnl_tracking_data = []  # 5-min P&L tracking
        self.sl_update_logs = []  # SL update history
        self.ml_sl_decisions = {}  # trade_id -> ML vs rule-based decision tracking
    
    async def execute(self, params: MLBacktestParameters) -> str:
        """
        Execute ML-enhanced backtest
        
        Args:
            params: ML backtest parameters
            
        Returns:
            Backtest run ID
        """
        logger.info(f"Starting ML-enhanced backtest from {params.from_date} to {params.to_date}")
        logger.info(f"ML Features - Exits: {params.use_ml_exits}, Trailing: {params.use_trailing_stops}, "
                   f"Targets: {params.use_profit_targets}, Adjustments: {params.use_position_adjustments}")
        
        # Train ML models if needed
        if params.use_ml_exits:
            await self._train_ml_models(params)
        
        # Get optimal profit targets
        if params.use_profit_targets:
            self.optimal_targets = self.profit_target_optimizer.optimize_targets(
                params.from_date, params.to_date
            )
        
        # Create backtest run record
        backtest_run = await self._create_backtest_run(params)
        
        try:
            # Update status to running
            await self._update_backtest_status(backtest_run.id, BacktestStatus.RUNNING)
            
            # Get 5-minute NIFTY data
            nifty_data = await self._get_5min_data(params.from_date, params.to_date)
            
            if nifty_data.empty:
                raise ValueError("No NIFTY data available for the specified period")
            
            # Run ML-enhanced backtest
            results = await self._run_ml_backtest_logic(
                backtest_run, nifty_data, params
            )
            
            # Save lifecycle analysis data
            await self._save_lifecycle_data(backtest_run.id)
            
            # Update backtest run with results
            await self._update_backtest_results(backtest_run.id, results)
            
            # Update status to completed
            await self._update_backtest_status(backtest_run.id, BacktestStatus.COMPLETED)
            
            logger.info(f"ML Backtest completed successfully. ID: {backtest_run.id}")
            return backtest_run.id
            
        except Exception as e:
            logger.error(f"ML Backtest failed: {e}")
            await self._update_backtest_status(
                backtest_run.id, BacktestStatus.FAILED, str(e)
            )
            raise
    
    async def _train_ml_models(self, params: MLBacktestParameters):
        """Train ML models before backtesting"""
        logger.info("Training ML models...")
        
        # Train exit predictor
        train_from = params.from_date - timedelta(days=180)  # Use 6 months prior data
        self.exit_predictor.train_models(train_from, params.from_date)
        
        # Train regime classifier
        self.regime_classifier.train_classifier(train_from, params.from_date)
        
        logger.info("ML models trained successfully")
    
    async def _get_5min_data(self, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        """Get 5-minute NIFTY data"""
        import pyodbc
        
        query = """
        SELECT 
            Timestamp,
            [Open] as open_price,
            High as high_price,
            Low as low_price,
            [Close] as close_price,
            Volume
        FROM NiftyIndexData5Minute
        WHERE Timestamp >= ?
            AND Timestamp <= ?
        ORDER BY Timestamp
        """
        
        # Use direct pyodbc connection for compatibility
        conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\mssqllocaldb;Database=KiteConnectApi;Trusted_Connection=yes;"
        with pyodbc.connect(conn_str) as conn:
            df = pd.read_sql(query, conn, params=[from_date, to_date])
        
        return df
    
    async def _run_ml_backtest_logic(
        self,
        backtest_run: BacktestRun,
        nifty_data: pd.DataFrame,
        params: MLBacktestParameters
    ) -> Dict:
        """Main ML-enhanced backtest logic with 5-minute bars"""
        # Initialize tracking
        current_capital = float(params.initial_capital)
        open_trades: List[BacktestTrade] = []
        all_trades: List[BacktestTrade] = []
        daily_results: List[BacktestDailyResult] = []
        
        # Track intraday P&L
        intraday_pnl = []  # List of (timestamp, pnl) tuples
        
        # Convert DataFrame to list of BarData for context manager
        bar_data_list = []
        for _, df_row in nifty_data.iterrows():
            bar = BarData(
                timestamp=df_row['Timestamp'],
                open=df_row['open_price'],
                high=df_row['high_price'],
                low=df_row['low_price'],
                close=df_row['close_price'],
                volume=df_row.get('Volume', 0)
            )
            bar_data_list.append(bar)
        
        # Process each 5-minute bar
        for idx, row in nifty_data.iterrows():
            timestamp = row['Timestamp']
            
            # Skip non-market hours
            if timestamp.hour < 9 or (timestamp.hour == 9 and timestamp.minute < 15):
                continue
            if timestamp.hour >= 15 and timestamp.minute > 30:
                continue
            
            # Check for signals (only if no open trades and during valid hours)
            if not open_trades and timestamp.hour >= 10 and timestamp.hour < 14:
                # Create BarData for signal evaluation
                current_bar = BarData(
                    timestamp=timestamp,
                    open=row['open_price'],
                    high=row['high_price'],
                    low=row['low_price'],
                    close=row['close_price'],
                    volume=row.get('Volume', 0)
                )
                
                # Get weekly context for signal evaluation
                # Get previous week data for context
                # Get the index in the bar_data_list
                bar_idx = next((i for i, b in enumerate(bar_data_list) if b.timestamp == timestamp), None)
                if bar_idx is None or bar_idx < 35:  # Need at least 35 bars for previous week
                    continue
                    
                prev_week_data = self.context_manager.get_previous_week_data(
                    timestamp, bar_data_list[:bar_idx]
                )
                
                if not prev_week_data:
                    logger.debug(f"No previous week data at {timestamp}, skipping signal check")
                    continue
                
                # Update weekly context
                context = self.context_manager.update_context(current_bar, prev_week_data)
                
                # Evaluate signals
                signal_result = self.signal_evaluator.evaluate_all_signals(
                    current_bar, context, timestamp
                )
                
                # Log evaluation for debugging on Monday
                if timestamp.date() == datetime(2025, 7, 14).date() and timestamp.hour == 11:
                    logger.info(f"ML Signal check at {timestamp}: triggered={signal_result.is_triggered}, "
                               f"type={signal_result.signal_type}, context_zones={context.zones is not None}")
                
                # Process detected signals
                if signal_result.is_triggered and signal_result.signal_type in params.signals_to_test:
                    logger.info(f"ML Backtest: Detected {signal_result.signal_type} at {timestamp}")
                    
                    # Create new trade
                    trade = await self._create_trade_entry(
                        signal_result,
                        timestamp,
                        row['close_price'],
                        params,
                        backtest_run.id
                    )
                    
                    if trade:
                        open_trades.append(trade)
                        all_trades.append(trade)
                        
                        # Initialize progressive SL if enabled
                        if params.use_progressive_sl:
                            sl_manager = ProgressiveSLManager(
                                initial_sl_per_lot=params.initial_sl_per_lot,
                                lots=params.lots_to_trade,
                                profit_trigger_percent=params.profit_trigger_percent,
                                day2_sl_factor=params.day2_sl_factor,
                                day3_breakeven=params.day3_breakeven,
                                day4_profit_lock_percent=params.day4_profit_lock_percent
                            )
                            self.progressive_sl_managers[trade.id] = sl_manager
            
            # Check market regime if enabled
            if params.use_regime_filter and open_trades:
                regime = self.regime_classifier.classify_current_regime("NIFTY", 20)
                if regime.current_regime.value in ['CHOPPY', 'BREAKDOWN']:
                    # Consider reducing position or tightening stops
                    pass
            
            # Process open trades with ML logic
            for trade in open_trades[:]:  # Copy list to allow modification
                if trade.outcome != TradeOutcome.OPEN:
                    continue
                
                # Get current P&L for the trade
                current_pnl = await self._calculate_trade_pnl(
                    trade, timestamp, row['close_price']
                )
                
                # Track max P&L
                if trade.id not in self.trade_max_pnl:
                    self.trade_max_pnl[trade.id] = current_pnl
                else:
                    self.trade_max_pnl[trade.id] = max(self.trade_max_pnl[trade.id], current_pnl)
                
                # ML Exit Prediction
                if params.use_ml_exits:
                    exit_action = await self._get_ml_exit_decision(
                        trade, timestamp, current_pnl, params
                    )
                    
                    if exit_action == 'FULL_EXIT':
                        pnl = await self._close_trade(
                            trade, timestamp, row['close_price'],
                            TradeOutcome.WIN if current_pnl > 0 else TradeOutcome.LOSS,
                            "ML Exit Signal"
                        )
                        current_capital += pnl
                        open_trades.remove(trade)
                        continue
                    elif exit_action == 'PARTIAL_EXIT' and params.partial_exit_enabled:
                        # Close 50% of position
                        partial_pnl = await self._partial_close_trade(
                            trade, timestamp, row['close_price'], 0.5
                        )
                        current_capital += partial_pnl
                
                # Trailing Stop Update
                if params.use_trailing_stops and current_pnl > 0:
                    stop_level = self.trailing_stop_engine.update_trailing_stop(
                        trade_id=trade.id,
                        signal_type=trade.signal_type,
                        current_pnl=current_pnl,
                        max_pnl=self.trade_max_pnl[trade.id],
                        current_price=row['close_price'],
                        entry_price=float(trade.index_price_at_entry),
                        entry_time=trade.entry_time
                    )
                    
                    # Check if trailing stop triggered
                    triggered, reason = self.trailing_stop_engine.check_stop_triggered(
                        trade.id, current_pnl, row['close_price']
                    )
                    
                    if triggered:
                        pnl = await self._close_trade(
                            trade, timestamp, row['close_price'],
                            TradeOutcome.STOPPED, f"Trailing Stop: {reason}"
                        )
                        current_capital += pnl
                        open_trades.remove(trade)
                        continue
                
                # Profit Target Check
                if params.use_profit_targets and trade.signal_type in self.optimal_targets:
                    target = self.optimal_targets[trade.signal_type]
                    if current_pnl >= target.primary_target:
                        pnl = await self._close_trade(
                            trade, timestamp, row['close_price'],
                            TradeOutcome.WIN, "Profit Target Reached"
                        )
                        current_capital += pnl
                        open_trades.remove(trade)
                        continue
                
                # Wednesday Morning Exit
                if params.wednesday_exit_enabled:
                    if timestamp.weekday() == 2 and timestamp.hour <= 12:  # Wednesday
                        if current_pnl > 0:
                            # Exit 50% on Wednesday morning
                            partial_pnl = await self._partial_close_trade(
                                trade, timestamp, row['close_price'], 0.5
                            )
                            current_capital += partial_pnl
                
                # Position Adjustment Check
                if params.use_position_adjustments:
                    position_state = self._create_position_state(
                        trade, timestamp, row['close_price'], current_pnl
                    )
                    adjustment = self.position_adjustment_engine.analyze_position(position_state)
                    
                    if adjustment.adjustment_needed and adjustment.urgency in ['IMMEDIATE', 'HIGH']:
                        # Execute adjustment (simplified for backtest)
                        logger.info(f"Position adjustment recommended: {adjustment.adjustment_type.value}")
                
                # Greeks Analysis (for options risk)
                greeks = self.greeks_analyzer.analyze_current_greeks(
                    trade.id, trade.signal_type,
                    float(trade.stop_loss_price),  # Main strike
                    'PE' if 'BULLISH' in str(trade.direction) else 'CE'
                )
                
                if greeks.current_risk_level in ['HIGH', 'CRITICAL']:
                    logger.warning(f"High Greeks risk for trade {trade.id}: {greeks.recommended_action}")
            
            # Track intraday P&L every 30 minutes
            if timestamp.minute % 30 == 0:
                total_open_pnl = sum([
                    await self._calculate_trade_pnl(t, timestamp, row['close_price'])
                    for t in open_trades if t.outcome == TradeOutcome.OPEN
                ])
                intraday_pnl.append((timestamp, total_open_pnl))
            
            # Check for new signals (hourly bars for signal evaluation)
            if timestamp.minute == 15:  # Check signals at X:15 (hourly close)
                # Create hourly bar for signal evaluation
                hourly_bar = self._create_hourly_bar(nifty_data, idx)
                if hourly_bar:
                    # [Signal evaluation logic - similar to original but with hourly bars]
                    pass
        
        # Calculate enhanced metrics
        results = self._calculate_enhanced_metrics(
            all_trades, daily_results, intraday_pnl, params
        )
        
        return results
    
    async def _get_ml_exit_decision(
        self,
        trade: BacktestTrade,
        timestamp: datetime,
        current_pnl: float,
        params: MLBacktestParameters
    ) -> str:
        """Get ML-based exit decision"""
        # Calculate time in trade
        time_in_trade = (timestamp - trade.entry_time).total_seconds() / 3600
        
        # Prepare state for ML prediction
        state = {
            'signal_type': trade.signal_type,
            'entry_time': trade.entry_time,
            'entry_hour': trade.entry_time.hour,
            'entry_day_of_week': trade.entry_time.weekday(),
            'time_in_trade_hours': time_in_trade,
            'current_pnl': current_pnl,
            'max_pnl': self.trade_max_pnl.get(trade.id, current_pnl),
            'direction': trade.direction
        }
        
        # Get ML prediction
        prediction = self.exit_predictor.predict_exit(trade.signal_type, state)
        
        # Check confidence threshold
        if prediction.confidence >= params.ml_confidence_threshold:
            return prediction.action
        
        return 'HOLD'
    
    def _create_position_state(
        self,
        trade: BacktestTrade,
        timestamp: datetime,
        spot_price: float,
        current_pnl: float
    ) -> PositionState:
        """Create position state for adjustment analysis"""
        # Get main position details
        main_position = next((p for p in trade.positions if p.position_type == 'MAIN'), None)
        hedge_position = next((p for p in trade.positions if p.position_type == 'HEDGE'), None)
        
        return PositionState(
            trade_id=trade.id,
            signal_type=trade.signal_type,
            entry_time=trade.entry_time,
            current_time=timestamp,
            main_strike=float(main_position.strike_price) if main_position else 0,
            main_type=main_position.option_type if main_position else '',
            main_quantity=abs(main_position.quantity) if main_position else 0,
            main_entry_price=float(main_position.entry_price) if main_position else 0,
            main_current_price=100,  # Simplified - would get actual price
            hedge_strike=float(hedge_position.strike_price) if hedge_position else None,
            hedge_type=hedge_position.option_type if hedge_position else None,
            hedge_quantity=abs(hedge_position.quantity) if hedge_position else None,
            hedge_current_price=50 if hedge_position else None,  # Simplified
            spot_price=spot_price,
            implied_volatility=20,  # Simplified - would calculate actual IV
            days_to_expiry=self._calculate_days_to_expiry(main_position.expiry_date, timestamp),
            net_delta=0.3,  # Simplified - would get actual Greeks
            net_gamma=0.01,
            net_theta=-50,
            net_vega=100,
            current_pnl=current_pnl,
            max_pnl=self.trade_max_pnl.get(trade.id, current_pnl),
            unrealized_pnl=current_pnl
        )
    
    def _calculate_days_to_expiry(self, expiry_date: datetime, current_time: datetime) -> int:
        """Calculate days remaining to expiry"""
        return max(0, (expiry_date - current_time).days)
    
    async def _calculate_trade_pnl(
        self,
        trade: BacktestTrade,
        timestamp: datetime,
        spot_price: float
    ) -> float:
        """Calculate current P&L for a trade"""
        total_pnl = 0.0
        
        for position in trade.positions:
            # Get current option price
            current_price = await self.option_pricing.get_option_price_at_time(
                timestamp,
                position.strike_price,
                position.option_type,
                position.expiry_date
            )
            
            if not current_price:
                # Estimate based on intrinsic value
                if position.option_type == "CE":
                    current_price = max(0, spot_price - position.strike_price)
                else:  # PE
                    current_price = max(0, position.strike_price - spot_price)
            
            # Calculate P&L
            if position.quantity < 0:  # Sold option
                pnl = abs(position.quantity) * (float(position.entry_price) - current_price)
            else:  # Bought option
                pnl = position.quantity * (current_price - float(position.entry_price))
            
            total_pnl += pnl
        
        # Subtract commission
        lots = abs(trade.positions[0].quantity) // 75 if trade.positions else 0
        commission = lots * 40 * 2  # Entry + exit
        
        return total_pnl - commission
    
    async def _partial_close_trade(
        self,
        trade: BacktestTrade,
        timestamp: datetime,
        spot_price: float,
        percentage: float
    ) -> float:
        """Partially close a trade"""
        # Calculate P&L for partial close
        full_pnl = await self._calculate_trade_pnl(trade, timestamp, spot_price)
        partial_pnl = full_pnl * percentage
        
        # Update position quantities
        for position in trade.positions:
            position.quantity = int(position.quantity * (1 - percentage))
        
        # Record partial close in lifecycle data
        if trade.id not in self.trade_lifecycle_data:
            self.trade_lifecycle_data[trade.id] = {}
        
        if 'partial_exits' not in self.trade_lifecycle_data[trade.id]:
            self.trade_lifecycle_data[trade.id]['partial_exits'] = []
        
        self.trade_lifecycle_data[trade.id]['partial_exits'].append({
            'timestamp': timestamp,
            'percentage': percentage,
            'pnl': partial_pnl
        })
        
        logger.info(f"Partial close {percentage*100}% of trade {trade.id} for P&L: {partial_pnl:.2f}")
        
        return partial_pnl
    
    def _create_hourly_bar(self, df: pd.DataFrame, current_idx: int) -> Optional[BarData]:
        """Create hourly bar from 5-minute data"""
        # Get last 12 bars (60 minutes)
        if current_idx < 11:
            return None
        
        hourly_data = df.iloc[current_idx-11:current_idx+1]
        
        return BarData(
            timestamp=df.iloc[current_idx]['Timestamp'],
            open=hourly_data.iloc[0]['open_price'],
            high=hourly_data['high_price'].max(),
            low=hourly_data['low_price'].min(),
            close=hourly_data.iloc[-1]['close_price'],
            volume=hourly_data['Volume'].sum() if 'Volume' in hourly_data.columns else 0
        )
    
    def _calculate_enhanced_metrics(
        self,
        all_trades: List[BacktestTrade],
        daily_results: List[BacktestDailyResult],
        intraday_pnl: List[Tuple[datetime, float]],
        params: MLBacktestParameters
    ) -> Dict:
        """Calculate enhanced metrics including ML performance"""
        base_metrics = {
            'total_trades': len(all_trades),
            'winning_trades': len([t for t in all_trades if t.outcome == TradeOutcome.WIN]),
            'losing_trades': len([t for t in all_trades if t.outcome == TradeOutcome.LOSS])
        }
        
        # ML-specific metrics
        ml_metrics = {
            'ml_exit_trades': len([t for t in all_trades if 'ML Exit' in t.exit_reason]),
            'trailing_stop_trades': len([t for t in all_trades if 'Trailing' in t.exit_reason]),
            'target_hit_trades': len([t for t in all_trades if 'Target' in t.exit_reason]),
            'wednesday_exits': len([t for t in all_trades if t.exit_time and t.exit_time.weekday() == 2]),
            'partial_exits_count': sum(len(self.trade_lifecycle_data.get(t.id, {}).get('partial_exits', [])) for t in all_trades)
        }
        
        # Profit capture analysis
        profit_captures = []
        for trade in all_trades:
            if trade.id in self.trade_max_pnl and trade.total_pnl:
                capture_ratio = float(trade.total_pnl) / self.trade_max_pnl[trade.id] if self.trade_max_pnl[trade.id] > 0 else 0
                profit_captures.append(capture_ratio)
        
        ml_metrics['avg_profit_capture'] = sum(profit_captures) / len(profit_captures) if profit_captures else 0
        
        # Intraday volatility
        if intraday_pnl:
            pnl_values = [pnl for _, pnl in intraday_pnl]
            ml_metrics['intraday_volatility'] = pd.Series(pnl_values).std()
            ml_metrics['max_intraday_profit'] = max(pnl_values)
            ml_metrics['max_intraday_loss'] = min(pnl_values)
        
        return {**base_metrics, **ml_metrics, 'trades': all_trades, 'daily_results': daily_results}
    
    async def _save_lifecycle_data(self, backtest_run_id: str):
        """Save trade lifecycle analysis data"""
        with self.db_manager.get_session() as session:
            for trade_id, data in self.trade_lifecycle_data.items():
                # Create lifecycle analysis record
                query = """
                INSERT INTO TradeLifecycleAnalysis (
                    TradeId, MaxProfit, TimeToMaxProfitHours, 
                    ProfitCaptureRatio, PartialExitsCount
                ) VALUES (
                    :trade_id, :max_profit, :time_to_max,
                    :capture_ratio, :partial_count
                )
                """
                # [Execute query to save lifecycle data]
    
    async def _create_backtest_run(self, params: MLBacktestParameters) -> BacktestRun:
        """Create ML backtest run record"""
        backtest_run = BacktestRun(
            name=f"ML Backtest {params.from_date.date()} to {params.to_date.date()}",
            from_date=params.from_date,
            to_date=params.to_date,
            initial_capital=Decimal(str(params.initial_capital)),
            lot_size=params.lot_size,
            lots_to_trade=params.lots_to_trade,
            signals_to_test=",".join(params.signals_to_test),
            use_hedging=params.use_hedging,
            hedge_offset=params.hedge_offset,
            commission_per_lot=Decimal(str(params.commission_per_lot)),
            slippage_percent=Decimal(str(params.slippage_percent)),
            status=BacktestStatus.PENDING
        )
        
        with self.db_manager.get_session() as session:
            session.add(backtest_run)
            session.commit()
            session.refresh(backtest_run)
        
        return backtest_run
    
    async def _update_backtest_status(
        self,
        backtest_run_id: str,
        status: BacktestStatus,
        error_message: str = None
    ):
        """Update backtest run status"""
        with self.db_manager.get_session() as session:
            backtest_run = session.query(BacktestRun).filter_by(id=backtest_run_id).first()
            if backtest_run:
                backtest_run.status = status
                if error_message:
                    backtest_run.error_message = error_message
                session.commit()
    
    async def _update_backtest_results(self, backtest_run_id: str, results: Dict):
        """Update backtest with enhanced results"""
        with self.db_manager.get_session() as session:
            backtest_run = session.query(BacktestRun).filter_by(id=backtest_run_id).first()
            if backtest_run:
                # Update standard metrics
                backtest_run.total_trades = results['total_trades']
                backtest_run.winning_trades = results['winning_trades']
                backtest_run.losing_trades = results['losing_trades']
                
                # ML-specific metrics could be stored in a separate table if needed
                # For now, just log them
                logger.info(f"ML Metrics - Exits: {results.get('ml_exit_trades', 0)}, "
                           f"Trailing: {results.get('trailing_stop_trades', 0)}, "
                           f"Targets: {results.get('target_hit_trades', 0)}")
                
                session.commit()
    
    async def _create_trade_entry(
        self,
        signal_result,
        entry_time: datetime,
        index_price: float,
        params: MLBacktestParameters,
        backtest_run_id: str
    ) -> Optional[BacktestTrade]:
        """Create a new trade entry based on signal"""
        try:
            # Determine trade direction
            direction = "BULLISH" if signal_result.signal_type in ["S1", "S2", "S4", "S7"] else "BEARISH"
            
            # Calculate option strikes
            atm_strike = round(index_price / 100) * 100
            
            if direction == "BULLISH":
                # Sell PUT
                main_strike = atm_strike
                main_option_type = "PE"
            else:
                # Sell CALL
                main_strike = atm_strike
                main_option_type = "CE"
            
            # Calculate hedge strike if enabled
            hedge_strike = None
            hedge_option_type = None
            if params.use_hedging:
                hedge_strike = main_strike - params.hedge_offset if direction == "BULLISH" else main_strike + params.hedge_offset
                hedge_option_type = main_option_type
            
            # Get option prices
            main_price = await self.option_pricing.get_option_price(
                main_strike, main_option_type, entry_time
            )
            
            hedge_price = 0
            if hedge_strike:
                hedge_price = await self.option_pricing.get_option_price(
                    hedge_strike, hedge_option_type, entry_time
                )
            
            # Create trade record
            trade = BacktestTrade(
                backtest_run_id=backtest_run_id,
                signal_type=signal_result.signal_type,
                entry_time=entry_time,
                index_price_at_entry=Decimal(str(index_price)),
                direction=direction,
                stop_loss_price=Decimal(str(main_strike)),  # Use strike as stop loss
                outcome=TradeOutcome.OPEN
            )
            
            # Save trade to database
            with self.db_manager.get_session() as session:
                session.add(trade)
                session.commit()
                session.refresh(trade)
            
            # Create position records
            quantity = params.lots_to_trade * params.lot_size
            
            # Main position (SELL)
            main_position = BacktestPosition(
                trade_id=trade.id,
                position_type="MAIN",
                strike_price=main_strike,
                option_type=main_option_type,
                quantity=-quantity,  # Negative for sell
                entry_price=Decimal(str(main_price))
            )
            
            # Hedge position (BUY) if enabled
            if hedge_strike:
                hedge_position = BacktestPosition(
                    trade_id=trade.id,
                    position_type="HEDGE",
                    strike_price=hedge_strike,
                    option_type=hedge_option_type,
                    quantity=quantity,  # Positive for buy
                    entry_price=Decimal(str(hedge_price))
                )
                
                with self.db_manager.get_session() as session:
                    session.add(main_position)
                    session.add(hedge_position)
                    session.commit()
            else:
                with self.db_manager.get_session() as session:
                    session.add(main_position)
                    session.commit()
            
            logger.info(f"Created trade {trade.id}: {signal_result.signal_type} at {entry_time}, "
                       f"Main: {main_strike}{main_option_type}@{main_price:.2f}, "
                       f"Hedge: {hedge_strike}{hedge_option_type}@{hedge_price:.2f}" if hedge_strike else "")
            
            return trade
            
        except Exception as e:
            logger.error(f"Error creating trade entry: {e}")
            return None
    
    async def _close_trade(
        self,
        trade: BacktestTrade,
        exit_time: datetime,
        index_price: float,
        outcome: TradeOutcome,
        reason: str
    ) -> float:
        """Close a trade with ML tracking"""
        # Calculate final P&L
        final_pnl = await self._calculate_trade_pnl(trade, exit_time, index_price)
        
        # Update trade record
        trade.exit_time = exit_time
        trade.index_price_at_exit = Decimal(str(index_price))
        trade.outcome = outcome
        trade.exit_reason = reason
        trade.total_pnl = Decimal(str(final_pnl))
        
        # Record in lifecycle data
        if trade.id not in self.trade_lifecycle_data:
            self.trade_lifecycle_data[trade.id] = {}
        
        self.trade_lifecycle_data[trade.id].update({
            'exit_time': exit_time,
            'final_pnl': final_pnl,
            'max_pnl': self.trade_max_pnl.get(trade.id, final_pnl),
            'capture_ratio': final_pnl / self.trade_max_pnl[trade.id] if trade.id in self.trade_max_pnl and self.trade_max_pnl[trade.id] > 0 else 0,
            'exit_reason': reason
        })
        
        # Update in database
        with self.db_manager.get_session() as session:
            session.merge(trade)
            session.commit()
        
        logger.info(f"Closed trade {trade.id}: {outcome.value} - P&L: {final_pnl:.2f} - Reason: {reason}")
        return final_pnl