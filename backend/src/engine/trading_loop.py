"""
Trading Loop Engine

Core trading loop logic separated from main.py for better maintainability.
"""

import os
import time
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Callable

from src.config import Settings
Config = Settings  # Alias used in run_once()
from src.data.holidays_manager import get_holidays_manager
from src.trade.user_session import UserSession
from src.utils.cache_manager import ActiveTradesCache

logger = logging.getLogger(__name__)


class TradingLoop:
    """
    Main trading loop orchestrating market data, signals, and trade execution.
    
    Responsibilities:
    - Holiday and market hours checking
    - Daily reset management
    - Stop trigger monitoring
    - Kill switch handling
    - Session lifecycle management
    """
    
    def __init__(
        self,
        sessions: List[UserSession],
        data_provider: Any,
        signal_processor: Any,
        trades_cache: ActiveTradesCache,
        stop_trigger_file: str,
        loop_interval: float = 5.0
    ):
        """
        Initialize trading loop.
        
        Args:
            sessions: List of active user sessions
            data_provider: Market data provider instance
            signal_processor: Signal processing engine
            trades_cache: Active trades cache for GUI updates
            stop_trigger_file: Path to stop trigger file
            loop_interval: Seconds between loop iterations (default: 5.0)
        """
        self.sessions = sessions
        self.data_provider = data_provider
        self.signal_processor = signal_processor
        self.trades_cache = trades_cache
        self.stop_trigger_file = stop_trigger_file
        self.loop_interval = loop_interval
        
        self.loop_count = 0
        self.should_exit_on_stop = True
        self.current_date: date = date.today()
        
        self._running = False
        self._on_stop_callbacks: List[Callable] = []
    
    def add_stop_callback(self, callback: Callable):
        """Register callback to run on loop stop."""
        self._on_stop_callbacks.append(callback)
    
    def _check_holiday(self, today: date) -> bool:
        """Check if today is a market holiday."""
        holidays_mgr = get_holidays_manager()
        
        if holidays_mgr.is_holiday(today):
            if self.loop_count % 60 == 1:  # Log once per minute
                holiday_name = holidays_mgr.get_holiday_name(today)
                logger.info(f"📅 Today is a {holiday_name} ({today}). Bot is idling …")
            return True
        return False
    
    def _check_stop_trigger(self) -> bool:
        """Check for stop trigger file with proper locking."""
        import os
        import sys
        
        if not os.path.exists(self.stop_trigger_file):
            return False
        
        try:
            with open(self.stop_trigger_file, "r") as f:
                if sys.platform != "win32":
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        content = f.read().strip()
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                else:
                    content = f.read().strip()
                
                if ":keep" in content:
                    self.should_exit_on_stop = False
                    logger.info("🛑 Stop requested (keep mode) — finishing active trades...")
                else:
                    logger.info("🛑 Stop trigger detected — shutting down...")
                return True
        except (IOError, OSError, BlockingIOError) as e:
            logger.debug(f"Could not read stop trigger file: {e}")
            return False
    
    def _check_command_file(self) -> Optional[Dict[str, Any]]:
        """Check for external command file with proper locking."""
        import os
        import json
        import sys
        
        cmd_file = os.path.join(os.path.dirname(self.stop_trigger_file), ".cmd.json")
        
        if not os.path.exists(cmd_file):
            return None
        
        try:
            with open(cmd_file, "r") as f:
                if sys.platform != "win32":
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        cmd_data = json.load(f)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                else:
                    cmd_data = json.load(f)
            os.remove(cmd_file)
            return cmd_data
        except (json.JSONDecodeError, KeyError, IOError, OSError, BlockingIOError) as e:
            logger.error(f"Error processing command: {e}")
            return None
    
    def _execute_command(self, cmd_data: Dict[str, Any]):
        """Execute external command."""
        cmd = cmd_data.get("cmd", "").upper()
        target_user_id = cmd_data.get("user_id")
        symbol = cmd_data.get("symbol")
        
        if cmd == "CLOSE_TRADE" and target_user_id and symbol:
            for s in self.sessions:
                if s.user_id == target_user_id:
                    for tracker in [s.nifty_tracker, s.bn_tracker]:
                        if tracker and symbol in tracker.active_trades:
                            try:
                                quote = s.broker.get_quote(symbol)
                                ltp = quote.get("last_price") or quote.get("price", 0) if quote else 0
                                tracker.close_trade(symbol, ltp, "MANUAL_CMD")
                                logger.info(f"🔴 Manual close: {symbol} for {s.user_id}")
                            except Exception as e:
                                logger.error(f"Manual close failed: {e}")
        
        elif cmd == "CLOSE_ALL":
            for s in self.sessions:
                if s.user_id == target_user_id:
                    s.close_all()
                    logger.info(f"🔴 Manual close all requested")
    
    def _check_kill_switch(self, now: datetime) -> bool:
        """Check if kill switch should trigger shutdown."""
        for s in self.sessions:
            if s.config.KILL_AFTER_DAILY_LIMIT and s.risk.trades_today >= s.config.MAX_TRADES_PER_DAY:
                logger.critical(f"🚀 [KILL SWITCH] Daily trade limit reached for {s.name}. Shutting down.")
                try:
                    import os
                    with open(self.stop_trigger_file, "w") as f:
                        f.write("stop:exit")
                except (IOError, OSError) as e:
                    logger.error(f"Failed to write stop trigger: {e}")
                return True
        return False
    
    def _update_trades_cache(self):
        """Update trades cache for GUI."""
        all_active_data = []
        for s in self.sessions:
            try:
                all_active_data.extend(s.get_active_trades())
            except (AttributeError, KeyError, TypeError) as e:
                logger.debug(f"Could not get active trades for session: {e}")
        
        self.trades_cache.update_trades(all_active_data)
    
    def run_once(self) -> bool:
        """
        Execute one iteration of the trading loop.
        
        Returns:
            True if loop should continue, False to exit
        """
        self.loop_count += 1
        now = datetime.now()
        today = now.date()
        
        # Holiday check
        if self._check_holiday(today):
            time.sleep(60)
            return True
        
        # Market hours check
        if not (Config.MARKET_OPEN <= now.time() <= Config.MARKET_CLOSE):
            if self.loop_count % 12 == 0:
                logger.info(f"Outside market hours ({now.strftime('%H:%M')}). Waiting …")
            time.sleep(self.loop_interval)
            return True
        
        # Daily reset
        if today != self.current_date:
            self._handle_daily_reset(today)
        
        # Stop trigger check
        if os.path.exists(self.stop_trigger_file):
            if self._check_stop_trigger():
                return False
        
        # Command file check
        cmd = self._check_command_file()
        if cmd:
            self._execute_command(cmd)
        
        # Update trades cache
        self._update_trades_cache()
        
        # Check kill switch
        if self._check_kill_switch(now):
            return False
        
        # EOD exit check
        if now.time() >= Config.EXIT_ALL:
            logger.info("⏰ EOD exit — closing all sessions.")
            for s in self.sessions:
                s.close_all()
            return False
        
        return True
    
    def _handle_daily_reset(self, new_date: date):
        """Handle daily reset of all state."""
        logger.info(f"🔄 New trading day {new_date} — resetting state.")
        self.current_date = new_date
        
        # Reset signal processor
        if self.signal_processor:
            self.signal_processor.reset()
        
        # Reset all session trackers
        for s in self.sessions:
            if s.nifty_tracker:
                s.nifty_tracker.load_active_trades()
            if s.bn_tracker:
                s.bn_tracker.load_active_trades()
    
    def run(self):
        """Run the trading loop until stopped."""
        self._running = True
        
        logger.info("=" * 60)
        logger.info("  TRADING LOOP STARTED")
        logger.info("=" * 60)
        
        try:
            while self._running:
                if not self.run_once():
                    break
                time.sleep(self.loop_interval)
                
        except KeyboardInterrupt:
            logger.info("⚠️ Keyboard interrupt — shutting down.")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the trading loop gracefully."""
        self._running = False
        
        # Run stop callbacks
        for callback in self._on_stop_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Stop callback error: {e}")
        
        logger.info("=" * 60)
        logger.info("  TRADING LOOP STOPPED")
        logger.info("=" * 60)
