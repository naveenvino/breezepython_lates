"""
Add max_exposure column to existing database
"""

import sqlite3
from pathlib import Path

def add_max_exposure_column():
    db_path = Path("data/trading_settings.db")
    
    if not db_path.exists():
        print("Database doesn't exist yet, will be created with correct schema on first use")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(TradeConfiguration)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'max_exposure' not in columns:
        print("Adding max_exposure column...")
        cursor.execute("""
            ALTER TABLE TradeConfiguration 
            ADD COLUMN max_exposure REAL DEFAULT 200000
        """)
        conn.commit()
        print("Column added successfully!")
    else:
        print("max_exposure column already exists")
    
    conn.close()

if __name__ == "__main__":
    add_max_exposure_column()