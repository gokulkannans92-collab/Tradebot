"""
TradeBot Exception Taxonomy

Standardized exception hierarchy for domain and infrastructure errors.
"""

from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN EXCEPTIONS - Business logic and trading errors
# ══════════════════════════════════════════════════════════════════════════════

class TradeBotException(Exception):
    """Base exception for all TradeBot errors."""
    pass


class TradingException(TradeBotException):
    """Base exception for trading-related errors."""
    pass


class SignalException(TradingException):
    """Errors in signal generation or processing."""
    pass


class StrategyException(TradingException):
    """Errors in strategy execution."""
    pass


class OrderException(TradingException):
    """Errors in order placement or management."""
    pass


class RiskException(TradingException):
    """Risk management violations."""
    pass


class InsufficientCapitalError(RiskException):
    """Insufficient capital for trade."""
    pass


class PositionLimitExceededError(RiskException):
    """Maximum position limit exceeded."""
    pass


class DailyLossLimitError(RiskException):
    """Daily loss limit exceeded."""
    pass


class BrokerException(TradingException):
    """Base exception for broker-related errors."""
    pass


class BrokerConnectionError(BrokerException):
    """Failed to connect to broker."""
    pass


class BrokerAPIError(BrokerException):
    """Broker API returned an error."""
    pass


class BrokerAuthenticationError(BrokerException):
    """Broker authentication failed."""
    pass


class OrderPlacementError(OrderException):
    """Failed to place an order."""
    pass


class OrderCancellationError(OrderException):
    """Failed to cancel an order."""
    pass


class OrderTimeoutError(OrderException):
    """Order execution timed out."""
    pass


# ══════════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE EXCEPTIONS - System and technical errors
# ══════════════════════════════════════════════════════════════════════════════

class InfrastructureException(TradeBotException):
    """Base exception for infrastructure errors."""
    pass


class DatabaseException(InfrastructureException):
    """Database-related errors."""
    pass


class DatabaseConnectionError(DatabaseException):
    """Failed to connect to database."""
    pass


class DatabaseQueryError(DatabaseException):
    """Database query failed."""
    pass


class CacheException(InfrastructureException):
    """Cache-related errors."""
    pass


class NetworkException(InfrastructureException):
    """Network-related errors."""
    pass


class WebSocketException(NetworkException):
    """WebSocket connection errors."""
    pass


class APIException(NetworkException):
    """External API errors."""
    pass


class ConfigurationException(TradeBotException):
    """Configuration-related errors."""
    pass


class ValidationException(TradeBotException):
    """Data validation errors."""
    pass


# ══════════════════════════════════════════════════════════════════════════════
# EXCEPTION FACTORY - Create standardized exceptions
# ══════════════════════════════════════════════════════════════════════════════

class ExceptionFactory:
    """Factory for creating standardized exceptions."""
    
    @staticmethod
    def from_error(error: Exception, context: str = "") -> TradeBotException:
        """Convert any exception to TradeBot exception."""
        error_str = str(error).lower()
        
        # Map common errors to domain exceptions
        if "connection" in error_str:
            return BrokerConnectionError(f"{context}: {error}") if "broker" in context.lower() else NetworkException(f"{context}: {error}")
        elif "authentication" in error_str or "unauthorized" in error_str:
            return BrokerAuthenticationError(f"{context}: {error}")
        elif "timeout" in error_str:
            return OrderTimeoutError(f"{context}: {error}")
        elif "limit" in error_str or "exceeded" in error_str:
            return RiskException(f"{context}: {error}")
        elif "database" in error_str or "sqlite" in error_str:
            return DatabaseException(f"{context}: {error}")
        elif "cache" in error_str:
            return CacheException(f"{context}: {error}")
        
        # Default to base exception
        return TradeBotException(f"{context}: {error}")


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK EXCEPTIONS
# ══════════════════════════════════════════════════════════════════════════════

class HealthCheckException(TradeBotException):
    """Base exception for health check failures."""
    pass


class ComponentUnhealthyError(HealthCheckException):
    """A component failed health check."""
    def __init__(self, component: str, message: str):
        self.component = component
        super().__init__(f"{component}: {message}")


class DatabaseUnhealthyError(HealthCheckException):
    """Database health check failed."""
    pass


class BrokerUnhealthyError(HealthCheckException):
    """Broker connection unhealthy."""
    pass


class WebSocketUnhealthyError(HealthCheckException):
    """WebSocket feed unhealthy."""
    pass


class RiskManagerUnhealthyError(HealthCheckException):
    """Risk manager unhealthy."""
    pass