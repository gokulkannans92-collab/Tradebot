"""
Combined Signal Strategy
Requires 2 out of 3 independent strategies to agree before generating a signal.

Sub-Strategies:
 1. EMA 9/21 Crossover
 2. Breakout (previous candle high/low + volume spike)
 3. RSI  (>60 = bullish, <40 = bearish)
"""

import pandas as pd
import numpy as np
import logging
from datetime import date
from typing import Dict, List, Tuple

from src.strategy.base import Strategy
from src.utils.options_utils import (
    get_upcoming_expiry,
    build_option_symbol,
    select_atm_strike,
    estimate_option_premium,
)

logger = logging.getLogger("CombinedSignalStrategy")


class CombinedSignalStrategy(Strategy):
    """
    3-signal combined strategy for NIFTY / BANKNIFTY options.
    Entry fires only when at least `min_signals` (default 2) of the 3
    sub-strategies agree on direction.
    """

    def __init__(
        self,
        underlying: str = "NIFTY",
        strike_step: int = 50,
        expiry_weekday: int = 1,       # 1=Tuesday (NIFTY), 2=Wednesday (BANKNIFTY)
        ema_fast: int = 9,
        ema_slow: int = 21,
        rsi_period: int = 14,
        volume_multiplier: float = 1.5,  # volume spike threshold
        min_signals: int = 2,
    ):
        self.underlying       = underlying.upper()
        self.strike_step      = strike_step
        self.expiry_weekday   = expiry_weekday
        self.ema_fast         = ema_fast
        self.ema_slow         = ema_slow
        self.rsi_period       = rsi_period
        self.volume_mult      = volume_multiplier
        self.min_signals      = min_signals
        self._name = f"{underlying.upper()}_Combined_EMA_Breakout_RSI"

    def name(self) -> str:
        return self._name

    # ──────────────────────────────────────────────────────────────────
    # Indicator helpers
    # ──────────────────────────────────────────────────────────────────

    def _add_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["EMA_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["EMA_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()

        # RSI
        delta = df["close"].diff()
        gain  = delta.clip(lower=0)
        loss  = (-delta).clip(lower=0)
        avg_gain = gain.ewm(com=self.rsi_period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=self.rsi_period - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI"] = 100 - (100 / (1 + rs))

        # Volume moving average for spike detection
        df["vol_ma"] = df["volume"].rolling(20).mean()

        return df

    # ──────────────────────────────────────────────────────────────────
    # Sub-strategy signals: return +1 (bullish), -1 (bearish), 0 (neutral)
    # ──────────────────────────────────────────────────────────────────

    def _ema_signal(self, curr: pd.Series, prev: pd.Series) -> Tuple[int, str]:
        """EMA 9/21 trend direction — bullish when EMA9 > EMA21, bearish when below."""
        fast, slow = curr["EMA_fast"], curr["EMA_slow"]
        if pd.isna(fast) or pd.isna(slow):
            return 0, "EMA unavailable"
        gap_pct = abs(fast - slow) / slow * 100  # % gap — ignore near-zero noise
        if gap_pct < 0.05:          # EMAs too close — no clear trend (increased from 0.01%)
            return 0, f"EMA neutral (gap {gap_pct:.3f}%)"
        if fast > slow:
            return 1,  f"EMA9={fast:.1f} > EMA21={slow:.1f} (uptrend)"
        if fast < slow:
            return -1, f"EMA9={fast:.1f} < EMA21={slow:.1f} (downtrend)"
        return 0, "EMA flat"

    def _breakout_signal(self, curr: pd.Series, prev: pd.Series) -> Tuple[int, str]:
        """5-min candle breakout. Volume spike required only when vol_ma is reliable (>5 candles)."""
        vol_ma = curr["vol_ma"]
        if pd.isna(vol_ma) or vol_ma <= 0:
            # Not enough history for volume average — use price breakout alone
            vol_spike = True
        else:
            vol_spike = curr["volume"] > self.volume_mult * vol_ma

        if curr["close"] > prev["high"] and vol_spike:
            return 1, f"Breakout above ₹{prev['high']:.1f}"
        if curr["close"] < prev["low"] and vol_spike:
            return -1, f"Breakout below ₹{prev['low']:.1f}"
        return 0, "No breakout"

    def _rsi_signal(self, curr: pd.Series) -> Tuple[int, str]:
        """RSI threshold signal."""
        rsi = curr["RSI"]
        if pd.isna(rsi):
            return 0, "RSI unavailable"
        if rsi > 60:
            return 1,  f"RSI={rsi:.1f} > 60 (bullish)"
        if rsi < 40:
            return -1, f"RSI={rsi:.1f} < 40 (bearish)"
        return 0, f"RSI={rsi:.1f} neutral (40–60)"

    # ──────────────────────────────────────────────────────────────────
    # Main signal generation
    # ──────────────────────────────────────────────────────────────────

    def generate_signal(self, data: pd.DataFrame, broker=None, max_premium: float = None) -> Dict:
        # Need at least 5 candles for EMA/RSI to produce meaningful values.
        # (EMAs are exponential — they work from the first row, just with less accuracy early on)
        min_rows = 5
        if len(data) < min_rows:
            return {
                "signal": "HOLD",
                "reason": f"Warming up ({len(data)}/{min_rows} candles)",
            }

        try:
            df   = self._add_indicators(data)
            curr = df.iloc[-1]
            prev = df.iloc[-2]

            # --- Market Filter: Sideways/Low Volatility ---
            # 1. Average Candle Range (Volatility)
            recent_rows = df.tail(10)
            avg_range = (recent_rows['high'] - recent_rows['low']).mean()
            range_pct = (avg_range / curr['close']) * 100
            
            # If range is less than 0.05% of price, it's low volatility
            if range_pct < 0.05:
                return {"signal": "HOLD", "reason": f"Low Volatility (Range: {range_pct:.3f}%)"}

            spot = float(curr["close"])
            if self.underlying == "BANKNIFTY":
                from src.utils.options_utils import get_monthly_expiry
                expiry = get_monthly_expiry(date.today())
            else:
                expiry = get_upcoming_expiry(date.today(), self.expiry_weekday)
                
            days_to_exp   = max((expiry - date.today()).days, 1)
            strike        = select_atm_strike(spot, self.strike_step)

            # Collect sub-signals
            s_ema,  r_ema       = self._ema_signal(curr, prev)
            s_brk,  r_brk       = self._breakout_signal(curr, prev)
            s_rsi,  r_rsi       = self._rsi_signal(curr)

            signals = [s_ema, s_brk, s_rsi]
            reasons = {"EMA": r_ema, "Breakout": r_brk, "RSI": r_rsi}
            bullish = sum(1 for s in signals if s == 1)
            bearish = sum(1 for s in signals if s == -1)

            logger.info(
                f"[{self.underlying}] Signal votes — "
                f"EMA:{s_ema:+d} Breakout:{s_brk:+d} RSI:{s_rsi:+d} | "
                f"Bullish:{bullish} Bearish:{bearish} (need {self.min_signals})"
            )

            active_reasons = ", ".join(
                f"{k}:{v}" for k, v in reasons.items() if "No " not in v and "neutral" not in v
            )

            if bullish >= self.min_signals:
                option_type = "CE"
                symbol = broker.get_symbol(self.underlying, expiry, strike, option_type) if broker else build_option_symbol(self.underlying, expiry, strike, option_type)
                premium = estimate_option_premium(spot, strike, option_type, days_to_exp)
                
                return {
                    "signal":        "BUY",
                    "option_type":   option_type,
                    "option_symbol": symbol,
                    "strike":        strike,
                    "expiry":        str(expiry),
                    "price":         round(premium, 2),
                    "spot":          spot,
                    "sl":            round(premium * 0.50, 2),
                    "target":        round(premium * 2.00, 2),
                    "confidence":    round(bullish / 3, 2),
                    "reason":        f"2/3 bullish — {active_reasons}",
                    "signals":       {"EMA": s_ema, "Breakout": s_brk, "RSI": s_rsi},
                }

            if bearish >= self.min_signals:
                option_type = "PE"
                symbol = broker.get_symbol(self.underlying, expiry, strike, option_type) if broker else build_option_symbol(self.underlying, expiry, strike, option_type)
                premium = estimate_option_premium(spot, strike, option_type, days_to_exp)
                
                return {
                    "signal":        "SELL",
                    "option_type":   option_type,
                    "option_symbol": symbol,
                    "strike":        strike,
                    "expiry":        str(expiry),
                    "price":         round(premium, 2),
                    "spot":          spot,
                    "sl":            round(premium * 0.50, 2),
                    "target":        round(premium * 2.00, 2),
                    "confidence":    round(bearish / 3, 2),
                    "reason":        f"2/3 bearish — {active_reasons}",
                    "signals":       {"EMA": s_ema, "Breakout": s_brk, "RSI": s_rsi},
                }

        except Exception as e:
            logger.error(f"CombinedSignalStrategy error: {e}", exc_info=True)

        return {"signal": "HOLD", "reason": "No 2-of-3 confirmation"}
