"""
Dynamic Holidays Manager

Fetches and manages NSE trading holidays from external sources.
Never hardcodes holiday dates - always fetches fresh data.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime, date, timedelta
from dataclasses import dataclass
import requests
from pathlib import Path

from src.utils.cache_manager import TimedCache

logger = logging.getLogger(__name__)


@dataclass
class Holiday:
    """Represents a trading holiday."""
    date: date
    name: str
    market_closed: bool = True
    
    def __hash__(self):
        return hash(self.date)
    
    def __eq__(self, other):
        if isinstance(other, Holiday):
            return self.date == other.date
        return self.date == other


class HolidaysManager:
    """
    Manages NSE trading holidays dynamically.
    
    Features:
    - Fetches from NSE India API or alternative sources
    - Caches holidays locally with automatic refresh
    - Supports manual override via config file
    - Weekend detection (Saturday/Sunday)
    """
    
    CACHE_FILE = "data/holidays_cache.json"
    CACHE_TTL_DAYS = 7  # Refresh cache weekly
    
    # NSE India official holiday calendar endpoint
    NSE_HOLIDAYS_URL = "https://www.nseindia.com/api/holiday-master?type=trading"
    
    # Alternative: Backup API (if NSE endpoint changes)
    BACKUP_SOURCES = [
        "https://api.nse.tools/holidays",  # Hypothetical - replace with real endpoint
    ]
    
    def __init__(self, cache_file: Optional[str] = None):
        self.cache_file = cache_file or self.CACHE_FILE
        self._holidays: Set[Holiday] = set()
        self._last_fetch: Optional[datetime] = None
        
        # Ensure directory exists
        Path(self.cache_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Load from cache on init
        self._load_from_cache()
    
    def _load_from_cache(self):
        """Load holidays from local cache file."""
        if not os.path.exists(self.cache_file):
            return
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
            
            # Check if cache is still valid
            last_update = datetime.fromisoformat(data.get('last_update', '2000-01-01'))
            if datetime.now() - last_update > timedelta(days=self.CACHE_TTL_DAYS):
                logger.info("Holiday cache expired, will refresh")
                return
            
            # Load holidays
            for holiday_data in data.get('holidays', []):
                holiday = Holiday(
                    date=date.fromisoformat(holiday_data['date']),
                    name=holiday_data['name'],
                    market_closed=holiday_data.get('market_closed', True)
                )
                self._holidays.add(holiday)
            
            self._last_fetch = last_update
            logger.info(f"Loaded {len(self._holidays)} holidays from cache")
            
        except Exception as e:
            logger.warning(f"Failed to load holiday cache: {e}")
    
    def _save_to_cache(self):
        """Save holidays to local cache file."""
        data = {
            'last_update': datetime.now().isoformat(),
            'holidays': [
                {
                    'date': h.date.isoformat(),
                    'name': h.name,
                    'market_closed': h.market_closed
                }
                for h in self._holidays
            ]
        }
        
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save holiday cache: {e}")
    
    def fetch_from_nse(self) -> bool:
        """
        Fetch holidays from NSE India official API.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Note: NSE API requires proper headers and session handling
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            }
            
            response = requests.get(
                self.NSE_HOLIDAYS_URL,
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning(f"NSE API returned status {response.status_code}")
                return False
            
            data = response.json()
            
            # Parse NSE holiday format
            for holiday_entry in data.get('CM', []):  # CM = Capital Market
                trading_date = holiday_entry.get('tradingDate')
                if trading_date:
                    try:
                        # Date format from NSE: "01-Apr-2024"
                        dt = datetime.strptime(trading_date, '%d-%b-%Y').date()
                        holiday = Holiday(
                            date=dt,
                            name=holiday_entry.get('description', 'Trading Holiday'),
                            market_closed=True
                        )
                        self._holidays.add(holiday)
                    except ValueError as e:
                        logger.warning(f"Could not parse date: {trading_date}")
            
            self._last_fetch = datetime.now()
            self._save_to_cache()
            logger.info(f"Fetched {len(self._holidays)} holidays from NSE")
            return True
            
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch from NSE: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error fetching holidays: {e}")
            return False
    
    def load_from_config(self, config_file: str = "config/holidays.json") -> bool:
        """
        Load holidays from user-provided config file.
        Allows manual override or fallback when API is unavailable.
        
        Args:
            config_file: Path to JSON file with holiday definitions
            
        Returns:
            True if loaded successfully
        """
        if not os.path.exists(config_file):
            return False
        
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
            
            for holiday_data in data.get('holidays', []):
                try:
                    holiday = Holiday(
                        date=date.fromisoformat(holiday_data['date']),
                        name=holiday_data.get('name', 'Holiday'),
                        market_closed=holiday_data.get('market_closed', True)
                    )
                    self._holidays.add(holiday)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid holiday entry: {holiday_data}")
            
            logger.info(f"Loaded {len(self._holidays)} holidays from config file")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load holidays from config: {e}")
            return False
    
    def refresh(self, force: bool = False) -> bool:
        """
        Refresh holiday data from sources.
        
        Args:
            force: Force refresh even if cache is valid
            
        Returns:
            True if refresh succeeded
        """
        # Check if refresh is needed
        if not force and self._last_fetch:
            age = datetime.now() - self._last_fetch
            if age < timedelta(days=self.CACHE_TTL_DAYS):
                logger.debug("Holiday cache still fresh, skipping refresh")
                return True
        
        # Try to fetch from NSE
        if self.fetch_from_nse():
            return True
        
        # Fallback to config file
        if self.load_from_config():
            return True
        
        # If we have cached data, use it even if expired
        if self._holidays:
            logger.warning("Using expired holiday cache - API unavailable")
            return True
        
        return False
    
    def is_holiday(self, check_date: Optional[date] = None) -> bool:
        """
        Check if a date is a trading holiday.
        
        Args:
            check_date: Date to check (defaults to today)
            
        Returns:
            True if holiday or weekend
        """
        if check_date is None:
            check_date = date.today()
        
        # Weekend check
        if check_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return True
        
        # Holiday check
        return check_date in self._holidays
    
    def get_holiday_name(self, check_date: Optional[date] = None) -> Optional[str]:
        """
        Get the name of the holiday for a given date.
        
        Args:
            check_date: Date to check (defaults to today)
            
        Returns:
            Holiday name if it's a holiday, None otherwise
        """
        if check_date is None:
            check_date = date.today()
        
        for holiday in self._holidays:
            if holiday.date == check_date:
                return holiday.name
        
        if check_date.weekday() == 5:
            return "Saturday"
        if check_date.weekday() == 6:
            return "Sunday"
        
        return None
    
    def get_upcoming_holidays(self, days: int = 30) -> List[Holiday]:
        """
        Get list of upcoming holidays within specified days.
        
        Args:
            days: Number of days to look ahead
            
        Returns:
            List of upcoming holidays
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        upcoming = []
        for holiday in self._holidays:
            if today <= holiday.date <= end_date:
                upcoming.append(holiday)
        
        # Add weekends
        current = today
        while current <= end_date:
            if current.weekday() >= 5:
                name = "Saturday" if current.weekday() == 5 else "Sunday"
                upcoming.append(Holiday(date=current, name=name))
            current += timedelta(days=1)
        
        return sorted(upcoming, key=lambda h: h.date)
    
    def get_all_holidays(self, year: Optional[int] = None) -> List[Holiday]:
        """
        Get all holidays for a specific year or all known holidays.
        
        Args:
            year: Optional year filter
            
        Returns:
            List of holidays
        """
        if year is None:
            return sorted(self._holidays, key=lambda h: h.date)
        
        return sorted(
            [h for h in self._holidays if h.date.year == year],
            key=lambda h: h.date
        )
    
    def is_market_open_today(self) -> bool:
        """Check if market is open today."""
        return not self.is_holiday()
    
    def next_trading_day(self, from_date: Optional[date] = None) -> date:
        """
        Get the next trading day from a given date.
        
        Args:
            from_date: Starting date (defaults to today)
            
        Returns:
            Next trading day
        """
        if from_date is None:
            from_date = date.today()
        
        next_day = from_date + timedelta(days=1)
        while self.is_holiday(next_day):
            next_day += timedelta(days=1)
        
        return next_day


# Global instance for application-wide use
_holidays_manager: Optional[HolidaysManager] = None


def get_holidays_manager() -> HolidaysManager:
    """Get or create the global holidays manager instance."""
    global _holidays_manager
    if _holidays_manager is None:
        _holidays_manager = HolidaysManager()
        _holidays_manager.refresh()
    return _holidays_manager


def is_holiday(check_date: Optional[date] = None) -> bool:
    """Convenience function to check if a date is a holiday."""
    return get_holidays_manager().is_holiday(check_date)


def is_market_open_today() -> bool:
    """Convenience function to check if market is open today."""
    return get_holidays_manager().is_market_open_today()


# Backward compatibility - replace NSE_HOLIDAYS_2026
NSE_HOLIDAYS_2026 = set()  # Deprecated - use HolidaysManager instead


def get_holiday_for_backwards_compatibility(check_date: date) -> bool:
    """
    Backward compatibility function for code using NSE_HOLIDAYS_2026.
    
    Usage:
        Replace: if today in NSE_HOLIDAYS_2026
        With:    if is_holiday(today)
    """
    return is_holiday(check_date)
