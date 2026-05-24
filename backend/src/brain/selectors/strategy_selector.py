"""
Strategy Selector Module
Maps market states to trading strategies and risk levels.
"""

import logging
from typing import Dict

logger = logging.getLogger("Brain.StrategySelector")

class StrategySelector:
    """
    Decides the best strategy based on market score and volatility regime.
    """
    
    def select_strategy(self, score: float, confidence: float, vix_regime: str) -> Dict:
        """
        Determines strategy, risk level, and reasoning.
        """
        # Default neutral decision
        decision = {
            "strategy": "WAIT_AND_WATCH",
            "risk_level": "LOW",
            "reason": []
        }
        
        # 1. Determine Bias
        bias = "BULLISH" if score > 60 else "BEARISH" if score < 40 else "NEUTRAL"
        
        # 2. Risk Level based on VIX and Confidence
        if vix_regime in ["HIGH", "EXTREME"]:
            decision["risk_level"] = "HIGH"
            decision["reason"].append(f"High volatility regime detected ({vix_regime})")
        elif confidence < 40:
            decision["risk_level"] = "LOW"
            decision["reason"].append("Low signal confidence - reducing risk")
        else:
            decision["risk_level"] = "MEDIUM"
            
        # 3. Strategy Mapping Logic
        if bias == "NEUTRAL":
            if vix_regime == "LOW":
                decision["strategy"] = "MEAN_REVERSION"
                decision["reason"].append("Range-bound market with low volatility")
            else:
                decision["strategy"] = "WAIT_AND_WATCH"
                decision["reason"].append("No clear direction in volatile environment")
                
        elif bias == "BULLISH":
            if vix_regime == "LOW":
                decision["strategy"] = "TREND_FOLLOWING"
                decision["reason"].append("Strong bullish bias in stable market")
            elif vix_regime == "NORMAL":
                decision["strategy"] = "BREAKOUT"
                decision["reason"].append("Positive momentum with standard volatility")
            else: # HIGH/EXTREME
                decision["strategy"] = "MOMENTUM_SCALPING"
                decision["reason"].append("Fast moves in high volatility - scalping preferred")
                
        elif bias == "BEARISH":
            if vix_regime in ["HIGH", "EXTREME"]:
                decision["strategy"] = "MOMENTUM_SCALPING"
                decision["reason"].append("Aggressive bearish moves - quick exits required")
            else:
                decision["strategy"] = "TREND_FOLLOWING"
                decision["reason"].append("Steady bearish trend detected")

        # 4. Filter for No-Trade zone
        if confidence < 30 and vix_regime == "EXTREME":
            decision["strategy"] = "NO_TRADE"
            decision["reason"] = ["Conflicting signals in extreme volatility - safety first"]

        return decision
