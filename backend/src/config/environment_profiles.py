"""
Environment Profiles Module

Defines environment profiles (dev, paper, live) with safety gates.
Each profile has specific restrictions and requirements.
"""

import os
import logging
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class EnvironmentProfile(Enum):
    """Environment profiles with different safety levels."""
    DEVELOPMENT = "development"
    PAPER = "paper"
    LIVE = "live"


@dataclass
class ProfileConfig:
    """Configuration for an environment profile."""
    name: str
    allow_live_trading: bool
    max_daily_loss: float
    max_position_size: int
    require_telegram_alerts: bool
    require_manual_confirmation: bool
    allow_risk_breach: bool
    log_level: str
    rate_limit_per_minute: int


# Profile configurations
PROFILES: Dict[EnvironmentProfile, ProfileConfig] = {
    EnvironmentProfile.DEVELOPMENT: ProfileConfig(
        name="Development",
        allow_live_trading=False,
        max_daily_loss=1000.0,
        max_position_size=10,
        require_telegram_alerts=False,
        require_manual_confirmation=False,
        allow_risk_breach=True,
        log_level="DEBUG",
        rate_limit_per_minute=100
    ),
    EnvironmentProfile.PAPER: ProfileConfig(
        name="Paper Trading",
        allow_live_trading=False,  # Paper money, not real
        max_daily_loss=50000.0,
        max_position_size=100,
        require_telegram_alerts=True,
        require_manual_confirmation=False,
        allow_risk_breach=False,
        log_level="INFO",
        rate_limit_per_minute=60
    ),
    EnvironmentProfile.LIVE: ProfileConfig(
        name="Live Trading",
        allow_live_trading=True,
        max_daily_loss=15000.0,
        max_position_size=65,
        require_telegram_alerts=True,
        require_manual_confirmation=True,
        allow_risk_breach=False,
        log_level="WARNING",
        rate_limit_per_minute=30
    )
}


class EnvironmentManager:
    """
    Manages environment profiles and enforces safety gates.
    """
    
    def __init__(self, profile: Optional[EnvironmentProfile] = None):
        self._profile = profile or self._detect_environment()
        self._config = PROFILES[self._profile]
        
    def _detect_environment(self) -> EnvironmentProfile:
        """Detect environment from environment variable."""
        env = os.getenv("ENVIRONMENT", "development").lower()
        
        if env == "live":
            return EnvironmentProfile.LIVE
        elif env == "paper":
            return EnvironmentProfile.PAPER
        else:
            return EnvironmentProfile.DEVELOPMENT
    
    @property
    def profile(self) -> EnvironmentProfile:
        """Get current environment profile."""
        return self._profile
    
    @property
    def config(self) -> ProfileConfig:
        """Get current profile configuration."""
        return self._config
    
    def is_live_trading_allowed(self) -> bool:
        """Check if live trading is allowed in current profile."""
        return self._config.allow_live_trading
    
    def validate_trade(self, trade_value: float, daily_pnl: float) -> tuple[bool, Optional[str]]:
        """
        Validate a trade against profile safety gates.
        
        Returns:
            (is_allowed, error_message)
        """
        # Check daily loss limit
        if daily_pnl <= -self._config.max_daily_loss:
            return False, f"Daily loss limit exceeded: {self._config.max_daily_loss}"
        
        # Check position size limit
        if trade_value > self._config.max_position_size:
            return False, f"Position size exceeds limit: {self._config.max_position_size}"
        
        return True, None
    
    def validate_risk_breach(self, breach_type: str) -> tuple[bool, Optional[str]]:
        """Check if risk breach is allowed."""
        if self._config.allow_risk_breach:
            return True, None
        
        return False, f"Risk breach not allowed in {self._profile.value} environment"
    
    def get_rate_limit(self) -> int:
        """Get rate limit for current profile."""
        return self._config.rate_limit_per_minute
    
    def requires_confirmation(self) -> bool:
        """Check if manual confirmation is required."""
        return self._config.require_manual_confirmation
    
    def log_warning(self, message: str):
        """Log a warning based on profile settings."""
        if self._config.log_level in ["DEBUG", "INFO"]:
            logger.info(f"[{self._profile.value.upper()}] {message}")
        else:
            logger.warning(f"[{self._profile.value.upper()}] {message}")


# Global instance
_environment_manager: Optional[EnvironmentManager] = None


def get_environment_manager() -> EnvironmentManager:
    """Get the global environment manager instance."""
    global _environment_manager
    if _environment_manager is None:
        _environment_manager = EnvironmentManager()
    return _environment_manager


def get_current_profile() -> EnvironmentProfile:
    """Get current environment profile."""
    return get_environment_manager().profile


def is_live_mode() -> bool:
    """Check if running in live mode."""
    return get_current_profile() == EnvironmentProfile.LIVE


def is_paper_mode() -> bool:
    """Check if running in paper mode."""
    return get_current_profile() == EnvironmentProfile.PAPER


def is_development_mode() -> bool:
    """Check if running in development mode."""
    return get_current_profile() == EnvironmentProfile.DEVELOPMENT