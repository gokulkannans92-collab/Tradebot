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
        min_signals: int = 3,            # Senior Analyst: All 3 must agree
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

        # ATR (Average True Range) for Dynamic SL/Target
        high_low = df["high"] - df["low"]
        high_cp  = (df["high"] - df["close"].shift(1)).abs()
        low_cp   = (df["low"] - df["close"].shift(1)).abs()
        
        tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
        df["ATR"] = tr.ewm(span=self.rsi_period, adjust=False).mean()

        # VWAP (Cumulative since start of data - assumes daily data)
        df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()

        return df

    def _get_mtf_trend(self, df: pd.DataFrame) -> int:
        """Resample to 15m and check trend using EMA 26."""
        try:
            # Resample 5m to 15m
            df_15 = df.resample('15min', on='time').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            if len(df_15) < 5: return 0
            
            ema_26 = df_15["close"].ewm(span=26, adjust=False).mean()
            curr_ema = ema_26.iloc[-1]
            curr_price = df_15["close"].iloc[-1]
            
            if curr_price > curr_ema: return 1
            if curr_price < curr_ema: return -1
            return 0
        except:
            return 0

    # ──────────────────────────────────────────────────────────────────
    # Sub-strategy signals: return +1 (bullish), -1 (bearish), 0 (neutral)
    # ──────────────────────────────────────────────────────────────────

    def _ema_signal(self, curr: pd.Series, prev: pd.Series) -> Tuple[int, str]:
        """EMA 9/21 trend direction - bullish when EMA9 > EMA21, bearish when below."""
        fast, slow = curr["EMA_fast"], curr["EMA_slow"]
        if pd.isna(fast) or pd.isna(slow):
            return 0, "EMA unavailable"
        gap_pct = abs(fast - slow) / slow * 100  # % gap - ignore near-zero noise
        if gap_pct < 0.1:          # Increased from 0.05% for higher trend quality
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
            return 1, f"Breakout above Rs{prev['high']:.1f}"
        if curr["close"] < prev["low"] and vol_spike:
            return -1, f"Breakout below Rs{prev['low']:.1f}"
        return 0, "No breakout"

    def _rsi_signal(self, curr: pd.Series) -> Tuple[int, str]:
        """RSI threshold signal with exhaustion filters."""
        rsi = curr["RSI"]
        if pd.isna(rsi):
            return 0, "RSI unavailable"
        
        # --- EXHAUSTION FILTERS ---
        if rsi > 85:
            return 0, f"RSI={rsi:.1f} EXHAUSTION (Overbought - Too High to Buy)"
        if rsi < 15:
            return 0, f"RSI={rsi:.1f} EXHAUSTION (Oversold - Too Low to Sell)"
            
        if rsi > 60:
            return 1,  f"RSI={rsi:.1f} > 60 (High Momentum)"
        if rsi < 40:
            return -1, f"RSI={rsi:.1f} < 40 (High Pressure)"
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

            # --- FILTER 1: Volatility Check (ATR) ---
            atr = curr.get("ATR", 0)
            candle_range = curr["high"] - curr["low"]
            if candle_range < 0.2 * atr:
                return {"signal": "HOLD", "reason": f"Dead Market (Range < 20% ATR: {candle_range:.1f} < {0.2*atr:.1f})"}

            # --- FILTER 2: VWAP (Institutional Trend) ---
            vwap = curr.get("vwap", 0)
            price = curr["close"]

            # --- FILTER 3: MTF (15m Alignment) ---
            mtf_trend = self._get_mtf_trend(data)

            # --- FILTER 4: VIX (Volatility Guard) ---
            vix = None  # None = unknown; we will HOLD if we can't verify VIX
            if broker:
                try:
                    # Use broker-specific VIX symbols (falls back to Angel defaults)
                    vix_symbols = broker.get_vix_symbols() if hasattr(broker, 'get_vix_symbols') \
                        else ["India VIX", "INDIA VIX", "NSE:INDIAVIX-INDEX"]
                    vix_data = None
                    for sym in vix_symbols:
                        vix_data = broker.get_quote(sym)
                        if vix_data: break
                        
                    if vix_data:
                        vix = float(vix_data.get("last_price") or vix_data.get("price", 0) or 0)
                        if vix == 0:
                            vix = None  # Treat zero as fetch failure
                except Exception as e:
                    logger.debug(f"VIX fetch failed: {e}")
            
            if vix is None:
                return {"signal": "HOLD", "reason": "VIX data unavailable - cannot verify market conditions (Safety HOLD)"}
            
            if vix < 11.5:
                return {"signal": "HOLD", "reason": f"VIX Too Low ({vix:.2f}) - No movement expected"}
            if vix > 20.0:
                return {"signal": "HOLD", "reason": f"VIX Too High ({vix:.2f}) - Market Volatility Guard (Avoid)"}

            # --- Market Filter: Sideways/Low Volatility ---
            # 1. Average Candle Range (Volatility)
            recent_rows = df.tail(10)
            avg_range = (recent_rows['high'] - recent_rows['low']).mean()
            range_pct = (avg_range / curr['close']) * 100
            
            # If range is less than 0.05% of price, it's low volatility
            if range_pct < 0.05:
                return {"signal": "HOLD", "reason": f"Low Volatility (Range: {range_pct:.3f}%)"}

            spot = float(curr["close"])
            if broker:
                try:
                    expiry_str = broker.get_live_expiry(self.underlying)
                    if expiry_str:
                        from datetime import datetime
                        # Handle different formats (Angel: 27MAR2024, Zerodha: 2024-03-27)
                        try:
                            expiry = datetime.strptime(expiry_str, "%d%b%Y").date()
                        except:
                            expiry = date.fromisoformat(expiry_str)
                        logger.info(f"📅 [DYNAMIC] Using live expiry for {self.underlying}: {expiry}")
                    else:
                        if not getattr(broker, 'is_paper_trading', True):
                            return {"signal": "HOLD", "reason": "CRITICAL: Live expiry fetch failed - Aborting Live Trade for safety"}
                        expiry = get_upcoming_expiry(date.today(), self.expiry_weekday)
                except Exception as e:
                    if not getattr(broker, 'is_paper_trading', True):
                        return {"signal": "HOLD", "reason": f"CRITICAL: Expiry API Error ({e}) - Aborting Live Trade for safety"}
                    logger.warning(f"Failed to fetch live expiry: {e}. Falling back to calculation.")
                    expiry = get_upcoming_expiry(date.today(), self.expiry_weekday)
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

            # --- ENRICHED LOGGING ---
            # Construct a clear summary of all signal components
            sig_markers = {1: "✅", -1: "📉", 0: "⚪"}
            detailed_status = (
                f"EMA:{sig_markers[s_ema]} ({r_ema}) | "
                f"BRK:{sig_markers[s_brk]} ({r_brk}) | "
                f"RSI:{sig_markers[s_rsi]} ({r_rsi})"
            )
            
            # Log evaluation summary on every candle if not just warming up
            logger.info(f"[{self.underlying}] Evaluation: {detailed_status} | Signals: {bullish}B / {bearish}S")

            # --- RSI EXHAUSTION LOCK (Hard-Stop Safety) ---
            # Even if 2/3 agree, we ABORT if RSI is in exhaustion to prevent buying the top/selling the bottom.
            if "EXHAUSTION" in r_rsi:
                return {"signal": "HOLD", "reason": f"Aborted: RSI Exhaustion ({r_rsi})"}

            # --- STRICT CONSENSUS (Senior Analyst Rule) ---
            if bullish < self.min_signals and bearish < self.min_signals:
                return {"signal": "HOLD", "reason": f"No Full Consensus ({self.min_signals}/3 required)"}

            # --- CONFLICT CHECK (Senior Analyst Rule: Zero Tolerance) ---
            if bullish > 0 and bearish > 0:
                return {"signal": "HOLD", "reason": f"Signal Conflict: {bullish}B vs {bearish}S (Zero Tolerance)"}

            active_reasons = ", ".join(
                f"{k}:{v}" for k, v in reasons.items() if "No " not in v and "neutral" not in v and "EXHAUSTION" not in v
            )

            if bullish >= self.min_signals:
                # ENFORCE TRIPLE CONFIRMATION: EMA Trend must NOT be neutral
                if s_ema == 0:
                    return {"signal": "HOLD", "reason": f"Bullish Rejected: EMA Trend is Neutral (Sideways)"}
                
                # ENFORCE FILTERS
                if price < vwap:
                    return {"signal": "HOLD", "reason": f"Bullish signal Rejected: Price ({price:.1f}) < VWAP ({vwap:.1f})"}
                if mtf_trend == -1:
                    return {"signal": "HOLD", "reason": f"Bullish signal Rejected: 15m Trend is Bearish"}

                option_type = "CE"
                symbol = broker.get_symbol(self.underlying, expiry, strike, option_type) if broker else build_option_symbol(self.underlying, expiry, strike, option_type)
                
                # --- LIVE PRICE ACQUISITION ---
                # Attempt to get real LTP from broker instead of mock estimation
                premium = 0
                if broker:
                    try:
                        quote = broker.get_quote(symbol)
                        if quote:
                            premium = float(quote.get("last_price") or quote.get("price", 0))
                            if premium > 0:
                                logger.info(f"🟢 [LIVE QUOTE] Fetched real premium for {symbol}: Rs{premium:.2f}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch live quote for {symbol}: {e}")
                
                # Fallback check: Do not trade if live quote fails
                if premium <= 0:
                    return {"signal": "HOLD", "reason": f"Signal aborted: Could not fetch real-time quote for {symbol} from broker."}
                
                # Dynamic ATR-based Risk Management
                atr = curr.get("ATR", 0)
                # Map Spot ATR to Option SL/Target (roughly 0.5 delta for ATM)
                # We use 1.5x ATR for SL and 3.0x ATR for Target
                sl_points     = atr * 1.5 * 0.5
                target_points = atr * 3.0 * 0.5
                
                # Ensure SL doesn't exceed 60% of premium and Target is at least 30%
                sl_price     = round(max(premium - sl_points, premium * 0.4), 2)
                target_price = round(min(premium + target_points, premium * 3.0), 2)
                
                return {
                    "signal":        "BUY",
                    "option_type":   option_type,
                    "option_symbol": symbol,
                    "strike":        strike,
                    "expiry":        str(expiry),
                    "price":         round(premium, 2),
                    "spot":          spot,
                    "sl":            sl_price,
                    "target":        target_price,
                    "confidence":    round(bullish / 3, 2),
                    "reason":        f"2/3 bullish - {active_reasons} (ATR={atr:.1f})",
                    "signals":       {"EMA": s_ema, "Breakout": s_brk, "RSI": s_rsi},
                }

            if bearish >= self.min_signals:
                # ENFORCE TRIPLE CONFIRMATION: EMA Trend must NOT be neutral
                if s_ema == 0:
                    return {"signal": "HOLD", "reason": f"Bearish Rejected: EMA Trend is Neutral (Sideways)"}
                
                # ENFORCE FILTERS
                if price > vwap:
                    return {"signal": "HOLD", "reason": f"Bearish signal Rejected: Price ({price:.1f}) > VWAP ({vwap:.1f})"}
                if mtf_trend == 1:
                    return {"signal": "HOLD", "reason": f"Bearish signal Rejected: 15m Trend is Bullish"}

                option_type = "PE"
                symbol = broker.get_symbol(self.underlying, expiry, strike, option_type) if broker else build_option_symbol(self.underlying, expiry, strike, option_type)
                
                # --- LIVE PRICE ACQUISITION ---
                premium = 0
                if broker:
                    try:
                        quote = broker.get_quote(symbol)
                        if quote:
                            premium = float(quote.get("last_price") or quote.get("price", 0))
                            if premium > 0:
                                logger.info(f"🟢 [LIVE QUOTE] Fetched real premium for {symbol}: Rs{premium:.2f}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch live quote for {symbol}: {e}")
                
                if premium <= 0:
                    return {"signal": "HOLD", "reason": f"Signal aborted: Could not fetch real-time quote for {symbol} from broker."}
                
                # Dynamic ATR-based Risk Management
                atr = curr.get("ATR", 0)
                sl_points     = atr * 1.5 * 0.5
                target_points = atr * 3.0 * 0.5
                
                sl_price     = round(max(premium - sl_points, premium * 0.4), 2)
                target_price = round(min(premium + target_points, premium * 3.0), 2)
                
                return {
                    "signal":        "SELL",
                    "option_type":   option_type,
                    "option_symbol": symbol,
                    "strike":        strike,
                    "expiry":        str(expiry),
                    "price":         round(premium, 2),
                    "spot":          spot,
                    "sl":            sl_price,
                    "target":        target_price,
                    "confidence":    round(bearish / 3, 2),
                    "reason":        f"2/3 bearish - {active_reasons} (ATR={atr:.1f})",
                    "signals":       {"EMA": s_ema, "Breakout": s_brk, "RSI": s_rsi},
                }

        except Exception as e:
            logger.error(f"CombinedSignalStrategy error: {e}", exc_info=True)

        return {"signal": "HOLD", "reason": "No 2-of-3 confirmation"}
