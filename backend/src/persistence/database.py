"""
Database Layer

SQLite database for TradeBot with support for swapping to PostgreSQL.
"""

import sqlite3
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import os

from src.utils.paths import get_data_dir

logger = logging.getLogger(__name__)

# Database path configuration
DATA_DIR = get_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "tradebot.db")


class DatabaseError(Exception):
    """Database operation error."""
    pass


@dataclass
class TradeRecord:
    """Trade record data class."""
    id: Optional[int] = None
    user_id: str = ""
    symbol: str = ""
    side: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    pnl: float = 0.0
    entry_time: str = ""
    exit_time: str = ""
    exit_reason: str = ""
    strategy: str = ""
    option_type: str = ""
    strike: str = ""
    expiry: str = ""
    invested: float = 0.0


class Database:
    """
    SQLite database manager for TradeBot.
    """
    
    _instance = None
    
    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = None):
        if self._initialized and db_path is None:
            return
        
        self.db_path = db_path or DB_PATH
        self._initialized = True
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency and crash recovery
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA cache_size=1000;")
            
            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL DEFAULT 0,
                    quantity INTEGER NOT NULL,
                    pnl REAL DEFAULT 0,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    exit_reason TEXT,
                    strategy TEXT,
                    option_type TEXT,
                    strike TEXT,
                    expiry TEXT,
                    invested REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            
            # Daily stats table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    won_trades INTEGER DEFAULT 0,
                    lost_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, date)
                )
            """)
            
            # Active positions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    sl REAL,
                    target REAL,
                    option_type TEXT,
                    strike TEXT,
                    expiry TEXT,
                    opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, symbol)
                )
            """)
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    broker_type TEXT,
                    config_json TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Brain journal table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS brain_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    market TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, market)
                )
            """)
            
            # Settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_user_date ON trades(user_id, entry_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_brain_date ON brain_journal(date)")
            
            # Run migrations (ensure all tables exist first)
            self._run_migrations(cursor)
            
            conn.commit()
            
            # Final verification of schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            required = ['trades', 'daily_stats', 'positions', 'users', 'settings']
            missing = [t for t in required if t not in tables]
            
            if missing:
                logger.error(f"❌ DATABASE INTEGRITY ERROR: Missing tables: {missing}")
                raise DatabaseError(f"Failed to initialize core tables: {missing}")
                
            logger.info(f"✅ Database fully initialized with {len(tables)} tables at {self.db_path}")
    
    def _run_migrations(self, cursor):
        """Run database migrations to update schema."""
        try:
            # Check if trades table has entry_time column
            cursor.execute("PRAGMA table_info(trades)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Migrate trades table - add missing columns
            missing_columns = {
                'entry_price': 'REAL DEFAULT 0',
                'exit_price': 'REAL DEFAULT 0',
                'entry_time': 'TEXT DEFAULT CURRENT_TIMESTAMP',
                'exit_time': 'TEXT',
                'exit_reason': 'TEXT',
                'strategy': 'TEXT',
                'option_type': 'TEXT',
                'strike': 'TEXT',
                'expiry': 'TEXT',
                'invested': 'REAL DEFAULT 0'
            }
            
            for col_name, col_def in missing_columns.items():
                if col_name not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_def}")
                        logger.info(f"Added column 'trades.{col_name}'")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e):
                            logger.debug(f"Column 'trades.{col_name}' already exists")
                        else:
                            raise
            
            # Migrate positions table
            cursor.execute("PRAGMA table_info(positions)")
            pos_columns = [row[1] for row in cursor.fetchall()]
            
            pos_missing = {
                'sl': 'REAL',
                'target': 'REAL',
                'option_type': 'TEXT',
                'strike': 'TEXT',
                'expiry': 'TEXT',
                'opened_at': 'TEXT DEFAULT CURRENT_TIMESTAMP'
            }
            
            for col_name, col_def in pos_missing.items():
                if col_name not in pos_columns:
                    try:
                        cursor.execute(f"ALTER TABLE positions ADD COLUMN {col_name} {col_def}")
                        logger.info(f"Added column 'positions.{col_name}'")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e):
                            logger.debug(f"Column 'positions.{col_name}' already exists")
                        else:
                            raise
            
        except Exception as e:
            logger.warning(f"Migration error (non-critical): {e}")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # ── Trade Operations ───────────────────────────────────────────────
    
    def insert_trade(self, trade: TradeRecord) -> int:
        """Insert a trade record."""
        # Input validation
        if not trade.user_id or not trade.user_id.strip():
            raise ValueError("user_id is required and cannot be empty")
        if not trade.symbol or not trade.symbol.strip():
            raise ValueError("symbol is required and cannot be empty")
        if not trade.side or trade.side not in ['BUY', 'SELL']:
            raise ValueError("side must be 'BUY' or 'SELL'")
        if trade.quantity <= 0:
            raise ValueError("quantity must be positive")
        if trade.entry_price <= 0:
            raise ValueError("entry_price must be positive")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO trades (
                        user_id, symbol, side, entry_price, exit_price,
                        quantity, pnl, entry_time, exit_time, exit_reason,
                        strategy, option_type, strike, expiry, invested
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.user_id, trade.symbol, trade.side, trade.entry_price,
                    trade.exit_price, trade.quantity, trade.pnl, trade.entry_time,
                    trade.exit_time, trade.exit_reason, trade.strategy,
                    trade.option_type, trade.strike, trade.expiry, trade.invested
                ))
                conn.commit()
                trade.id = cursor.lastrowid
                
                # Synchronize to CSV for Jarvis AI and SL Guard
                try:
                    from src.utils.trade_logger import log_trade_to_csv
                    log_trade_to_csv(trade)
                except Exception as sync_err:
                    logger.error(f"Failed to sync trade to CSV: {sync_err}")
                    
                return cursor.lastrowid
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to insert trade: {e}")
                raise DatabaseError(f"Trade insertion failed: {e}") from e
    
    def get_trades(
        self,
        user_id: str = None,
        from_date: str = None,
        to_date: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get trades with optional filters."""
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if from_date:
            query += " AND date(entry_time) >= date(?)"
            params.append(from_date)
        if to_date:
            query += " AND date(entry_time) <= date(?)"
            params.append(to_date)
        
        query += " ORDER BY entry_time DESC LIMIT ?"
        params.append(limit)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_trades_by_user(self, user_id: str, date_str: Optional[str] = None) -> List[TradeRecord]:
        """Get all trades for a specific user as TradeRecord objects, optionally filtered by date."""
        query = "SELECT * FROM trades WHERE user_id = ?"
        params = [user_id]
        
        if date_str:
            query += " AND date(entry_time) = date(?)"
            params.append(date_str)
            
        query += " ORDER BY entry_time DESC"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                TradeRecord(
                    id=row['id'],
                    user_id=row['user_id'],
                    symbol=row['symbol'],
                    side=row['side'],
                    entry_price=row['entry_price'],
                    exit_price=row['exit_price'],
                    quantity=row['quantity'],
                    pnl=row['pnl'],
                    entry_time=row['entry_time'],
                    exit_time=row['exit_time'],
                    exit_reason=row['exit_reason'],
                    strategy=row['strategy'],
                    option_type=row['option_type'],
                    strike=row['strike'],
                    expiry=row['expiry'],
                    invested=row['invested']
                ) for row in rows
            ]
    
    def get_trade_stats(self, user_id: str, date_str: str = None) -> Dict:
        """
        Get trade statistics for a user.
        Ensures consistent dictionary structure even if no trades are found.
        """
        query = """
            SELECT 
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as won,
                COALESCE(SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END), 0) as lost,
                COALESCE(SUM(pnl), 0.0) as total_pnl,
                COALESCE(AVG(pnl), 0.0) as avg_pnl
            FROM trades
            WHERE user_id = ?
        """
        params = [user_id]
        
        if date_str:
            query += " AND date(entry_time) = date(?)"
            params.append(date_str)
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                row = cursor.fetchone()
                if not row or row['total'] == 0:
                    return {
                        "total": 0, "won": 0, "lost": 0, 
                        "total_pnl": 0.0, "avg_pnl": 0.0,
                        "win_rate": 0.0
                    }
                
                res = dict(row)
                res["win_rate"] = (res["won"] / res["total"]) * 100 if res["total"] > 0 else 0.0
                return res
        except Exception as e:
            logger.error(f"Failed to get trade stats for {user_id}: {e}")
            return {"total": 0, "won": 0, "lost": 0, "total_pnl": 0.0, "avg_pnl": 0.0, "win_rate": 0.0}
    
    # ── Position Operations ──────────────────────────────────────────────
    
    def upsert_position(self, position: Dict) -> None:
        """Insert or update a position."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO positions (
                    user_id, symbol, side, entry_price, quantity,
                    sl, target, option_type, strike, expiry
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, symbol) DO UPDATE SET
                    entry_price = excluded.entry_price,
                    quantity = excluded.quantity,
                    sl = excluded.sl,
                    target = excluded.target
            """, (
                position["user_id"], position["symbol"], position["side"],
                position["entry_price"], position["quantity"], position.get("sl"),
                position.get("target"), position.get("option_type"),
                position.get("strike"), position.get("expiry")
            ))
            conn.commit()
    
    def get_positions(self, user_id: str = None) -> List[Dict]:
        """Get active positions."""
        query = "SELECT * FROM positions"
        params = []
        
        if user_id:
            query += " WHERE user_id = ?"
            params.append(user_id)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def close_position(self, user_id: str, symbol: str) -> None:
        """Remove a position."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM positions WHERE user_id = ? AND symbol = ?",
                (user_id, symbol)
            )
            conn.commit()
    
    # ── User Operations ─────────────────────────────────────────────────
    
    def save_user(self, user_id: str, name: str, broker_type: str, config: Dict, active: bool = True) -> None:
        """Save user configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, name, broker_type, config_json, active, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    name = excluded.name,
                    broker_type = excluded.broker_type,
                    config_json = excluded.config_json,
                    active = excluded.active,
                    updated_at = datetime('now')
            """, (user_id, name, broker_type, json.dumps(config), 1 if active else 0))
            conn.commit()
    
    def get_users(self, active_only: bool = True) -> List[Dict]:
        """Get all users."""
        query = "SELECT * FROM users"
        if active_only:
            query += " WHERE active = 1"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            users = []
            for row in cursor.fetchall():
                user = dict(row)
                if user.get("config_json"):
                    user["config"] = json.loads(user["config_json"])
                users.append(user)
            return users
    
    # ── Settings Operations ─────────────────────────────────────────────
    
    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = datetime('now')
            """, (key, value))
            conn.commit()
    
    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a setting value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default


# Global database instance
_db: Optional[Database] = None


def get_database() -> Database:
    """Get or create global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


# Legacy CSV importer for migrating existing data
class CSVImporter:
    """Import data from CSV files."""
    
    @staticmethod
    def _safe_float(val: Any) -> float:
        try:
            return float(val) if val and str(val).strip() else 0.0
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _safe_int(val: Any) -> int:
        try:
            return int(val) if val and str(val).strip() else 0
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def import_trades_from_csv(csv_path: str, user_id: str = "default") -> int:
        """Import trades from CSV file with deduplication and safe parsing."""
        import csv
        
        db = get_database()
        count = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = row.get('instrument') or row.get('symbol', '')
                    strategy = row.get('strategy_used') or row.get('strategy', '')
                    
                    date_val = row.get('date', '')
                    time_val = row.get('time', '')
                    timestamp = f"{date_val}T{time_val}" if date_val and time_val else date_val
                    
                    # Deduplication: Check if this trade already exists
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT COUNT(*) FROM trades WHERE symbol = ? AND exit_time = ?", 
                            (symbol, timestamp)
                        )
                        if cursor.fetchone()[0] > 0:
                            continue # Skip duplicate
                    
                    # Determine user_id (CSV might have one)
                    final_user_id = row.get('user_id') or user_id

                    trade = TradeRecord(
                        user_id=final_user_id,
                        symbol=symbol,
                        side=row.get('side', ''),
                        entry_price=CSVImporter._safe_float(row.get('entry_price')),
                        exit_price=CSVImporter._safe_float(row.get('exit_price')),
                        quantity=CSVImporter._safe_int(row.get('quantity')),
                        pnl=CSVImporter._safe_float(row.get('pnl')),
                        entry_time=timestamp,
                        exit_time=timestamp,
                        exit_reason=row.get('exit_reason', ''),
                        strategy=strategy,
                        option_type=row.get('option_type', ''),
                        strike=row.get('strike', ''),
                        expiry=row.get('expiry', ''),
                        invested=CSVImporter._safe_float(row.get('invested'))
                    )
                    db.insert_trade(trade)
                    count += 1
        except Exception as e:
            logger.error(f"CSV import failed: {e}")
        
        return count