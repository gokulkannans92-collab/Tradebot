"""
NIFTY Options Strategy
Generates CE/PE option trade signals based on EMA + VWAP crossover on the NIFTY spot index.
"""

import pandas as pd
import numpy as np
import logging
from datetime import date
from typing import Dict
from src.strategy.base import Strategy
from src.utils.options_utils import (
    get_upcoming_expiry,
    build_option_symbol,
    select_atm_strike,
    estimate_option_premium,
)

logger = logging.getLogger("NiftyOptionsStrategy")


class NiftyOptionsStrategy(Strategy):
    """
    Trades NIFTY Options (CE/PE) on the upcoming weekly expiry.
    - BUY signal  → Buy ATM CALL (CE)
    - SELL signal → Buy ATM PUT  (PE)
    Uses EMA crossover above/below VWAP as the entry condition.
    """

    def __init__(self, ema_period: int = 20, underlying: str = "NIFTY",
                 strike_step: int = 50, expiry_weekday: int = 3):
        self.ema_period = ema_period
        self.underlying = underlying.upper()
        self.strike_step = strike_step
        self.expiry_weekday = expiry_weekday  # 3=Thursday (NIFTY), 2=Wednesday (BANKNIFTY)
        self._name = f"{underlying.upper()}_Options_EMA_VWAP"

    def name(self) -> str:
        return self._name

    # ------------------------------------------------------------------
    # Indicator Calculation
    # ------------------------------------------------------------------

    def _calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        # EMA on close
        df["EMA"] = df["close"].ewm(span=self.ema_period, adjust=False).mean()

        # VWAP (running, resets at start of data — good enough for intraday)
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        df["VWAP"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()

        return df

    # ------------------------------------------------------------------
    # Signal Generation
    # ------------------------------------------------------------------

    def generate_signal(self, data: pd.DataFrame) -> Dict:
        """
        Analyse NIFTY spot data and return an options trade signal.
        Returns:
            dict with keys: signal, option_type, option_symbol, strike,
                            expiry, price, sl, target, confidence, reason
        """
        min_candles = max(5, self.ema_period // 2 + 2)   # signal after ~5 candles instead of 22
        if len(data) < min_candles:
            return {"signal": "HOLD", "reason": f"Not enough data ({len(data)}/{min_candles} candles)"}

        try:
            df = self._calculate_indicators(data)
            curr = df.iloc[-1]
            prev = df.iloc[-2]

            spot = float(curr["close"])
            expiry = get_upcoming_expiry(date.today(), expiry_weekday=self.expiry_weekday)
            days_to_expiry = max((expiry - date.today()).days, 1)
            strike = select_atm_strike(spot, self.strike_step)

            # ── BUY CE: price crosses above EMA while above VWAP ──────
            bullish_cross = (
                prev["close"] <= prev["EMA"]
                and curr["close"] > curr["EMA"]
                and curr["close"] > curr["VWAP"]
            )

            # ── BUY PE: price crosses below EMA while below VWAP ──────
            bearish_cross = (
                prev["close"] >= prev["EMA"]
                and curr["close"] < curr["EMA"]
                and curr["close"] < curr["VWAP"]
            )

            if bullish_cross:
                option_type = "CE"
                symbol = build_option_symbol(self.underlying, expiry, strike, option_type)
                premium = estimate_option_premium(spot, strike, option_type, days_to_expiry)
                reason = (
                    f"EMA crossover ↑ above VWAP → BUY {self.underlying} {strike} CE "
                    f"(Expiry: {expiry.strftime('%d-%b-%Y')})"
                )
                return {
                    "signal": "BUY",
                    "option_type": option_type,
                    "option_symbol": symbol,
                    "strike": strike,
                    "expiry": str(expiry),
                    "price": round(premium, 2),
                    "sl": round(premium * 0.50, 2),        # 50% SL on option premium
                    "target": round(premium * 2.00, 2),    # 2× target on option premium
                    "confidence": 0.75,
                    "reason": reason,
                }

            if bearish_cross:
                option_type = "PE"
                symbol = build_option_symbol(self.underlying, expiry, strike, option_type)
                premium = estimate_option_premium(spot, strike, option_type, days_to_expiry)
                reason = (
                    f"EMA crossover ↓ below VWAP → BUY {self.underlying} {strike} PE "
                    f"(Expiry: {expiry.strftime('%d-%b-%Y')})"
                )
                return {
                    "signal": "SELL",
                    "option_type": option_type,
                    "option_symbol": symbol,
                    "strike": strike,
                    "expiry": str(expiry),
                    "price": round(premium, 2),
                    "sl": round(premium * 0.50, 2),
                    "target": round(premium * 2.00, 2),
                    "confidence": 0.75,
                    "reason": reason,
                }

        except Exception as e:
            logger.error(f"NiftyOptionsStrategy signal error: {e}", exc_info=True)

        return {"signal": "HOLD", "reason": "No crossover detected"}
