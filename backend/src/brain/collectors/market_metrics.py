"""
Market Metrics Collector
Analyzes technical metrics like Volatility (VIX) and Trend Strength.
"""

import logging
import yfinance as yf
import pandas as pd
import asyncio
from typing import Dict, Optional

logger = logging.getLogger("Brain.MarketMetrics")

class MarketMetricsCollector:
    """
    Analyzes technical health of the markets.
    """
    
    # India VIX ticker on Yahoo Finance
    VIX_TICKER = "^INDIAVIX"
    
    # Primary Indian Indices
    MARKETS = {
        "NIFTY":      "^NSEI",
        "BANKNIFTY":  "^NSEBANK",
        "FINNIFTY":   "^CNXFIN",
        "MIDCPNIFTY": "^NSEMDCP50"
    }

    async def fetch_metrics(self, requested_market: Optional[str] = None) -> Dict:
        """
        Fetches VIX and basic trend metrics for the requested market and primary indices.
        """
        loop = asyncio.get_event_loop()
        
        # Fetch VIX
        vix_data = await loop.run_in_executor(None, self._get_vix)
        
        # Determine markets to analyze
        markets_to_fetch = self.MARKETS.copy()
        if requested_market and requested_market.upper() not in markets_to_fetch:
            # Try to map common names to Yahoo Finance tickers
            ticker_map = {
                "GOLD": "GC=F",
                "SILVER": "SI=F",
                "CRUDEOIL": "CL=F",
                "RELIANCE": "RELIANCE.NS",
                "HDFCBANK": "HDFCBANK.NS",
                "COMMODITY": "GC=F", # Default to Gold
                "EQUITY": "RELIANCE.NS" # Default to Reliance
            }
            ticker = ticker_map.get(requested_market.upper(), f"{requested_market.upper()}.NS")
            markets_to_fetch[requested_market.upper()] = ticker

        # Fetch Market Health
        tasks = [
            loop.run_in_executor(None, self._analyze_trend, name, ticker)
            for name, ticker in markets_to_fetch.items()
        ]
        
        market_results = await asyncio.gather(*tasks)
        
        combined_markets = {}
        for res in market_results:
            combined_markets.update(res)
            
        return {
            "vix": vix_data,
            "markets": combined_markets,
            "volatility_regime": self._get_vix_regime(vix_data["current"])
        }

    def _get_vix(self) -> Dict:
        """Fetch India VIX value."""
        try:
            vix = yf.Ticker(self.VIX_TICKER)
            curr = vix.history(period="1d")['Close'].iloc[-1]
            prev = vix.history(period="5d")['Close'].iloc[-2]
            change = ((curr - prev) / prev) * 100
            return {"current": round(curr, 2), "change_pct": round(change, 2)}
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return {"current": 15.0, "change_pct": 0.0} # Default/Neutral

    def _analyze_trend(self, name: str, ticker: str) -> Dict:
        """Basic trend analysis using EMA and RSI."""
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="30d")
            
            if len(df) < 20:
                return {name: {"trend": "UNKNOWN", "rsi": 50}}
                
            # Simple EMA 9 vs 21
            ema9 = df['Close'].ewm(span=9).mean().iloc[-1]
            ema21 = df['Close'].ewm(span=21).mean().iloc[-1]
            
            # Simple RSI 14
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            
            trend = "BULLISH" if ema9 > ema21 else "BEARISH"
            
            return {
                name: {
                    "trend": trend,
                    "rsi": round(rsi, 2),
                    "close": round(df['Close'].iloc[-1], 2)
                }
            }
        except Exception as e:
            logger.error(f"Error analyzing {name}: {e}")
            return {name: {"trend": "UNKNOWN", "rsi": 50}}

    def _get_vix_regime(self, vix_value: float) -> str:
        """Categorize volatility regime."""
        if vix_value < 13: return "LOW"
        if vix_value < 18: return "NORMAL"
        if vix_value < 25: return "HIGH"
        return "EXTREME"
