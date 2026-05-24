"""
User Settings Module

Per-user configuration and risk parameters.
"""

import os
from typing import Optional, Dict, Any
from src.config.enums import BrokerType
from src.config.secrets import SecureCredentialVault


class UserSettings:
    """Per-user settings loaded from users.json or environment."""
    
    def __init__(self, user_config: Optional[Dict[str, Any]] = None):
        # Initialize secure credential vault
        self._vault = SecureCredentialVault()
        
        if user_config:
            self._load_from_dict(user_config)
        else:
            self._load_from_env()
    
    def _load_from_dict(self, config: Dict[str, Any]):
        """Load user settings from dictionary (e.g., users.json)."""
        self.user_id = config.get("user_id", "")
        self.name = config.get("name", "")
        self.broker_type = BrokerType.from_string(config.get("broker_type", "MOCK"))
        
        # Helper to find keys in root or nested dicts
        def _get_val(key, default, section=None):
            if section and section in config and isinstance(config[section], dict):
                return config[section].get(key, config.get(key, default))
            return config.get(key, default)

        # Broker credentials - load from secure vault first, fallback to config/env
        self.ZERODHA_API_KEY = self._vault.get_credential("ZERODHA_API_KEY") or _get_val("zerodha_api_key", "") or os.getenv("ZERODHA_API_KEY", "")
        self.ZERODHA_ACCESS_TOKEN = self._vault.get_credential("ZERODHA_ACCESS_TOKEN") or _get_val("zerodha_access_token", "") or os.getenv("ZERODHA_ACCESS_TOKEN", "")
        self.ZERODHA_API_SECRET = self._vault.get_credential("ZERODHA_API_SECRET") or _get_val("zerodha_api_secret", "") or os.getenv("ZERODHA_API_SECRET", "")
        
        self.ANGEL_API_KEY = self._vault.get_credential("ANGEL_API_KEY") or _get_val("api_key", "", "credentials") or os.getenv("ANGEL_API_KEY", "") or os.getenv("API_KEY", "")
        self.ANGEL_API_SECRET = self._vault.get_credential("ANGEL_API_SECRET") or _get_val("api_secret", "", "credentials") or os.getenv("ANGEL_API_SECRET", "") or os.getenv("API_SECRET", "")
        self.ANGEL_CLIENT_ID = self._vault.get_credential("ANGEL_CLIENT_ID") or _get_val("client_id", "", "credentials") or os.getenv("ANGEL_CLIENT_ID", "") or os.getenv("CLIENT_ID", "")
        self.ANGEL_PASSWORD = self._vault.get_credential("ANGEL_PASSWORD") or _get_val("password", "", "credentials") or os.getenv("ANGEL_PASSWORD", "") or os.getenv("PASSWORD", "")
        self.ANGEL_TOTP_SECRET = self._vault.get_credential("ANGEL_TOTP_SECRET") or _get_val("totp_secret", "", "credentials") or os.getenv("ANGEL_TOTP_SECRET", "") or os.getenv("TOTP_SECRET", "")
        
        # AI Intelligence keys
        self.GEMINI_API_KEY = self._vault.get_credential("GEMINI_API_KEY") or _get_val("gemini_api_key", "", "ai_intelligence") or os.getenv("GEMINI_API_KEY", "")
        self.OPENAI_API_KEY = self._vault.get_credential("OPENAI_API_KEY") or _get_val("openai_api_key", "", "ai_intelligence") or os.getenv("OPENAI_API_KEY", "")
        self.ANTHROPIC_API_KEY = self._vault.get_credential("ANTHROPIC_API_KEY") or _get_val("anthropic_api_key", "", "ai_intelligence") or os.getenv("ANTHROPIC_API_KEY", "")
        self.OPENROUTER_API_KEY = self._vault.get_credential("OPENROUTER_API_KEY") or _get_val("openrouter_api_key", "", "ai_intelligence") or os.getenv("OPENROUTER_API_KEY", "")
        
        # AI Control
        self.AI_BRAIN_ENABLED = bool(_get_val("ai_brain_enabled", True, "ai_intelligence"))
        
        # Trading capital (nested in risk_rules)
        self.TOTAL_CAPITAL = float(_get_val("total_capital", 1000, "risk_rules"))
        self.TRADE_CAPITAL = float(_get_val("trade_capital", 1000, "risk_rules"))
        
        # Risk parameters (nested in risk_rules)
        self.MAX_TRADES_PER_DAY = int(_get_val("max_trades_per_day", 5, "risk_rules"))
        self.MAX_DAILY_LOSS = float(_get_val("max_daily_loss_rs", 15000, "risk_rules"))
        self.MAX_DAILY_LOSS_PCT = float(_get_val("max_daily_loss_pct", 5, "risk_rules"))
        self.MAX_RISK_PER_TRADE_PERCENT = float(_get_val("max_risk_per_trade_percent", 2.0, "risk_rules"))
        
        # Trade parameters
        self.TRADE_TARGET_RS = float(_get_val("trade_target_rs", 25000, "risk_rules"))
        self.TRADE_SL_RS = float(_get_val("trade_sl_rs", 1000, "risk_rules"))
        
        # Strategy settings (nested in strategy or instruments)
        strat = config.get("strategy", {})
        if isinstance(strat, dict):
            self.NIFTY_OPTIONS_STRATEGY = strat.get("name", "") == "Combined"
            self.USE_TSL = _get_val("use_tsl", True, "strategy")
            self.TSL_ACTIVATION_PERCENT = float(_get_val("tsl_activation_percent", 0.5, "strategy"))
            self.TSL_LOCK_PERCENT = float(_get_val("tsl_lock_percent", 0.1, "strategy"))
            self.MIN_SIGNALS_REQUIRED = int(_get_val("min_signals", 3, "strategy"))
        else:
            self.NIFTY_OPTIONS_STRATEGY = False
            self.USE_TSL = True
            self.TSL_ACTIVATION_PERCENT = 0.5
            self.TSL_LOCK_PERCENT = 0.1
            self.MIN_SIGNALS_REQUIRED = 3
        
        inst = config.get("instruments", {})
        if isinstance(inst, dict):
            self.NIFTY_LOTS = int(inst.get("nifty_lot", inst.get("nifty_lots", 1)))
            self.BANKNIFTY_LOTS = int(inst.get("banknifty_lot", inst.get("banknifty_lots", 1)))
            self.FINNIFTY_LOTS = int(inst.get("finnifty_lot", inst.get("finnifty_lots", 1)))
            self.COMMODITY_LOTS = int(inst.get("commodity_lot", 1))
            self.EQUITY_LOTS = int(inst.get("equity_lot", 1))
            self.BANKNIFTY_ENABLED = inst.get("banknifty_enabled", True)
            self.FINNIFTY_ENABLED = inst.get("finnifty_enabled", False)
            self.COMMODITY_ENABLED = inst.get("commodity_enabled", True)
            self.EQUITY_ENABLED = inst.get("equity_enabled", False)
        else:
            # Fallback to root/defaults
            self.NIFTY_LOTS = int(config.get("nifty_lot", config.get("nifty_lots", 1)))
            self.BANKNIFTY_LOTS = int(config.get("banknifty_lot", config.get("banknifty_lots", 1)))
            self.FINNIFTY_LOTS = int(config.get("finnifty_lot", config.get("finnifty_lots", 1)))
            self.COMMODITY_LOTS = int(config.get("commodity_lot", 1))
            self.EQUITY_LOTS = int(config.get("equity_lot", 1))
            self.BANKNIFTY_ENABLED = config.get("banknifty_enabled", True)
            self.FINNIFTY_ENABLED = config.get("finnifty_enabled", False)
            self.COMMODITY_ENABLED = config.get("commodity_enabled", True)
            self.EQUITY_ENABLED = config.get("equity_enabled", False)

        # Safety guard: TRADE_CAPITAL must never exceed TOTAL_CAPITAL
        if self.TRADE_CAPITAL > self.TOTAL_CAPITAL:
            import logging as _log
            _log.getLogger(__name__).warning(
                f"[UserSettings] TRADE_CAPITAL ({self.TRADE_CAPITAL}) exceeds TOTAL_CAPITAL "
                f"({self.TOTAL_CAPITAL}). Capping TRADE_CAPITAL to TOTAL_CAPITAL."
            )
            self.TRADE_CAPITAL = self.TOTAL_CAPITAL

        # Broker settings
        bs = config.get("broker_settings", {})
        if isinstance(bs, dict):
            self.PAPER_TRADING = bs.get("paper_trading", True)
            self.CANDLE_PERIOD_SECONDS = 300 # Default 5m
            cp = bs.get("candle_period")
            if cp == "1m": self.CANDLE_PERIOD_SECONDS = 60
            elif cp == "3m": self.CANDLE_PERIOD_SECONDS = 180
            elif cp == "5m": self.CANDLE_PERIOD_SECONDS = 300
            elif cp == "15m": self.CANDLE_PERIOD_SECONDS = 900
        else:
            self.PAPER_TRADING = config.get("paper_trading", True)
            self.CANDLE_PERIOD_SECONDS = 300

        # Notifications (nested in notifications)
        notif = config.get("notifications", {})
        if isinstance(notif, dict):
            self.TELEGRAM_BOT_TOKEN = notif.get("telegram_bot_token", "")
            self.TELEGRAM_CHAT_ID = notif.get("telegram_chat_id", "")
        else:
            self.TELEGRAM_BOT_TOKEN = config.get("telegram_bot_token", "")
            self.TELEGRAM_CHAT_ID = config.get("telegram_chat_id", "")
        
        self.KILL_AFTER_DAILY_LIMIT = _get_val("kill_after_daily_limit", False, "risk_rules")
    
    def _load_from_env(self):
        """Load user settings from environment variables."""
        self.user_id = os.getenv("USER_ID", "default")
        self.name = os.getenv("USER_NAME", "Default User")
        
        broker_type = os.getenv("BROKER_TYPE", "MOCK").upper()
        self.broker_type = BrokerType.from_string(broker_type)
        
        # Broker credentials
        self.ZERODHA_API_KEY = os.getenv("ZERODHA_API_KEY", "")
        self.ZERODHA_ACCESS_TOKEN = os.getenv("ZERODHA_ACCESS_TOKEN", "")
        self.ZERODHA_API_SECRET = os.getenv("ZERODHA_API_SECRET", "")
        
        self.ANGEL_API_KEY = os.getenv("API_KEY", os.getenv("ANGEL_API_KEY", ""))
        self.ANGEL_API_SECRET = os.getenv("API_SECRET", os.getenv("ANGEL_API_SECRET", ""))
        self.ANGEL_CLIENT_ID = os.getenv("CLIENT_ID", os.getenv("ANGEL_CLIENT_ID", ""))
        self.ANGEL_PASSWORD = os.getenv("PASSWORD", os.getenv("ANGEL_PASSWORD", ""))
        self.ANGEL_TOTP_SECRET = os.getenv("TOTP_SECRET", os.getenv("ANGEL_TOTP_SECRET", ""))
        
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        
        self.UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY", "")
        self.UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET", "")
        self.UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN", "")
        
        self.GROWW_API_KEY = os.getenv("GROWW_API_KEY", "")
        
        # Trading capital
        self.TOTAL_CAPITAL = float(os.getenv("TOTAL_CAPITAL", 1000))
        self.TRADE_CAPITAL = float(os.getenv("TRADE_CAPITAL", 1000))
        
        # Risk parameters
        self.MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", 5))
        self.MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", 15000))
        self.MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", 5))
        self.MAX_RISK_PER_TRADE_PERCENT = float(os.getenv("MAX_RISK_PER_TRADE_PERCENT", 2.0))
        
        # Trade parameters
        self.TRADE_TARGET_RS = float(os.getenv("TRADE_TARGET_RS", 25000))
        self.TRADE_SL_RS = float(os.getenv("TRADE_SL_RS", 1000))
        self.USE_TSL = os.getenv("USE_TSL", "true").lower() == "true"
        self.TSL_ACTIVATION_PERCENT = float(os.getenv("TSL_ACTIVATION_PERCENT", 0.5))
        self.TSL_LOCK_PERCENT = float(os.getenv("TSL_LOCK_PERCENT", 0.1))
        
        # Strategy settings
        self.NIFTY_OPTIONS_STRATEGY = os.getenv("NIFTY_OPTIONS_STRATEGY", "true").lower() == "true"
        self.BANKNIFTY_ENABLED = os.getenv("BANKNIFTY_ENABLED", "true").lower() == "true"
        self.FINNIFTY_ENABLED = os.getenv("FINNIFTY_ENABLED", "false").lower() == "true"
        
        self.FINNIFTY_LOTS = int(os.getenv("FINNIFTY_LOT", os.getenv("FINNIFTY_LOTS", 1)))
        self.COMMODITY_LOTS = int(os.getenv("COMMODITY_LOT", 1))
        self.EQUITY_LOTS = int(os.getenv("EQUITY_LOT", 1))
        
        self.COMMODITY_ENABLED = os.getenv("COMMODITY_ENABLED", "true").lower() == "true"
        self.EQUITY_ENABLED = os.getenv("EQUITY_ENABLED", "false").lower() == "true"
        
        # Notifications
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
        
        # Other settings
        self.PAPER_TRADING = os.getenv("PAPER_TRADING", "true").lower() == "true"
        self.KILL_AFTER_DAILY_LIMIT = os.getenv("KILL_AFTER_DAILY_LIMIT", "false").lower() == "true"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "broker_type": self.broker_type.value,
            "total_capital": self.TOTAL_CAPITAL,
            "trade_capital": self.TRADE_CAPITAL,
            "max_trades_per_day": self.MAX_TRADES_PER_DAY,
            "max_daily_loss": self.MAX_DAILY_LOSS,
            "trade_target_rs": self.TRADE_TARGET_RS,
            "trade_sl_rs": self.TRADE_SL_RS,
            "use_tsl": self.USE_TSL,
            "tsl_activation_percent": self.TSL_ACTIVATION_PERCENT,
            "tsl_lock_percent": self.TSL_LOCK_PERCENT,
            "nifty_options_strategy": self.NIFTY_OPTIONS_STRATEGY,
            "banknifty_enabled": self.BANKNIFTY_ENABLED,
            "paper_trading": self.PAPER_TRADING,
            "kill_after_daily_limit": self.KILL_AFTER_DAILY_LIMIT,
        }
    
    # ── Broker Credential Properties (for backward compatibility) ────────────────────
    
    @property
    def API_KEY(self) -> str:
        """Get API key for the configured broker."""
        if self.broker_type == BrokerType.ZERODHA:
            return self.ZERODHA_API_KEY
        elif self.broker_type == BrokerType.ANGEL:
            return self.ANGEL_API_KEY
        elif self.broker_type == BrokerType.UPSTOX:
            return self.UPSTOX_API_KEY
        elif self.broker_type == BrokerType.GROWW:
            return self.GROWW_API_KEY
        return ""
    
    @property
    def API_SECRET(self) -> str:
        """Get API secret for the configured broker."""
        if self.broker_type == BrokerType.ZERODHA:
            return self.ZERODHA_API_SECRET
        elif self.broker_type == BrokerType.ANGEL:
            return self.ANGEL_API_SECRET
        elif self.broker_type == BrokerType.UPSTOX:
            return self.UPSTOX_API_SECRET
        return ""
    
    @property
    def ACCESS_TOKEN(self) -> str:
        """Get access token for the configured broker."""
        if self.broker_type == BrokerType.ZERODHA:
            return self.ZERODHA_ACCESS_TOKEN
        elif self.broker_type == BrokerType.UPSTOX:
            return self.UPSTOX_ACCESS_TOKEN
        return ""
    
    @property
    def CLIENT_ID(self) -> str:
        """Get client ID for the configured broker."""
        if self.broker_type == BrokerType.ANGEL:
            return self.ANGEL_CLIENT_ID
        return ""
    
    @property
    def PASSWORD(self) -> str:
        """Get password for the configured broker."""
        if self.broker_type == BrokerType.ANGEL:
            return self.ANGEL_PASSWORD
        return ""
    
    @property
    def TOTP_SECRET(self) -> str:
        """Get TOTP secret for the configured broker."""
        if self.broker_type == BrokerType.ANGEL:
            return self.ANGEL_TOTP_SECRET
        return ""

    @property
    def LOT_SIZE(self) -> int:
        """Fallback to global NIFTY lot size."""
        from src.config.app_settings import AppSettings
        return AppSettings.LOT_SIZE

    @property
    def BANKNIFTY_LOT_SIZE(self) -> int:
        """Fallback to global BANKNIFTY lot size."""
        from src.config.app_settings import AppSettings
        return AppSettings.BANKNIFTY_LOT_SIZE