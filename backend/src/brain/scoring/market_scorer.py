"""
Market Scorer Module
Aggregates multiple signals into a unified tradeability score.
"""

import logging
from typing import Dict, List

logger = logging.getLogger("Brain.MarketScorer")

class MarketScorer:
    """
    Combines sentiment, global cues, and technical metrics into a normalized score.
    """
    
    # Weight configuration for different signals
    # These can be moved to a config file later
    WEIGHTS = {
        "sentiment": 0.30,
        "global_cues": 0.35,
        "technical": 0.35
    }

    def calculate_score(self, sentiment: Dict, global_cues: Dict, metrics: Dict, market: str) -> Dict:
        """
        Calculates a final score (0-100) for a specific market.
        """
        try:
            # 1. Sentiment Component (0 to 1.0)
            # Normalized from news collector score (-1.0 to 1.0)
            sent_score = (sentiment.get("score", 0.0) + 1.0) / 2.0
            
            # 2. Global Cues Component (0 to 1.0)
            # Cap at +/- 2% change for normalization
            avg_change = global_cues.get("avg_change_pct", 0.0)
            global_score = max(0, min(1.0, (avg_change + 2.0) / 4.0))
            
            # 3. Technical Component (0 to 1.0)
            # Combine trend and RSI
            market_tech = metrics.get("markets", {}).get(market.upper(), {})
            trend_val = 1.0 if market_tech.get("trend") == "BULLISH" else 0.0
            rsi_val = market_tech.get("rsi", 50) / 100.0
            tech_score = (trend_val * 0.7) + (rsi_val * 0.3)
            
            # Weighted Average
            final_score = (
                (sent_score * self.WEIGHTS["sentiment"]) +
                (global_score * self.WEIGHTS["global_cues"]) +
                (tech_score * self.WEIGHTS["technical"])
            )
            
            # Confidence Calculation
            # Higher confidence if signals align
            confidence = self._calculate_confidence(sent_score, global_score, tech_score)
            
            return {
                "market": market,
                "score": round(final_score * 100, 1),
                "confidence": round(confidence * 100, 1),
                "components": {
                    "sentiment": round(sent_score, 2),
                    "global": round(global_score, 2),
                    "technical": round(tech_score, 2)
                }
            }

        except Exception as e:
            logger.error(f"Error calculating score for {market}: {e}")
            return {"market": market, "score": 50.0, "confidence": 0.0}

    def _calculate_confidence(self, s: float, g: float, t: float) -> float:
        """
        Determines confidence based on signal convergence/divergence.
        Max confidence if all signals are strongly bullish or strongly bearish.
        """
        # Variance between signals (lower variance = higher confidence)
        vals = [s, g, t]
        avg = sum(vals) / 3
        variance = sum((x - avg) ** 2 for x in vals) / 3
        
        # Base confidence 0.5, modified by convergence
        # If variance is 0 (all same), confidence adds 0.5
        # If variance is high, confidence drops
        conv_bonus = max(0, 0.5 - (variance * 2))
        
        # Strength bonus: signals at extremes (0 or 1) give more confidence
        strength = sum(abs(x - 0.5) for x in vals) / 1.5 # 0 to 1.0
        
        return min(1.0, 0.4 + conv_bonus + (strength * 0.2))
