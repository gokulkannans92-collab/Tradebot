"""
Market Selector Logic
Chooses the best market to trade based on news sentiment and technical trend.
"""

import logging
from typing import Dict, List, Optional
from src.strategy.sentiment_engine import NewsSentimentAnalyzer

logger = logging.getLogger("MarketSelector")

class MarketSelector:
    """
    Coordinates multi-market analysis to pick the focus market for the day.
    """
    
    def __init__(self):
        self.analyzer = NewsSentimentAnalyzer()
        self.market_stats = {}

    def analyze_all_markets(self, enabled_markets: List[str]) -> Dict:
        """
        Runs sentiment analysis on all enabled markets and returns the winner.
        """
        results = {}
        for market in enabled_markets:
            sentiment = self.analyzer.get_market_sentiment(market)
            results[market] = sentiment
            
        self.market_stats = results
        return self.pick_best_market(results)

    def pick_best_market(self, results: Dict) -> Dict:
        """
        Ranks markets by sentiment score and confidence.
        """
        if not results:
            return {"market": "NIFTY", "reason": "Default fallback"}

        # Sort by absolute score to find the most "active" market bias
        ranked = sorted(
            results.items(), 
            key=lambda item: abs(item[1]["score"]), 
            reverse=True
        )

        best_market, best_data = ranked[0]
        
        # If the strongest sentiment is too weak, default to NIFTY (unless only one market was analyzed)
        if abs(best_data["score"]) < 0.15:
            fallback_market = "NIFTY"
            if len(results) == 1:
                fallback_market = best_market # Keep the requested market
            
            return {
                "market": fallback_market,
                "reason": f"Neutral sentiment for {best_market}. " + ("Sticking to primary Index." if fallback_market == "NIFTY" else "Proceeding with caution."),
                "all_results": results
            }

        bias_text = "Bullish" if best_data["score"] > 0 else "Bearish"
        
        return {
            "market": best_market,
            "bias": best_data["bias"],
            "score": best_data["score"],
            "reason": f"Strong {bias_text} news sentiment detected ({best_data['score']:.2f}).",
            "headlines": best_data["headlines"],
            "all_results": results
        }

    def get_latest_stats(self) -> Dict:
        return self.market_stats
