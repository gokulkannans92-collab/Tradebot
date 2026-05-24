"""
DataManager - Centralized data handling for TradeBot
=====================================
Manages all data loading, caching, and file operations.
Eliminates duplicate data handling across the app.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta

from src.ui.dashboard.constants import ACTIVE_TRADES_FILE, USERS_FILE
from src.utils.trade_logger import get_all_trades

logger = logging.getLogger("DataManager")


class DataManager:
    """
    Centralized data manager with caching.
    Use this instead of direct file reads throughout the app.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern - one instance across the app"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # Cache storage
        self._active_trades_cache = None
        self._active_trades_mtime = 0
        self._all_trades_cache = None
        self._trades_cache_time = 0
        self._users_cache = None
        self._users_mtime = 0
        
        # Cache TTL (seconds)
        self.ACTIVE_TRADES_TTL = 5    # 5 seconds for active trades
        self.TRADES_TTL = 60        # 60 seconds for historical trades
        self.USERS_TTL = 300      # 5 minutes for users
    
    def get_active_trades(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get active trades with caching.
        
        Args:
            force_refresh: Skip cache and force read from disk
            
        Returns:
            List of active trade dictionaries
        """
        # Check if cache needs refresh
        if force_refresh:
            self._active_trades_cache = None
        
        current_mtime = 0
        if os.path.exists(ACTIVE_TRADES_FILE):
            current_mtime = os.path.getmtime(ACTIVE_TRADES_FILE)
        
        # Use cache if valid
        if (self._active_trades_cache is not None and 
            current_mtime == self._active_trades_mtime and
            time.time() - self._trades_cache_time < self.ACTIVE_TRADES_TTL):
            return [t for t in self._active_trades_cache if isinstance(t, dict)]
        
        # Load from disk
        try:
            with open(ACTIVE_TRADES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure we always return a list of dicts
                if isinstance(data, dict):
                    self._active_trades_cache = list(data.values())
                elif isinstance(data, list):
                    self._active_trades_cache = data
                else:
                    self._active_trades_cache = []
            self._active_trades_mtime = current_mtime
            self._trades_cache_time = time.time()
        except Exception as e:
            logger.error(f"Failed to load active trades: {e}")
            self._active_trades_cache = []
        
        # Ensure we only return dict items
        if isinstance(self._active_trades_cache, list):
            return [t for t in self._active_trades_cache if isinstance(t, dict)]
        return []
    
    def get_all_trades(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get all historical trades with caching.
        """
        if force_refresh:
            self._all_trades_cache = None
        
        # Check cache validity
        if (self._all_trades_cache is not None and 
            time.time() - self._trades_cache_time < self.TRADES_TTL):
            return [t for t in self._all_trades_cache if isinstance(t, dict)]
        
        try:
            raw_trades = get_all_trades()
            # Filter to only dict items
            self._all_trades_cache = [t for t in raw_trades if isinstance(t, dict)]
            self._trades_cache_time = time.time()
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")
            self._all_trades_cache = []
        
        return self._all_trades_cache or []
    
    def get_users(self, force_refresh: bool = False) -> List[Dict]:
        """Get users with caching."""
        if force_refresh:
            self._users_cache = None
        
        current_mtime = 0
        if os.path.exists(USERS_FILE):
            current_mtime = os.path.getmtime(USERS_FILE)
        
        if (self._users_cache is not None and 
            current_mtime == self._users_mtime and
            time.time() - self._users_cache_time < self.USERS_TTL):
            return self._users_cache
        
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                self._users_cache = json.load(f)
            self._users_mtime = current_mtime
            self._users_cache_time = time.time()
        except Exception as e:
            logger.error(f"Failed to load users: {e}")
            self._users_cache = []
        
        return self._users_cache or []
    
    def get_filtered_trades(self, period: str = "Today", 
                        force_refresh: bool = False) -> List[Dict]:
        """
        Get trades filtered by period.
        
        Args:
            period: "All", "Today", "Yesterday", "This Week", "This Month"
        """
        all_trades = self.get_all_trades(force_refresh)
        
        if period == "All":
            return [t for t in all_trades if isinstance(t, dict)]
        
        today = date.today()
        
        filtered = []
        for trade in all_trades:
            if not isinstance(trade, dict):
                continue
            trade_date_str = trade.get('date', '')
            if not trade_date_str:
                continue
            
            try:
                trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d').date()
                
                if period == "Today":
                    if trade_date == today:
                        filtered.append(trade)
                elif period == "Yesterday":
                    if trade_date == today - timedelta(days=1):
                        filtered.append(trade)
                elif period == "This Week":
                    week_start = today - timedelta(days=today.weekday())
                    if week_start <= trade_date <= today:
                        filtered.append(trade)
                elif period == "This Month":
                    if trade_date.year == today.year and trade_date.month == today.month:
                        filtered.append(trade)
            except (ValueError, TypeError):
                continue
        
        return filtered
    
    def calculate_stats(self, trades: List[Dict] = None) -> Dict[str, Any]:
        """
        Calculate statistics from trades.
        
        Returns:
            Dict with: total_trades, total_pnl, win_trades, win_rate, avg_trade
        """
        if trades is None:
            trades = self.get_all_trades()
        
        total = len(trades)
        if total == 0:
            return {
                'total_trades': 0,
                'total_pnl': 0,
                'win_trades': 0,
                'win_rate': 0,
                'avg_trade': 0
            }
        
        pnl_values = [float(t.get('pnl', 0)) for t in trades if isinstance(t, dict)]
        total_pnl = sum(pnl_values)
        wins = sum(1 for p in pnl_values if p > 0)
        
        return {
            'total_trades': total,
            'total_pnl': total_pnl,
            'win_trades': wins,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'avg_trade': total_pnl / total if total > 0 else 0
        }
    
    def invalidate_cache(self, cache_type: str = "all"):
        """
        Manually invalidate cache.
        
        Args:
            cache_type: "active", "trades", "users", or "all"
        """
        if cache_type in ("active", "all"):
            self._active_trades_cache = None
        if cache_type in ("trades", "all"):
            self._all_trades_cache = None
        if cache_type in ("users", "all"):
            self._users_cache = None


# Singleton accessor
def get_data_manager() -> DataManager:
    """Get the singleton DataManager instance."""
    return DataManager()