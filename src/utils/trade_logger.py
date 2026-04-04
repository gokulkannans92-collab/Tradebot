"""
Trade Logger
Appends one row per closed trade to trades_log.csv.
"""

import csv
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("TradeLogger")

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "trades_log.csv")

FIELDNAMES = [
    "user_id",
    "trade_id",
    "date",
    "time",
    "instrument",
    "option_type",
    "strike",
    "expiry",
    "side",
    "entry_price",
    "exit_price",
    "quantity",
    "invested",
    "returns",
    "pnl",
    "exit_reason",
    "strategy_used",
]


def _ensure_header():
    """Create the CSV with header row if it doesn't exist."""
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding='utf-8', errors='replace') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
        logger.info(f"Created trade log: {CSV_PATH}")


def log_trade(
    user_id: str,
    instrument: str,
    side: str,
    entry_price: float,
    exit_price: float,
    quantity: int,
    pnl: float,
    exit_reason: str,
    strategy_used: str,
    option_type: str = "",
    strike: str = "",
    expiry: str = "",
    invested: float = 0.0,
):
    """Append one completed trade record to trades_log.csv."""
    _ensure_header()
    now = datetime.now()
    row = {
        "user_id":      user_id,
        "trade_id":     now.strftime("%Y%m%d%H%M%S%f"),
        "date":         now.strftime("%Y-%m-%d"),
        "time":         now.strftime("%H:%M:%S"),
        "instrument":   instrument,
        "option_type":  option_type,
        "strike":       strike,
        "expiry":       expiry,
        "side":         side,
        "entry_price":  round(entry_price, 2),
        "exit_price":   round(exit_price, 2),
        "quantity":     quantity,
        "invested":     round(invested, 2),
        "returns":      round(invested + pnl, 2),
        "pnl":          round(pnl, 2),
        "exit_reason":  exit_reason,
        "strategy_used": strategy_used,
    }
    try:
        with open(CSV_PATH, "a", newline="", encoding='utf-8', errors='replace') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writerow(row)
        logger.info(f"Trade logged → {instrument} PnL=₹{pnl:.2f} Reason={exit_reason}")
    except Exception as e:
        logger.error(f"Failed to write trade log: {e}")


def get_today_trades() -> list:
    """Return list of today's trade records from the CSV."""
    _ensure_header()
    today_str = datetime.now().strftime("%Y-%m-%d")
    trades = []
    try:
        with open(CSV_PATH, "r", newline="", encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("date") == today_str:
                    trades.append(row)
    except Exception as e:
        logger.error(f"Failed to read trade log: {e}")
    return trades


def get_all_trades() -> list:
    """Return all trade records from the CSV."""
    _ensure_header()
    trades = []
    try:
        with open(CSV_PATH, "r", newline="", encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            trades = list(reader)
    except Exception as e:
        logger.error(f"Failed to read trade log: {e}")
    return trades
