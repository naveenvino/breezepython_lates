"""
Market Classifier - Classifies NIFTY movements using hourly data
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pyodbc
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class MarketClassifier:
    """Classifies market movements and regimes"""
    
    def __init__(self):
        self.conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\mssqllocaldb;Database=KiteConnectApi;Trusted_Connection=yes;"
        
    def get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.conn_str)
    
    async def classify_all_trades(
        self,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """Classify market movement for all trades in period"""
        
        logger.info(f"Classifying market movements from {from_date} to {to_date}")
        
        results = []
        
        with self.get_connection() as conn:
            # Get all trades
            trades = self._get_trades(conn, from_date, to_date)
            
            for _, trade in trades.iterrows():
                classification = await self._classify_single_trade(conn, trade)
                results.append(classification)
        
        return results
    
    def _get_trades(self, conn, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        """Get all trades in the period"""
        query = """
        SELECT 
            Id as TradeId,
            SignalType,
            EntryTime,
            ExitTime,
            IndexPriceAtEntry,
            IndexPriceAtExit
        FROM BacktestTrades
        WHERE EntryTime >= ? AND EntryTime <= DATEADD(day, 1, ?)
        ORDER BY EntryTime
        """
        
        return pd.read_sql(query, conn, params=[from_date, to_date])
    
    async def _classify_single_trade(self, conn, trade: pd.Series) -> Dict[str, Any]:
        """Classify market movement for a single trade"""
        
        # Get hourly NIFTY data
        hourly_data = self._get_hourly_nifty_data(
            conn,
            trade['EntryTime'],
            trade['ExitTime']
        )
        
        if hourly_data.empty:
            return {
                "trade_id": trade['TradeId'],
                "signal_type": trade['SignalType'],
                "classification": "NO_DATA"
            }
        
        # Calculate metrics
        entry_price = hourly_data.iloc[0]['open']
        exit_price = hourly_data.iloc[-1]['close']
        high_price = hourly_data['high'].max()
        low_price = hourly_data['low'].min()
        
        # Find when high and low occurred
        high_idx = hourly_data['high'].idxmax()
        low_idx = hourly_data['low'].idxmin()
        high_time = hourly_data.loc[high_idx, 'timestamp']
        low_time = hourly_data.loc[low_idx, 'timestamp']
        
        # Calculate movements
        total_range = high_price - low_price
        directional_move = exit_price - entry_price
        net_move_pct = (directional_move / entry_price) * 100
        
        # Calculate volatility metrics
        returns = hourly_data['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252 * 6.5)  # Annualized, 6.5 trading hours
        
        # Calculate ATR (Average True Range)
        atr = self._calculate_atr(hourly_data)
        
        # Calculate ADX (Average Directional Index)
        adx = self._calculate_adx(hourly_data)
        
        # Classify trend
        trend_classification = self._classify_trend(
            directional_move,
            total_range,
            adx,
            volatility
        )
        
        # Classify volatility regime
        volatility_regime = self._classify_volatility(volatility, atr)
        
        # Build hourly path for detailed analysis
        hourly_path = []
        for _, row in hourly_data.iterrows():
            hourly_path.append({
                "hour": row['timestamp'].strftime("%Y-%m-%d %H:%M"),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": int(row['volume']) if row['volume'] else 0
            })
        
        return {
            "trade_id": trade['TradeId'],
            "signal_type": trade['SignalType'],
            "entry_time": trade['EntryTime'],
            "exit_time": trade['ExitTime'],
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "high_price": float(high_price),
            "high_time": high_time,
            "low_price": float(low_price),
            "low_time": low_time,
            "total_movement": float(total_range),
            "directional_move": float(directional_move),
            "net_move_pct": float(net_move_pct),
            "trend_classification": trend_classification,
            "volatility_regime": volatility_regime,
            "atr": float(atr),
            "adx": float(adx),
            "volatility": float(volatility),
            "hourly_path": hourly_path
        }
    
    def _get_hourly_nifty_data(self, conn, entry_time: datetime, exit_time: datetime) -> pd.DataFrame:
        """Get hourly NIFTY data between entry and exit"""
        query = """
        SELECT 
            timestamp,
            [open],
            [high],
            [low],
            [close],
            volume
        FROM NiftyIndexDataHourly
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp
        """
        
        df = pd.read_sql(query, conn, params=[entry_time, exit_time])
        
        # If no hourly data, try 5-minute and aggregate
        if df.empty:
            query_5min = """
            SELECT 
                DATEADD(hour, DATEDIFF(hour, 0, timestamp), 0) as timestamp,
                MIN([open]) as first_open,
                MAX([high]) as high,
                MIN([low]) as low,
                MAX([close]) as last_close,
                SUM(volume) as volume
            FROM NiftyIndexData5Minute
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY DATEADD(hour, DATEDIFF(hour, 0, timestamp), 0)
            ORDER BY timestamp
            """
            
            df = pd.read_sql(query_5min, conn, params=[entry_time, exit_time])
            if not df.empty:
                df['open'] = df['first_open']
                df['close'] = df['last_close']
        
        return df
    
    def _calculate_atr(self, hourly_data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(hourly_data) < 2:
            return 0
        
        high = hourly_data['high'].values
        low = hourly_data['low'].values
        close = hourly_data['close'].values
        
        # True Range calculation
        tr = np.zeros(len(hourly_data))
        tr[0] = high[0] - low[0]
        
        for i in range(1, len(hourly_data)):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i-1])
            lc = abs(low[i] - close[i-1])
            tr[i] = max(hl, hc, lc)
        
        # ATR is average of True Range
        if len(tr) >= period:
            atr = np.mean(tr[-period:])
        else:
            atr = np.mean(tr)
        
        return atr
    
    def _calculate_adx(self, hourly_data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index"""
        if len(hourly_data) < period + 1:
            return 0
        
        high = hourly_data['high'].values
        low = hourly_data['low'].values
        close = hourly_data['close'].values
        
        # Calculate +DM and -DM
        plus_dm = np.zeros(len(hourly_data))
        minus_dm = np.zeros(len(hourly_data))
        
        for i in range(1, len(hourly_data)):
            up_move = high[i] - high[i-1]
            down_move = low[i-1] - low[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
        
        # Calculate ATR
        atr = self._calculate_atr(hourly_data, period)
        
        if atr == 0:
            return 0
        
        # Calculate +DI and -DI
        plus_di = 100 * (np.mean(plus_dm[-period:]) / atr)
        minus_di = 100 * (np.mean(minus_dm[-period:]) / atr)
        
        # Calculate DX and ADX
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 0
        
        dx = 100 * abs(plus_di - minus_di) / di_sum
        
        # ADX is smoothed DX (we'll use simple average for last period)
        adx = dx  # Simplified - normally would be smoothed
        
        return adx
    
    def _classify_trend(
        self,
        directional_move: float,
        total_range: float,
        adx: float,
        volatility: float
    ) -> str:
        """Classify the trend based on multiple factors"""
        
        # Calculate directional ratio
        if total_range == 0:
            directional_ratio = 0
        else:
            directional_ratio = abs(directional_move) / total_range
        
        # Strong trend criteria
        if adx > 25:
            if directional_move > 0:
                if directional_ratio > 0.6:
                    return "STRONG_UP"
                else:
                    return "WEAK_UP"
            else:
                if directional_ratio > 0.6:
                    return "STRONG_DOWN"
                else:
                    return "WEAK_DOWN"
        
        # Sideways market
        if adx < 20 and directional_ratio < 0.3:
            return "SIDEWAYS"
        
        # Mixed signals
        if directional_move > 0:
            return "WEAK_UP"
        elif directional_move < 0:
            return "WEAK_DOWN"
        else:
            return "SIDEWAYS"
    
    def _classify_volatility(self, volatility: float, atr: float) -> str:
        """Classify volatility regime"""
        
        # Historical NIFTY volatility benchmarks
        # Low: < 15%, Medium: 15-25%, High: > 25%
        
        if volatility < 0.15:
            return "LOW"
        elif volatility < 0.25:
            return "MEDIUM"
        else:
            return "HIGH"
    
    async def store_market_classification(
        self,
        validation_run_id: str,
        classifications: List[Dict]
    ):
        """Store market classification results in database"""
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for classification in classifications:
                cursor.execute("""
                    INSERT INTO MLMarketRegime
                    (ValidationRunId, TradeId, SignalType, EntryTime, ExitTime,
                     EntryNiftyPrice, ExitNiftyPrice, HighPrice, HighTime,
                     LowPrice, LowTime, TotalMovement, DirectionalMove,
                     TrendClassification, VolatilityRegime, ATR, ADX,
                     HourlyPath)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, 
                    validation_run_id,
                    classification['trade_id'],
                    classification['signal_type'],
                    classification['entry_time'],
                    classification['exit_time'],
                    classification['entry_price'],
                    classification['exit_price'],
                    classification['high_price'],
                    classification['high_time'],
                    classification['low_price'],
                    classification['low_time'],
                    classification['total_movement'],
                    classification['directional_move'],
                    classification['trend_classification'],
                    classification['volatility_regime'],
                    classification['atr'],
                    classification['adx'],
                    str(classification['hourly_path'])
                )
            
            conn.commit()
            logger.info(f"Stored market classification for {len(classifications)} trades")