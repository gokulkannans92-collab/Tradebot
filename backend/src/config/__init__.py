"""
TradeBot Configuration Package

Single point of entry for all configuration classes.
Centralizes imports to avoid circular dependencies.
"""

import os
import json
import logging
from datetime import time, datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

from src.utils.paths import ensure_paths, get_path
from src.utils.security import encrypt_credentials, decrypt_credentials

logger = logging.getLogger(__name__)

# Ensure paths are set up
DATA_DIR = ensure_paths()

# Load environment variables
# 1. Try local root .env (for dev/source mode)
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_local_env = os.path.join(_root_dir, ".env")
if os.path.exists(_local_env):
    load_dotenv(_local_env)
else:
    # 2. Fall back to standard get_path for EXE/AppData mode
    load_dotenv(get_path(".env"))


# ═══════════════════════════════════════════════════════════════════════
# Re-export from submodules for backwards compatibility
# ═══════════════════════════════════════════════════════════════════════

# Market configuration
from src.config.market import MarketConfig, MarketRegistry

# App settings
from src.config.app_settings import AppSettings, Settings

# User settings and manager
from src.config.user_settings import UserSettings

from src.config.user_manager import UserManager

# Enums
from src.config.enums import BrokerType


# ═══════════════════════════════════════════════════════════════════════
# Backwards compatibility aliases
# ═══════════════════════════════════════════════════════════════════════

Config = UserManager


# ═══════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════

def validate_configuration():
    """
    Validates critical application settings at startup.
    Raises ValueError if configuration is fundamentally broken or unsafe.
    """
    logger.info("Validating application configuration...")
    
    # Check data directory
    if not os.path.exists(DATA_DIR) or not os.access(DATA_DIR, os.W_OK):
        raise ValueError(f"DATA_DIR '{DATA_DIR}' is not writable or does not exist.")
        
    # Validate Risk Parameters
    slippage = getattr(AppSettings, 'MAX_ALLOWED_SLIPPAGE_PCT', 1.0)
    if not isinstance(slippage, (int, float)) or slippage < 0 or slippage > 10.0:
        raise ValueError(f"MAX_ALLOWED_SLIPPAGE_PCT must be between 0 and 10.0 (Got {slippage})")
        
    buffer = getattr(AppSettings, 'BROKERAGE_BUFFER_PCT', 0.5)
    if not isinstance(buffer, (int, float)) or buffer < 0 or buffer > 5.0:
        raise ValueError(f"BROKERAGE_BUFFER_PCT must be between 0 and 5.0 (Got {buffer})")
        
    logger.info("✅ Configuration validation passed.")


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

__all__ = [
    "validate_configuration",
    "AppSettings",
    "Settings",
    "UserSettings",
    "UserManager",
    "Config",
    "MarketRegistry",
    "MarketConfig",
    "BrokerType",
    "DATA_DIR",
]