"""
Application Settings
Configuration management using Pydantic
"""
import os
from typing import List, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class AppSettings(BaseSettings):
    """Application settings"""
    name: str = Field(default="KiteApp", env="APP_NAME")
    version: str = Field(default="2.0.0")
    environment: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=True, env="APP_DEBUG")
    host: str = Field(default="0.0.0.0", env="APP_HOST")
    port: int = Field(default=8100, env="APP_PORT")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8100"],
        env="CORS_ORIGINS"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields


class DatabaseSettings(BaseSettings):
    """Database settings"""
    server: str = Field(default="(localdb)\\mssqllocaldb", env="DB_SERVER")
    database: str = Field(default="KiteConnectApi", env="DB_NAME")
    driver: str = Field(default="ODBC Driver 17 for SQL Server", env="DB_DRIVER")
    trusted_connection: bool = Field(default=True, env="DB_TRUSTED_CONNECTION")
    username: Optional[str] = Field(default=None, env="DB_USERNAME")
    password: Optional[str] = Field(default=None, env="DB_PASSWORD")
    echo_sql: bool = Field(default=False, env="DB_ECHO_SQL")
    
    @property
    def connection_string(self) -> str:
        """Build SQL Server connection string"""
        if self.trusted_connection:
            return (
                f"mssql+pyodbc://{self.server}/{self.database}"
                f"?driver={self.driver.replace(' ', '+')}"
                "&trusted_connection=yes"
            )
        else:
            return (
                f"mssql+pyodbc://{self.username}:{self.password}@"
                f"{self.server}/{self.database}"
                f"?driver={self.driver.replace(' ', '+')}"
            )
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields


class BreezeSettings(BaseSettings):
    """Breeze API settings"""
    api_key: str = Field(default="", env="BREEZE_API_KEY")
    api_secret: str = Field(default="", env="BREEZE_API_SECRET")
    session_token: str = Field(default="", env="BREEZE_API_SESSION")  # Changed to match .env file
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields in .env


class TradingSettings(BaseSettings):
    """Trading configuration settings"""
    max_positions: int = Field(default=5, env="MAX_POSITIONS")
    max_daily_loss: float = Field(default=10000, env="MAX_DAILY_LOSS")
    risk_per_trade: float = Field(default=2.0, env="RISK_PER_TRADE")
    default_lot_size: int = Field(default=75, env="DEFAULT_LOT_SIZE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields


class LoggingSettings(BaseSettings):
    """Logging settings"""
    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    file_path: str = Field(default="logs/app.log", env="LOG_FILE_PATH")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields


class Settings:
    """Main settings class - simplified to avoid nested validation issues"""
    def __init__(self):
        self.app = AppSettings()
        self.database = DatabaseSettings()
        self.breeze = BreezeSettings()
        self.trading = TradingSettings()
        self.logging = LoggingSettings()


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()