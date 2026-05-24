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
import socket
import string
import time
from datetime import datetime, date
from typing import Dict, List, Optional
from src.broker.base import Broker, BrokerError

from src.utils.paths import ensure_paths
DATA_DIR = ensure_paths()
CACHE_FILE = os.path.join(DATA_DIR, "angel_instruments.json")

logger = logging.getLogger("AngelBroker")
INSTRUMENT_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"


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
        # Validate required credentials
        if not api_key or not api_key.strip():
            raise ValueError("ANGEL_API_KEY is required and cannot be empty")
        if not client_id or not client_id.strip():
            raise ValueError("ANGEL_CLIENT_ID is required and cannot be empty")
        if not password or not password.strip():
            raise ValueError("ANGEL_PASSWORD is required and cannot be empty")
        
        self.api_key          = self._clean_credential(api_key)
        self.client_id        = self._clean_credential(client_id).upper() # Client ID must be Uppercase
        self.password         = self._clean_credential(password)
        self.totp_secret      = self._clean_credential(totp_secret)
        self.is_paper_trading = is_paper_trading
        
        if self.api_key:
            logger.info(f"[ANGEL] Credentials validated. Client: {self.client_id}")
        self._obj             = None   # SmartConnect session object
        self._auth_token      = None
        self._refresh_token   = None
        self._instruments     = {}     # symbol -> {token, lotsize, etc}
        self.is_connected     = False   # Flag for live data capability
    
    @property
    def name(self) -> str:
        return "Angel One"

    def _clean_credential(self, val: str) -> str:
        """Removes non-printable and non-ASCII characters that cause login failures."""
        if not val: return ""
        # Keep only printable ASCII characters, remove all whitespace/newlines
        printable = set(string.printable) - set(string.whitespace)
        cleaned = ''.join(filter(lambda x: x in printable, val))
        return cleaned.strip()

    def _get_local_ip(self) -> str:
        """Finds the local IP address safely to satisfy Angel One SDK headers."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)) # Connect to a public DNS to find local route
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "192.168.1.1" # Dummy fallback

    def _load_instruments(self):
        """Downloads and maps Angel One instrument tokens."""
        if self._instruments:
            return
        
        # Try local cache first
        if os.path.exists(CACHE_FILE):
             try:
                 # Check if cache is fresh (less than 24 hours old)
                 file_time = os.path.getmtime(CACHE_FILE)
                 if (time.time() - file_time) < 86400: # 24 hours
                     with open(CACHE_FILE, "r") as f:
                         self._instruments = json.load(f)
                     logger.info(f"[ANGEL] Loaded {len(self._instruments)} instruments from cache (Age: {int((time.time()-file_time)/3600)}h).")
                     return
                 else:
                     logger.info("[ANGEL] Cache is older than 24 hours. Refreshing...")
             except (IOError, OSError, json.JSONDecodeError) as e:
                 logger.warning(f"[ANGEL] Cache load failed: {e}. Re-downloading...")

        logger.info(f"[ANGEL] Downloading instrument list from {INSTRUMENT_URL}...")
        try:
            import certifi
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(
                INSTRUMENT_URL, 
                headers=headers, 
                timeout=15, 
                verify=certifi.where()
            )
            logger.info(f"[ANGEL] Download Status: {resp.status_code}, Length: {len(resp.text)}")
            
            if resp.status_code != 200:
                logger.error(f"[ANGEL] Download failed with status {resp.status_code}")
            else:
                try:
                    data = resp.json()
                except Exception as json_err:
                    # If it's not JSON, let's see what it is
                    content_preview = resp.text[:500]
                    logger.error(f"[ANGEL] JSON Parse failed: {json_err}")
                    logger.error(f"[ANGEL] Content Preview: {content_preview}")
                    data = []

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
            except (IOError, OSError) as e:
                logger.warning(f"[ANGEL] Could not save cache: {e}")
        except (requests.RequestException, TimeoutError, ConnectionError) as e:
            logger.error(f"[ANGEL] Instrument download failed: {e}")
        
        # Final check: ensure we have instruments loaded
        if not self._instruments:
            raise BrokerError("Failed to load instrument data from both cache and API. Trading cannot proceed.")

    def refresh_instruments(self):
        """Forces a re-download of the instrument list by clearing cache and memory."""
        self._instruments = {}
        if os.path.exists(CACHE_FILE):
            try:
                os.remove(CACHE_FILE)
                logger.info("[ANGEL] Instrument cache file deleted for fresh download.")
            except Exception as e:
                logger.error(f"[ANGEL] Failed to delete cache file: {e}")
        self._load_instruments()

    def _validate_totp_secret(self, secret: str) -> str:
        """Validate and clean TOTP secret for base32 format.
        
        Base32 valid characters: A-Z, 2-7
        Removes spaces, invalid chars, converts to uppercase.
        Returns cleaned secret or empty string if invalid.
        """
        if not secret:
            return ""
        
        # Remove spaces and convert to uppercase
        cleaned = secret.replace(" ", "").replace("-", "").upper()
        
        # Keep only valid base32 characters (A-Z, 2-7)
        valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')
        cleaned = ''.join(c for c in cleaned if c in valid_chars)
        
        # PyOTP handles padding automatically, we just need to avoid trimming the user's key
        if not cleaned:
            logger.error("[ANGEL] TOTP secret is empty after cleaning - check your Config")
        elif len(cleaned) < 16:
            logger.warning(f"[ANGEL] TOTP secret may be too short ({len(cleaned)} chars)")
        
        # Ensure it's valid base32 by checking if pyotp can use it
        try:
            import pyotp
            pyotp.TOTP(cleaned).now()
        except Exception:
            logger.error("[ANGEL] TOTP secret is NOT a valid base32 string. Please check it.")
            return ""
        
        # Ensure it's valid base32 by checking if pyotp can use it
        try:
            import pyotp
            pyotp.TOTP(cleaned).now()
        except Exception:
            logger.error("[ANGEL] TOTP secret is NOT a valid base32 string. Please check it.")
            return ""
        
        return cleaned

    def login(self) -> bool:
        try:
            import pyotp
            from SmartApi import SmartConnect
            # Initialize with cleaned credentials and explicit local IP
            local_ip = self._get_local_ip()
            
            # Fix for SSL certificate path error in SmartApi (PostgreSQL path error)
            import certifi
            os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
            os.environ["SSL_CERT_FILE"] = certifi.where()
            
            # SmartConnect in recent versions accepts local/public IP in constructor
            self._obj = SmartConnect(
                api_key=self.api_key,
                clientLocalIP=local_ip,
                clientPublicIP="1.1.1.1", # Placeholder
                disable_ssl=False
            )
            self._obj.local_ip = local_ip
            
            # Validate and clean TOTP secret
            totp_secret_clean = self._validate_totp_secret(self.totp_secret)
            
            # Generate TOTP only if valid secret exists
            if totp_secret_clean:
                try:
                    totp_generator = pyotp.TOTP(totp_secret_clean)
                    totp = totp_generator.now()
                    logger.debug(f"[ANGEL] Generated TOTP Code: {totp}")
                    logger.debug("👉 Compare this 6-digit code with your mobile app.")
                    logger.debug("👉 If it DOES NOT match, please Sync your Windows Clock (Settings -> Time -> Sync Now).")
                except Exception as e:
                    logger.error(f"[ANGEL] TOTP generation failed: {e}")
                    logger.error(f"[ANGEL] Invalid TOTP secret format. Expected: 16-32 base32 characters (A-Z, 2-7)")
                    logger.error(f"[ANGEL] Current secret length after cleaning: {len(totp_secret_clean)}")
                    totp = ""
            else:
                logger.warning("[ANGEL] No valid TOTP secret - login may fail")
                totp = ""
            
            # Use state if provided, default to ""
            state = os.getenv("ANGEL_STATE", "TRANSPORT")
            # generateSession is sometimes picky about parameter names (clientCode vs client_code)
            # Recent SmartApi SDK versions use 'clientCode'
            # Try different keyword name variants found in different SmartApi versions
            try:
                # Log attempt
                auth_mode = "PIN" if len(self.password) == 4 and self.password.isdigit() else "Password"
                logger.info(f"[ANGEL] Attempting login for {self.client_id} using {auth_mode}...")
                
                data = self._obj.generateSession(self.client_id, self.password, totp)
            except (TypeError, ValueError) as e:
                # If JSON parsing failed inside the library (empty response b''), it raises ValueError
                if "parse" in str(e).lower() or "json" in str(e).lower():
                    logger.error(f"[ANGEL] Login failed: Server returned an empty response. Verify your API Key and Client ID.")
                    return False
                
                # Try fallback keyword variant
                try:
                    data = self._obj.generateSession(clientcode=self.client_id, password=self.password, totp=totp)
                except Exception:
                    # Final fallback to positional
                    logger.warning("[ANGEL] Keyword login failed, trying positional...")
                    data = self._obj.generateSession(self.client_id, self.password, totp)
            except Exception as e:
                err_msg = str(e)
                logger.error(f"[ANGEL] Session generation error: {err_msg}")
                
                # Check for the specific "b''" error which means Angel gateway rejection
                if "Couldn't parse" in err_msg or "b''" in err_msg:
                    logger.error("="*60)
                    logger.error("🚨 ANGEL LOGIN FIX-IT GUIDE 🚨")
                    logger.error("The Angel One server rejected your request with an empty response.")
                    logger.error("Please perform this 3-step check in the Config tab:")
                    logger.error("1. KEY CHECK: Is your API Key correct? (Check for 'rVkM...' format)")
                    logger.error("2. STATUS: Is your API Key active in the SmartAPI Dashboard?")
                    logger.error("3. NO SPACES: Did you delete and re-paste your Client ID in UPPERCASE?")
                    logger.error("="*60)
                return False
            
            if not data:
                logger.error("[ANGEL] Login Failed: No response received from server. Check internet or API credentials.")
                return False

            if data.get("status"):
                try:
                    self._auth_token    = data["data"]["jwtToken"]
                    self._refresh_token = data["data"]["refreshToken"]
                    self.is_connected   = True
                    # Increase timeout to handle slow API responses for data fetching
                    if hasattr(self._obj, 'timeout'):
                        self._obj.timeout = 25
                    logger.info(f"[ANGEL] Logged in as {self.client_id}")
                    return True
                except (KeyError, TypeError) as e:
                    logger.error(f"[ANGEL] Malformed session data: {e}")
                    return False
            else:
                msg = data.get('message', 'Unknown Error')
                logger.error(f"[ANGEL] Session generation failed: {msg}")
                # Provide user-friendly hints
                if "Invalid" in msg or "400" in str(msg):
                    logger.error("[ANGEL] Tip: Please check your Client ID, Password, and TOTP Secret in Config.")
                return False
        except ImportError:
            logger.error("smartapi-python not installed. Run: pip install smartapi-python pyotp logzero")
            return False
        except (requests.RequestException, TimeoutError, ConnectionError, ValueError) as e:
            logger.error(f"[ANGEL] Login failed: {e}")
            return False

    def get_quote(self, symbol: str) -> Optional[Dict]:
        if not self._obj:
            logger.warning("[ANGEL] Not logged in: no live quote.")
            return None
        
        self._load_instruments()
        # Case-insensitive lookup for convenience
        inst = self._instruments.get(symbol)
        if not inst:
            # Try searching by uppercase name match
            for s, details in self._instruments.items():
                if s.upper() == symbol.upper():
                    inst = details
                    break
        
        if not inst:
            logger.error(f"[ANGEL] Symbol {symbol} not found in instrument list.")
            return None

        max_retries = 5
        for attempt in range(max_retries):
            try:
                exch = inst["exch"]
                token = inst["token"]
                data = self._obj.ltpData(exch, symbol, token)
                
                if data.get("status") and data.get("data"):
                    ltp = float(data["data"]["ltp"])
                    return {"symbol": symbol, "last_price": ltp, "price": ltp}
                
                msg = data.get('message', 'No message')
                err_code = data.get('errorcode', '')
                logger.error(f"[ANGEL] LTP Fetch failed for {symbol} (Attempt {attempt+1}/{max_retries}): {msg} ({err_code})")
                
                if (err_code == "AB4006" or err_code == "AB4046") and attempt == 0:
                    logger.warning(f"⚠️ [ANGEL] {msg} ({err_code}) for {symbol}. Forcing refresh...")
                    self.refresh_instruments()
                    # Re-fetch instrument details from the refreshed list
                    inst = self._instruments.get(symbol)
                    if not inst:
                        logger.error(f"[ANGEL] {symbol} not found even after refresh. Aborting retries.")
                        break
                    continue
                
            except (requests.RequestException, TimeoutError, ConnectionError, ValueError) as e:
                logger.error(f"[ANGEL] get_quote error (Attempt {attempt+1}/{max_retries}): {e}")
                # Check for various timeout signatures
                err_str = str(e).lower()
                wait_time = (2 ** attempt) * 2
                logger.info(f"[ANGEL] Connectivity issue ({e}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            # If we didn't continue, it's either success or a non-retryable error
            break
            
        return None

    def get_symbol(self, underlying: str, expiry, strike: int, option_type: str) -> str:
        """
        Build Angel One symbol format: NIFTY17MAR2623450PE
        """
        if isinstance(expiry, str):
             # If it's something like '2026-03-17', we might still need to parse it
             if "-" in expiry:
                 from datetime import datetime
                 expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
             else:
                 return f"{underlying.upper()}{expiry.upper()}{strike}{option_type.upper()}"
        
        # Format: DDMMMYY
        day = expiry.strftime("%d")
        month = expiry.strftime("%b").upper()
        year = str(expiry.year)[2:]
        return f"{underlying.upper()}{day}{month}{year}{strike}{option_type.upper()}"

    def get_feed_token(self) -> Optional[str]:
        """Get the feed token required for WebSocket authentication."""
        if not self._obj:
            return None
        try:
            # SmartConnect getfeedToken() returns the feed token string
            token = self._obj.getfeedToken()
            return token
        except Exception as e:
            logger.error(f"[ANGEL] Failed to get feed token: {e}")
            return None

    def get_index_token(self, underlying: str) -> Optional[str]:
        """Get the exchange token for an index (for WebSocket subscription)."""
        # Angel One index tokens (NSE exchange type 1)
        INDEX_TOKENS = {
            "NIFTY":     "26000",
            "BANKNIFTY": "26009",
            "FINNIFTY":  "26037",
            "CRUDEOIL":  "210001", # CRUDEOIL INDEX
            "GOLD":      "210002"
        }
        return INDEX_TOKENS.get(underlying.upper())

    def get_index_quote_symbol(self, underlying: str) -> str:
        """Get the human-readable symbol name used in get_quote for an index."""
        # This must match what is used in the rest of the app (e.g. Nifty 50)
        NAMES = {
            "NIFTY":     "Nifty 50",
            "BANKNIFTY": "Nifty Bank",
            "FINNIFTY":  "Nifty Fin Service",
            "CRUDEOIL":  "Crude Oil",
            "GOLD":      "Gold",
            "RELIANCE":  "RELIANCE-EQ"
        }
        return NAMES.get(underlying.upper(), underlying.upper())

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
        trigger_price: Optional[float] = None,
        tag:        Optional[str] = None,
    ) -> str:
        self._load_instruments()
        inst = self._instruments.get(symbol)
        if not inst and not self.is_paper_trading:
            logger.error(f"[ANGEL] place_order: Symbol {symbol} not found.")
            return ""

        if self.is_paper_trading or not self._obj:
            import random
            mock_id = f"ANGEL_PAPER_{random.randint(10000, 99999)}"
            logger.info(f"[ANGEL PAPER] Order: {side} {quantity} {symbol} -> {mock_id}")
            return mock_id
        
        try:
            token = inst["token"]
            exch  = inst["exch"]
            
            # Map simplified order types to Angel-specific constants
            # Angel supports: MARKET, LIMIT, STOPLOSS_LIMIT, STOPLOSS_MARKET
            angel_type = "MARKET"
            if order_type == "LIMIT":
                angel_type = "LIMIT"
            elif order_type == "STOPLOSS_MARKET":
                angel_type = "STOPLOSS_MARKET"
            elif order_type == "STOPLOSS_LIMIT":
                angel_type = "STOPLOSS_LIMIT"

            order_params = {
                "variety":         "STOPLOSS" if "STOPLOSS" in angel_type else ("AMO" if inst.get("exch") == "MCX" else "NORMAL"),
                "tradingsymbol":   symbol,
                "symboltoken":     token,
                "transactiontype": side.upper(),
                "exchange":        exch,
                "ordertype":       angel_type,
                "producttype":     "CARRYOVER" if inst.get("exch") == "MCX" else "INTRADAY",
                "duration":        "DAY",
                "price":           str(price or 0) if "MARKET" not in angel_type else "0",
                "quantity":        str(quantity),
            }
            if "STOPLOSS" in angel_type:
                order_params["triggerprice"] = str(trigger_price or price)
            
            # Add custom tag for deduplication if provided
            if tag:
                order_params["tag"] = tag

            resp = self._obj.placeOrder(order_params)
            if resp.get("status"):
                order_id = resp.get("data", {}).get("orderid", "UNKNOWN")
                logger.info(f"[ANGEL] Order placed: {symbol} ID: {order_id}")
                return order_id
            logger.error(f"[ANGEL] Order failed: {resp.get('message')}")
            return ""
        except (requests.RequestException, TimeoutError, ConnectionError, KeyError, ValueError) as e:
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
        except (requests.RequestException, TimeoutError, ConnectionError, KeyError, ValueError) as e:
            logger.error(f"[ANGEL] get_order_status error: {e}")
            return "UNKNOWN"

    def get_positions(self) -> List[Dict]:
        if self.is_paper_trading or not self._obj:
            return []
        try:
            data = self._obj.position()
            return data.get("data", []) or []
        except (requests.RequestException, TimeoutError, ConnectionError, KeyError, ValueError) as e:
            logger.error(f"[ANGEL] get_positions error: {e}")
            return []

    def get_historical_data(self, symbol: str, interval: str = "FIVE_MINUTE", days: int = 2):
        """Fetch historical candles from Angel One."""
        self._load_instruments()
        inst = self._instruments.get(symbol)
        if not inst or not self._obj:
            return []
        
        try:
            from datetime import datetime, timedelta
            to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
            
            params = {
                "exchange": inst["exch"],
                "symboltoken": inst["token"],
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            }
            res = self._obj.getCandleData(params)
            if res.get("status"):
                return res.get("data", [])
            return []
        except Exception as e:
            logger.error(f"[ANGEL] get_historical_data error: {e}")
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

    def get_live_expiry(self, underlying: str, frequency: str = "WEEKLY") -> Optional[str]:
        """
        Dynamically finds the nearest expiry date for NIFTY/BANKNIFTY from the live instrument list.
        Args:
            underlying: "NIFTY" or "BANKNIFTY"
            frequency: "WEEKLY" or "MONTHLY"
        Returns:
            Expiry string in "DDMMMYYYY" or "YYYY-MM-DD" format.
        """
        self._load_instruments()
        expiries = []
        target_name = underlying.upper()
        if target_name == "NIFTY": target_name = "NIFTY"
        if target_name == "BANKNIFTY": target_name = "BANKNIFTY"

        for symbol, inst in self._instruments.items():
            if inst.get("name") == target_name and inst.get("exch") == "NFO":
                exp = inst.get("expiry")
                if exp:
                    expiries.append(exp)
        
        if not expiries:
            return None
            
        # Unique and sort expiries. Angel expiry format: 27MAR2025
        from datetime import datetime
        try:
            date_objs = []
            for e in set(expiries):
                try:
                    parsed_date = datetime.strptime(e, "%d%b%Y")
                    date_objs.append(parsed_date)
                except ValueError as ex:
                    logger.debug(f"Unparseable date format '{e}': expected '%d%b%Y' - {ex}")
                    continue  # Skip invalid date
            
            if not date_objs:
                return None
            
            # Filter out past expiries
            today = date.today()
            date_objs = [d for d in date_objs if d.date() >= today]
            
            if not date_objs:
                logger.warning(f"[ANGEL] No upcoming expiries found for {underlying} (all in past?)")
                return None
                
            date_objs.sort()
            
            if frequency == "WEEKLY":
                # Nearest available expiry
                return date_objs[0].strftime("%d%b%Y").upper()
            else:
                # Monthly: Last expiry of the current month (or first available month with expiries)
                now = datetime.now()
                # Filter for dates in the same month/year as the first available expiry
                first_expiry = date_objs[0]
                month_expiries = [d for d in date_objs if d.month == first_expiry.month and d.year == first_expiry.year]
                # The latest date in that month is the "Monthly" expiry
                return month_expiries[-1].strftime("%d%b%Y").upper()
        except Exception as e:
            logger.error(f"Error parsing expiries: {e}")
            return sorted(list(set(expiries)))[0]

    def get_instrument_details(self, symbol: str) -> Dict:
        """Fetch details (lot size, token, etc.) for a specific symbol from cache."""
        self._load_instruments()
        inst = self._instruments.get(symbol)
        if not inst:
            logger.warning(f"[ANGEL] Instrument details not found for {symbol}")
            return {}
        
        return {
            "token": inst.get("token"),
            "lotsize": int(inst.get("lotsize", 1)),
            "expiry": inst.get("expiry"),
            "strike": inst.get("strike"),
            "exch": inst.get("exch")
        }


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
