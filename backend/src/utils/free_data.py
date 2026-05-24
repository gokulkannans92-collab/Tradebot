import yfinance as yf
import pandas as pd
import threading
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("FreeData")

class FreeDataFetcher:
    """ Fetches free market data for Indian Indices using Yahoo Finance. """
    
    _TICKERS = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "FINNIFTY": "NIFTY_FIN_SERVICE.NS" # Yahoo ticker for Finnifty
    }
    
    def __init__(self):
        self._cache = {}
        self._last_fetch = {}
        self._lock = threading.Lock()

    def get_history(self, symbol: str, period="1d", interval="5m"):
        """ Fetch historical OHLC data. """
        ticker = self._TICKERS.get(symbol.upper(), symbol)
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
            if not df.empty:
                # Handle MultiIndex columns if present (common in newer yf versions)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                # Standardize columns and drop unwanted ones
                cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                df = df[[c for c in cols if c in df.columns]].rename(columns=lambda x: x.lower())
                return df
        except Exception as e:
            logger.error(f"Error fetching history for {symbol}: {e}")
        return pd.DataFrame()

    def get_latest_quote(self, symbol: str):
        """ Fetch real-time LTP/Quote. (Note: Yahoo has 1-15 min delay for free accounts) """
        ticker = self._TICKERS.get(symbol.upper(), symbol)
        
        # Rate limit to avoid blocking
        with self._lock:
            now = time.time()
            if symbol in self._last_fetch and (now - self._last_fetch[symbol]) < 30:
                return self._cache.get(symbol)

        try:
            # period="1d", interval="1m" gets today's data till now
            data = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
            if not data.empty:
                # Handle MultiIndex columns
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                
                last_row = data.iloc[-1]
                quote = {
                    "symbol": symbol,
                    "price": float(last_row['Close']),
                    "last_price": float(last_row['Close']),
                    "high": float(last_row['High']),
                    "low": float(last_row['Low']),
                    "open": float(last_row['Open']),
                    "volume": int(last_row['Volume']) if 'Volume' in last_row else 0,
                    "timestamp": datetime.now().timestamp(),
                    "source": "yfinance"
                }
                with self._lock:
                    self._cache[symbol] = quote
                    self._last_fetch[symbol] = now
                return quote
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
        
        return self._cache.get(symbol)

# Global Instance
free_data = FreeDataFetcher()
