"""
Trade Tracker
Monitors active trades for SL/Target hits, closes them, logs to CSV,
and updates the RiskManager P&L counters.
"""

import logging
import json
import os
from typing import Dict, Optional, List
from src.broker.base import Broker
from src.oms.order_manager import OrderManager
from src.utils.notifications import TelegramManager, escape_md
from src.utils import trade_logger

logger = logging.getLogger(__name__)


class TradeTracker:
    def __init__(
        self,
        user_id:      str,
        broker:   Broker,
        oms:      OrderManager,
        notifier: Optional[TelegramManager] = None,
        risk=None,          # RiskManager (optional, for P&L updates)
        strategy_name: str = "Unknown",
        trade_target_rs: float = 1000.0,
        trade_sl_rs:     float = 200.0,
        use_tsl:         bool  = True,
        tsl_activation_percent: float = 0.5,
    ):
        self.user_id         = user_id
        self.broker          = broker
        self.oms             = oms
        self.notifier        = notifier
        self.risk            = risk
        self.strategy_name   = strategy_name
        self.trade_target_rs = trade_target_rs   # ₹ fixed target
        self.trade_sl_rs     = trade_sl_rs       # ₹ fixed SL
        self.use_tsl         = use_tsl
        self.tsl_activation_percent = tsl_activation_percent
        # {symbol: {entry_price, quantity, side, sl, target, option_type, strike, expiry, peak_price, tsl_activated}}
        self.active_trades: Dict[str, Dict] = {}
        
        # Persistence setup
        self._persistence_file = f".active_trades_{self.user_id}_{self.strategy_name.lower()}.json"

    # ──────────────────────────────────────────────────────────────────
    # Open a trade
    # ──────────────────────────────────────────────────────────────────

    def add_trade(
        self,
        symbol:      str,
        entry_price: float,
        quantity:    int,
        side:        str,
        sl:          float,
        target:      float,
        option_type: str = "",
        strike:      str = "",
        expiry:      str = "",
    ):
        self.active_trades[symbol] = {
            "entry_price": entry_price,
            "quantity":    quantity,
            "side":        side,
            "sl":          sl,
            "target":      target,
            "option_type": option_type,
            "strike":      strike,
            "expiry":      expiry,
            "peak_price":  entry_price,
            "tsl_activated": False,
        }
        self.save_active_trades()
        msg = (
            fr"📈 *\[User: {escape_md(self.user_id)}\] TRADE OPENED*\n"
            fr"Symbol : `{escape_md(symbol)}`\n"
            fr"Side   : {escape_md(side)}  \|  Qty: {escape_md(str(quantity))}\n"
            fr"Entry  : ₹{escape_md(f'{entry_price:.2f}')}\n"
            fr"SL     : ₹{escape_md(f'{sl:.2f}')}  \|  Target: ₹{escape_md(f'{target:.2f}')}"
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
            # Risk: ₹ fixed SL/Target
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
            "peak_price":  entry_price,
            "tsl_activated": False,
        }
        self.save_active_trades()
        logger.info(f"🛡️ [{self.user_id}] Re-adopted {symbol} position at ₹{entry_price:.2f} (SL: ₹{sl:.2f}, Target: ₹{target:.2f})")

    # ──────────────────────────────────────────────────────────────────
    # Monitor exits (called every polling tick)
    # ──────────────────────────────────────────────────────────────────

    def check_exits(self):
        for symbol, trade in list(self.active_trades.items()):
            try:
                quote = self.broker.get_quote(symbol)
                if not quote:
                    continue
                ltp = quote.get("last_price") or quote.get("price", 0)

                exit_reason = None
                if trade["side"] == "BUY":
                    if ltp <= trade["sl"]:     exit_reason = "SL_HIT"
                    elif ltp >= trade["target"]: exit_reason = "TARGET_HIT"
                else:  # SELL
                    if ltp >= trade["sl"]:     exit_reason = "SL_HIT"
                    elif ltp <= trade["target"]: exit_reason = "TARGET_HIT"

                if exit_reason:
                    logger.info(f"[{self.user_id}] Exit: {symbol} → {exit_reason} at ₹{ltp:.2f}")
                    self.close_trade(symbol, ltp, exit_reason)
                else:
                    # ── Trailing SL Logic ──
                    if self.use_tsl:
                        self._apply_tsl(symbol, trade, ltp)

            except Exception as e:
                logger.error(f"check_exits error for {symbol} ({self.user_id}): {e}")

    def _apply_tsl(self, symbol: str, trade: Dict, ltp: float):
        """Update SL based on profit levels (Moving to Break-even or locking profit)"""
        pnl = (ltp - trade["entry_price"]) * trade["quantity"] if trade["side"] == "BUY" else (trade["entry_price"] - ltp) * trade["quantity"]
        
        target_rs = self.trade_target_rs
        
        # TSL Rule: Move to Break-even when profit hits ₹800
        # (This implements the "move SL to cost" logic for better risk management)
        activation_pnl = 800.0
        if pnl >= activation_pnl and not trade.get("tsl_activated"):
            # Move to Entry price
            new_sl = trade["entry_price"]
            
            if (trade["side"] == "BUY" and new_sl > trade["sl"]) or (trade["side"] == "SELL" and new_sl < trade["sl"]):
                trade["sl"] = new_sl
                trade["tsl_activated"] = True
                msg = fr"🛡️ *\[User: {escape_md(self.user_id)}\] TSL ACTIVATED*\n`{escape_md(symbol)}` SL moved to Break\-even \(₹{escape_md(f'{new_sl:.2f}')}\)"
                logger.info(msg)
                if self.notifier:
                    self.notifier.send_message(msg)
                self.save_active_trades()

        # Level 2 (Optional): Lock profit when pnl hits 80% of target
        # This provides a secondary safeguard to lock in some gains.
        lock_pnl = target_rs * 0.8
        if pnl >= lock_pnl and trade.get("tsl_activated") != "LEVEL2":
            lock_in_rs = target_rs * 0.2  # Lock in 20% of target
            profit_per_qty = lock_in_rs / trade["quantity"]
            new_sl = trade["entry_price"] + profit_per_qty if trade["side"] == "BUY" else trade["entry_price"] - profit_per_qty
            
            if (trade["side"] == "BUY" and new_sl > trade["sl"]) or (trade["side"] == "SELL" and new_sl < trade["sl"]):
                trade["sl"] = new_sl
                trade["tsl_activated"] = "LEVEL2"
                msg = fr"💰 *\[User: {escape_md(self.user_id)}\] PROFIT LOCKED*\n`{escape_md(symbol)}` SL moved to lock ₹{escape_md(f'{lock_in_rs:.0f}')} profit \(₹{escape_md(f'{new_sl:.2f}')}\)"
                logger.info(msg)
                if self.notifier: self.notifier.send_message(msg)
                self.save_active_trades()

    # ──────────────────────────────────────────────────────────────────
    # Close a single trade
    # ──────────────────────────────────────────────────────────────────

    def close_trade(self, symbol: str, exit_price: float, reason: str) -> float:
        trade = self.active_trades.pop(symbol, None)
        if not trade:
            return 0.0
        
        self.save_active_trades() # Update persistent state

        exit_side = "SELL" if trade["side"] == "BUY" else "BUY"
        self.oms.place_market_order(symbol, trade["quantity"], exit_side)

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

        # Log to CSV
        invested = trade["entry_price"] * trade["quantity"]
        trade_logger.log_trade(
            user_id      = self.user_id,
            instrument   = symbol,
            side         = trade["side"],
            entry_price  = trade["entry_price"],
            exit_price   = exit_price,
            quantity     = trade["quantity"],
            pnl          = pnl,
            exit_reason  = reason,
            strategy_used= self.strategy_name,
            option_type  = trade.get("option_type", ""),
            strike       = str(trade.get("strike", "")),
            expiry       = str(trade.get("expiry", "")),
            invested     = invested,
        )

        icon = "🟢" if pnl >= 0 else "🔴"
        msg = (
            fr"{icon} *\[User: {escape_md(self.user_id)}\] TRADE CLOSED*\n"
            fr"Symbol : `{escape_md(symbol)}`\n"
            fr"Exit   : ₹{escape_md(f'{exit_price:.2f}')}  \|  Reason: `{escape_md(reason)}`\n"
            fr"PnL    : ₹{escape_md(f'{pnl:.2f}')}"
        )
        logger.info(msg)
        if self.notifier:
            self.notifier.send_message(msg)

        return pnl

    def get_current_margin(self) -> float:
        """Returns the total capital invested in currently active trades."""
        return sum(t["entry_price"] * t["quantity"] for t in self.active_trades.values())

    # ──────────────────────────────────────────────────────────────────
    # Force close all
    # ──────────────────────────────────────────────────────────────────

    def close_all(self) -> float:
        total_pnl = 0.0
        for symbol in list(self.active_trades.keys()):
            quote = self.broker.get_quote(symbol)
            price = quote.get("last_price", 0) if quote else 0
            total_pnl += self.close_trade(symbol, price, "FORCE_EXIT")
        return total_pnl

    def get_active_trades_list(self) -> List[Dict]:
        """Returns a list of active trades for JSON export."""
        trades = []
        for symbol, t in self.active_trades.items():
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
            except:
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
        except Exception as e:
            logger.error(f"Failed to save active trades for {self.user_id}: {e}")

    def load_active_trades(self):
        """Loads active trades from the local JSON file on startup."""
        if not os.path.exists(self._persistence_file):
            return
        
        try:
            with open(self._persistence_file, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.active_trades = data
                    if data:
                        logger.info(f"✅ [{self.user_id}] Resumed {len(data)} active trades for {self.strategy_name}")
        except Exception as e:
            logger.error(f"Failed to load active trades for {self.user_id}: {e}")

