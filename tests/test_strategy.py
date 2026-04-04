import pytest
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy.base import Strategy, StrategyManager


class TestStrategy(Strategy):
    def generate_signal(self, data: pd.DataFrame) -> dict:
        return {"signal": "HOLD", "price": 0.0, "sl": 0.0, "target": 0.0}
    
    def name(self) -> str:
        return "TestStrategy"


class TestStrategyManager:
    def test_add_strategy(self):
        manager = StrategyManager()
        strategy = TestStrategy()
        manager.add_strategy(strategy)
        assert len(manager.strategies) == 1

    def test_get_signals_hold(self):
        manager = StrategyManager()
        manager.add_strategy(TestStrategy())
        
        data = pd.DataFrame({"close": [100, 101, 102]})
        signals = manager.get_signals(data)
        assert len(signals) == 0

    def test_get_signals_buy(self):
        class BuyStrategy(Strategy):
            def generate_signal(self, data: pd.DataFrame) -> dict:
                return {"signal": "BUY", "price": 100.0, "sl": 95.0, "target": 110.0}
            
            def name(self) -> str:
                return "BuyStrategy"
        
        manager = StrategyManager()
        manager.add_strategy(BuyStrategy())
        
        data = pd.DataFrame({"close": [100]})
        signals = manager.get_signals(data)
        assert len(signals) == 1
        assert signals[0]["signal"] == "BUY"
        assert signals[0]["strategy"] == "BuyStrategy"
