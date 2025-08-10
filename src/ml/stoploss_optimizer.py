import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

class StopLossOptimizer:
    def __init__(self, db_connection_string):
        self.engine = create_engine(db_connection_string)

    def analyze_stoploss_levels(self):
        """
        Analyzes the optimal overall stop-loss level for each signal.
        """
        print("Starting stop-loss level analysis...")

        # Fetch trade data from the database
        query = """
        SELECT
            SignalType AS signal_type,
            WeeklyOutcome AS outcome,
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

        # Define stop-loss multipliers to test
        sl_multipliers = [0.5, 1.0, 1.5, 2.0]

        results = {}
        for signal in sorted(trades_df['signal_type'].unique()):
            results[signal] = {}
            signal_df = trades_df[trades_df['signal_type'] == signal]

            for multiplier in sl_multipliers:
                simulated_pnl = []
                for index, trade in signal_df.iterrows():
                    original_sl_delta = abs(trade['entry_price'] - trade['stoploss_price'])
                    new_sl_price = trade['entry_price'] - (original_sl_delta * multiplier)

                    # Simplified simulation
                    if trade['outcome'] == 'WIN':
                        # Assume win, but a tighter SL might have turned it into a loss
                        # This is a major simplification
                        simulated_pnl.append(1) # Assume a win is a win
                    else: # LOSS
                        # If the new SL is wider, it might have been a win
                        # Again, a major simplification
                        if multiplier > 1.0:
                            simulated_pnl.append(1) # Hypothetically a win
                        else:
                            simulated_pnl.append(-1) # Still a loss

                results[signal][multiplier] = {
                    "average_pnl": sum(simulated_pnl) / len(simulated_pnl) if simulated_pnl else 0
                }

        print("\n--- Stop-Loss Level Analysis Results (Simplified) ---")
        for signal, multipliers in results.items():
            print(f"\nSignal: {signal}")
            for multiplier, data in multipliers.items():
                print(f"  Stop-Loss Multiplier: {multiplier}")
                print(f"    Average Simulated PnL: {data['average_pnl']:.2f}")

            if multipliers:
                best_multiplier = max(multipliers, key=lambda m: multipliers[m]['average_pnl'])
                print(f"\n  Best Stop-Loss Multiplier for {signal}: {best_multiplier} (based on simplified PnL)")

    def optimize_all_strategies(self, from_date, to_date):
        # This is a placeholder for the actual optimization logic.
        # For now, it will just call the analyze_stoploss_levels method.
        self.analyze_stoploss_levels()
        return {}

if __name__ == '__main__':
    # Load environment variables
    load_dotenv()

    # Database connection
    DB_SERVER = os.getenv("DB_SERVER")
    DB_NAME = os.getenv("DB_NAME")

    # Connection string
    conn_str = f"mssql+pyodbc://{DB_SERVER}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
    
    optimizer = StopLossOptimizer(conn_str)
    optimizer.analyze_stoploss_levels()