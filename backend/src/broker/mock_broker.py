import logging
import random
import time as time_module
from typing import Dict, List, Optional
from datetime import date
from src.broker.base import Broker
from src.utils.nse_fetcher import NSEFetcher

logger = logging.getLogger("MockBroker")

class MockBroker(Broker):
    def __init__(self):
        self.orders = {}
        self.positions = []
        self.prices = {}  # Cache of last prices (live or simulated)
        self._is_connected = True  # Signals that get_quote is ready
    
    @property
    def name(self) -> str:
        return "Paper Trading (Mock)"
    # Realistic base prices used when yfinance is unavailable
    _SIM_BASE = {
        "NIFTY":     22500.0,
        "NIFTY50":   22500.0,
        "BANKNIFTY": 48000.0,
    }

    def login(self) -> bool:
        print("[MOCK] Logged in successfully.")
        return True

    # Map underlying names to Yahoo Finance tickers
    _YAHOO_TICKERS = {
        "NIFTY":     "^NSEI",
        "NIFTY50":   "^NSEI",
        "BANKNIFTY": "^NSEBANK",
    }

    def _fetch_real_price(self, symbol: str) -> float:
        """Try to get real-time price from yfinance. Returns 0 if unavailable."""
        ticker_sym = self._YAHOO_TICKERS.get(symbol.upper())
        if not ticker_sym:
            return 0.0
        try:
            import yfinance as yf
            data = yf.download(ticker_sym, period="1d", interval="1m",
                               progress=False, auto_adjust=True)
            if not data.empty:
                val = data["Close"].iloc[-1]
                # Newer yfinance returns a Series for single-ticker; extract scalar
                price = float(val.item() if hasattr(val, "item") else val)
                return price
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")
        return 0.0

    def get_quote(self, symbol: str) -> Dict:
        import logging
        _log = logging.getLogger("MockBroker")

        # Option symbols contain 'CE' or 'PE' - simulate premium with random walk
        is_option = symbol.upper().endswith("CE") or symbol.upper().endswith("PE")
        if is_option:
            # Better simulation: link premium to spot distance and decay
            # We'll use a slightly more stable random walk for mock testing
            base_premium = self.prices.get(symbol.upper(), 150.0)
            # Volatility depends on premium level: ~0.1% to 0.5% drift per poll
            vol_factor = max(base_premium * 0.005, 0.5)
            curr_premium = max(base_premium + random.uniform(-vol_factor, vol_factor), 1.0)
            self.prices[symbol.upper()] = round(curr_premium, 2)
            
            # Realistic random volume: base ~500, occasional 2-5× spikes
            vol = int(random.lognormvariate(6.2, 0.8))
            return {"symbol": symbol, "last_price": self.prices[symbol], "price": self.prices[symbol],
                    "volume": vol, "timestamp": time_module.time(), "exchange": "NFO"}

        # Spot price: try yfinance first for realism
        real_price = self._fetch_real_price(symbol)
        if real_price > 0:
            self.prices[symbol] = real_price
            _log.info(f"[LIVE] {symbol} spot = ₹{real_price:.2f} (NSE/yfinance)")
            return {"symbol": symbol, "last_price": real_price, "price": real_price,
                    "timestamp": time_module.time(), "source": "live"}

        # API unavailable - simulate a realistic random-walk price so mock
        # mode never stalls or triggers the API-failure circuit breaker.
        sym_key = symbol.upper()
        base = self.prices.get(sym_key) or self._SIM_BASE.get(sym_key, 22500.0)
        # Small tick: ±0.05 % per poll (realistic intraday drift)
        simulated = round(base * (1 + random.uniform(-0.0005, 0.0005)), 2)
        self.prices[sym_key] = simulated
        _log.debug(f"[SIM] {symbol} spot = Rs{simulated:.2f} (simulated - API unavailable)")
        return {"symbol": symbol, "last_price": simulated, "price": simulated,
                "timestamp": time_module.time(), "source": "simulated"}


    def get_symbol(self, underlying: str, expiry, strike: int, option_type: str) -> str:
        from src.utils.options_utils import build_option_symbol
        return build_option_symbol(underlying, expiry, strike, option_type)

    def get_option_chain(self, symbol: str, expiry: str) -> List[Dict]:
        from src.utils.options_utils import build_option_symbol
        from datetime import date
        
        chain = []
                             
        # Fallback to simulated chain if NSE fetch fails
        quote = self.get_quote(symbol)
        spot = quote["last_price"] if quote else 22000.0
        atm_strike = round(spot / 50) * 50
        
        for strike in range(atm_strike - 100, atm_strike + 150, 50):
            for opt_type in ["CE", "PE"]:
                sym = build_option_symbol(symbol, date.fromisoformat(expiry) if "-" in expiry else date.today(), strike, opt_type)
                chain.append({
                    "strike": strike,
                    "type": opt_type,
                    "price": random.uniform(50, 200),
                    "symbol": sym
                })
        return chain

    def place_order(self, symbol: str, quantity: int, order_type: str, side: str, price: Optional[float] = None, trigger_price: Optional[float] = None) -> str:
        order_id = f"MOCK_ORD_{random.randint(1000, 9999)}"
        fill_price = price or (self.get_quote(symbol) or {}).get("last_price", 0.0)
        
        # In simulation, LIMIT orders stay OPEN until TradeTracker hits price.
        # MARKET orders fill immediately.
        status = "COMPLETE" if order_type == "MARKET" else "OPEN"
        
        self.orders[order_id] = {
            "order_id": order_id,
            "symbol": symbol.upper(),
            "quantity": quantity,
            "side": side,
            "status": status,
            "price": fill_price,
            "type": order_type
        }
        # Seed the price cache so get_quote starts from this price
        self.prices[symbol.upper()] = fill_price
        
        if side == "BUY" and status == "COMPLETE":
            self.positions.append(self.orders[order_id])
        
        print(f"[MOCK] Order Placed: {side} {quantity} {symbol.upper()} @ {fill_price} Status: {status}")
        return order_id

    def get_order_status(self, order_id: str) -> str:
        return self.orders.get(order_id, {}).get("status", "REJECTED")

    def get_positions(self) -> List[Dict]:
        return self.positions

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id]["status"] = "CANCELLED"
            return True
        return False

    def get_balance(self) -> float:
        """Mock balance for paper trading."""
        return 1000000.0  # Rs10 Lakhs mock balance

    def get_instrument_details(self, symbol: str) -> Dict:
        """Fetch details (lot size, token, etc.) for a specific symbol in mock mode."""
        # For mock, we'll return standard lot sizes
        lotsize = 65 if "NIFTY" in symbol.upper() and "BANK" not in symbol.upper() else 30
        if "FIN" in symbol.upper(): lotsize = 40
        
        return {
            "token": "MOCK_TOKEN",
            "lotsize": lotsize,
            "expiry": "2026-03-31",
            "strike": 22000,
            "exch": "NFO"
        }

    def get_live_expiry(self, underlying: str, frequency: str = "WEEKLY") -> str:
        """Returns a dummy expiry for mock trading."""
        from datetime import date, timedelta
        # Next Tuesday (Weekly)
        days_to_tuesday = (1 - date.today().weekday()) % 7
        if days_to_tuesday == 0: days_to_tuesday = 7
        return (date.today() + timedelta(days=days_to_tuesday)).strftime("%d%b%Y").upper()

    def get_historical_data(self, symbol, interval, days=5):
        """Mock historical data for strategy warm-up"""
        import logging
        logger = logging.getLogger("MockBroker")
        logger.info(f"[MOCK] Pre-fetching historical {interval} candles for {symbol} ({days} days)")
        
        # Return dummy candle data to satisfy strategy warm-up
        import pandas as pd
        import numpy as np
        from datetime import datetime, timedelta
        
        # Create 500 candles (standard for most warmups)
        now = datetime.now()
        dates = [now - timedelta(minutes=5*i) for i in range(500)]
        dates.reverse()
        
        prices = 18000 + np.random.randn(500).cumsum()
        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': prices + 2,
            'low': prices - 2,
            'close': prices + 1,
            'volume': np.random.randint(100, 1000, 500)
        })
        return df

if __name__ == "__main__":
    broker = MockBroker()
    broker.login()
    print(broker.get_quote("NIFTY"))
    oid = broker.place_order("NIFTY_22MAY_22000_CE", 50, "MARKET", "BUY")
    print(f"Order Status: {broker.get_order_status(oid)}")
    print(f"Positions: {broker.get_positions()}")
