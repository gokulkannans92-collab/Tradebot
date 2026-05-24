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

from src.utils.paths import get_path
CSV_PATH = get_path("trades_log.csv")

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


from src.persistence.database import get_database

def log_trade(*args, **kwargs):
    """
    Deprecated: Trades are now logged directly to SQLite Database in TradeTracker.
    We keep this function as a no-op to maintain backward compatibility.
    """
    pass

def log_trade_to_csv(trade) -> None:
    """
    Append a trade record to trades_log_history.csv and trades_log.csv.
    Accepts a TradeRecord object or a dictionary.
    """
    from src.utils.paths import get_path
    
    # Extract fields from TradeRecord or dict
    if hasattr(trade, '__dict__'):
        t_dict = trade.__dict__
    else:
        t_dict = trade
        
    # Split entry/exit ISO time into date and time
    ts = t_dict.get('exit_time') or t_dict.get('entry_time', '')
    date_val = ""
    time_val = ""
    if ts:
        if 'T' in ts:
            try:
                date_val, time_val = ts.split('T')
                time_val = time_val.split('.')[0] # Remove microseconds
            except Exception:
                date_val = ts
        else:
            date_val = ts
            
    pnl = float(t_dict.get('pnl', 0))
    invested = float(t_dict.get('invested', 0))
    trade_id = str(t_dict.get('id', ''))
    if not trade_id or trade_id == 'None':
        trade_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    
    row = {
        "user_id":      t_dict.get('user_id', ''),
        "trade_id":     trade_id,
        "date":         date_val,
        "time":         time_val,
        "instrument":   t_dict.get('symbol', ''),
        "option_type":  t_dict.get('option_type', ''),
        "strike":       t_dict.get('strike', ''),
        "expiry":       t_dict.get('expiry', ''),
        "side":         t_dict.get('side', ''),
        "entry_price":  t_dict.get('entry_price', 0),
        "exit_price":   t_dict.get('exit_price', 0),
        "quantity":     t_dict.get('quantity', 0),
        "invested":     invested,
        "returns":      round(invested + pnl, 2),
        "pnl":          pnl,
        "exit_reason":  t_dict.get('exit_reason', ''),
        "strategy_used": t_dict.get('strategy', ''),
    }
    
    # Synchronize to BOTH trades_log_history.csv and trades_log.csv
    for filename in ["trades_log_history.csv", "trades_log.csv"]:
        csv_path = get_path(filename)
        write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        try:
            with open(csv_path, "a", newline="", encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
            logger.info(f"📝 Synced trade {row['trade_id']} to {filename}")
        except Exception as e:
            logger.error(f"Failed to sync trade to {filename}: {e}")

def _db_to_csv_row(trade_dict: dict) -> dict:
    """Normalize a database record to the dictionary format expected by the GUI."""
    # Split ISO exit_time (e.g. 2026-04-20T12:38:49) into Date and Time
    ts = trade_dict.get('exit_time') or trade_dict.get('entry_time', '')
    date_val = ""
    time_val = ""
    if ts:
        if 'T' in ts:
            date_val, time_val = ts.split('T')
            time_val = time_val.split('.')[0] # Remove microseconds
        else:
            date_val = ts
            
    pnl = float(trade_dict.get('pnl', 0))
    invested = float(trade_dict.get('invested', 0))
    
    return {
        "user_id":      trade_dict.get('user_id', ''),
        "trade_id":     str(trade_dict.get('id', '')),
        "date":         date_val,
        "time":         time_val,
        "instrument":   trade_dict.get('symbol', ''),
        "option_type":  trade_dict.get('option_type', ''),
        "strike":       trade_dict.get('strike', ''),
        "expiry":       trade_dict.get('expiry', ''),
        "side":         trade_dict.get('side', ''),
        "entry_price":  trade_dict.get('entry_price', 0),
        "exit_price":   trade_dict.get('exit_price', 0),
        "quantity":     trade_dict.get('quantity', 0),
        "invested":     invested,
        "returns":      round(invested + pnl, 2),
        "pnl":          pnl,
        "exit_reason":  trade_dict.get('exit_reason', ''),
        "strategy_used": trade_dict.get('strategy', ''),
    }

def get_today_trades() -> list:
    """Return list of today's trade records from the Database."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    return [t for t in get_all_trades() if t.get("date") == today_str]

def get_all_trades() -> list:
    """Return all trade records from the Database, unifying the data source."""
    try:
        db = get_database()
        raw_trades = db.get_trades(limit=5000)
        return [_db_to_csv_row(t) for t in raw_trades]
    except Exception as e:
        logger.error(f"Failed to read trades from database: {e}")
        return []
