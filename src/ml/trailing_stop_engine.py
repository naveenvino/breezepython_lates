import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
from enum import Enum

class TrailingStopType(Enum):
    FIXED = 'fixed'
    PERCENTAGE = 'percentage'

class TrailingStopEngine:
    def __init__(self, db_connection_string):
        self.engine = create_engine(db_connection_string)

    def analyze_trailing_stop_loss(self):
        """
        Analyzes the effectiveness of different trailing stop-loss strategies.
        """
        print("Starting trailing stop-loss analysis...")

        # Fetch trade data from the database
        query = """
        SELECT
            SignalType AS signal_type,
            WeeklyOutcome AS outcome,
            StopLossHit AS stoploss_hit,
            EntryPrice AS entry_price,
            StopLossPrice AS stoploss_price
        FROM SignalAnalysis
        WHERE WeeklyOutcome IN ('WIN', 'LOSS') AND EntryPrice IS NOT NULL AND StopLossPrice IS NOT NULL
        """
        try:
            trades_df = pd.read_sql(query, self.engine)
            print(f"Successfully fetched {len(trades_df)} trades from the database.")
        except Exception as e:
            print(f"Error fetching data from the database: {e}")
            return

        if trades_df.empty:
            print("No trade data found for analysis.")
            return

        # Define trailing stop-loss percentages to test
        trailing_percentages = [0.1, 0.2, 0.3]

        results = {}
        for signal in sorted(trades_df['signal_type'].unique()):
            results[signal] = {}
            signal_df = trades_df[trades_df['signal_type'] == signal]

            for percentage in trailing_percentages:
                simulated_pnl = []
                for index, trade in signal_df.iterrows():
                    # Simplified simulation
                    if trade['outcome'] == 'WIN':
                        # Assume the trade moved in our favor
                        # and the trailing stop was hit at some point.
                        # This is a major simplification due to lack of price data.
                        simulated_pnl.append(trade['entry_price'] * percentage)
                    else: # LOSS
                        simulated_pnl.append(trade['entry_price'] - trade['stoploss_price'])

                results[signal][percentage] = {
                    "average_pnl": sum(simulated_pnl) / len(simulated_pnl) if simulated_pnl else 0
                }

        print("\n--- Trailing Stop-Loss Analysis Results (Simplified) ---")
        for signal, percentages in results.items():
            print(f"\nSignal: {signal}")
            for percentage, data in percentages.items():
                print(f"  Trailing SL Percentage: {percentage * 100:.0f}%")
                print(f"    Average Simulated PnL: {data['average_pnl']:.2f}")

            if percentages:
                best_percentage = max(percentages, key=lambda p: percentages[p]['average_pnl'])
                print(f"\n  Best Trailing SL for {signal}: {best_percentage * 100:.0f}% (based on simplified PnL)")

    def update_trailing_stop(self, trade_id, signal_type, current_pnl, max_pnl, current_price, entry_price, entry_time, current_volatility):
        """
        Update trailing stop loss based on market conditions and trade performance
        """
        try:
            # Calculate percentage gain
            pnl_percentage = (current_pnl / entry_price) * 100 if entry_price > 0 else 0
            max_pnl_percentage = (max_pnl / entry_price) * 100 if entry_price > 0 else 0
            
            # Calculate time elapsed since entry
            if isinstance(entry_time, str):
                from datetime import datetime
                entry_datetime = datetime.fromisoformat(entry_time)
            else:
                entry_datetime = entry_time
            
            time_elapsed = datetime.now() - entry_datetime
            hours_elapsed = time_elapsed.total_seconds() / 3600
            
            # Dynamic trailing stop based on volatility and time
            # Higher volatility = wider stops, longer time = tighter stops
            base_trailing_percentage = 0.2  # 20% base trailing stop
            
            # Adjust for volatility
            volatility_adjustment = (current_volatility / 20.0) * 0.1  # Scale by expected VIX range
            adjusted_trailing_percentage = base_trailing_percentage + volatility_adjustment
            
            # Time-based adjustment - tighten stops as day progresses
            if hours_elapsed > 4:  # After 4 hours, tighten stops
                adjusted_trailing_percentage *= 0.8
            elif hours_elapsed > 6:  # After 6 hours, tighten further
                adjusted_trailing_percentage *= 0.6
            
            # Calculate trailing stop level
            trailing_stop_amount = max_pnl * adjusted_trailing_percentage
            stop_level = max_pnl - trailing_stop_amount
            
            # Check if stop is triggered
            triggered = current_pnl <= stop_level
            
            # Determine trigger reason
            trigger_reason = None
            if triggered:
                if pnl_percentage < -50:  # Major loss
                    trigger_reason = "MAJOR_LOSS_PROTECTION"
                elif max_pnl_percentage > 30 and (max_pnl - current_pnl) / max_pnl > 0.3:
                    trigger_reason = "PROFIT_PROTECTION"
                elif hours_elapsed > 5 and pnl_percentage < 0:
                    trigger_reason = "TIME_DECAY_PROTECTION"
                else:
                    trigger_reason = "TRAILING_STOP_HIT"
            
            # Generate recommendation
            recommendation = "EXIT_POSITION" if triggered else "CONTINUE_HOLDING"
            
            # Additional recommendations based on conditions
            if not triggered:
                if pnl_percentage > 50:  # Significant profit
                    recommendation = "CONSIDER_PARTIAL_EXIT"
                elif hours_elapsed > 6 and pnl_percentage > 0:
                    recommendation = "MONITOR_CLOSELY"
                elif current_volatility > 25:  # High volatility
                    recommendation = "TIGHTEN_STOP"
            
            return {
                "trade_id": trade_id,
                "stop_level": round(stop_level, 2),
                "triggered": triggered,
                "trigger_reason": trigger_reason,
                "recommendation": recommendation,
                "analysis": {
                    "pnl_percentage": round(pnl_percentage, 2),
                    "max_pnl_percentage": round(max_pnl_percentage, 2),
                    "hours_elapsed": round(hours_elapsed, 1),
                    "trailing_percentage": round(adjusted_trailing_percentage * 100, 1),
                    "current_volatility": current_volatility
                }
            }
            
        except Exception as e:
            # Fallback to conservative approach on error
            return {
                "trade_id": trade_id,
                "stop_level": entry_price * 0.9,  # 10% stop loss as fallback
                "triggered": current_pnl < (entry_price * 0.9),
                "trigger_reason": "ERROR_FALLBACK" if current_pnl < (entry_price * 0.9) else None,
                "recommendation": "EXIT_POSITION" if current_pnl < (entry_price * 0.9) else "CONTINUE_HOLDING",
                "error": str(e)
            }

if __name__ == '__main__':
    # Load environment variables
    load_dotenv()

    # Database connection
    DB_SERVER = os.getenv("DB_SERVER")
    DB_NAME = os.getenv("DB_NAME")

    # Connection string
    conn_str = f"mssql+pyodbc://{DB_SERVER}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
    
    engine = TrailingStopEngine(conn_str)
    engine.analyze_trailing_stop_loss()