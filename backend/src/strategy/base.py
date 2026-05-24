from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd

class Strategy(ABC):
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Dict:
        """
        Analyze data and return signal.
        Expected return: {"signal": "BUY"|"SELL"|"HOLD", "price": float, "sl": float, "target": float}
        """
        pass

    @abstractmethod
    def name(self) -> str:
        pass
class StrategyManager:
    def __init__(self):
        self.strategies: List[Strategy] = []

    def add_strategy(self, strategy: Strategy):
        self.strategies.append(strategy)

    def get_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        signals = []
        for strat in self.strategies:
            signal = strat.generate_signal(market_data)
            if signal["signal"] != "HOLD":
                signal["strategy"] = strat.name()
                signals.append(signal)
        return signals
