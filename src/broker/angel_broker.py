"""
Angel One Smart API Broker
Implements the Broker interface for Angel One's Smart API.
Install: pip install smart-api-python
"""

import logging
import requests
import json
import logging
import os
import sys
from datetime import datetime
from src.broker.base import Broker

# ── Distribution Path Handling ──────────────────────────────────
if getattr(sys, 'frozen', False):
    PROJECT_DIR = os.path.dirname(sys.executable)
else:
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
    # Adjust for src/broker/ position
    PROJECT_DIR = os.path.dirname(os.path.dirname(PROJECT_DIR))

logger = logging.getLogger("AngelBroker")
INSTRUMENT_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
CACHE_FILE = os.path.join(PROJECT_DIR, "data", "angel_instruments.json")


class AngelBroker(Broker):
    """
    Angel One Smart API integration.
    Requires: ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET in .env
    """

    def __init__(
        self,
        api_key:     str,
        client_id:   str,
        password:    str,
        totp_secret: str = "",
        is_paper_trading: bool = True,
    ):
        self.api_key          = api_key
        self.client_id        = client_id
        self.password         = password
        self.totp_secret      = totp_secret
        self.is_paper_trading = is_paper_trading
        self._obj             = None   # SmartConnect session object
        self._auth_token      = None
        self._refresh_token   = None
        self._instruments     = {}     # symbol -> {token, lotsize, etc}
        self.is_connected     = False   # Flag for live data capability

    def _load_instruments(self):
        """Downloads and maps Angel One instrument tokens."""
        if self._instruments:
            return
        
        # Try local cache first
        if os.path.exists(CACHE_FILE):
             try:
                 with open(CACHE_FILE, "r") as f:
                     self._instruments = json.load(f)
                 logger.info(f"[ANGEL] Loaded {len(self._instruments)} instruments from cache.")
                 return
             except Exception as e:
                 logger.warning(f"[ANGEL] Cache load failed: {e}. Re-downloading...")

        logger.info(f"[ANGEL] Downloading instrument list from {INSTRUMENT_URL}...")
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(INSTRUMENT_URL, headers=headers, timeout=60)
            logger.info(f"[ANGEL] Download Status: {resp.status_code}, Length: {len(resp.text)}")
            
            if resp.status_code != 200:
                logger.error(f"[ANGEL] Download failed with status {resp.status_code}")
                return
            
            try:
                data = resp.json()
            except Exception as json_err:
                # If it's not JSON, let's see what it is
                content_preview = resp.text[:500]
                logger.error(f"[ANGEL] JSON Parse failed: {json_err}")
                logger.error(f"[ANGEL] Content Preview: {content_preview}")
                return

            logger.info(f"[ANGEL] Received {len(data)} items from Angel One API.")
            
            # Map by 'symbol' for fast lookup (this is Angel's tradingsymbol)
            for item in data:
                symbol = item.get("symbol")
                if symbol:
                    self._instruments[symbol] = {
                        "token":     item.get("token"),
                        "symbol":    symbol,
                        "exch":      item.get("exch_seg"),
                        "expiry":    item.get("expiry"),
                        "lotsize":   item.get("lotsize"),
                        "tick_size": item.get("tick_size"),
                        "name":      item.get("name"),
                        "strike":    item.get("strike"),
                        "type":      item.get("instrumenttype")
                    }
            
            # Save to cache
            try:
                os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
                with open(CACHE_FILE, "w") as f:
                    json.dump(self._instruments, f)
                logger.info(f"[ANGEL] Downloaded and cached {len(self._instruments)} instruments.")
            except Exception as e:
                logger.warning(f"[ANGEL] Could not save cache: {e}")
        except Exception as e:
            logger.error(f"[ANGEL] Instrument download failed: {e}")

    def login(self) -> bool:
        try:
            import pyotp
            from SmartApi import SmartConnect
            # Initialize with user-provided URL if needed
            self._obj = SmartConnect(api_key=self.api_key)
            totp = pyotp.TOTP(self.totp_secret).now() if self.totp_secret else ""
            
            # Use state if provided, default to ""
            state = os.getenv("ANGEL_STATE", "TRANSPORT")
            data = self._obj.generateSession(self.client_id, self.password, totp)
            
            if data and data.get("status"):
                self._auth_token    = data["data"]["jwtToken"]
                self._refresh_token = data["data"]["refreshToken"]
                self.is_connected   = True
                # Increase timeout to handle slow API responses
                if hasattr(self._obj, 'timeout'):
                    self._obj.timeout = 15
                logger.info(f"[ANGEL] Logged in as {self.client_id} (Timeout: {getattr(self._obj, 'timeout', 'Default')}s)")
                return True
            else:
                logger.error(f"[ANGEL] Session generation failed: {data.get('message')}")
                return False
        except ImportError:
            logger.error("smartapi-python not installed. Run: pip install smartapi-python pyotp logzero")
            return False
        except Exception as e:
            logger.error(f"[ANGEL] Login failed: {e}")
            return False

    def get_quote(self, symbol: str) -> Optional[Dict]:
        if not self._obj:
            logger.warning("[ANGEL] Not logged in: no live quote.")
            return None
        
        self._load_instruments()
        inst = self._instruments.get(symbol)
        if not inst:
            logger.error(f"[ANGEL] Symbol {symbol} not found in instrument list.")
            return None

        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                exch = inst["exch"]
                token = inst["token"]
                data = self._obj.ltpData(exch, symbol, token)
                
                if data.get("status") and data.get("data"):
                    ltp = float(data["data"]["ltp"])
                    return {"symbol": symbol, "last_price": ltp, "price": ltp}
                
                msg = data.get('message', 'No message')
                logger.error(f"[ANGEL] LTP Fetch failed for {symbol} (Attempt {attempt+1}/{max_retries}): {msg}")
                
            except Exception as e:
                logger.error(f"[ANGEL] get_quote error (Attempt {attempt+1}/{max_retries}): {e}")
                if "Read timed out" in str(e) or "timeout" in str(e).lower():
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        logger.info(f"[ANGEL] Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
            
            # If we didn't continue, it's either success or a non-retryable error
            break
            
        return None

    def get_symbol(self, underlying: str, expiry, strike: int, option_type: str) -> str:
        """
        Build Angel One symbol format: NIFTY17MAR2623450PE
        """
        if isinstance(expiry, str) and len(expiry) > 7: # Already a formatted string?
             # If it's something like '2026-03-17', we might still need to parse it
             if "-" in expiry:
                 from datetime import datetime
                 expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
             else:
                 return expiry
        
        # Format: DDMMMYY
        day = expiry.strftime("%d")
        month = expiry.strftime("%b").upper()
        year = str(expiry.year)[2:]
        return f"{underlying.upper()}{day}{month}{year}{strike}{option_type.upper()}"

    def get_option_chain(self, symbol, expiry):
        """
        Filter instrument list for options matching the given index/symbol and expiry.
        """
        self._load_instruments()
        chain = []
        for s, inst in self._instruments.items():
            # Check if name matches (e.g. NIFTY) and it's an option in NFO
            if inst.get("name") == symbol and inst.get("exch") == "NFO":
                # Instrument types: OPTIDX, OPTSTK
                if "OPT" in str(inst.get("type")):
                    # Check expiry (Angel format: 27MAR2025)
                    inst_expiry = inst.get("expiry", "")
                    if not expiry or expiry.upper() in inst_expiry.upper():
                        chain.append({
                            "symbol": s,
                            "strike": float(inst.get("strike", 0)),
                            "type":   "CE" if s.endswith("CE") else "PE",
                            "expiry": inst_expiry,
                            "token":  inst["token"],
                            "lotsize": int(inst.get("lotsize", 1))
                        })
        return chain

    def place_order(
        self,
        symbol:     str,
        quantity:   int,
        order_type: str,
        side:       str,
        price:      Optional[float] = None,
    ) -> str:
        self._load_instruments()
        inst = self._instruments.get(symbol)
        if not inst and not self.is_paper_trading:
            logger.error(f"[ANGEL] place_order: Symbol {symbol} not found.")
            return ""

        if self.is_paper_trading or not self._obj:
            import random
            mock_id = f"ANGEL_PAPER_{random.randint(10000, 99999)}"
            logger.info(f"[ANGEL PAPER] Order: {side} {quantity} {symbol} → {mock_id}")
            return mock_id
        
        try:
            token = inst["token"]
            exch  = inst["exch"]
            order_params = {
                "variety":         "NORMAL",
                "tradingsymbol":   symbol,
                "symboltoken":     token,
                "transactiontype": side.upper(),
                "exchange":        exch,
                "ordertype":       "MARKET" if order_type == "MARKET" else "LIMIT",
                "producttype":     "INTRADAY",
                "duration":        "DAY",
                "price":           str(price or 0) if order_type != "MARKET" else "0",
                "quantity":        str(quantity),
            }
            resp = self._obj.placeOrder(order_params)
            if resp.get("status"):
                order_id = resp.get("data", {}).get("orderid", "UNKNOWN")
                logger.info(f"[ANGEL] Order placed: {symbol} ID: {order_id}")
                return order_id
            logger.error(f"[ANGEL] Order failed: {resp.get('message')}")
            return ""
        except Exception as e:
            logger.error(f"[ANGEL] place_order error: {e}")
            return ""

    def get_order_status(self, order_id: str) -> str:
        if self.is_paper_trading or not self._obj:
            return "COMPLETE"
        try:
            # Angel One does not have a direct single-order status call;
            # iterate order book to find matching ID.
            orders = self._obj.orderBook().get("data", []) or []
            for o in orders:
                if o.get("orderid") == order_id:
                    return o.get("status", "UNKNOWN").upper()
            return "UNKNOWN"
        except Exception as e:
            logger.error(f"[ANGEL] get_order_status error: {e}")
            return "UNKNOWN"

    def get_positions(self) -> List[Dict]:
        if self.is_paper_trading or not self._obj:
            return []
        try:
            data = self._obj.position()
            return data.get("data", []) or []
        except Exception as e:
            logger.error(f"[ANGEL] get_positions error: {e}")
            return []

    def get_balance(self) -> float:
        """Fetch available margin from Angel One."""
        if self.is_paper_trading or not self._obj:
            return 10000.0  # Default mock balance
        try:
            resp = self._obj.rmsLimit()
            if resp.get("status"):
                # Total available cash is usually in 'availablecash' or 'net'
                data = resp.get("data", {})
                return float(data.get("availablecash", 0))
            return 0.0
        except Exception as e:
            logger.error(f"[ANGEL] get_balance error: {e}")
            return 0.0

    def cancel_order(self, order_id: str) -> bool:
        if self.is_paper_trading or not self._obj:
            logger.info(f"[ANGEL PAPER] Cancel order {order_id}")
            return True
        try:
            self._obj.cancelOrder(order_id, variety="NORMAL")
            return True
        except Exception as e:
            logger.error(f"[ANGEL] cancel_order error: {e}")
            return False


if __name__ == "__main__":
    # Quick self-test
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    logging.basicConfig(level=logging.INFO)
    
    broker = AngelBroker(
        api_key=os.getenv("ANGEL_API_KEY"),
        client_id=os.getenv("ANGEL_CLIENT_ID"),
        password=os.getenv("ANGEL_PASSWORD"),
        totp_secret=os.getenv("ANGEL_TOTP_SECRET"),
        is_paper_trading=True
    )
    
    if broker.login():
        print("Login Success")
        quote = broker.get_quote("SBIN-EQ")
        print(f"Quote: {quote}")
        chain = broker.get_option_chain("NIFTY", "17MAR2026")
        print(f"Option Chain items: {len(chain)}")
        if chain:
            print(f"First item: {chain[0]}")
