"""
App Settings Module

Global application settings - loads from environment variables.
"""

import os
from typing import Optional, List, Dict, Any


class AppSettings:
    """Global application settings - loads from environment variables."""
    
    # Market configuration (uses MarketRegistry)
    ACTIVE_MARKET = os.getenv("ACTIVE_MARKET", "NSE_IN")
    
    @property
    def MARKET_OPEN(self):
        from src.config.market import MarketRegistry
        return MarketRegistry.get_active_market().open_time
    
    @property
    def MARKET_CLOSE(self):
        from src.config.market import MarketRegistry
        return MarketRegistry.get_active_market().close_time
    
    @property
    def ENTRY_START(self):
        from src.config.market import MarketRegistry
        return MarketRegistry.get_active_market().entry_start
    
    @property
    def ENTRY_END(self):
        from src.config.market import MarketRegistry
        return MarketRegistry.get_active_market().entry_end
    
    @property
    def EXIT_ALL(self):
        from src.config.market import MarketRegistry
        return MarketRegistry.get_active_market().exit_all
    
    @property
    def RESTRICTED_ZONES(self):
        from src.config.market import MarketRegistry
        return MarketRegistry.get_active_market().restricted_zones
    
    @property
    def MARKET_TIMEZONE(self):
        from src.config.market import MarketRegistry
        return MarketRegistry.get_active_market().timezone
    
    # Trading Settings
    PAPER_TRADING = os.getenv("PAPER_TRADING", "True").lower() == "true"
    CANDLE_PERIOD_SECONDS = int(os.getenv("CANDLE_PERIOD_SECONDS", 300))
    MIN_SIGNALS_REQUIRED = int(os.getenv("MIN_SIGNALS_REQUIRED", 2))
    USE_TSL = os.getenv("USE_TSL", "True").lower() == "true"
    TSL_ACTIVATION_PERCENT = float(os.getenv("TSL_ACTIVATION_PERCENT", 0.5))
    TSL_LOCK_PERCENT = float(os.getenv("TSL_LOCK_PERCENT", 0.1))
    KILL_AFTER_DAILY_LIMIT = os.getenv("KILL_AFTER_DAILY_LIMIT", "False").lower() == "true"
    # Minimum seconds to wait after a trade closes before taking a new one (per market)
    TRADE_COOLDOWN_SECONDS = int(os.getenv("TRADE_COOLDOWN_SECONDS", 900))  # Default: 15 minutes
    # Capital reserved for brokerage/STT/GST so bot never deploys 100% of margin
    BROKERAGE_BUFFER_PCT = float(os.getenv("BROKERAGE_BUFFER_PCT", 0.5))  # Default: 0.5%
    # Maximum price movement (%) allowed from signal price before aborting entry
    MAX_ALLOWED_SLIPPAGE_PCT = float(os.getenv("MAX_ALLOWED_SLIPPAGE_PCT", 1.0)) # Default: 1.0%
    
    # Symbol Settings
    TRADING_SYMBOL_PREFIX = os.getenv("TRADING_SYMBOL_PREFIX", "NIFTY")
    LOT_SIZE = int(os.getenv("LOT_SIZE", 65))
    NIFTY_OPTIONS_STRATEGY = os.getenv("NIFTY_OPTIONS_STRATEGY", "True").lower() == "true"
    NIFTY_STRIKE_STEP = int(os.getenv("NIFTY_STRIKE_STEP", 50))
    
    BANKNIFTY_ENABLED = os.getenv("BANKNIFTY_ENABLED", "True").lower() == "true"
    BANKNIFTY_LOT_SIZE = int(os.getenv("BANKNIFTY_LOT_SIZE", 30))
    BANKNIFTY_STRIKE_STEP = int(os.getenv("BANKNIFTY_STRIKE_STEP", 100))
    
    FINNIFTY_ENABLED = os.getenv("FINNIFTY_ENABLED", "True").lower() == "true"
    FINNIFTY_LOT_SIZE = int(os.getenv("FINNIFTY_LOT_SIZE", 40))
    FINNIFTY_STRIKE_STEP = int(os.getenv("FINNIFTY_STRIKE_STEP", 40))
    
    NIFTY_LOTS = int(os.getenv("NIFTY_LOTS", 1))
    BANKNIFTY_LOTS = int(os.getenv("BANKNIFTY_LOTS", 1))
    FINNIFTY_LOTS = int(os.getenv("FINNIFTY_LOTS", 1))
    
    @classmethod
    def is_market_open(cls) -> bool:
        from src.config.market import MarketRegistry
        return MarketRegistry.is_market_open()


# Create singleton for backwards compatibility
Settings = AppSettings()