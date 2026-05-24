"""
News Sentiment Engine
Fetches financial news and performs keyword-based sentiment analysis.
"""

import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import time
from datetime import datetime

logger = logging.getLogger("SentimentEngine")

class NewsSentimentAnalyzer:
    """
    Analyzes news headlines to determine market bias.
    """
    
    # Target News URLs
    SOURCES = {
        "NIFTY":      "https://www.moneycontrol.com/news/tags/nifty.html",
        "BANKNIFTY":  "https://www.moneycontrol.com/news/tags/bank-nifty.html",
        "COMMODITY":  "https://www.moneycontrol.com/news/business/commodities/",
        "EQUITY":     "https://www.moneycontrol.com/news/business/stocks/"
    }
    
    # Sentiment Keywords with Weights
    # High impact words get 2.0, medium 1.0
    BULLISH_KEYWORDS = {
        "surge": 2.0, "rally": 2.0, "record high": 2.0, "breakout": 2.0,
        "rise": 1.0, "gain": 1.0, "growth": 1.0, "positive": 1.0, 
        "strong": 1.0, "outperform": 1.0, "bullish": 1.0, "profit": 1.0, 
        "up": 1.0, "buy": 1.0, "optimistic": 1.0, "expansion": 1.0, 
        "dividend": 1.0, "recovery": 1.0, "win": 1.0
    }
    
    BEARISH_KEYWORDS = {
        "crash": 2.0, "slump": 2.0, "scam": 2.0, "panic": 2.0, "plunge": 2.0,
        "fall": 1.0, "drop": 1.0, "negative": 1.0, "weak": 1.0, 
        "underperform": 1.0, "bearish": 1.0, "loss": 1.0, "down": 1.0, 
        "sell": 1.0, "low": 1.0, "pessimistic": 1.0, "contraction": 1.0, 
        "debt": 1.0, "dip": 1.0, "correction": 1.0, "volatile": 1.0
    }

    def __init__(self, cache_expiry_minutes: int = 5):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.cache_expiry = cache_expiry_minutes * 60
        self._cache: Dict[str, Dict] = {} # {market: {"result": dict, "time": timestamp}}

    def get_market_sentiment(self, market: str) -> Dict:
        """
        Fetches headlines and calculates a sentiment score.
        Uses caching to avoid redundant API calls and rate limiting.
        """
        market = market.upper()
        
        # ─── 1. Rate Limiting / Caching Check ───
        if market in self._cache:
            elapsed = time.time() - self._cache[market]["time"]
            if elapsed < self.cache_expiry:
                logger.debug(f"Using cached sentiment for {market} ({int(elapsed)}s old)")
                return self._cache[market]["result"]

        url = self.SOURCES.get(market)
        if not url:
            return {"score": 0.0, "headlines": [], "bias": "NEUTRAL"}

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to fetch news for {market}: Status {response.status_code}")
                return {"score": 0.0, "headlines": [], "bias": "NEUTRAL"}

            soup = BeautifulSoup(response.text, 'html.parser')
            headlines = []
            for tag in soup.find_all(['h2', 'h3'], limit=12):
                text = tag.get_text().strip()
                if len(text) > 25:
                    headlines.append(text)

            if not headlines:
                return {"score": 0.0, "headlines": [], "bias": "NEUTRAL"}

            score = self._calculate_score(headlines)
            bias = "BULLISH" if score > 0.15 else "BEARISH" if score < -0.15 else "NEUTRAL"
            
            result = {
                "score": round(score, 2),
                "headlines": headlines[:5],
                "bias": bias,
                "timestamp": datetime.now().isoformat()
            }
            
            # ─── 2. Update Cache ───
            self._cache[market] = {
                "result": result,
                "time": time.time()
            }
            
            logger.info(f"Sentiment for {market}: {score:.2f} ({bias}) based on {len(headlines)} headlines")
            return result

        except Exception as e:
            logger.error(f"Sentiment analysis error for {market}: {e}")
            return {"score": 0.0, "headlines": [], "bias": "NEUTRAL"}

    def _calculate_score(self, headlines: List[str]) -> float:
        """Calculates a weighted sentiment score based on keyword impact."""
        total_bull_weight = 0.0
        total_bear_weight = 0.0
        
        for text in headlines:
            text = text.lower()
            
            # Weighted Bullish matching
            for word, weight in self.BULLISH_KEYWORDS.items():
                if word in text:
                    total_bull_weight += weight
            
            # Weighted Bearish matching
            for word, weight in self.BEARISH_KEYWORDS.items():
                if word in text:
                    total_bear_weight += weight
            
        total_weight = total_bull_weight + total_bear_weight
        if total_weight == 0:
            return 0.0
            
        # Normalised score between -1 and 1
        return (total_bull_weight - total_bear_weight) / total_weight


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyzer = NewsSentimentAnalyzer()
    for m in ["NIFTY", "COMMODITY"]:
        print(analyzer.get_market_sentiment(m))

