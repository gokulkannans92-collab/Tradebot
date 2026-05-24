"""
Broker Mixins

Shared functionality for broker implementations.
Provides common error handling, retry logic, and rate limiting.
"""

import time
import logging
from functools import wraps
from typing import Optional, Callable, Any, TypeVar, List
from datetime import datetime, timedelta

from src.utils.error_handler import safe_execute, exception_handler

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RateLimiterMixin:
    """
    Mixin for rate limiting API calls.
    
    Ensures minimum interval between calls to avoid API rate limits.
    """
    
    def __init__(self, calls_per_second: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self._min_interval = 1.0 / calls_per_second
        self._last_call_time: Optional[datetime] = None
    
    def _rate_limit(self):
        """Enforce rate limit - call before making API request."""
        if self._last_call_time is not None:
            elapsed = (datetime.now() - self._last_call_time).total_seconds()
            if elapsed < self._min_interval:
                sleep_time = self._min_interval - elapsed
                time.sleep(sleep_time)
        
        self._last_call_time = datetime.now()


class RetryMixin:
    """
    Mixin for retry logic on failed operations.
    
    Automatically retries transient failures with exponential backoff.
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        retryable_exceptions: tuple = (Exception,),
        **kwargs
    ):
        super().__init__(**kwargs)
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._retryable_exceptions = retryable_exceptions
    
    def _with_retry(self, operation: Callable[[], T], operation_name: str = "operation") -> Optional[T]:
        """
        Execute operation with retry logic.
        
        Args:
            operation: Function to execute
            operation_name: Name for logging
            
        Returns:
            Operation result or None if all retries failed
        """
        for attempt in range(self._max_retries):
            try:
                return operation()
            except self._retryable_exceptions as e:
                if attempt < self._max_retries - 1:
                    delay = min(self._base_delay * (2 ** attempt), self._max_delay)
                    logger.warning(f"{operation_name} failed (attempt {attempt + 1}): {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"{operation_name} failed after {self._max_retries} attempts: {e}")
                    raise
        
        return None


class ErrorHandlingMixin:
    """
    Mixin for standardized error handling.
    
    Provides consistent logging and error transformation.
    """
    
    def _handle_error(self, error: Exception, context: str = "") -> dict:
        """
        Standardize error handling.
        
        Args:
            error: The exception that occurred
            context: Additional context for logging
            
        Returns:
            Standardized error response dict
        """
        error_msg = f"{context}: {str(error)}" if context else str(error)
        logger.error(error_msg, exc_info=True)
        
        return {
            "success": False,
            "error": error_msg,
            "error_type": type(error).__name__,
            "timestamp": datetime.now().isoformat()
        }
    
    def _log_api_call(self, method: str, endpoint: str, **kwargs):
        """Log API call details."""
        logger.debug(f"API Call: {method} {endpoint} | Params: {kwargs}")


class ConnectionHealthMixin:
    """
    Mixin for tracking connection health.
    
    Monitors success/failure rates and can trigger circuit breaker.
    """
    
    def __init__(self, failure_threshold: int = 5, **kwargs):
        super().__init__(**kwargs)
        self._failure_threshold = failure_threshold
        self._consecutive_failures = 0
        self._last_success: Optional[datetime] = None
        self._is_healthy = True
    
    def _record_success(self):
        """Record a successful operation."""
        self._consecutive_failures = 0
        self._last_success = datetime.now()
        if not self._is_healthy:
            self._is_healthy = True
            logger.info("Connection health restored")
    
    def _record_failure(self):
        """Record a failed operation."""
        self._consecutive_failures += 1
        
        if self._consecutive_failures >= self._failure_threshold:
            if self._is_healthy:
                self._is_healthy = False
                logger.error(f"Connection unhealthy: {self._consecutive_failures} consecutive failures")
    
    @property
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        return self._is_healthy


class BrokerBaseMixin(RateLimiterMixin, RetryMixin, ErrorHandlingMixin, ConnectionHealthMixin):
    """
    Combined mixin with all broker utility features.
    
    Usage:
        class MyBroker(BrokerBaseMixin, BaseBroker):
            def __init__(self):
                super().__init__(
                    calls_per_second=2.0,
                    max_retries=3,
                    failure_threshold=5
                )
            
            def get_quote(self, symbol):
                self._rate_limit()  # Enforce rate limit
                
                def _fetch():
                    # Actual API call here
                    return self._api.get_quote(symbol)
                
                result = self._with_retry(_fetch, f"get_quote({symbol})")
                
                if result:
                    self._record_success()
                    return result
                else:
                    self._record_failure()
                    return None
    """
    
    def __init__(
        self,
        calls_per_second: float = 1.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        failure_threshold: int = 5,
        retryable_exceptions: tuple = (Exception,),
        **kwargs
    ):
        # Initialize all mixins
        RateLimiterMixin.__init__(self, calls_per_second=calls_per_second)
        RetryMixin.__init__(
            self,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            retryable_exceptions=retryable_exceptions
        )
        ErrorHandlingMixin.__init__(self)
        ConnectionHealthMixin.__init__(self, failure_threshold=failure_threshold)
        
        # Call any remaining parent init
        super().__init__(**kwargs)


def broker_method(operation_name: str, retry: bool = True):
    """
    Decorator for broker methods with automatic error handling and retry.
    
    Args:
        operation_name: Name of the operation for logging
        retry: Whether to enable retry logic
        
    Usage:
        class MyBroker(BrokerBaseMixin):
            @broker_method("get_quote")
            def get_quote(self, symbol):
                return self._api.get_quote(symbol)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Rate limit check
            if hasattr(self, '_rate_limit'):
                self._rate_limit()
            
            # Log the call
            if hasattr(self, '_log_api_call'):
                self._log_api_call(func.__name__, operation_name, args=args, kwargs=kwargs)
            
            def _execute():
                return func(self, *args, **kwargs)
            
            try:
                if retry and hasattr(self, '_with_retry'):
                    result = self._with_retry(_execute, operation_name)
                else:
                    result = _execute()
                
                # Record success
                if hasattr(self, '_record_success'):
                    self._record_success()
                
                return result
                
            except Exception as e:
                # Record failure
                if hasattr(self, '_record_failure'):
                    self._record_failure()
                
                # Handle error
                if hasattr(self, '_handle_error'):
                    return self._handle_error(e, operation_name)
                raise
        
        return wrapper
    return decorator
