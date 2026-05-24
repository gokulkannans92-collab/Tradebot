"""
Config Validator using Pydantic
============================
Validates configuration with type safety.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Literal
from enum import Enum


class AppEnvironment(str, Enum):
    """Application environment"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class BrokerConfig(BaseModel):
    """Broker configuration"""
    api_key: str = Field(min_length=1)
    api_secret: str = Field(min_length=1)
    broker: Literal["angel", "zerodha", "upstox", "groww"] = "angel"
    paper_mode: bool = True


class RiskConfig(BaseModel):
    """Risk management configuration"""
    max_daily_trades: int = Field(ge=1, le=10, default=5)
    max_loss_per_trade: float = Field(ge=100, le=10000, default=1000)
    max_daily_loss: float = Field(ge=500, le=50000, default=5000)
    stop_loss_percentage: float = Field(ge=0.5, le=10, default=1.0)
    target_percentage: float = Field(ge=1, le=50, default=3.0)


class StrategyConfig(BaseModel):
    """Strategy configuration"""
    name: str = Field(min_length=1)
    enabled: bool = True
    instruments: list[str] = Field(default_factory=lambda: ["NIFTY", "BANKNIFTY"])
    lot_size: int = Field(ge=1, default=1)
    use_trailing_stop: bool = True
    trailing_stop_percentage: float = Field(ge=0.5, le=5, default=1.0)


class AppConfig(BaseModel):
    """Main application configuration"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    environment: AppEnvironment = AppEnvironment.DEVELOPMENT
    user_id: str = Field(min_length=1)
    user_name: str = Field(min_length=1)
    broker: BrokerConfig
    risk: RiskConfig
    strategy: StrategyConfig
    
    # Feature flags
    enable_notifications: bool = True
    enable_sound_alerts: bool = True
    enable_auto_trade: bool = False
    
    # Paths (computed, not validated)


class ConfigValidator:
    """
    Validates configuration using Pydantic.
    
    Usage:
        validator = ConfigValidator()
        config = validator.load_config("config.json")
        errors = validator.validate(config)
    """
    
    @staticmethod
    def from_dict(data: dict) -> tuple[AppConfig, list[str]]:
        """
        Create config from dictionary.
        
        Returns:
            (config, error_list)
        """
        errors = []
        config = None
        
        try:
            config = AppConfig(**data)
        except Exception as e:
            errors.append(str(e))
        
        return config, errors
    
    @staticmethod
    def validate_environment(env: str) -> bool:
        """Check if environment is valid."""
        try:
            AppEnvironment(env)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def get_environment() -> AppEnvironment:
        """Get current environment from .env or default."""
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        env = os.getenv("APP_ENV", "development")
        
        try:
            return AppEnvironment(env)
        except ValueError:
            return AppEnvironment.DEVELOPMENT


# Validation helpers
def validate_api_key(key: str) -> bool:
    """Validate API key format."""
    return bool(key and len(key) >= 10)


def validate_user_id(user_id: str) -> bool:
    """Validate user ID format."""
    return bool(user_id and user_id.startswith("user_"))


# Singleton
_config_validator = None

def get_config_validator() -> ConfigValidator:
    """Get config validator instance."""
    global _config_validator
    if _config_validator is None:
        _config_validator = ConfigValidator()
    return _config_validator