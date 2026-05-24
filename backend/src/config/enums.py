"""
Enumerations for consistent naming and type safety across the application.

These enums should be used throughout the codebase instead of magic strings
to improve type safety, IDE autocompletion, and prevent naming inconsistencies.
"""

from enum import Enum


class BrokerType(str, Enum):
    """
    Supported broker types.
    
    Use BrokerType instead of string literals like "ZERODHA" or "ANGEL"
    for better type safety and IDE support.
    """
    ZERODHA = "ZERODHA"
    ANGEL = "ANGEL"
    UPSTOX = "UPSTOX"
    GROWW = "GROWW"
    MOCK = "MOCK"

    def __str__(self) -> str:
        """Return the string representation."""
        return self.value

    @classmethod
    def from_string(cls, value: str):
        """Convert string to BrokerType enum.
        
        Args:
            value: String value to convert
            
        Returns:
            BrokerType enum value
            
        Raises:
            ValueError: If value is not a valid broker type
        """
        if not value:
            return cls.MOCK
        
        value_upper = str(value).upper().strip()
        for member in cls:
            if member.value == value_upper:
                return member
        
        # If not found, return MOCK as default
        return cls.MOCK

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if value is a valid broker type."""
        try:
            cls(value.upper())
            return True
        except ValueError:
            return False


class OrderType(str, Enum):
    """
    Order type enumerations.
    
    MARKET: Execute immediately at market price
    LIMIT: Execute at specified price or better
    STOP: Trigger order at specified price
    STOP_LIMIT: Stop loss with limit price
    """
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(str, Enum):
    """
    Order direction.
    
    BUY: Long position
    SELL: Short position
    """
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(str, Enum):
    """
    Trade lifecycle status.
    
    PENDING: Waiting to enter
    ACTIVE: Entered position
    EXITED: Closed position
    CANCELLED: Trade was cancelled
    ERROR: Trade failed
    """
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXITED = "EXITED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class OrderStatus(str, Enum):
    """
    Order status from broker.
    
    PENDING: Order not yet processed
    OPEN: Order placed, waiting to fill
    PARTIALLY_FILLED: Partial fill
    FILLED: Fully executed
    CANCELLED: User cancelled
    REJECTED: Broker rejected
    EXPIRED: Order expired
    """
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class StrategyType(str, Enum):
    """
    Available trading strategies.
    """
    EMA_VWAP = "EMA_VWAP"
    ML_PATTERN = "ML_PATTERN"
    NIFTY_OPTIONS = "NIFTY_OPTIONS"
    COMBINED_SIGNAL = "COMBINED_SIGNAL"
    DEBUG = "DEBUG"


class TimeFrame(str, Enum):
    """
    Candle time frames in seconds.
    """
    ONE_MIN = 60
    FIVE_MIN = 300
    FIFTEEN_MIN = 900
    ONE_HOUR = 3600


class UserStatus(str, Enum):
    """
    User account status.
    
    ACTIVE: User can trade
    PAUSED: Temporarily disabled
    DISABLED: Permanently disabled
    """
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"
