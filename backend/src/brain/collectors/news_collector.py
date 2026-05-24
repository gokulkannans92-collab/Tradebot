"""
News Collector Module
Fetches and analyzes market-specific news using async HTTP.
"""

import logging
import httpx
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import time
from datetime import datetime

logger = logging.getLogger("Brain.NewsCollector")

class NewsCollector:
    """
    Modular collector for financial news sentiment.
    """
    
    SOURCES = {
        "NIFTY":      "https://www.moneycontrol.com/news/tags/nifty.html",
        "BANKNIFTY":  "https://www.moneycontrol.com/news/tags/bank-nifty.html",
        "FINNIFTY":   "https://www.moneycontrol.com/news/tags/finnifty.html",
        "MIDCPNIFTY": "https://www.moneycontrol.com/news/tags/midcap-nifty.html",
        "COMMODITY":  "https://www.moneycontrol.com/news/business/commodities/",
        "EQUITY":     "https://www.moneycontrol.com/news/business/stocks/"
    }
    
    # Weighted sentiment keywords — kept in sync with strategy/sentiment_engine.py
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

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def fetch_sentiment(self, market: str) -> Dict:
        """
        Asynchronously fetches and analyzes sentiment for a given market.
        """
        url = self.SOURCES.get(market.upper())
        if not url:
            return {"market": market, "score": 0.0, "bias": "NEUTRAL", "error": "Invalid market"}

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return {"market": market, "score": 0.0, "bias": "NEUTRAL", "error": f"HTTP {response.status_code}"}

                soup = BeautifulSoup(response.text, 'html.parser')
                headlines = [tag.get_text().strip() for tag in soup.find_all(['h2', 'h3'], limit=10) if len(tag.get_text().strip()) > 20]

                if not headlines:
                    return {"market": market, "score": 0.0, "bias": "NEUTRAL", "count": 0}

                score = self._calculate_score(headlines)
                bias = "BULLISH" if score > 0.1 else "BEARISH" if score < -0.1 else "NEUTRAL"

                return {
                    "market": market,
                    "score": round(score, 2),
                    "bias": bias,
                    "headlines_count": len(headlines),
                    "top_headline": headlines[0] if headlines else "",
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Error collecting news for {market}: {e}")
            return {"market": market, "score": 0.0, "bias": "NEUTRAL", "error": str(e)}

    def _calculate_score(self, headlines: List[str]) -> float:
        """Weighted sentiment scoring."""
        bull_weight = 0.0
        bear_weight = 0.0
        
        for text in headlines:
            text = text.lower()
            for word, weight in self.BULLISH_KEYWORDS.items():
                if word in text: bull_weight += weight
            for word, weight in self.BEARISH_KEYWORDS.items():
                if word in text: bear_weight += weight
        
        total = bull_weight + bear_weight
        return (bull_weight - bear_weight) / total if total > 0 else 0.0
