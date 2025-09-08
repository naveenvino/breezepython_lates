"""Add missing columns for weekday config and exit timing to TradeConfiguration table"""
import sqlite3
import json
import os

def add_missing_columns():
    db_path = 'data/trading_settings.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    print("Adding missing columns to TradeConfiguration table...")
    print("="*60)
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Get current columns
            cursor.execute("PRAGMA table_info(TradeConfiguration)")
            columns = cursor.fetchall()
            existing_columns = [col[1] for col in columns]
            print(f"Existing columns: {len(existing_columns)}")
            
            # Add missing columns if they don't exist
            columns_to_add = [
                ("selected_expiry", "TEXT", None),
                ("exit_day_offset", "INTEGER", 2),
                ("exit_time", "TEXT", "15:15"),
                ("auto_square_off_enabled", "BOOLEAN", 1),
                ("weekday_config", "TEXT", '{"monday":"current","tuesday":"current","wednesday":"next","thursday":"next","friday":"next"}'),
                ("max_loss_per_trade", "REAL", 20000),
                ("max_exposure", "REAL", 200000),
                ("max_positions", "INTEGER", 5)
            ]
            
            added = 0
            for col_name, col_type, default_value in columns_to_add:
                if col_name not in existing_columns:
                    if default_value is not None:
                        if col_type == "TEXT":
                            cursor.execute(f"ALTER TABLE TradeConfiguration ADD COLUMN {col_name} {col_type} DEFAULT '{default_value}'")
                        else:
                            cursor.execute(f"ALTER TABLE TradeConfiguration ADD COLUMN {col_name} {col_type} DEFAULT {default_value}")
                    else:
                        cursor.execute(f"ALTER TABLE TradeConfiguration ADD COLUMN {col_name} {col_type}")
                    print(f"  [OK] Added column: {col_name} ({col_type})")
                    added += 1
                else:
                    print(f"  - Column already exists: {col_name}")
            
            conn.commit()
            
            # Verify the columns were added
            cursor.execute("PRAGMA table_info(TradeConfiguration)")
            columns = cursor.fetchall()
            new_column_count = len(columns)
            
            print(f"\nColumns after update: {new_column_count}")
            print(f"Added {added} new columns")
            
            # Show all columns
            print("\nAll columns in TradeConfiguration:")
            for col in columns:
                print(f"  {col[1]:25} {col[2]:10} {col[4] if col[4] else ''}")
            
            print("\n" + "="*60)
            print("[SUCCESS] Database schema updated successfully!")
            return True
            
    except Exception as e:
        print(f"Error updating database: {e}")
        return False

if __name__ == "__main__":
    success = add_missing_columns()
    exit(0 if success else 1)