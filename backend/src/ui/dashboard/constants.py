"""
File paths for TradeBot Dashboard
Centralized path definitions
"""
import os
from src.utils.paths import get_path, get_data_dir

# Data directory
DATA_DIR = get_data_dir()

# ─── CORE DATA FILES ───────────────────────────────────────────────────────────────────
ACTIVE_TRADES_FILE = get_path('.active_trades')
USERS_FILE = get_path('users.json')
LOG_FILE = get_path('trade_bot.log')

# ─── COMMAND FILES ────────────────────────────────────────────────────────────────
TRADE_COMMANDS_FILE = get_path('.trade_commands.json')
STOP_TRIGGER_FILE = get_path('.stop_trigger')

# ─── CACHE & TEMP FILES ────────────────────────────────────────────────────
SESSION_CACHE_FILE = get_path('.session_cache')
BOT_PID_FILE = get_path('.bot.pid')

# ─── BROKER FILES ──────────────────────────────────────────────────────
INSTRUMENTS_FILE = get_path('angel_instruments.json')

# ─── CHART DATA ─────────────────────────────────────────────────────
NIFTY_CHART_FILE = get_path('.nifty_chart.json')
BANKNIFTY_CHART_FILE = get_path('.bn_chart.json')

# ─── ENVIRONMENT ──────────────────────────────────────────────────────
ENV_FILE = get_path('.env')

# ─── LOG BACKUPS ─────────────────────────────────────────────────────
def get_log_backup_path(date_obj) -> str:
    """Get path for log file backup."""
    return get_path(f"trade_bot.log.{date_obj.strftime('%Y-%m-%d')}")

# ─── PAUSE FILES ────────────────────────────────────────────────────
PAUSED_USERS_FILE = get_path('paused_users.json')