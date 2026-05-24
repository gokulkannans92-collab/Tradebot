"""
Generic Technical Strategy
Used for Equity and Commodity trading where option strikes are not required.
"""

import pandas as pd
import logging
from typing import Dict
from src.strategy.base import Strategy

logger = logging.getLogger("GenericTechnicalStrategy")

class GenericTechnicalStrategy(Strategy):
    """
    Standard technical analysis (EMA/RSI) for direct asset trading.
    """
    
    def __init__(self, underlying: str, ema_fast: int = 9, ema_slow: int = 21, rsi_period: int = 14):
        self.underlying = underlying
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self._name = f"{underlying}_Technical_RSI"

    def name(self) -> str:
        return self._name

    def _add_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        # EMA
        df["EMA_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["EMA_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()
        
        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss.replace(0, 0.001) # Avoid division by zero
        df["RSI"] = 100 - (100 / (1 + rs))
        return df

    def generate_signal(self, data: pd.DataFrame, broker=None) -> Dict:
        if len(data) < max(self.ema_slow, self.rsi_period) + 5:
            return {"signal": "HOLD", "reason": f"Warming up ({len(data)} candles)"}

        df = self._add_indicators(data)
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = curr["close"]
        rsi = curr["RSI"]
        
        # Bullish Crossover + RSI Confirmation (> 50)
        if prev["EMA_fast"] <= prev["EMA_slow"] and curr["EMA_fast"] > curr["EMA_slow"]:
            if rsi > 50:
                return {
                    "signal": "BUY",
                    "price": round(price, 2),
                    "sl": round(price * 0.99, 2), # 1% SL
                    "target": round(price * 1.02, 2), # 2% Target
                    "reason": f"Bullish EMA Crossover confirmed by RSI ({rsi:.1f})",
                    "option_symbol": self.underlying,
                    "option_type": "EQUITY"
                }
            else:
                return {"signal": "HOLD", "reason": f"Bullish EMA Crossover rejected by RSI ({rsi:.1f} <= 50)"}
            
        # Bearish Crossover + RSI Confirmation (< 50)
        if prev["EMA_fast"] >= prev["EMA_slow"] and curr["EMA_fast"] < curr["EMA_slow"]:
            if rsi < 50:
                return {
                    "signal": "SELL",
                    "price": round(price, 2),
                    "sl": round(price * 1.01, 2), # 1% SL
                    "target": round(price * 0.98, 2), # 2% Target
                    "reason": f"Bearish EMA Crossover confirmed by RSI ({rsi:.1f})",
                    "option_symbol": self.underlying,
                    "option_type": "EQUITY"
                }
            else:
                return {"signal": "HOLD", "reason": f"Bearish EMA Crossover rejected by RSI ({rsi:.1f} >= 50)"}

        return {"signal": "HOLD", "reason": f"No clear trend (RSI: {rsi:.1f})"}
