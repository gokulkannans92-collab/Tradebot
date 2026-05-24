import pandas as pd
from src.strategy.base import Strategy
from typing import Dict
import logging
import time

logger = logging.getLogger("DebugStrategy")

class DebugStrategy(Strategy):
    """
    Dummy strategy that generates a BUY signal every few iterations
    Used ONLY for verifying the system flow.
    """
    def __init__(self, interval_seconds: int = 120):
        self.interval = interval_seconds
        self.last_signal_time = 0
        self._name = "DEBUG_RANDOM_BUY"

    def name(self) -> str:
        return self._name

    def generate_signal(self, data: pd.DataFrame) -> Dict:
        now = time.time()
        
        # Generate a BUY signal every 'interval' seconds
        if now - self.last_signal_time > self.interval:
            self.last_signal_time = now
            if not data.empty:
                ltp = data['close'].iloc[-1]
                return {
                    "signal": "BUY",
                    "price": ltp,
                    "sl": ltp * 0.99,
                    "target": ltp * 1.02,
                    "confidence": 1.0,
                    "reason": "DEBUG: Periodic trigger for testing flow"
                }
        
        return {"signal": "HOLD", "reason": "DEBUG: Waiting for interval"}
