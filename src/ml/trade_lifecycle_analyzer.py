"""
Trade Lifecycle Analyzer
Analyzes the complete lifecycle of trades using 5-minute options data
to identify optimal exit points and profit patterns
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import json

logger = logging.getLogger(__name__)

@dataclass
class TradeLifecycleMetrics:
    """Metrics for a trade's complete lifecycle"""
    trade_id: int
    signal_type: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    
    # P&L progression metrics
    max_profit: float
    max_profit_time: datetime
    time_to_max_profit_hours: float
    max_drawdown: float
    max_drawdown_time: datetime
    
    # Profit capture efficiency
    final_pnl: float
    profit_capture_ratio: float  # final_pnl / max_profit
    profit_decay_from_peak: float  # (max_profit - final_pnl) / max_profit
    
    # Time-based analysis
    profitable_duration_pct: float  # % of time trade was profitable
    best_exit_day: str  # Mon, Tue, Wed, Thu
    best_exit_hour: int
    
    # Volatility during trade
    avg_5min_volatility: float
    max_5min_move: float
    
    # Greeks progression (if available)
    max_delta_exposure: float
    avg_theta_collected: float
    vega_risk_encountered: float
    
    # Intraday patterns
    intraday_profit_curve: List[float]  # Hourly P&L snapshots
    reversal_points: List[Tuple[datetime, float]]  # Times when P&L reversed
    
    # Risk metrics
    stop_loss_distance_pct: float
    times_near_stop_loss: int
    min_distance_to_stop_pct: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'trade_id': self.trade_id,
            'signal_type': self.signal_type,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'max_profit': self.max_profit,
            'max_profit_time': self.max_profit_time.isoformat() if self.max_profit_time else None,
            'time_to_max_profit_hours': self.time_to_max_profit_hours,
            'max_drawdown': self.max_drawdown,
            'final_pnl': self.final_pnl,
            'profit_capture_ratio': self.profit_capture_ratio,
            'profit_decay_from_peak': self.profit_decay_from_peak,
            'profitable_duration_pct': self.profitable_duration_pct,
            'best_exit_day': self.best_exit_day,
            'best_exit_hour': self.best_exit_hour,
            'avg_5min_volatility': self.avg_5min_volatility,
            'max_delta_exposure': self.max_delta_exposure,
            'avg_theta_collected': self.avg_theta_collected,
            'stop_loss_distance_pct': self.stop_loss_distance_pct,
            'times_near_stop_loss': self.times_near_stop_loss
        }

class TradeLifecycleAnalyzer:
    """Analyzes complete lifecycle of trades using 5-minute data"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize analyzer with database connection
        
        Args:
            db_connection_string: Database connection string
        """
        self.engine = create_engine(db_connection_string)
        
    def analyze_trade_lifecycle(self, 
                               trade_id: int,
                               granularity_minutes: int = 5) -> Optional[TradeLifecycleMetrics]:
        """
        Analyze complete lifecycle of a single trade
        
        Args:
            trade_id: ID of the trade to analyze
            granularity_minutes: Data granularity (default 5 minutes)
            
        Returns:
            TradeLifecycleMetrics object with complete analysis
        """
        # Get trade details
        trade_query = """
        SELECT 
            bt.Id,
            bt.SignalType,
            bt.EntryTime,
            bt.ExitTime,
            bt.IndexPriceAtEntry,
            bt.IndexPriceAtExit,
            bt.TotalPnL,
            bt.StopLossPrice,
            bt.Direction,
            bp_main.Strike as MainStrike,
            bp_main.OptionType as MainOptionType,
            bp_main.Quantity as MainQuantity,
            bp_main.EntryPrice as MainEntryPrice,
            bp_hedge.Strike as HedgeStrike,
            bp_hedge.OptionType as HedgeOptionType,
            bp_hedge.Quantity as HedgeQuantity,
            bp_hedge.EntryPrice as HedgeEntryPrice
        FROM BacktestTrades bt
        LEFT JOIN BacktestPositions bp_main ON bt.Id = bp_main.TradeId AND bp_main.PositionType = 'Main'
        LEFT JOIN BacktestPositions bp_hedge ON bt.Id = bp_hedge.TradeId AND bp_hedge.PositionType = 'Hedge'
        WHERE bt.Id = :trade_id
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(trade_query), {'trade_id': trade_id})
            trade = result.fetchone()
            
            if not trade:
                logger.warning(f"Trade {trade_id} not found")
                return None
                
            # Get 5-minute options data for the trade period
            options_query = """
            SELECT 
                Timestamp,
                Strike,
                OptionType,
                Close as Price,
                Volume,
                OpenInterest,
                ImpliedVolatility,
                Delta,
                Gamma,
                Theta,
                Vega,
                BidPrice,
                AskPrice
            FROM OptionsData
            WHERE Strike IN (:main_strike, :hedge_strike)
                AND OptionType IN (:main_type, :hedge_type)
                AND Timestamp >= :entry_time
                AND Timestamp <= :exit_time
                AND DATEPART(MINUTE, Timestamp) % :granularity = 0
            ORDER BY Timestamp
            """
            
            params = {
                'main_strike': trade.MainStrike,
                'hedge_strike': trade.HedgeStrike if trade.HedgeStrike else trade.MainStrike,
                'main_type': trade.MainOptionType,
                'hedge_type': trade.HedgeOptionType if trade.HedgeOptionType else trade.MainOptionType,
                'entry_time': trade.EntryTime,
                'exit_time': trade.ExitTime,
                'granularity': granularity_minutes
            }
            
            df_options = pd.read_sql(text(options_query), conn, params=params)
            
            if df_options.empty:
                logger.warning(f"No options data found for trade {trade_id}")
                return None
                
        # Calculate P&L at each 5-minute interval
        pnl_series = self._calculate_pnl_series(df_options, trade)
        
        # Analyze the P&L series
        metrics = self._analyze_pnl_series(pnl_series, trade)
        
        # Add Greeks analysis
        greeks_metrics = self._analyze_greeks_progression(df_options, trade)
        metrics.update(greeks_metrics)
        
        # Add volatility analysis
        volatility_metrics = self._analyze_volatility(df_options, pnl_series)
        metrics.update(volatility_metrics)
        
        return TradeLifecycleMetrics(
            trade_id=trade.Id,
            signal_type=trade.SignalType,
            entry_time=trade.EntryTime,
            exit_time=trade.ExitTime,
            entry_price=float(trade.IndexPriceAtEntry),
            exit_price=float(trade.IndexPriceAtExit),
            final_pnl=float(trade.TotalPnL),
            **metrics
        )
    
    def _calculate_pnl_series(self, 
                             df_options: pd.DataFrame,
                             trade) -> pd.Series:
        """
        Calculate P&L at each timestamp
        
        Args:
            df_options: Options data DataFrame
            trade: Trade record
            
        Returns:
            Series with timestamp index and P&L values
        """
        pnl_data = []
        
        # Group by timestamp
        for timestamp, group in df_options.groupby('Timestamp'):
            main_data = group[(group['Strike'] == trade.MainStrike) & 
                            (group['OptionType'] == trade.MainOptionType)]
            
            if main_data.empty:
                continue
                
            main_price = main_data['Price'].iloc[0]
            
            # Calculate main position P&L (sold option)
            main_pnl = (float(trade.MainEntryPrice) - main_price) * trade.MainQuantity
            
            # Add hedge P&L if exists
            hedge_pnl = 0
            if trade.HedgeStrike:
                hedge_data = group[(group['Strike'] == trade.HedgeStrike) & 
                                 (group['OptionType'] == trade.HedgeOptionType)]
                if not hedge_data.empty:
                    hedge_price = hedge_data['Price'].iloc[0]
                    # Hedge is bought option
                    hedge_pnl = (hedge_price - float(trade.HedgeEntryPrice)) * trade.HedgeQuantity
            
            total_pnl = main_pnl + hedge_pnl
            pnl_data.append({'timestamp': timestamp, 'pnl': total_pnl})
        
        df_pnl = pd.DataFrame(pnl_data)
        if not df_pnl.empty:
            df_pnl.set_index('timestamp', inplace=True)
            return df_pnl['pnl']
        else:
            return pd.Series()
    
    def _analyze_pnl_series(self, 
                           pnl_series: pd.Series,
                           trade) -> Dict:
        """
        Analyze P&L series to extract key metrics
        
        Args:
            pnl_series: Time series of P&L values
            trade: Trade record
            
        Returns:
            Dictionary of metrics
        """
        if pnl_series.empty:
            return {}
            
        # Find maximum profit point
        max_profit = pnl_series.max()
        max_profit_idx = pnl_series.idxmax()
        time_to_max_profit = (max_profit_idx - trade.EntryTime).total_seconds() / 3600
        
        # Find maximum drawdown
        cummax = pnl_series.cummax()
        drawdown = pnl_series - cummax
        max_drawdown = drawdown.min()
        max_drawdown_idx = drawdown.idxmin()
        
        # Profit capture efficiency
        final_pnl = pnl_series.iloc[-1]
        profit_capture_ratio = final_pnl / max_profit if max_profit > 0 else 0
        profit_decay = (max_profit - final_pnl) / max_profit if max_profit > 0 else 0
        
        # Time spent profitable
        profitable_periods = (pnl_series > 0).sum()
        total_periods = len(pnl_series)
        profitable_duration_pct = profitable_periods / total_periods if total_periods > 0 else 0
        
        # Best exit time analysis
        best_exit_idx = pnl_series.idxmax()
        best_exit_day = best_exit_idx.strftime('%A')
        best_exit_hour = best_exit_idx.hour
        
        # Reversal points (where P&L direction changes)
        pnl_diff = pnl_series.diff()
        sign_changes = np.sign(pnl_diff).diff().fillna(0) != 0
        reversal_points = [(idx, pnl_series[idx]) for idx in pnl_series[sign_changes].index]
        
        # Stop loss analysis
        stop_loss_price = float(trade.StopLossPrice) if trade.StopLossPrice else 0
        if stop_loss_price > 0:
            # For sold options, loss occurs when price goes above entry
            if trade.Direction == 'BEARISH':  # Sold CALL
                stop_loss_pnl = (float(trade.MainEntryPrice) - stop_loss_price) * trade.MainQuantity
            else:  # Sold PUT
                stop_loss_pnl = (float(trade.MainEntryPrice) - stop_loss_price) * trade.MainQuantity
                
            # Count times near stop loss (within 20% of stop loss distance)
            stop_distance = abs(stop_loss_pnl)
            near_stop = (pnl_series < -0.8 * stop_distance).sum()
            min_distance_to_stop = abs(pnl_series.min() / stop_loss_pnl) if stop_loss_pnl != 0 else 1
        else:
            near_stop = 0
            min_distance_to_stop = 1
            stop_distance = 0
        
        # Hourly P&L snapshots
        hourly_pnl = pnl_series.resample('1H').last().fillna(method='ffill').tolist()
        
        return {
            'max_profit': max_profit,
            'max_profit_time': max_profit_idx,
            'time_to_max_profit_hours': time_to_max_profit,
            'max_drawdown': max_drawdown,
            'max_drawdown_time': max_drawdown_idx,
            'profit_capture_ratio': profit_capture_ratio,
            'profit_decay_from_peak': profit_decay,
            'profitable_duration_pct': profitable_duration_pct,
            'best_exit_day': best_exit_day,
            'best_exit_hour': best_exit_hour,
            'intraday_profit_curve': hourly_pnl,
            'reversal_points': reversal_points[:5],  # Keep top 5 reversals
            'stop_loss_distance_pct': stop_distance / abs(float(trade.MainEntryPrice) * trade.MainQuantity) if trade.MainEntryPrice else 0,
            'times_near_stop_loss': near_stop,
            'min_distance_to_stop_pct': min_distance_to_stop
        }
    
    def _analyze_greeks_progression(self, 
                                   df_options: pd.DataFrame,
                                   trade) -> Dict:
        """
        Analyze Greeks progression during trade
        
        Args:
            df_options: Options data with Greeks
            trade: Trade record
            
        Returns:
            Dictionary of Greeks metrics
        """
        # Filter for main position
        main_options = df_options[(df_options['Strike'] == trade.MainStrike) & 
                                 (df_options['OptionType'] == trade.MainOptionType)]
        
        if main_options.empty:
            return {
                'max_delta_exposure': 0,
                'avg_theta_collected': 0,
                'vega_risk_encountered': 0
            }
        
        # Delta exposure (absolute max)
        max_delta = main_options['Delta'].abs().max() * trade.MainQuantity
        
        # Average theta collected (positive for sold options)
        avg_theta = main_options['Theta'].mean() * trade.MainQuantity
        
        # Vega risk (max vega exposure)
        max_vega = main_options['Vega'].abs().max() * trade.MainQuantity
        
        return {
            'max_delta_exposure': max_delta,
            'avg_theta_collected': abs(avg_theta),  # Positive value for collection
            'vega_risk_encountered': max_vega
        }
    
    def _analyze_volatility(self, 
                           df_options: pd.DataFrame,
                           pnl_series: pd.Series) -> Dict:
        """
        Analyze volatility metrics during trade
        
        Args:
            df_options: Options data
            pnl_series: P&L time series
            
        Returns:
            Dictionary of volatility metrics
        """
        if pnl_series.empty:
            return {
                'avg_5min_volatility': 0,
                'max_5min_move': 0
            }
        
        # Calculate 5-minute P&L changes
        pnl_changes = pnl_series.diff()
        
        # Average 5-minute volatility (standard deviation of changes)
        avg_volatility = pnl_changes.std()
        
        # Maximum 5-minute move
        max_move = pnl_changes.abs().max()
        
        return {
            'avg_5min_volatility': avg_volatility,
            'max_5min_move': max_move
        }
    
    def analyze_all_trades(self, 
                          from_date: datetime,
                          to_date: datetime) -> pd.DataFrame:
        """
        Analyze lifecycle of all trades in date range
        
        Args:
            from_date: Start date
            to_date: End date
            
        Returns:
            DataFrame with lifecycle metrics for all trades
        """
        # Get all trades in date range
        query = """
        SELECT Id
        FROM BacktestTrades
        WHERE EntryTime >= :from_date
            AND EntryTime <= :to_date
        ORDER BY EntryTime
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(query), {
                'from_date': from_date,
                'to_date': to_date
            })
            trade_ids = [row[0] for row in result]
        
        logger.info(f"Analyzing {len(trade_ids)} trades")
        
        # Analyze each trade
        metrics_list = []
        for trade_id in trade_ids:
            try:
                metrics = self.analyze_trade_lifecycle(trade_id)
                if metrics:
                    metrics_list.append(metrics.to_dict())
            except Exception as e:
                logger.error(f"Error analyzing trade {trade_id}: {e}")
                continue
        
        # Convert to DataFrame
        df_metrics = pd.DataFrame(metrics_list)
        
        return df_metrics
    
    def get_optimal_exit_rules(self, 
                              signal_type: str = None) -> Dict:
        """
        Derive optimal exit rules from historical analysis
        
        Args:
            signal_type: Specific signal to analyze (None for all)
            
        Returns:
            Dictionary with optimal exit rules
        """
        # Get all analyzed trades
        query = """
        SELECT 
            SignalType,
            AVG(DATEDIFF(hour, EntryTime, ExitTime)) as AvgHoldingHours,
            AVG(TotalPnL) as AvgPnL
        FROM BacktestTrades
        WHERE TotalPnL IS NOT NULL
        """
        
        if signal_type:
            query += f" AND SignalType = '{signal_type}'"
            
        query += " GROUP BY SignalType"
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        
        optimal_rules = {}
        
        for _, row in df.iterrows():
            signal = row['SignalType']
            
            # Derive rules based on analysis
            # These would be enhanced with the lifecycle metrics
            optimal_rules[signal] = {
                'optimal_holding_hours': row['AvgHoldingHours'],
                'target_profit': row['AvgPnL'] * 1.2,  # 20% above average
                'stop_loss_multiplier': 1.5,  # 1.5x premium received
                'trailing_stop_pct': 0.25,  # Trail by 25% of profit
                'wednesday_exit_threshold': 0.7,  # Exit if 70% of target reached by Wed
                'breakeven_move_threshold': 0.5,  # Move to breakeven after 50% of target
                'recommended_exit_times': {
                    'Monday': None,  # Hold
                    'Tuesday': 0.5,  # Exit 50% if profitable
                    'Wednesday': 0.75,  # Exit 75% by Wed close
                    'Thursday': 1.0  # Full exit before expiry
                }
            }
        
        return optimal_rules
    
    def save_analysis_results(self, 
                             df_metrics: pd.DataFrame,
                             output_path: str = None):
        """
        Save lifecycle analysis results
        
        Args:
            df_metrics: DataFrame with lifecycle metrics
            output_path: Optional file path for export
        """
        # Save to database
        try:
            with self.engine.begin() as conn:
                # Check if table exists
                check_query = """
                IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES 
                              WHERE TABLE_NAME = 'TradeLifecycleAnalysis')
                BEGIN
                    CREATE TABLE TradeLifecycleAnalysis (
                        Id INT IDENTITY(1,1) PRIMARY KEY,
                        TradeId INT,
                        SignalType NVARCHAR(10),
                        MaxProfit DECIMAL(18,2),
                        TimeToMaxProfitHours DECIMAL(10,2),
                        ProfitCaptureRatio DECIMAL(5,2),
                        ProfitDecayFromPeak DECIMAL(5,2),
                        BestExitDay NVARCHAR(20),
                        BestExitHour INT,
                        MaxDeltaExposure DECIMAL(10,4),
                        AvgThetaCollected DECIMAL(10,2),
                        AnalysisDate DATETIME DEFAULT GETDATE(),
                        MetricsJson NVARCHAR(MAX)
                    )
                END
                """
                conn.execute(text(check_query))
                
                # Insert metrics
                for _, row in df_metrics.iterrows():
                    insert_query = """
                    INSERT INTO TradeLifecycleAnalysis (
                        TradeId, SignalType, MaxProfit, TimeToMaxProfitHours,
                        ProfitCaptureRatio, ProfitDecayFromPeak, BestExitDay,
                        BestExitHour, MaxDeltaExposure, AvgThetaCollected,
                        MetricsJson
                    ) VALUES (
                        :trade_id, :signal_type, :max_profit, :time_to_max,
                        :capture_ratio, :decay, :best_day, :best_hour,
                        :max_delta, :avg_theta, :metrics_json
                    )
                    """
                    
                    conn.execute(text(insert_query), {
                        'trade_id': row.get('trade_id'),
                        'signal_type': row.get('signal_type'),
                        'max_profit': row.get('max_profit', 0),
                        'time_to_max': row.get('time_to_max_profit_hours', 0),
                        'capture_ratio': row.get('profit_capture_ratio', 0),
                        'decay': row.get('profit_decay_from_peak', 0),
                        'best_day': row.get('best_exit_day', ''),
                        'best_hour': row.get('best_exit_hour', 0),
                        'max_delta': row.get('max_delta_exposure', 0),
                        'avg_theta': row.get('avg_theta_collected', 0),
                        'metrics_json': json.dumps(row.to_dict())
                    })
                    
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
        
        # Save to file if specified
        if output_path:
            df_metrics.to_csv(output_path, index=False)
            logger.info(f"Analysis saved to {output_path}")