"""
Zerodha Broker Integration
Uses Kite API for live trading and market data
"""
from src.broker.base import Broker
from typing import Dict, List, Optional
import logging
import os

logger = logging.getLogger("ZerodhaBroker")
class ZerodhaBroker(Broker):
    """
    Zerodha Broker Integration using KiteConnect API
    Supports live trading, paper trading, and market data
    """
    
    @property
    def name(self) -> str:
        return "Zerodha"
    
    def __init__(self, api_key: str = "", access_token: str = "", is_paper_trading: bool = True):
        """
        Args:
            api_key: Zerodha API key from Kite Console
            access_token: Access token from Kite login
            is_paper_trading: If True, uses paper trading without real money
        """
        self.api_key = api_key or os.getenv("ZERODHA_API_KEY", "")
        self.access_token = access_token or os.getenv("ZERODHA_ACCESS_TOKEN", "")
        self.is_paper_trading = is_paper_trading
        
        # Validate credentials for live trading
        if not self.is_paper_trading:
            if not self.api_key or not self.api_key.strip():
                raise ValueError("ZERODHA_API_KEY is required for live trading and cannot be empty")
            if not self.access_token or not self.access_token.strip():
                raise ValueError("ZERODHA_ACCESS_TOKEN is required for live trading and cannot be empty")
        
        self.is_connected = False
        
        # Initialize KiteConnect - will be lazy loaded
        self.kite = None
        self.instruments_map = {}  # Cache for symbol -> instrument mapping
        
        # Paper trading tracking
        self.paper_positions = {}
        self.paper_orders = {}
        self.paper_cash = 100000  # Default paper trading capital
        self.order_counter = 0
        
        if not self.is_paper_trading and not self.api_key:
            logger.warning("Live trading enabled but no API key provided")
    
    def login(self) -> bool:
        """Authenticate with Zerodha/Kite API"""
        # Always try to authenticate if credentials are provided, so we can fetch live data
        try:
            # Lazy import KiteConnect
            try:
                from kiteconnect import KiteConnect
            except ImportError:
                logger.error("kiteconnect library not installed. Install with: pip install kiteconnect")
                if self.is_paper_trading:
                    logger.info("Paper trading enabled but kiteconnect missing. Skipping actual login.")
                    self.is_connected = True
                    return True
                return False
            
            if not self.access_token:
                logger.warning("No access_token provided.")
                if self.is_paper_trading:
                    logger.info("Paper trading enabled without tokens. Skipping actual login.")
                    self.is_connected = True
                    return True
                return False
            
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.access_token)
            
            # Verify connection
            profile = self.kite.profile()
            mode = "Paper" if self.is_paper_trading else "Live"
            logger.info(f"Connected to Zerodha as {profile['user_name']} in {mode} mode")
            self.is_connected = True
            return True
        
        except Exception as e:
            logger.error(f"Failed to connect to Zerodha: {str(e)}")
            self.kite = None
            if self.is_paper_trading:
                logger.info("Falling back to pure mock paper trading.")
                self.is_connected = True
                return True
            self.is_connected = False
            return False
    
    def get_quote(self, symbol: str) -> Dict:
        """Get live price quote for a symbol"""
        is_option = symbol.upper().endswith("CE") or symbol.upper().endswith("PE")
        exchange = "NFO" if is_option else "NSE"

        if not self.kite:
            if self.is_paper_trading:
                # Return mock quote for paper trading if no active connection
                if is_option:
                    return {
                        "symbol": symbol,
                        "price": 150.0,  # Mock option premium
                        "exchange": "NFO"
                    }
                return {
                    "symbol": symbol,
                    "price": 22500.0,  # Mock NIFTY spot
                    "last_trade_time": None,
                    "exchange": "NSE",
                    "bid": 22499.0,
                    "ask": 22501.0
                }
            return {"symbol": symbol, "price": 0, "error": "Not connected"}

        # Map indices to correct Kite Connect symbols
        kite_symbol = symbol
        if symbol == "NIFTY":
            kite_symbol = "NIFTY 50"
        elif symbol == "BANKNIFTY":
            kite_symbol = "NIFTY BANK"
            
        try:
            # Get quote from Zerodha
            key = f"{exchange}:{kite_symbol}"
            data = self.kite.quote(key)
            quote_price = data[key]["last_price"]

            return {
                "symbol": symbol,
                "price": float(quote_price) if quote_price else 0.0,
                "timestamp": None,
                "exchange": exchange
            }
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {str(e)}")
            return {"symbol": symbol, "price": 0, "error": str(e)}
    
    def get_historical_data(self, symbol: str, interval: str = "5minute", 
                          from_date: str = None, to_date: str = None) -> List[Dict]:
        """
        Get historical OHLCV data
        interval: "1minute", "5minute", "15minute", "30minute", "60minute", "daily"
        """
        if not self.kite:
            if self.is_paper_trading:
                logger.warning("Paper trading: Cannot fetch historical data without active connection")
            return []
        
        try:
            # Map indices to correct Kite Connect symbols
            kite_symbol = symbol
            if symbol == "NIFTY":
                kite_symbol = "NIFTY 50"
            elif symbol == "BANKNIFTY":
                kite_symbol = "NIFTY BANK"
                
            # Get historical data
            data = self.kite.historical_data(
                "NSE:" + kite_symbol,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            # Convert to list of dictionaries
            candles = []
            for candle in data:
                candles.append({
                    "time": candle["date"],
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": candle["volume"]
                })
            
            return candles
        except Exception as e:
            logger.error(f"Failed to get historical data for {symbol}: {str(e)}")
            return []
    
    def get_symbol(self, underlying: str, expiry, strike: int, option_type: str) -> str:
        from src.utils.options_utils import build_option_symbol
        return build_option_symbol(underlying, expiry, strike, option_type)

    def get_option_chain(self, symbol: str, expiry: str) -> List[Dict]:
        """Fetch option chain data for a symbol"""
        if not self.kite:
            if self.is_paper_trading:
                logger.warning("Paper trading: Cannot fetch option chain without active connection")
            return []
        
        try:
            # Get instruments
            all_instruments = self.kite.instruments()
            option_chain = [
                inst for inst in all_instruments
                if inst["name"] == symbol and 
                inst["instrument_type"] == "CE" or inst["instrument_type"] == "PE" and
                inst["expiry"] == expiry
            ]
            
            return option_chain
        except Exception as e:
            logger.error(f"Failed to get option chain: {str(e)}")
            return []
    
    def place_order(self, symbol: str, quantity: int, order_type: str, 
                   side: str, price: Optional[float] = None) -> str:
        """
        Place an order
        Args:
            symbol: Trading symbol (e.g., "NIFTY50", "RELIANCE")
            quantity: Number of shares/contracts
            order_type: "MARKET", "LIMIT"
            side: "BUY", "SELL"
            price: Price for LIMIT orders
        
        Returns:
            Order ID
        """
        if self.is_paper_trading:
            # Paper trading: simulate order
            self.order_counter += 1
            order_id = f"PAPER_{self.order_counter}"

            self.paper_orders[order_id] = {
                "order_id": order_id,
                "symbol": symbol,
                "quantity": quantity,
                "side": side,
                "order_type": order_type,
                "price": price or 22000,
                "status": "COMPLETE",
                "timestamp": None
            }

            logger.info(f"Paper trading order placed: {order_id} - {side} {quantity} {symbol}")
            return order_id

        try:
            if not self.kite:
                return ""

            # Use NFO exchange for options (CE/PE), NSE for equity
            is_option = symbol.upper().endswith("CE") or symbol.upper().endswith("PE")
            exchange = "NFO" if is_option else "NSE"

            order_id = self.kite.place_order(
                tradingsymbol=symbol,
                exchange=exchange,
                quantity=quantity,
                transaction_type=side.upper(),
                order_type=order_type.upper(),
                product="MIS",  # Intraday for options
                price=price
            )

            logger.info(f"Order placed on Zerodha ({exchange}): {order_id}")
            return str(order_id)
        except Exception as e:
            logger.error(f"Failed to place order: {str(e)}")
            return ""
    
    def get_order_status(self, order_id: str) -> str:
        """Check status of an order"""
        if self.is_paper_trading:
            if order_id in self.paper_orders:
                return self.paper_orders[order_id].get("status", "UNKNOWN")
            return "UNKNOWN"
        
        try:
            if not self.kite:
                return "UNKNOWN"
            
            orders = self.kite.orders()
            for order in orders:
                if order["order_id"] == int(order_id):
                    return order["status"]
            return "UNKNOWN"
        except Exception as e:
            logger.error(f"Failed to get order status: {str(e)}")
            return "UNKNOWN"
    
    def get_positions(self) -> List[Dict]:
        """Fetch current open positions"""
        if self.is_paper_trading:
            return list(self.paper_positions.values())
        
        try:
            if not self.kite:
                return []
            
            positions = self.kite.positions()
            return positions.get("net", [])
        except Exception as e:
            logger.error(f"Failed to get positions: {str(e)}")
            return []
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        if self.is_paper_trading:
            if order_id in self.paper_orders:
                self.paper_orders[order_id]["status"] = "CANCELLED"
                logger.info(f"Paper trading order cancelled: {order_id}")
                return True
            return False
        
        try:
            if not self.kite:
                return False
            
            self.kite.cancel_order(order_id=order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order: {str(e)}")
            return False

    def get_balance(self) -> float:
        """Fetch available margin/balance."""
        if self.is_paper_trading:
            return float(self.paper_cash)
        
        try:
            if not self.kite:
                return 0.0
            
            margins = self.kite.margins()
            # In Zerodha, 'available' normally means 'net' cash available
            return float(margins.get("equity", {}).get("available", 0.0))
        except Exception as e:
            logger.error(f"Failed to get balance: {str(e)}")
            return 0.0

    def get_instrument_details(self, symbol: str) -> Dict:
        """Fetch details (lot size, token, etc.) for a specific symbol."""
        if not self.kite:
            # Fallback for paper trading
            lotsize = 65 if "NIFTY" in symbol.upper() and "BANK" not in symbol.upper() else 30
            return {"lotsize": lotsize, "expiry": None}
            
        try:
            # Fetch instrument from Zerodha
            all_inst = self.kite.instruments("NFO")
            for inst in all_inst:
                if inst["tradingsymbol"] == symbol:
                    return {
                        "token": inst["instrument_token"],
                        "lotsize": int(inst["lot_size"]),
                        "expiry": str(inst["expiry"]),
                        "strike": float(inst["strike"]),
                        "exch": "NFO"
                    }
        except Exception as e:
            logger.error(f"Failed to get instrument details for {symbol}: {e}")
        return {}

    def get_live_expiry(self, underlying: str, frequency: str = "WEEKLY") -> Optional[str]:
        """Fetch live expiry from Zerodha"""
        if not self.kite: return None
        try:
            insts = self.kite.instruments("NFO")
            expiries = sorted(list(set([str(i["expiry"]) for i in insts if i["name"] == underlying])))
            return expiries[0] if expiries else None
        except Exception as e:
            logger.error(f"Error fetching expiry from Zerodha: {e}")
            return None
    
    def get_account_info(self) -> Dict:
        """Get account information"""
        if self.is_paper_trading:
            return {
                "balance": self.paper_cash,
                "used_margin": 0,
                "available_margin": self.paper_cash,
                "mode": "Paper Trading"
            }
        
        try:
            if not self.kite:
                return {}
            
            margins = self.kite.margins()
            return {
                "balance": margins["equity"]["available"],
                "used_margin": margins["equity"]["used"],
                "available_margin": margins["equity"]["available"],
                "mode": "Live"
            }
        except Exception as e:
            logger.error(f"Failed to get account info: {str(e)}")
            return {}
