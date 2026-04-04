import requests
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("NSEFetcher")

class NSEFetcher:
    """
    Handles fetching data from NSE API.
    Maintains a session with proper headers to bypass basic rate-limiting/blocking.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        self.session.headers.update(self.headers)
        self._cookies_initialized = False
        
    def _ensure_cookies(self):
        """Hit the main page once to get valid session cookies"""
        if self._cookies_initialized:
            return True
            
        try:
            logger.debug("Initializing NSE session cookies...")
            self.session.get('https://www.nseindia.com', timeout=10)
            time.sleep(1) # Wait a bit before making actual API calls
            self._cookies_initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize NSE cookies: {e}")
            return False

    def fetch_option_chain(self, symbol: str) -> Optional[Dict]:
        """
        Fetch the full option chain and spot price for a given symbol (e.g., NIFTY, BANKNIFTY).
        """
        if not self._ensure_cookies():
            return None
            
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        headers = {
            'referer': f'https://www.nseindia.com/get-quotes/derivatives?symbol={symbol}'
        }
        
        try:
            response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'records' in data:
                    return data['records']
                else:
                    logger.warning(f"Unexpected JSON structure from NSE for {symbol}")
                    return None
            elif response.status_code == 401 and not self._cookies_initialized:
                 # Cookies might be expired, reset and try again
                 logger.info("Session expired, re-initializing cookies...")
                 self._cookies_initialized = False
                 self._ensure_cookies()
                 response = self.session.get(url, headers=headers, timeout=10)
                 if response.status_code == 200:
                     return response.json().get('records')
                 else:
                     logger.error(f"Failed to fetch {symbol} option chain after retry. Status: {response.status_code}")
                     return None
            else:
                logger.error(f"Failed to fetch {symbol} option chain. Status: {response.status_code}")
                # Reset cookies for next time if we get blocked
                if response.status_code in [403, 401]:
                    self._cookies_initialized = False
                return None
        except Exception as e:
            logger.error(f"Error fetching option chain for {symbol}: {e}")
            return None

    def get_spot_price(self, symbol: str) -> Optional[float]:
        """Convenience method to just get the spot price."""
        data = self.fetch_option_chain(symbol)
        if data and 'underlyingValue' in data:
            return float(data['underlyingValue'])
        return None
