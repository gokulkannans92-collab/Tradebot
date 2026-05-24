"""
Service layer for TradeBot.

Provides clean interfaces for:
- Bot process management
- Environment profiles
- Health monitoring
"""

from src.service.bot_service import BotService, BotConfig, BotState, get_bot_service
from src.config.environment_profiles import (
    EnvironmentProfile,
    EnvironmentManager,
    get_environment_manager,
    get_current_profile,
    is_live_mode,
    is_paper_mode,
    is_development_mode
)

__all__ = [
    # Bot service
    'BotService',
    'BotConfig', 
    'BotState',
    'get_bot_service',
    # Environment
    'EnvironmentProfile',
    'EnvironmentManager',
    'get_environment_manager',
    'get_current_profile',
    'is_live_mode',
    'is_paper_mode',
    'is_development_mode'
]