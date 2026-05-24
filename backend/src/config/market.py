"""
Market Configuration Module

Defines market timings, timezones, and market registry for multi-market support.
"""

from datetime import time
from typing import Dict, Optional, List
from dataclasses import dataclass
import os


@dataclass
class MarketConfig:
    """Configuration for a single market."""
    name: str
    open_time: time
    close_time: time
    entry_start: time
    entry_end: time
    exit_all: time
    timezone: str
    restricted_zones: List[tuple] = None
    
    def __post_init__(self):
        if self.restricted_zones is None:
            self.restricted_zones = []


class MarketRegistry:
    """
    Centralized market configuration with timezone support.
    
    Supports multiple markets: NSE (India), NYSE (US), LSE (UK), etc.
    """
    
    MARKETS: Dict[str, MarketConfig] = {
        "NSE_IN": MarketConfig(
            name="NSE (India)",
            open_time=time(9, 15),
            close_time=time(15, 30),
            entry_start=time(9, 30),
            entry_end=time(14, 30),
            exit_all=time(15, 10),
            timezone="Asia/Kolkata",
            restricted_zones=[(time(12, 0), time(13, 30))]
        ),
        "NYSE_US": MarketConfig(
            name="NYSE (US)",
            open_time=time(9, 30),
            close_time=time(16, 0),
            entry_start=time(9, 30),
            entry_end=time(15, 30),
            exit_all=time(15, 45),
            timezone="America/New_York"
        ),
        "LSE_UK": MarketConfig(
            name="LSE (UK)",
            open_time=time(8, 0),
            close_time=time(16, 30),
            entry_start=time(8, 0),
            entry_end=time(15, 30),
            exit_all=time(16, 15),
            timezone="Europe/London"
        ),
    }
    
    DEFAULT_MARKET = "NSE_IN"
    _active_market: Optional[str] = None
    
    @classmethod
    def get_active_market(cls) -> MarketConfig:
        return cls.MARKETS.get(cls._active_market or cls.DEFAULT_MARKET)
    
    @classmethod
    def set_active_market(cls, market_id: str) -> bool:
        if market_id in cls.MARKETS:
            cls._active_market = market_id
            return True
        return False
    
    @classmethod
    def get_available_markets(cls) -> Dict[str, str]:
        return {k: v.name for k, v in cls.MARKETS.items()}
    
    @classmethod
    def is_market_open(cls, market_id: str = None) -> bool:
        import pytz
        market = cls.MARKETS.get(market_id or cls._active_market or cls.DEFAULT_MARKET)
        if not market:
            return False
        
        try:
            from datetime import datetime
            tz = pytz.timezone(market.timezone)
            now_local = datetime.now(tz).time()
            return market.open_time <= now_local <= market.close_time
        except Exception:
            from datetime import datetime
            now_local = datetime.now().time()
            return market.open_time <= now_local <= market.close_time


# Initialize from environment
MarketRegistry.set_active_market(os.getenv("ACTIVE_MARKET", MarketRegistry.DEFAULT_MARKET))