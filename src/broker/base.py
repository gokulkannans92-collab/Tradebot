from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class Broker(ABC):
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
    def place_order(self, symbol: str, quantity: int, order_type: str, side: str, price: Optional[float] = None) -> str:
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
