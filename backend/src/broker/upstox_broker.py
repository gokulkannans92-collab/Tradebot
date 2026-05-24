"""
Upstox API Broker
Implements the Broker interface for Upstox v2 API.
Install: pip install upstox-python-sdk
"""

import logging
from typing import Dict, List, Optional
from src.broker.base import Broker

logger = logging.getLogger("UpstoxBroker")


class UpstoxBroker(Broker):
    """
    Upstox v2 API integration.
    Requires: UPSTOX_API_KEY, UPSTOX_API_SECRET, UPSTOX_REDIRECT_URI, UPSTOX_ACCESS_TOKEN in .env
    """
    
    @property
    def name(self) -> str:
        return "Upstox"

    def __init__(
        self,
        api_key:      str,
        api_secret:   str,
        access_token: str,
        is_paper_trading: bool = True,
    ):
        # Validate required credentials
        if not api_key or not api_key.strip():
            raise ValueError("UPSTOX_API_KEY is required and cannot be empty")
        if not api_secret or not api_secret.strip():
            raise ValueError("UPSTOX_API_SECRET is required and cannot be empty")
        if not access_token or not access_token.strip():
            raise ValueError("UPSTOX_ACCESS_TOKEN is required and cannot be empty")
        
        self.api_key          = api_key
        self.api_secret       = api_secret
        self.access_token     = access_token
        self.is_paper_trading = is_paper_trading
        self._config          = None   # upstox_client.Configuration
        self.is_connected     = False

    def _get_config(self):
        """Build Upstox SDK config (lazy init)."""
        if self._config:
            return self._config
        try:
            import upstox_client
            config = upstox_client.Configuration()
            config.access_token = self.access_token
            self._config = config
            return config
        except ImportError:
            logger.error("upstox-python-sdk not installed. Run: pip install upstox-python-sdk")
            return None

    def login(self) -> bool:
        if self.is_paper_trading:
            logger.info("[UPSTOX] Paper trading mode - login bypassed.")
            return True
        if not self.access_token:
            logger.error("[UPSTOX] No access token provided.")
            return False
        cfg = self._get_config()
        if cfg:
            self.is_connected = True
            logger.info("[UPSTOX] Config initialised with access token.")
            return True
        return False

    def get_quote(self, symbol: str) -> Optional[Dict]:
        if not self._get_config():
            return None
            
        upstox_symbol = symbol
        if symbol == "NIFTY":
            upstox_symbol = "NSE_INDEX|Nifty 50"
        elif symbol == "BANKNIFTY":
            upstox_symbol = "NSE_INDEX|Nifty Bank"
            
        try:
            import upstox_client
            api = upstox_client.MarketQuoteApi(upstox_client.ApiClient(self._config))
            resp = api.get_full_market_quote(upstox_symbol, "2.0")
            data = resp.data or {}
            ltp = float(list(data.values())[0].last_price) if data else 0.0
            return {"symbol": symbol, "last_price": ltp, "price": ltp}
        except Exception as e:
            logger.error(f"[UPSTOX] get_quote error: {e}")
            return None

    def get_symbol(self, underlying: str, expiry, strike: int, option_type: str) -> str:
        from src.utils.options_utils import build_option_symbol
        return build_option_symbol(underlying, expiry, strike, option_type)

    def get_option_chain(self, symbol: str, expiry: str) -> List[Dict]:
        """
        Fetch option chain for a symbol and expiry.
        Note: Upstox v2 requires instrument keys. For now, we simulate 
        by returning ATM/OTM strikes based on spot price.
        """
        logger.info(f"[UPSTOX] Fetching option chain for {symbol} - {expiry}")
        from src.utils.options_utils import select_atm_strike, build_option_symbol, estimate_option_premium
        from datetime import datetime
        
        quote = self.get_quote(symbol)
        spot = quote.get("last_price", 0) if quote else 0
        if spot == 0: return []
        
        atm = select_atm_strike(spot)
        try:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        except:
            from src.utils.options_utils import get_upcoming_expiry
            expiry_date = get_upcoming_expiry()
            
        chain = []
        # Generate 5 strikes above and below ATM
        for i in range(-5, 6):
            strike = atm + (i * 50)
            for opt_type in ["CE", "PE"]:
                opt_symbol = build_option_symbol(symbol, expiry_date, strike, opt_type)
                premium = estimate_option_premium(spot, strike, opt_type)
                chain.append({
                    "tradingsymbol": opt_symbol,
                    "strike": strike,
                    "option_type": opt_type,
                    "last_price": premium,
                    "expiry": str(expiry_date)
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
        if self.is_paper_trading or not self._get_config():
            import random
            mock_id = f"UPSTOX_PAPER_{random.randint(10000, 99999)}"
            logger.info(f"[UPSTOX PAPER] Order: {side} {quantity} {symbol} -> {mock_id}")
            return mock_id
        try:
            import upstox_client
            api   = upstox_client.OrderApi(upstox_client.ApiClient(self._config))
            body  = upstox_client.PlaceOrderRequest(
                quantity       = quantity,
                product        = "I",              # Intraday
                validity       = "DAY",
                price          = price or 0,
                tag            = "TradeBot",
                instrument_token = symbol,
                order_type     = "MARKET" if order_type == "MARKET" else "LIMIT",
                transaction_type = side,
                disclosed_quantity = 0,
                trigger_price  = 0,
                is_amo         = False,
            )
            resp = api.place_order(body, "2.0")
            return resp.data.order_id if resp.data else ""
        except Exception as e:
            logger.error(f"[UPSTOX] place_order error: {e}")
            return ""

    def get_order_status(self, order_id: str) -> str:
        if self.is_paper_trading or not self._get_config():
            return "COMPLETE"
        try:
            import upstox_client
            api  = upstox_client.OrderApi(upstox_client.ApiClient(self._config))
            resp = api.get_order_details("2.0", order_id=order_id)
            status = (resp.data[0].status if resp.data else "UNKNOWN").upper()
            return status
        except Exception as e:
            logger.error(f"[UPSTOX] get_order_status error: {e}")
            return "UNKNOWN"

    def get_positions(self) -> List[Dict]:
        if self.is_paper_trading or not self._get_config():
            return []
        try:
            import upstox_client
            api  = upstox_client.PortfolioApi(upstox_client.ApiClient(self._config))
            resp = api.get_positions("2.0")
            return [p.to_dict() for p in (resp.data or [])]
        except Exception as e:
            logger.error(f"[UPSTOX] get_positions error: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        if self.is_paper_trading or not self._get_config():
            logger.info(f"[UPSTOX PAPER] Cancel order {order_id}")
            return True
        try:
            import upstox_client
            api = upstox_client.OrderApi(upstox_client.ApiClient(self._config))
            api.cancel_order("2.0", order_id)
            return True
        except Exception as e:
            logger.error(f"[UPSTOX] cancel_order error: {e}")
            return False

    def get_balance(self) -> float:
        """Fetch available margin/balance."""
        if self.is_paper_trading or not self._get_config():
            return 100000.0  # Default mock balance
        try:
            import upstox_client
            api = upstox_client.UserApi(upstox_client.ApiClient(self._config))
            resp = api.get_user_fund_margin("equity")
            if resp.data and hasattr(resp.data, 'equity'):
                return float(resp.data.equity.available_margin)
            return 0.0
        except Exception as e:
            logger.error(f"[UPSTOX] get_balance error: {e}")
            return 0.0

    def get_instrument_details(self, symbol: str) -> Dict:
        """Fetch details (lot size, token, etc.) for a specific symbol."""
        # Simple fallback for now
        lotsize = 65 if "NIFTY" in symbol.upper() and "BANK" not in symbol.upper() else 30
        return {"lotsize": lotsize, "expiry": None}

    def get_live_expiry(self, underlying: str, frequency: str = "WEEKLY") -> Optional[str]:
        """
        Returns the nearest upcoming expiry date for the underlying.
        """
        from src.utils.options_utils import get_upcoming_expiry
        from datetime import date
        
        # Determine weekday based on underlying
        weekday = 3 if underlying == "NIFTY" else 2 # Thu for Nifty, Wed for Banknifty
        expiry_date = get_upcoming_expiry(date.today(), expiry_weekday=weekday)
        
        return str(expiry_date)
