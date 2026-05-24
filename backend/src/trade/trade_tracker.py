"""
Trade Tracker
Monitors active trades for SL/Target hits, closes them, logs to CSV,
and updates the RiskManager P&L counters
"""

import logging
import json
import os
import threading
from datetime import datetime
from typing import Dict, Optional, List, TYPE_CHECKING
from src.broker.base import Broker
from src.oms.order_manager import OrderManager
from src.persistence.database import get_database, TradeRecord
from src.utils.paths import get_path
from src.utils.notifications import escape_md
from src.utils.trade_logger import log_trade

if TYPE_CHECKING:
    from src.utils.notifications import TelegramManager

logger = logging.getLogger(__name__)


class TradeTracker:
    """
    Tracks active trades, monitors for SL/Target hits, and manages position exits.
    
    Features:
    - Real-time P&L tracking with live price updates
    - Trailing stop-loss with 4-level profit locking ladder
    - Automatic trade persistence to JSON for crash recovery
    - Telegram notifications for trade events
    - Thread-safe access to active_trades via internal lock
    """
    
    def __init__(
        self,
        user_id: str,
        broker: Broker,
        order_manager: OrderManager,
        notifier: Optional[TelegramManager] = None,
        risk=None,
        data_provider=None,
        strategy_name: str = "Unknown",
        trade_target_rs: float = 1000.0,
        trade_sl_rs: float = 200.0,
        use_trailing_stop_loss: bool = True,
        trailing_stop_loss_activation_percent: float = 0.5,
    ):
        """
        Initialize TradeTracker.
        
        Args:
            user_id: Unique identifier for the user
            broker: Broker instance for fetching quotes and placing orders
            order_manager: OrderManager instance for executing exit orders
            notifier: Optional TelegramManager for sending notifications
            risk: Optional RiskManager for updating P&L counters
            strategy_name: Name of the trading strategy (e.g., "NIFTY_COMBINED")
            trade_target_rs: Target profit in rupees for fixed target exits
            trade_sl_rs: Stop-loss amount in rupees for fixed SL exits
            use_trailing_stop_loss: Whether to enable trailing stop-loss logic
            trailing_stop_loss_activation_percent: Profit % required to activate TSL
        """
        self.user_id         = user_id
        self.broker          = broker
        self.order_manager   = order_manager
        self.notifier        = notifier
        self.risk            = risk
        self.data_provider   = data_provider
        self.strategy_name   = strategy_name
        self.trade_target_rs = trade_target_rs   # Rs fixed target
        self.trade_sl_rs     = trade_sl_rs       # Rs fixed SL
        self.use_trailing_stop_loss         = use_trailing_stop_loss
        self.trailing_stop_loss_activation_percent = trailing_stop_loss_activation_percent
        # {symbol: {entry_price, quantity, side, sl, target, option_type, strike, expiry, peak_price, tsl_activated}}
        self.active_trades: Dict[str, Dict] = {}
        
        # Thread lock for atomic operations on active_trades
        self._lock = threading.Lock()
        
        # Persistence setup
        self._persistence_file = get_path(f".active_trades_{self.user_id}_{self.strategy_name.lower()}.json")

    @property
    def trades_lock(self) -> threading.Lock:
        """Expose lock for external atomic operations (e.g., position reconciliation)."""
        return self._lock

    # ──────────────────────────────────────────────────────────────────
    # Open a trade
    # ──────────────────────────────────────────────────────────────────

    def add_trade(
        self,
        symbol: str,
        entry_price: float,
        quantity: int,
        side: str,
        sl: float,
        target: float,
        option_type: str = "",
        strike: str = "",
        expiry: str = "",
    ):
        """Add a new trade to tracking with duplicate prevention."""
        with self._lock:
            if symbol in self.active_trades:
                logger.warning(f"⚠️ [{self.user_id}] Duplicate trade rejected for {symbol}")
                return False

            self.active_trades[symbol] = {
                "entry_price": entry_price,
                "quantity":    quantity,
                "side":        side,
                "sl":          sl,
                "target":      target,
                "target_rs":   abs(target - entry_price) * quantity,
                "option_type": option_type,
                "strike":      strike,
                "expiry":      expiry,
                "entry_time":  datetime.now().isoformat(),
                "peak_price":  entry_price,
                "trailing_stop_activated": False,
                "trailing_stop_level": 0
            }
        
        self.save_active_trades()
        msg = (
            f"📈 <b>[User: {escape_md(self.user_id)}] TRADE OPENED</b>\n"
            f"Symbol : <code>{escape_md(symbol)}</code>\n"
            f"Side   : {escape_md(side)}  |  Qty: {escape_md(str(quantity))}\n"
            f"Entry  : Rs{escape_md(f'{entry_price:.2f}')}\n"
            f"SL     : Rs{escape_md(f'{sl:.2f}')}  |  Target: Rs{escape_md(f'{target:.2f}')}"
        )
        logger.info(msg)
        if self.notifier:
            self.notifier.send_message(msg)

    def adopt_trade(
        self,
        symbol:      str,
        entry_price: float,
        quantity:    int,
        side:        str,
        sl:          Optional[float] = None,
        target:      Optional[float] = None,
        option_type: str = "",
        strike:      str = "",
        expiry:      str = "",
    ):
        """Used to re-adopt an existing position found in the broker (Broker Reconciliation)."""
        if symbol in self.active_trades:
            return

        # Calculate default SL/Target if missing
        if sl is None or target is None:
            # Risk: Rs fixed SL/Target
            # pts = fixed / quantity
            sl_pts = self.trade_sl_rs / quantity
            tgt_pts = self.trade_target_rs / quantity
            if side == "BUY":
                sl = entry_price - sl_pts
                target = entry_price + tgt_pts
            else:
                sl = entry_price + sl_pts
                target = entry_price - tgt_pts

        self.active_trades[symbol] = {
            "entry_price": entry_price,
            "quantity":    quantity,
            "side":        side,
            "sl":          round(sl, 2),
            "target":      round(target, 2),
            "option_type": option_type,
            "strike":      strike,
            "expiry":      expiry,
            "entry_time":  datetime.now().isoformat(), # Re-adopted positions use current time as start
            "peak_price":  entry_price,
            "trailing_stop_activated": False,
        }
        self.save_active_trades()
        logger.info(f"🛡️ [{self.user_id}] Re-adopted {symbol} position at Rs{entry_price:.2f} (SL: Rs{sl:.2f}, Target: Rs{target:.2f})")

    # ──────────────────────────────────────────────────────────────────
    # Monitor exits (called every polling tick)
    # ──────────────────────────────────────────────────────────────────

    def check_exits(self):
        updated = False
        for symbol, trade in list(self.active_trades.items()):
            try:
                # 0. Fetch latest price (Prioritize WebSocket-backed DataProvider)
                if self.data_provider:
                    quote = self.data_provider.get_quote(symbol)
                else:
                    quote = self.broker.get_quote(symbol)
                
                if not quote:
                    continue
                ltp = quote.get("last_price") or quote.get("price", 0) or 0
                
                # Update live state for UI/Persistence
                trade["ltp"] = ltp
                pnl = (
                    (ltp - trade["entry_price"]) * trade["quantity"]
                    if trade["side"] == "BUY"
                    else (trade["entry_price"] - ltp) * trade["quantity"]
                )
                trade["pnl"] = round(pnl, 2)
                updated = True

                # 1. Price-based SL/Target
                exit_reason = None
                if trade["side"] == "BUY":
                    if ltp <= trade["sl"]:     exit_reason = "SL_HIT"
                    elif ltp >= trade["target"]: exit_reason = "TARGET_HIT"
                else:  # SELL
                    if ltp >= trade["sl"]:     exit_reason = "SL_HIT"
                    elif ltp <= trade["target"]: exit_reason = "TARGET_HIT"

                # 2. P&L-based Absolute Hard-SL (Emergency Circuit Breaker)
                # Fires if the realised loss on this trade exceeds:
                #   - The configured trade_sl_rs limit, OR
                #   - A hard floor of 20% of the trade's invested capital
                # whichever is the tighter (smaller) of the two.
                # This prevents a fast market from letting a single trade wipe out
                # more than 20% of the invested amount before the price-based SL fires.
                invested = trade["entry_price"] * trade["quantity"]
                hard_floor = min(self.trade_sl_rs, invested * 0.20)
                if not exit_reason and pnl <= -hard_floor:
                    exit_reason = "HARD_PNL_EXIT"
                    logger.warning(
                        f"🚨 [{self.user_id}] EMERGENCY: Hard P&L Floor Hit for {symbol}! "
                        f"PnL: Rs{pnl:.2f} | Limit: Rs{hard_floor:.2f} "
                        f"(trade_sl_rs={self.trade_sl_rs}, 20%_invested={invested * 0.20:.2f})"
                    )

                if exit_reason:
                    logger.info(f"[{self.user_id}] Exit: {symbol} -> {exit_reason} at Rs{ltp:.2f}")
                    self.close_trade(symbol, ltp, exit_reason)
                    updated = True
                else:
                    # ── Trailing SL Logic ──
                    if self.use_trailing_stop_loss:
                        if self._apply_trailing_stop_loss(symbol, trade, ltp):
                            updated = True

            except (IOError, OSError, ValueError, TypeError) as e:
                logger.error(f"Error checking exits: {e}")
        
        if updated:
            self.save_active_trades()

    def _apply_trailing_stop_loss(self, symbol: str, trade: Dict, ltp: float):
        """
        Aggressive 6-Level Trailing Stop Loss Ladder - Progressive profit locking.
          Level 1 (10% target): Move SL to 50% of initial risk (Reduce Loss)
          Level 2 (20% target): Move SL to Entry (Break-even)
          Level 3 (40% target): Lock 20% of target profit
          Level 4 (60% target): Lock 40% of target profit
          Level 5 (80% target): Lock 60% of target profit
          Level 6 (90% target): Lock 80% of target profit
        """
        pnl = (
            (ltp - trade["entry_price"]) * trade["quantity"]
            if trade["side"] == "BUY"
            else (trade["entry_price"] - ltp) * trade["quantity"]
        )

        target_rs = trade.get("target_rs") or self.trade_target_rs
        if not target_rs or target_rs <= 0:
            return

        current_level = trade.get("trailing_stop_level", 0)

        # ── Level 1: Reduce Risk at 10% of target ──
        if current_level < 1 and pnl >= target_rs * 0.10:
            # Move SL halfway to entry from original SL
            new_sl = (trade["sl"] + trade["entry_price"]) / 2
            if self._update_stop_loss_level(symbol, trade, new_sl, 1,
                    f"🛡️ <b>[{escape_md(self.user_id)}] TSL L1 - Risk Reduced</b>\n"
                    f"<code>{escape_md(symbol)}</code> SL -> Rs{escape_md(f'{new_sl:.2f}')} (10% target)"):
                return

        # ── Level 2: Break-even at 20% of target ──
        if current_level < 2 and pnl >= target_rs * 0.20:
            new_sl = trade["entry_price"]
            if self._update_stop_loss_level(symbol, trade, new_sl, 2,
                    f"🛡️ <b>[{escape_md(self.user_id)}] TSL L2 - Break-even</b>\n"
                    f"<code>{escape_md(symbol)}</code> SL -> Entry Rs{escape_md(f'{new_sl:.2f}')} (20% target)"):
                return

        # ── Level 3: Lock 20% profit at 40% of target ──
        if current_level < 3 and pnl >= target_rs * 0.40:
            lock_rs = target_rs * 0.20
            profit_per_qty = lock_rs / trade["quantity"]
            new_sl = (trade["entry_price"] + profit_per_qty if trade["side"] == "BUY"
                      else trade["entry_price"] - profit_per_qty)
            if self._update_stop_loss_level(symbol, trade, new_sl, 3,
                    f"💰 <b>[{escape_md(self.user_id)}] TSL L3 - 20% Locked</b>\n"
                    f"<code>{escape_md(symbol)}</code> SL -> Rs{escape_md(f'{new_sl:.2f}')} (40% target)"):
                return

        # ── Level 4: Lock 40% profit at 60% of target ──
        if current_level < 4 and pnl >= target_rs * 0.60:
            lock_rs = target_rs * 0.40
            profit_per_qty = lock_rs / trade["quantity"]
            new_sl = (trade["entry_price"] + profit_per_qty if trade["side"] == "BUY"
                      else trade["entry_price"] - profit_per_qty)
            if self._update_stop_loss_level(symbol, trade, new_sl, 4,
                    f"🔒 <b>[{escape_md(self.user_id)}] TSL L4 - 40% Locked</b>\n"
                    f"<code>{escape_md(symbol)}</code> SL -> Rs{escape_md(f'{new_sl:.2f}')} (60% target)"):
                return

        # ── Level 5: Lock 60% profit at 80% of target ──
        if current_level < 5 and pnl >= target_rs * 0.80:
            lock_rs = target_rs * 0.60
            profit_per_qty = lock_rs / trade["quantity"]
            new_sl = (trade["entry_price"] + profit_per_qty if trade["side"] == "BUY"
                      else trade["entry_price"] - profit_per_qty)
            if self._update_stop_loss_level(symbol, trade, new_sl, 5,
                    f"🔥 <b>[{escape_md(self.user_id)}] TSL L5 - 60% Locked</b>\n"
                    f"<code>{escape_md(symbol)}</code> SL -> Rs{escape_md(f'{new_sl:.2f}')} (80% target)"):
                return

        # ── Level 6: Lock 80% profit at 95% of target ──
        if current_level < 6 and pnl >= target_rs * 0.95:
            lock_rs = target_rs * 0.80
            profit_per_qty = lock_rs / trade["quantity"]
            new_sl = (trade["entry_price"] + profit_per_qty if trade["side"] == "BUY"
                      else trade["entry_price"] - profit_per_qty)
            self._update_stop_loss_level(symbol, trade, new_sl, 6,
                    f"🏆 <b>[{escape_md(self.user_id)}] TSL L6 - 80% Locked</b>\n"
                    f"<code>{escape_md(symbol)}</code> SL -> Rs{escape_md(f'{new_sl:.2f}')} (Near Target)")

    def _update_stop_loss_level(self, symbol: str, trade: Dict, new_sl: float, level: int, msg: str) -> bool:
        """Move SL if valid, update level, notify, and persist. Returns True if SL was moved."""
        is_buy = trade["side"] == "BUY"
        if (is_buy and new_sl > trade["sl"]) or (not is_buy and new_sl < trade["sl"]):
            trade["sl"] = new_sl
            trade["trailing_stop_level"] = level
            logger.info(f"[{self.user_id}] Trailing Stop Level {level} -> {symbol} new SL Rs{new_sl:.2f}")
            if self.notifier:
                try:
                    logger.debug(f"[{self.user_id}] Dispatching TSL L{level} alert for {symbol}")
                    self.notifier.send_message(msg)
                except (IOError, OSError, ValueError) as e:
                    logger.error(f"Trailing stop notify error: {e}")
            else:
                logger.warning(f"[{self.user_id}] No notifier linked - skipping TSL alert for {symbol}")
            self.save_active_trades()
            return True
        return False

    # ──────────────────────────────────────────────────────────────────
    # Close a single trade
    # ──────────────────────────────────────────────────────────────────

    def close_trade(self, symbol: str, exit_price: float, reason: str) -> float:
        trade = self.active_trades.pop(symbol, None)
        if not trade:
            return 0.0
        
        self.save_active_trades() # Update persistent state

        exit_side = "SELL" if trade["side"] == "BUY" else "BUY"
        
        # Always use place_market_order for exits. It already contains smart-limit
        # logic internally (fetches LTP and places a buffered LIMIT order for slippage
        # control). Critically, routing through order_manager ensures dedup tracking,
        # audit logging, and correct mock integration in tests.
        if "SL_HIT" in reason or "HARD_PNL_EXIT" in reason:
            logger.info(f"🚨 [PANIC EXIT] Stop Loss Hit for {symbol} - Executing MARKET exit...")
        self.order_manager.place_market_order(symbol, trade["quantity"], exit_side)

        pnl = (
            (exit_price - trade["entry_price"]) * trade["quantity"]
            if trade["side"] == "BUY"
            else (trade["entry_price"] - exit_price) * trade["quantity"]
        )

        # Update risk manager
        # Force-exits (EOD) don't count against the 2-trade daily limit
        is_entry_close = reason not in ("FORCE_EXIT",)
        if self.risk:
            self.risk.update_pnl(pnl, is_entry=is_entry_close)

        # Log to database
        invested = trade["entry_price"] * trade["quantity"]
        try:
            db = get_database()
            db.insert_trade(TradeRecord(
                user_id=self.user_id,
                symbol=symbol,
                side=trade["side"],
                entry_price=trade["entry_price"],
                exit_price=exit_price,
                quantity=trade["quantity"],
                pnl=pnl,
                entry_time=trade.get("entry_time", datetime.now().isoformat()),
                exit_time=datetime.now().isoformat(),
                exit_reason=reason,
                strategy=self.strategy_name,
                option_type=trade.get("option_type", ""),
                strike=str(trade.get("strike", "")),
                expiry=str(trade.get("expiry", "")),
                invested=invested
            ))
        except Exception as e:
            logger.error(f"Failed to log trade to database: {e}")


        # 📚 TEACH JARVIS (Daily Learning)
        # Uses get_path() to write to persistent data dir — works from both source and EXE
        try:
            from src.utils.paths import get_data_dir
            brain_path = os.path.join(get_data_dir(), "jarvis_brain.md")
            os.makedirs(os.path.dirname(brain_path), exist_ok=True)
            outcome = "Great success!" if pnl > 0 else "Need to improve entry timing."
            lesson = (
                f"\n- Lesson Learned ({datetime.now().strftime('%Y-%m-%d %H:%M')}): "
                f"Traded {symbol} ({trade['side']}). Result: Rs{pnl:.2f}. "
                f"Reason: {reason}. {outcome}\n"
            )
            with open(brain_path, "a", encoding="utf-8") as f:
                f.write(lesson)
            logger.info(f"🧠 Jarvis learned: {symbol} {trade['side']} Rs{pnl:.2f} ({reason})")
        except Exception as e:
            logger.warning(f"Jarvis learning failed: {e}")

        msg = f"[{self.user_id}] Trade closed: {symbol} at Rs{exit_price:.2f} | P&L: Rs{pnl:.2f} | Reason: {reason}"
        logger.info(msg)
        if self.notifier:
            self.notifier.send_message(msg)

        return pnl

    def get_current_margin(self) -> float:
        """Returns the total capital invested in currently active trades."""
        with self._lock:
            return sum(t["entry_price"] * t["quantity"] for t in self.active_trades.values())

    # ──────────────────────────────────────────────────────────────────
    # Force close all
    # ──────────────────────────────────────────────────────────────────

    def close_all(self) -> float:
        total_pnl = 0.0
        with self._lock:
            symbols = list(self.active_trades.keys())
        for symbol in symbols:
            quote = self.broker.get_quote(symbol)
            price = quote.get("last_price", 0) if quote else 0
            total_pnl += self.close_trade(symbol, price, "FORCE_EXIT")
        return total_pnl

    def get_active_trades_list(self) -> List[Dict]:
        """Returns a list of active trades for JSON export."""
        trades = []
        with self._lock:
            trades_snapshot = list(self.active_trades.items())
        for symbol, t in trades_snapshot:
            trade_data = t.copy()
            trade_data["symbol"] = symbol
            
            # Fetch latest price for P&L tracking (GUI utility)
            try:
                quote = self.broker.get_quote(symbol)
                ltp = quote.get("last_price") or quote.get("price", 0)
                trade_data["ltp"] = ltp
                
                # Calculate current P&L
                if t["side"] == "BUY":
                    unrealized = (ltp - t["entry_price"]) * t["quantity"]
                else:
                    unrealized = (t["entry_price"] - ltp) * t["quantity"]
                trade_data["unrealized_pnl"] = unrealized
            except (IOError, OSError, ValueError, TypeError) as e:
                logger.debug(f"Could not fetch quote for {symbol}: {e}")
                trade_data["ltp"] = t["entry_price"]
                trade_data["unrealized_pnl"] = 0.0
                
            trades.append(trade_data)
        return trades

    # ──────────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────────

    def save_active_trades(self):
        """Saves current active trades to a local JSON file for persistence."""
        try:
            with open(self._persistence_file, "w") as f:
                json.dump(self.active_trades, f, indent=4)
        except (IOError, OSError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to save active trades for {self.user_id}: {e}")

    def load_active_trades(self):
        """Loads active trades and cross-verifies with DB to prevent ghost trades."""
        if not os.path.exists(self._persistence_file):
            return
        
        try:
            with open(self._persistence_file, "r") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return

            # 🛡️ Safety Check: Cross-verify with DB
            # If a trade for this symbol exists in the database for TODAY,
            # and it's marked as closed, we should NOT load it as active.
            try:
                db = get_database()
                from datetime import date
                today_trades = db.get_trades_by_user(self.user_id, date_str=date.today().isoformat())
                # Filter for symbols that are in history but also in our active cache
                closed_symbols = {t.symbol for t in today_trades if t.exit_time}
                
                cleaned_data = {
                    s: v for s, v in data.items() 
                    if s not in closed_symbols
                }
                
                if len(cleaned_data) != len(data):
                    logger.info(f"🧹 Cleaned up {len(data) - len(cleaned_data)} ghost trades from cache.")
                    data = cleaned_data
                    self.active_trades = data
                    self.save_active_trades() # Update file immediately
            except Exception as e:
                logger.warning(f"Trade reconciliation skipped: {e}")

            self.active_trades = data
            if data:
                logger.info(f"✅ [{self.user_id}] Resumed {len(data)} active trades for {self.strategy_name}")
        except (IOError, OSError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to load active trades for {self.user_id}: {e}")

