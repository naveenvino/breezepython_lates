"""
Settings Service - Use this to get/set settings from anywhere in the codebase
"""

from src.infrastructure.database.database_manager import DatabaseManager
from sqlalchemy import text

class SettingsService:
    @staticmethod
    def get_setting(key: str, category: str = None) -> str:
        """Get a single setting value"""
        db = DatabaseManager()
        with db.get_session() as session:
            if category:
                full_key = f"{category}_{key}"
            else:
                full_key = key
                
            query = "SELECT setting_value FROM SystemSettings WHERE setting_key = :key"
            result = session.execute(text(query), {"key": full_key})
            row = result.first()
            return row[0] if row else None
    
    @staticmethod
    def set_setting(key: str, value: str, category: str = None):
        """Set a single setting value"""
        db = DatabaseManager()
        with db.get_session() as session:
            if category:
                full_key = f"{category}_{key}"
            else:
                full_key = key
            
            upsert_query = """
                MERGE SystemSettings AS target
                USING (SELECT :key AS setting_key) AS source
                ON target.setting_key = source.setting_key
                WHEN MATCHED THEN
                    UPDATE SET setting_value = :value, updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (setting_key, setting_value, category)
                    VALUES (:key, :value, :category);
            """
            
            session.execute(text(upsert_query), {
                "key": full_key,
                "value": str(value),
                "category": category or "general"
            })
            session.commit()
    
    @staticmethod
    def get_trading_settings():
        """Get all trading-related settings"""
        db = DatabaseManager()
        with db.get_session() as session:
            query = """
                SELECT setting_key, setting_value 
                FROM SystemSettings 
                WHERE category = 'trading'
            """
            result = session.execute(text(query))
            settings = {}
            for row in result:
                key = row[0].replace("trading_", "")
                settings[key] = row[1]
            return settings
    
    @staticmethod
    def get_risk_settings():
        """Get all risk management settings"""
        db = DatabaseManager()
        with db.get_session() as session:
            query = """
                SELECT setting_key, setting_value 
                FROM SystemSettings 
                WHERE category = 'risk'
            """
            result = session.execute(text(query))
            settings = {}
            for row in result:
                key = row[0].replace("risk_", "")
                settings[key] = row[1]
            return settings

# Global instance
settings_service = SettingsService()
