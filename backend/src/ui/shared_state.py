"""
Shared State Management
═══════════════════════════════════════════════════════════════════════════════

Centralized storage for Tkinter variables and global state that views access.
This avoids tight coupling to TradeBotGUI and prevents state sync issues.

Usage in views:
    from src.ui.shared_state import get_shared_state
    state = get_shared_state()
    state.nifty_enabled.get()  # Read
    state.nifty_enabled.set(True)  # Write
"""

import tkinter as tk
import json
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ─── DEFAULT VALUES (match user specification) ─────────────────────────────
DEFAULTS = {
    "broker": "angel",
    "strategy": "Combined",
    "paper_trading": True,
    "use_tsl": True,
    "kill_bot_limit": False,
    "candle_timeframe": "5m",
    "min_signals": "3",
    "nifty_enabled": True,
    "banknifty_enabled": True,
    "finnifty_enabled": False,
    "nifty_lot": "1",
    "banknifty_lot": "1",
    "finnifty_lot": "1",
    "commodity_enabled": True,
    "equity_enabled": False,
    "commodity_lot": "1",
    "equity_lot": "1",
    "risk_target": "2000",
    "risk_sl": "1000",
    "risk_max_trades": "5",
    "risk_max_daily_loss": "5000",
    "risk_max_cons_sl": "2",
    "brain_control": False,
    "openrouter_key": "",
    "ai_brain_enabled": True,
    "selected_category": "Options",
    "selected_instrument": "NIFTY",
    "selected_lots": "1",
    "gemini_key": "",
    "gemini_model": "gemini-3.1-flash-lite",
    "openai_key": "",
    "anthropic_key": "",
    "voice_assistant_enabled": True,
}

VALID_OPTIONS = {
    "strategy": ["Combined", "EMA-VWAP", "Nifty Options", "ML Pattern"],
    "candle_timeframe": ["1m", "3m", "5m", "15m", "30m", "1h"],
    "min_signals": ["1", "2", "3"]
}


def _get_settings_file() -> str:
    """Return path to the user settings JSON file."""
    try:
        from src.utils.paths import get_path
        return get_path("user_preferences.json")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".tradebot_prefs.json")


class SharedState:
    """Centralized state container for UI-wide variables."""
    
    # Keys that are persisted to disk
    _PERSISTED_KEYS = list(DEFAULTS.keys())
    
    def __init__(self, root: Optional[tk.Tk] = None):
        """Initialize shared state with optional Tk root for creating variables."""
        self.root = root
        self._loading = True  # Suppress saves during initial load
        
        # Load saved preferences (falls back to DEFAULTS)
        saved = self._load_preferences()
        
        def _bool(key):
            return bool(saved.get(key, DEFAULTS[key]))
        
        def _str(key):
            return str(saved.get(key, DEFAULTS[key]))
        
        # ─── TRADING FLAGS ────────────────────────────────────────────────
        self.nifty_enabled = tk.BooleanVar(value=_bool("nifty_enabled"))
        self.banknifty_enabled = tk.BooleanVar(value=_bool("banknifty_enabled"))
        self.finnifty_enabled = tk.BooleanVar(value=_bool("finnifty_enabled"))
        self.commodity_enabled = tk.BooleanVar(value=_bool("commodity_enabled"))
        self.equity_enabled = tk.BooleanVar(value=_bool("equity_enabled"))
        self.paper_trading = tk.BooleanVar(value=_bool("paper_trading"))
        self.brain_control = tk.BooleanVar(value=_bool("brain_control"))
        
        # ─── SHARED CONFIG (sidebar <-> config view sync) ─────────────────
        self.broker = tk.StringVar(value=_str("broker"))
        self.strategy = tk.StringVar(value=_str("strategy"))
        self.use_tsl = tk.BooleanVar(value=_bool("use_tsl"))
        self.kill_bot_limit = tk.BooleanVar(value=_bool("kill_bot_limit"))
        self.candle_timeframe = tk.StringVar(value=_str("candle_timeframe"))
        self.min_signals = tk.StringVar(value=_str("min_signals"))
        self.nifty_lot = tk.StringVar(value=_str("nifty_lot"))
        self.banknifty_lot = tk.StringVar(value=_str("banknifty_lot"))
        self.finnifty_lot = tk.StringVar(value=_str("finnifty_lot"))
        self.commodity_lot = tk.StringVar(value=_str("commodity_lot"))
        self.equity_lot = tk.StringVar(value=_str("equity_lot"))
        
        # ─── RISK RULES ────────────────────────────────────────────────────
        self.risk_target = tk.StringVar(value=_str("risk_target"))
        self.risk_sl = tk.StringVar(value=_str("risk_sl"))
        self.risk_max_trades = tk.StringVar(value=_str("risk_max_trades"))
        self.risk_max_daily_loss = tk.StringVar(value=_str("risk_max_daily_loss"))
        self.risk_max_cons_sl = tk.StringVar(value=_str("risk_max_cons_sl"))
        
        # ─── SINGLE MARKET FOCUS ──────────────────────────────────────────
        self.selected_category = tk.StringVar(value=_str("selected_category"))
        self.selected_instrument = tk.StringVar(value=_str("selected_instrument"))
        self.selected_lots = tk.StringVar(value=_str("selected_lots"))
        
        # ─── AI INTELLIGENCE ──────────────────────────────────────────────
        self.openrouter_key = tk.StringVar(value=_str("openrouter_key"))
        self.ai_brain_enabled = tk.BooleanVar(value=_bool("ai_brain_enabled"))
        self.voice_assistant_enabled = tk.BooleanVar(value=_bool("voice_assistant_enabled"))
        self.gemini_key = tk.StringVar(value=_str("gemini_key"))
        self.gemini_model = tk.StringVar(value=_str("gemini_model"))
        self.openai_key = tk.StringVar(value=_str("openai_key"))
        self.anthropic_key = tk.StringVar(value=_str("anthropic_key"))
        
        # ─── ACTIVE VALIDATIONS ────────────────────────────────────────────
        self._setup_validations()

        # ─── BOT RUNNING STATE (not persisted) ────────────────────────────
        self.bot_running = tk.BooleanVar(value=False)
        # Live session P&L — updated by the trading engine, read by Jarvis and LockScreen
        self.total_pnl = tk.DoubleVar(value=0.0)
        
        # ─── UI STATE ──────────────────────────────────────────────────────
        self.selected_period = tk.StringVar(value="Today")
        
        # ─── CACHES (avoid re-fetching data) ───────────────────────────────
        self.all_trades_cache: list = []
        self.last_trades_refresh: float = 0
        self.last_active_mtime: float = 0
        
        # ─── COMPONENT REFS (for live updates) ─────────────────────────────
        self._live_components: Dict[str, Any] = {}
        
        # Attach auto-save to every persisted variable
        self._loading = False
        
        # Validate options but DO NOT force resets to defaults if a valid alternative exists
        if self.strategy.get() not in VALID_OPTIONS["strategy"]:
            logger.warning(f"Invalid strategy '{self.strategy.get()}', falling back to default")
            self.strategy.set(DEFAULTS["strategy"])
            
        if self.candle_timeframe.get() not in VALID_OPTIONS["candle_timeframe"]:
            logger.warning(f"Invalid timeframe '{self.candle_timeframe.get()}', falling back to default")
            self.candle_timeframe.set(DEFAULTS["candle_timeframe"])
            
        try:
            val = int(self.min_signals.get())
            if val > 3:
                self.min_signals.set("3")
            elif val < 1:
                self.min_signals.set("1")
        except (ValueError, TypeError):
            self.min_signals.set(DEFAULTS["min_signals"])

        # Final pass to ensure no stale empty values from disk persist
        self._validate_lots()

        for key in self._PERSISTED_KEYS:
            var = getattr(self, key, None)
            if var is not None:
                var.trace_add("write", lambda *a: self._save_preferences())
    
    def _load_preferences(self) -> Dict[str, Any]:
        """Load saved preferences from disk. Returns {} on failure."""
        path = _get_settings_file()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data)} preferences from {os.path.basename(path)}")
                return data
        except Exception as e:
            logger.warning(f"Failed to load user preferences: {e}")
            return {}
    
    def _save_preferences(self) -> None:
        """Persist all tracked variables to disk."""
        if self._loading:
            return
        path = _get_settings_file()
        try:
            data = {}
            for key in self._PERSISTED_KEYS:
                var = getattr(self, key, None)
                if var is not None:
                    data[key] = var.get()
            
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(data)} preferences to disk (nifty_lot={data.get('nifty_lot')})")
        except Exception as e:
            logger.warning(f"Failed to save user preferences: {e}")

    def load_from_profile(self, profile: Dict[str, Any]):
        """Update state using a user profile from UserManager."""
        self._loading = True
        try:
            # Standard mappings
            if "strategy" in profile:
                s = profile["strategy"]
                if isinstance(s, dict):
                    self.strategy.set(s.get("name", self.strategy.get()))
                    self.min_signals.set(str(s.get("min_signals", self.min_signals.get())))
                else:
                    self.strategy.set(s)

            if "broker_settings" in profile:
                bs = profile["broker_settings"]
                self.candle_timeframe.set(bs.get("candle_period", self.candle_timeframe.get()))
                self.paper_trading.set(bs.get("paper_trading", self.paper_trading.get()))

            if "instruments" in profile:
                inst = profile["instruments"]
                # Traceable updates - snap back will trigger if these are empty
                self.nifty_lot.set(str(inst.get("nifty_lot", inst.get("nifty_lots", self.nifty_lot.get()))))
                self.banknifty_lot.set(str(inst.get("banknifty_lot", inst.get("banknifty_lots", self.banknifty_lot.get()))))
                self.commodity_lot.set(str(inst.get("commodity_lot", self.commodity_lot.get())))
                self.equity_lot.set(str(inst.get("equity_lot", self.equity_lot.get())))
                
                self.nifty_enabled.set(bool(inst.get("nifty_enabled", self.nifty_enabled.get())))
                self.banknifty_enabled.set(bool(inst.get("banknifty_enabled", self.banknifty_enabled.get())))
                self.commodity_enabled.set(bool(inst.get("commodity_enabled", self.commodity_enabled.get())))
                self.equity_enabled.set(bool(inst.get("equity_enabled", self.equity_enabled.get())))
            
            if "brain_control" in profile:
                self.brain_control.set(bool(profile["brain_control"]))
            
            # Risk rules
            risk = profile.get("risk_rules", {})
            if risk:
                self.risk_target.set(str(risk.get("trade_target_rs", self.risk_target.get())))
                self.risk_sl.set(str(risk.get("trade_sl_rs", self.risk_sl.get())))
                self.risk_max_trades.set(str(risk.get("max_trades_per_day", self.risk_max_trades.get())))
                self.risk_max_daily_loss.set(str(risk.get("max_daily_loss_rs", self.risk_max_daily_loss.get())))
                self.risk_max_cons_sl.set(str(risk.get("max_consecutive_sl", self.risk_max_cons_sl.get())))
                self.kill_bot_limit.set(bool(risk.get("kill_switch", self.kill_bot_limit.get())))

            # Single Market Focus
            self.selected_category.set(str(profile.get("selected_category", self.selected_category.get())))
            self.selected_instrument.set(str(profile.get("selected_instrument", self.selected_instrument.get())))
            self.selected_lots.set(str(profile.get("selected_lots", self.selected_lots.get())))

            if "ai_intelligence" in profile:
                ai = profile["ai_intelligence"]
                self.openrouter_key.set(str(ai.get("openrouter_api_key", self.openrouter_key.get())))
                self.ai_brain_enabled.set(bool(ai.get("ai_brain_enabled", self.ai_brain_enabled.get())))
                self.voice_assistant_enabled.set(bool(ai.get("voice_assistant_enabled", self.voice_assistant_enabled.get())))
                self.gemini_key.set(str(ai.get("gemini_api_key", self.gemini_key.get())))
                self.openai_key.set(str(ai.get("openai_api_key", self.openai_key.get())))
                self.anthropic_key.set(str(ai.get("anthropic_api_key", self.anthropic_key.get())))

            # Enforce sanity check on all variables after load
            self._validate_lots()

            logger.info(f"UI-SYNC: SharedState synchronized with profile (MinSig:{self.min_signals.get()}, Nifty:{self.nifty_lot.get()}, BN:{self.banknifty_lot.get()})")
        except Exception as e:
            logger.error(f"UI-SYNC ERROR: Syncing profile: {e}")
        finally:
            self._loading = False

    def to_profile_dict(self) -> Dict[str, Any]:
        """Convert current shared state to a profile-compatible dictionary (subset of users.json)."""
        return {
            "brain_control": self.brain_control.get(),
            "broker_type": self.broker.get().lower(),
            "broker_settings": {
                "api_mode": "Live" if not self.paper_trading.get() else "Paper",
                "candle_period": self.candle_timeframe.get(),
                "paper_trading": self.paper_trading.get()
            },
            "strategy": {
                "name": self.strategy.get(),
                "min_signals": self.min_signals.get()
            },
            "risk_rules": {
                "trade_target_rs": self.risk_target.get(),
                "trade_sl_rs": self.risk_sl.get(),
                "max_trades_per_day": self.risk_max_trades.get(),
                "max_consecutive_sl": self.risk_max_cons_sl.get(),
                "max_daily_loss_rs": self.risk_max_daily_loss.get(),
                "kill_switch": self.kill_bot_limit.get()
            },
            "selected_category": self.selected_category.get(),
            "selected_instrument": self.selected_instrument.get(),
            "selected_lots": self.selected_lots.get(),
            "ai_intelligence": {
                "openrouter_api_key": self.openrouter_key.get(),
                "ai_brain_enabled": self.ai_brain_enabled.get(),
                "voice_assistant_enabled": self.voice_assistant_enabled.get(),
                "gemini_api_key": self.gemini_key.get(),
                "openai_api_key": self.openai_key.get(),
                "anthropic_api_key": self.anthropic_key.get()
            }
        }

    def _setup_validations(self):
        """Monitor lot variables for invalid values and snap-back to default."""
        for key in ["nifty_lot", "banknifty_lot", "finnifty_lot", "commodity_lot", "equity_lot"]:
            var = getattr(self, key)
            # Use trace_add for real-time validation (UI->State)
            var.trace_add("write", lambda *a, k=key, v=var: self._validate_lots(k, v))

    def _validate_lots(self, key: Optional[str] = None, var: Optional[tk.StringVar] = None):
        """Ensure lot variables contain valid positive integers. Snaps to '1' if invalid."""
        keys = [key] if key else ["nifty_lot", "banknifty_lot", "finnifty_lot", "commodity_lot", "equity_lot"]
        
        for k in keys:
            v = var if var else getattr(self, k)
            current = v.get().strip()
            
            # Snap-back logic: If empty or not a positive integer, reset to "1"
            if not current or not current.isdigit() or current == "0":
                if not self._loading: # Log snap-back if not during initialization
                    logger.warning(f"UI-SYNC: Invalid value '{current}' for {k}. Snapping back to '1'")
                v.set("1")
    
    def register_component(self, name: str, widget: Any) -> None:
        """Register a widget for live updates. Called by views during init."""
        self._live_components[name] = widget
    
    def get_component(self, name: str) -> Optional[Any]:
        """Retrieve registered widget. Returns None if not found."""
        return self._live_components.get(name)
    
    def clear_components(self) -> None:
        """Clear all registered components. Call on cleanup."""
        self._live_components.clear()
    
    def clear_caches(self) -> None:
        """Clear cached data. Call when switching users or forcing refresh."""
        self.all_trades_cache = []
        self.last_trades_refresh = 0
        self.last_active_mtime = 0


# ─── SINGLETON INSTANCE ────────────────────────────────────────────────────

_shared_state_instance: Optional[SharedState] = None


def initialize_shared_state(root: tk.Tk) -> SharedState:
    """Initialize the singleton with Tk root. Call from main app __init__."""
    global _shared_state_instance
    _shared_state_instance = SharedState(root)
    return _shared_state_instance


def get_shared_state() -> SharedState:
    """Get the singleton instance. Views call this to access state."""
    if _shared_state_instance is None:
        raise RuntimeError(
            "Shared state not initialized. Call initialize_shared_state(root) first."
        )
    return _shared_state_instance


def reset_shared_state() -> None:
    """Reset singleton (for cleanup/testing). Views should NOT call this."""
    global _shared_state_instance
    if _shared_state_instance:
        _shared_state_instance.clear_components()
    _shared_state_instance = None
