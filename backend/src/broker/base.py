from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging
import time
import asyncio

logger = logging.getLogger(__name__)


class BrokerError(Exception):
    """Base exception for broker errors."""
    pass


class BrokerConnectionError(BrokerError):
    """Raised when broker connection fails."""
    pass


class BrokerAPIError(BrokerError):
    """Raised when broker API returns an error."""
    pass


class BrokerCircuitBreakerError(BrokerError):
    """Raised when the circuit breaker is active and requests are blocked."""
    pass


class Broker(ABC):
    """Abstract base class for broker implementations."""
    
    def __init__(self):
        self._is_connected = False
        self._last_error: Optional[str] = None
        # Rate limiting: minimum interval between API calls (seconds)
        self._min_api_interval = 0.5  # 500ms between calls
        self._last_api_call = 0.0
        
        # Circuit Breaker state
        self._api_failure_count = 0
        self._max_failures = 3
        self._circuit_breaker_tripped_until = 0.0
        self._circuit_breaker_cooldown = 60.0  # 60 seconds

    
    def _enforce_rate_limit(self):
        """Enforce minimum interval between API calls to prevent rate limiting."""
        elapsed = time.time() - self._last_api_call
        if elapsed < self._min_api_interval:
            sleep_time = self._min_api_interval - elapsed
            time.sleep(sleep_time)
        self._last_api_call = time.time()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the human-readable name of the broker."""
        pass

    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._is_connected
    
    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        """Set connection status."""
        self._is_connected = value
        
    def _check_circuit_breaker(self):
        """Check if the circuit breaker is tripped."""
        if time.time() < self._circuit_breaker_tripped_until:
            remaining = int(self._circuit_breaker_tripped_until - time.time())
            raise BrokerCircuitBreakerError(f"Circuit breaker active. Requests blocked for {remaining}s.")
            
    def _record_api_success(self):
        """Reset failure count on successful API call."""
        if self._api_failure_count > 0:
            logger.info("Broker API recovered. Circuit breaker reset.")
        self._api_failure_count = 0
    
    def _handle_error(self, operation: str, error: Exception) -> None:
        """Log and handle broker errors, tripping circuit breaker if necessary."""
        error_msg = f"Broker {operation} failed: {str(error)}"
        logger.error(error_msg)
        self._last_error = error_msg
        
        # Increment failure count and check circuit breaker
        self._api_failure_count += 1
        if self._api_failure_count >= self._max_failures:
            logger.critical(f"🛑 [CIRCUIT BREAKER] Tripped after {self._max_failures} consecutive API failures. Blocking requests for {self._circuit_breaker_cooldown}s.")
            self._circuit_breaker_tripped_until = time.time() + self._circuit_breaker_cooldown
        
        # Re-raise as specific exception
        if "connection" in str(error).lower() or "timeout" in str(error).lower():
            raise BrokerConnectionError(error_msg) from error
        else:
            raise BrokerAPIError(error_msg) from error

    def safe_get_quote(self, symbol: str) -> Dict:
        """Get live price with exception handling."""
        self._check_circuit_breaker()
        self._enforce_rate_limit()
        try:
            res = self.get_quote(symbol)
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("get_quote", e)

    def safe_get_historical_data(self, symbol: str, interval: str = "5minute", 
                                  from_date: str = None, to_date: str = None) -> List[Dict]:
        """Get historical data with exception handling."""
        self._check_circuit_breaker()
        try:
            res = self.get_historical_data(symbol, interval, from_date, to_date)
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("get_historical_data", e)

    def safe_place_order(self, symbol: str, quantity: int, order_type: str, 
                         side: str, price: Optional[float] = None) -> str:
        """Place order with exception handling."""
        self._check_circuit_breaker()
        self._enforce_rate_limit()
        try:
            res = self.place_order(symbol, quantity, order_type, side, price)
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("place_order", e)

    def safe_get_order_status(self, order_id: str) -> str:
        """Get order status with exception handling."""
        self._check_circuit_breaker()
        try:
            res = self.get_order_status(order_id)
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("get_order_status", e)

    def safe_get_positions(self) -> List[Dict]:
        """Get positions with exception handling."""
        self._check_circuit_breaker()
        try:
            res = self.get_positions()
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("get_positions", e)

    def safe_cancel_order(self, order_id: str) -> bool:
        """Cancel order with exception handling."""
        self._check_circuit_breaker()
        try:
            res = self.cancel_order(order_id)
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("cancel_order", e)

    # ──────────────────────────────────────────────────────────────────
    # Async versions for better performance
    # ──────────────────────────────────────────────────────────────────

    async def safe_get_quote_async(self, symbol: str) -> Dict:
        """Get live price asynchronously with exception handling."""
        self._check_circuit_breaker()
        self._enforce_rate_limit()
        try:
            # Run in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, self.get_quote, symbol)
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("get_quote_async", e)

    async def safe_place_order_async(self, symbol: str, quantity: int, order_type: str, 
                                   side: str, price: Optional[float] = None) -> str:
        """Place order asynchronously with exception handling."""
        self._check_circuit_breaker()
        self._enforce_rate_limit()
        try:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, self.place_order, symbol, quantity, order_type, side, price)
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("place_order_async", e)

    async def safe_get_order_status_async(self, order_id: str) -> str:
        """Get order status asynchronously with exception handling."""
        self._check_circuit_breaker()
        self._enforce_rate_limit()
        try:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, self.get_order_status, order_id)
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("get_order_status_async", e)

    def safe_get_balance(self) -> float:
        """Get balance with exception handling."""
        self._check_circuit_breaker()
        try:
            res = self.get_balance()
            self._record_api_success()
            return res
        except BrokerError:
            raise
        except Exception as e:
            self._handle_error("get_balance", e)

    @abstractmethod
    def login(self) -> bool:
        """Authenticate with the broker API."""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Dict:
        """Get live price for a symbol."""
        pass

    @abstractmethod
    def get_symbol(self, underlying: str, expiry, strike: int, option_type: str) -> str:
        """Build a broker-specific option symbol."""
        pass

    @abstractmethod
    def get_option_chain(self, symbol: str, expiry: str) -> List[Dict]:
        """Fetch option chain data."""
        pass

    @abstractmethod
    def place_order(self, symbol: str, quantity: int, order_type: str, side: str, price: Optional[float] = None, trigger_price: Optional[float] = None) -> str:
        """Place an order and return the order ID."""
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> str:
        """Check status of an order."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """Fetch current open positions."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        pass

    @abstractmethod
    def get_balance(self) -> float:
        """Fetch available margin/balance from the broker."""
        pass

    @abstractmethod
    def get_instrument_details(self, symbol: str) -> Dict:
        """Fetch details (lot size, expiry, etc.) for a specific symbol."""
        pass

    # ── Broker-specific symbol resolution (override per broker) ────────

    def get_index_quote_symbol(self, index_name: str) -> str:
        """
        Return the broker-specific quote symbol for a well-known index name.

        Default mapping covers Angel One naming. Override in Zerodha/Upstox
        subclasses with their own variants.

        Args:
            index_name: Canonical name ("NIFTY", "BANKNIFTY", "FINNIFTY")

        Returns:
            Broker-specific quote symbol string
        """
        _map = {
            "NIFTY":     "Nifty 50",
            "BANKNIFTY": "Nifty Bank",
            "FINNIFTY":  "Nifty Fin Service",
        }
        return _map.get(index_name.upper(), index_name)

    def get_vix_symbols(self) -> List[str]:
        """
        Return ordered list of broker-specific VIX quote symbols to try.

        Default covers Angel One. Override per broker as needed.
        """
        return ["India VIX", "INDIA VIX"]
