"""
Global Cues Collector
Fetches international market performance to gauge overall sentiment.
"""

import logging
import yfinance as yf
from typing import Dict
import asyncio

logger = logging.getLogger("Brain.GlobalCues")

class GlobalCuesCollector:
    """
    Fetches performance of major global indices.
    """
    
    # Mapping of logical names to Yahoo Finance tickers.
    # Note: GIFT Nifty futures are not available on Yahoo Finance.
    # NIFTYBEES.NS (Nippon India ETF) is the closest intraday proxy.
    # ^NSEI is used as a fallback for after-hours/weekend sentiment.
    TICKERS = {
        "S&P500":    "^GSPC",
        "NASDAQ":    "^IXIC",
        "NIFTY_ETF": "NIFTYBEES.NS",  # GIFT Nifty proxy (best available via yfinance)
        "HANG_SENG": "^HSI",
        "NIKKEI":    "^N225"
    }

    async def fetch_global_sentiment(self) -> Dict:
        """
        Fetches the percentage change for major global indices.
        """
        results = {}
        
        # yfinance is synchronous, so we run it in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        tasks = [
            loop.run_in_executor(None, self._get_ticker_data, name, ticker)
            for name, ticker in self.TICKERS.items()
        ]
        
        gathered_results = await asyncio.gather(*tasks)
        
        for res in gathered_results:
            results.update(res)
            
        # Calculate overall global score (-1.0 to 1.0)
        changes = [data["change_pct"] for data in results.values() if data["change_pct"] is not None]
        avg_change = sum(changes) / len(changes) if changes else 0.0
        
        return {
            "indices": results,
            "avg_change_pct": round(avg_change, 2),
            "global_bias": "BULLISH" if avg_change > 0.5 else "BEARISH" if avg_change < -0.5 else "NEUTRAL"
        }

    def _get_ticker_data(self, name: str, ticker: str) -> Dict:
        """Helper to fetch data via yfinance."""
        try:
            t = yf.Ticker(ticker)
            # Get last 2 days of data to calculate change
            hist = t.history(period="2d")
            
            if len(hist) < 2:
                return {name: {"change_pct": None, "price": None}}
            
            prev_close = hist['Close'].iloc[-2]
            curr_price = hist['Close'].iloc[-1]
            change_pct = ((curr_price - prev_close) / prev_close) * 100
            
            return {
                name: {
                    "change_pct": round(change_pct, 2),
                    "price": round(curr_price, 2)
                }
            }
        except Exception as e:
            logger.error(f"Error fetching {name} ({ticker}): {e}")
            return {name: {"change_pct": None, "price": None}}
