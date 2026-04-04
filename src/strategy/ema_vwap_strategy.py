import pandas as pd
import numpy as np
from src.strategy.base import Strategy
from typing import Dict

class EMAVWAPStrategy(Strategy):
    def __init__(self, ema_period: int = 20):
        self.ema_period = ema_period

    def name(self) -> str:
        return "EMA_VWAP_Crossover"

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # EMA
        df['EMA'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()
        
        # VWAP (Simplified: (Price * Volume).cumsum() / Volume.cumsum())
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        df['VWAP'] = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        
        return df

    def generate_signal(self, data: pd.DataFrame) -> Dict:
        if len(data) < self.ema_period:
            return {"signal": "HOLD"}

        df = self.calculate_indicators(data)
        curr = df.iloc[-1]
        prev = df.iloc[-2]

        # BUY logic: Price > VWAP and Price crosses above EMA
        if curr['close'] > curr['VWAP'] and prev['close'] <= prev['EMA'] and curr['close'] > curr['EMA']:
            return {
                "signal": "BUY",
                "price": curr['close'],
                "sl": curr['close'] * 0.99,  # 1% SL
                "target": curr['close'] * 1.02 # 2% Target
            }

        # SELL logic: Price < VWAP and Price crosses below EMA
        if curr['close'] < curr['VWAP'] and prev['close'] >= prev['EMA'] and curr['close'] < curr['EMA']:
            return {
                "signal": "SELL",
                "price": curr['close'],
                "sl": curr['close'] * 1.01,
                "target": curr['close'] * 0.98
            }

        return {"signal": "HOLD"}
