import os
import json
from datetime import time
from dotenv import load_dotenv

# Load environment variables from .env file
import sys
if getattr(sys, 'frozen', False):
    PROJECT_DIR = os.path.dirname(sys.executable)
else:
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_DIR = os.path.dirname(os.path.dirname(PROJECT_DIR))

load_dotenv(os.path.join(PROJECT_DIR, ".env"))

from src.utils.security import encrypt_credentials, decrypt_credentials

class Config:
    """Global configuration settings shared across all users."""
    # ── Market Timings (IST) ───────────────────────────────────────────
    MARKET_OPEN  = time(9, 15)
    MARKET_CLOSE = time(15, 30)
    ENTRY_START  = time(9, 20)
    ENTRY_END    = time(14, 30)   # no new trades after 2:30 PM
    EXIT_ALL     = time(15, 10)   # force-exit all positions at 3:10 PM

    # Global Settings
    PAPER_TRADING         = os.getenv("PAPER_TRADING", "True").lower() == "true"
    CANDLE_PERIOD_SECONDS = int(os.getenv("CANDLE_PERIOD_SECONDS", 300))
    MIN_SIGNALS_REQUIRED  = int(os.getenv("MIN_SIGNALS_REQUIRED", 3))
    USE_TSL               = os.getenv("USE_TSL", "True").lower() == "true"
    TSL_ACTIVATION_PERCENT = float(os.getenv("TSL_ACTIVATION_PERCENT", 0.5))
    TSL_LOCK_PERCENT      = float(os.getenv("TSL_LOCK_PERCENT", 0.1))
    KILL_AFTER_DAILY_LIMIT = os.getenv("KILL_AFTER_DAILY_LIMIT", "False").lower() == "true"

    # Asset Settings
    TRADING_SYMBOL_PREFIX = os.getenv("TRADING_SYMBOL_PREFIX", "NIFTY")
    LOT_SIZE              = int(os.getenv("LOT_SIZE", 65))
    NIFTY_OPTIONS_STRATEGY = os.getenv("NIFTY_OPTIONS_STRATEGY", "True").lower() == "true"
    NIFTY_STRIKE_STEP      = int(os.getenv("NIFTY_STRIKE_STEP", 50))
    
    BANKNIFTY_ENABLED     = os.getenv("BANKNIFTY_ENABLED", "True").lower() == "true"
    BANKNIFTY_LOT_SIZE    = int(os.getenv("BANKNIFTY_LOT_SIZE", 15))
    BANKNIFTY_STRIKE_STEP = int(os.getenv("BANKNIFTY_STRIKE_STEP", 100))

    NIFTY_LOTS            = int(os.getenv("NIFTY_LOTS", 1))
    BANKNIFTY_LOTS        = int(os.getenv("BANKNIFTY_LOTS", 1))

    USERS_FILE = os.path.join(PROJECT_DIR, "data", "users.json")

    @staticmethod
    def load_users():
        if not os.path.exists(Config.USERS_FILE):
            return []
        try:
            with open(Config.USERS_FILE, "r") as f:
                users = json.load(f)
            for user in users:
                if "credentials" in user and user["credentials"]:
                    user["credentials"] = decrypt_credentials(user["credentials"])
                if "notifications" in user and user["notifications"]:
                    user["notifications"] = decrypt_credentials(user["notifications"])
            return users
        except Exception as e:
            print(f"Error loading users: {e}")
            return []

    @staticmethod
    def save_user(user_data: dict) -> bool:
        """Append a new user to users.json."""
        users = Config.load_users()
        if any(u["name"] == user_data["name"] for u in users):
            return False
        if "credentials" in user_data and user_data["credentials"]:
            user_data["credentials"] = encrypt_credentials(user_data["credentials"])
        if "notifications" in user_data and user_data["notifications"]:
            user_data["notifications"] = encrypt_credentials(user_data["notifications"])
        users.append(user_data)
        try:
            with open(Config.USERS_FILE, "w") as f:
                json.dump(users, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving user: {e}")
            return False

    @staticmethod
    def update_user(user_id: str, updates: dict) -> bool:
        """Update specific fields for a user in users.json."""
        users = Config.load_users()
        updated = False
        for u in users:
            if u["user_id"] == user_id:
                if "risk_rules" in updates: u.setdefault("risk_rules", {}).update(updates.pop("risk_rules"))
                if "credentials" in updates: 
                    updates["credentials"] = encrypt_credentials(updates.pop("credentials"))
                if "notifications" in updates:
                    updates["notifications"] = encrypt_credentials(updates.pop("notifications"))
                u.update(updates)
                updated = True
                break
        if updated:
            try:
                with open(Config.USERS_FILE, "w") as f: json.dump(users, f, indent=2)
                return True
            except Exception as e:
                print(f"Error updating user: {e}")
                return False
        return False

    @staticmethod
    def delete_user(user_id: str) -> bool:
        """Permanently remove a user from users.json."""
        users = Config.load_users()
        initial_count = len(users)
        users = [u for u in users if u["user_id"] != user_id]
        
        if len(users) < initial_count:
            try:
                with open(Config.USERS_FILE, "w") as f:
                    json.dump(users, f, indent=2)
                return True
            except Exception as e:
                print(f"Error deleting user: {e}")
                return False
        return False

class UserConfig:
    """User-specific configuration overrides."""
    def __init__(self, user_dict):
        self.user_id = user_dict.get("user_id")
        self.name = user_dict.get("name")
        self.broker_name = user_dict.get("broker_type", "MOCK").upper()
        
        # Credentials
        creds = user_dict.get("credentials", {})
        # Credentials
        creds = user_dict.get("credentials", {})
        br = self.broker_name.lower() + "_"
        
        def _get_cred(key):
            # Prefer broker-prefixed key (e.g., 'angel_api_key') over generic key ('api_key')
            return creds.get(br + key.lower(), creds.get(key.lower(), ""))

        self.API_KEY = _get_cred("api_key")
        self.API_SECRET = _get_cred("api_secret")
        self.ACCESS_TOKEN = _get_cred("access_token")
        self.CLIENT_ID = _get_cred("client_id")
        self.PASSWORD = _get_cred("password")
        self.TOTP_SECRET = _get_cred("totp_secret")
        self.GROWW_EMAIL = _get_cred("groww_email")
        self.GROWW_PASSWORD = _get_cred("groww_password")

        # Risk Rules
        risk = user_dict.get("risk_rules", {})
        self.TOTAL_CAPITAL = float(risk.get("total_capital", 100000))
        self.TRADE_CAPITAL = float(risk.get("trade_capital", 10000))
        self.MAX_TRADES_PER_DAY = int(risk.get("max_trades_per_day", 2))
        self.MAX_DAILY_LOSS_PCT = float(risk.get("max_daily_loss_pct", 15.0)) # Percentage
        self.TRADE_TARGET_RS = float(risk.get("trade_target_rs", 2000))
        self.TRADE_SL_RS = float(risk.get("trade_sl_rs", 1000))
        self.MIN_SIGNALS_REQUIRED = int(risk.get("min_signals", 3))
        self.NIFTY_LOTS = int(risk.get("nifty_lots", 1))
        self.BANKNIFTY_LOTS = int(risk.get("banknifty_lots", 1))

        # Notifications
        notif = user_dict.get("notifications", {})
        self.TELEGRAM_BOT_TOKEN = notif.get("telegram_bot_token", "")
        self.TELEGRAM_CHAT_ID = notif.get("telegram_chat_id", "")

        # Inherit global settings
        self.PAPER_TRADING = Config.PAPER_TRADING
        self.USE_TSL = Config.USE_TSL
        self.TSL_ACTIVATION_PERCENT = Config.TSL_ACTIVATION_PERCENT
        self.TSL_LOCK_PERCENT = Config.TSL_LOCK_PERCENT
        self.TRADING_SYMBOL_PREFIX = Config.TRADING_SYMBOL_PREFIX
        self.LOT_SIZE = Config.LOT_SIZE
        self.NIFTY_STRIKE_STEP = Config.NIFTY_STRIKE_STEP
        self.NIFTY_OPTIONS_STRATEGY = Config.NIFTY_OPTIONS_STRATEGY
        self.BANKNIFTY_ENABLED = Config.BANKNIFTY_ENABLED
        self.BANKNIFTY_LOT_SIZE = Config.BANKNIFTY_LOT_SIZE
        self.BANKNIFTY_STRIKE_STEP = Config.BANKNIFTY_STRIKE_STEP
        self.EXIT_ALL = Config.EXIT_ALL
        self.ENTRY_START = Config.ENTRY_START
        self.ENTRY_END = Config.ENTRY_END
        self.MARKET_OPEN = Config.MARKET_OPEN
        self.MARKET_CLOSE = Config.MARKET_CLOSE
        self.KILL_AFTER_DAILY_LIMIT = Config.KILL_AFTER_DAILY_LIMIT

if __name__ == "__main__":
    print(f"Trading Bot Config for {Config.TRADING_SYMBOL_PREFIX}")
    print(f"Paper Trading   : {Config.PAPER_TRADING}")
    users = Config.load_users()
    print(f"Loaded {len(users)} users.")
