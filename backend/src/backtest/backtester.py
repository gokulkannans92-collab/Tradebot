"""
Enhanced Backtester
Applies strategy signals to historical OHLCV data and computes:
  - Win Rate
  - Total Profit
  - Max Drawdown
  - Per-trade P&L
"""

import pandas as pd
import numpy as np
import logging
from typing import Type, List, Dict
from src.strategy.base import Strategy

logger = logging.getLogger("Backtester")


class Backtester:
    """
    Walk-forward backtester that respects:
    - Fixed ₹ target and ₹ SL per trade (mirrors live bot rules)
    - Max 2 trades per day
    - Intraday only (no overnight positions)
    """

    def __init__(
        self,
        strategy:        Strategy,
        data:            pd.DataFrame,
        initial_capital: float = 100_000,
        trade_capital:   float = 10_000,   # ₹ per trade
        target_rs:       float = 1_000,    # ₹ fixed target
        sl_rs:           float = 200,      # ₹ fixed SL
        lot_size:        int   = 75,
        max_trades_day:  int   = 2,
    ):
        if isinstance(strategy, type):
            # Allow passing a class instead of an instance
            strategy = strategy()
        self.strategy        = strategy
        self.data            = data.copy()
        self.initial_capital = initial_capital
        self.trade_capital   = trade_capital
        self.target_rs       = target_rs
        self.sl_rs           = sl_rs
        self.lot_size        = lot_size
        self.max_trades_day  = max_trades_day
        self.trades: List[Dict] = []

    # ──────────────────────────────────────────────────────────────────
    def run(self) -> Dict:
        """Execute backtest and return a summary dict."""
        capital      = self.initial_capital
        trades_today = 0
        current_date = None
        in_trade     = False
        entry_price  = 0.0
        entry_idx    = 0
        signal_side  = ""

        warmup = max(50, int(len(self.data) * 0.1))   # skip first 10% for indicator warmup

        for i in range(warmup, len(self.data)):
            window = self.data.iloc[:i]
            row    = self.data.iloc[i]
            ts     = self.data.index[i]

            # Reset daily counter
            row_date = ts.date() if hasattr(ts, "date") else None
            if row_date != current_date:
                current_date = row_date
                trades_today = 0
                if in_trade:
                    # Force exit at end of day
                    exit_price = float(row["close"])
                    pnl = self._calc_pnl(signal_side, entry_price, exit_price)
                    capital += pnl
                    self.trades.append({
                        "entry_time": self.data.index[entry_idx],
                        "exit_time":  ts,
                        "side":       signal_side,
                        "entry":      entry_price,
                        "exit":       exit_price,
                        "pnl":        pnl,
                        "reason":     "EOD_FORCE_EXIT",
                    })
                    in_trade = False

            if in_trade:
                price = float(row["close"])
                opt_price = price  # simplified: track underlying close
                pnl_unrealised = self._calc_pnl(signal_side, entry_price, opt_price)
                # Check SL / target in ₹ terms
                if pnl_unrealised >= self.target_rs:
                    pnl = pnl_unrealised
                    reason = "TARGET"
                elif pnl_unrealised <= -self.sl_rs:
                    pnl = pnl_unrealised
                    reason = "SL"
                else:
                    continue  # still in trade

                capital += pnl
                self.trades.append({
                    "entry_time": self.data.index[entry_idx],
                    "exit_time":  ts,
                    "side":       signal_side,
                    "entry":      entry_price,
                    "exit":       opt_price,
                    "pnl":        round(pnl, 2),
                    "reason":     reason,
                })
                in_trade = False
                trades_today += 1
                continue

            # Look for new entry
            if trades_today >= self.max_trades_day:
                continue

            try:
                sig = self.strategy.generate_signal(window)
            except Exception as e:
                continue

            if sig.get("signal") in ("BUY", "SELL") and not in_trade:
                entry_price = float(sig.get("price", row["close"]))
                signal_side = sig["signal"]
                in_trade    = True
                entry_idx   = i

        # ── Summary ───────────────────────────────────────────────────
        return self._summary(capital)

    def _calc_pnl(self, side: str, entry: float, current: float) -> float:
        qty = max(1, int(self.trade_capital / (entry or 1)) // self.lot_size * self.lot_size)
        if side == "BUY":
            return (current - entry) * qty
        else:
            return (entry - current) * qty

    def _summary(self, final_capital: float) -> Dict:
        if not self.trades:
            print("No trades executed in backtest.")
            return {
                "total_trades": 0, "win_rate": 0,
                "total_profit": 0, "max_drawdown": 0,
                "final_capital": final_capital,
            }

        df = pd.DataFrame(self.trades)
        total_trades = len(df)
        wins         = (df["pnl"] > 0).sum()
        win_rate     = wins / total_trades * 100
        total_profit = df["pnl"].sum()

        # Max drawdown on cumulative P&L
        cum_pnl  = df["pnl"].cumsum()
        peak     = cum_pnl.cummax()
        drawdown = (cum_pnl - peak)
        max_dd   = drawdown.min()

        summary = {
            "strategy":       self.strategy.name(),
            "total_trades":   total_trades,
            "wins":           int(wins),
            "losses":         int(total_trades - wins),
            "win_rate":       round(win_rate, 2),
            "total_profit":   round(total_profit, 2),
            "avg_pnl":        round(df["pnl"].mean(), 2),
            "best_trade":     round(df["pnl"].max(), 2),
            "worst_trade":    round(df["pnl"].min(), 2),
            "max_drawdown":   round(max_dd, 2),
            "final_capital":  round(final_capital, 2),
        }

        print("\n" + "=" * 55)
        print(f"  BACKTEST RESULTS - {summary['strategy']}")
        print("=" * 55)
        print(f"  Total Trades  : {summary['total_trades']}")
        print(f"  Win Rate      : {summary['win_rate']:.1f}%  ({summary['wins']}W / {summary['losses']}L)")
        print(f"  Total Profit  : ₹{summary['total_profit']:,.2f}")
        print(f"  Avg Trade PnL : ₹{summary['avg_pnl']:,.2f}")
        print(f"  Best Trade    : ₹{summary['best_trade']:,.2f}")
        print(f"  Worst Trade   : ₹{summary['worst_trade']:,.2f}")
        print(f"  Max Drawdown  : ₹{summary['max_drawdown']:,.2f}")
        print(f"  Final Capital : ₹{summary['final_capital']:,.2f}")
        print("=" * 55 + "\n")

        return summary

    def get_trades_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.trades)
