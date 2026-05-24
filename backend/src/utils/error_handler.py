"""
Centralized Error Handling Utilities

Provides standardized exception handling patterns to replace bare except clauses.
"""

import logging
import functools
import sys
import json
import requests
from typing import Callable, Optional, TypeVar, Tuple, Union

logger = logging.getLogger(__name__)
T = TypeVar('T')


# Standard exception tuples for common operations
FILE_IO_EXCEPTIONS = (OSError, IOError, FileNotFoundError, PermissionError)
JSON_EXCEPTIONS = (json.JSONDecodeError, TypeError, ValueError)
NETWORK_EXCEPTIONS = (requests.RequestException, TimeoutError, ConnectionError)
CRYPTO_EXCEPTIONS = (ValueError, TypeError)




def safe_execute(
    func: Callable[..., T],
    *args,
    default: Optional[T] = None,
    exceptions: Tuple[type, ...] = (Exception,),
    log_message: Optional[str] = None,
    **kwargs
) -> Optional[T]:
    """
    Execute a function safely with proper exception handling.
    
    Args:
        func: Function to execute
        args: Positional arguments
        default: Default value to return on exception
        exceptions: Tuple of exception types to catch
        log_message: Optional message to log on exception
        kwargs: Keyword arguments
        
    Returns:
        Function result or default value on exception
    """
    try:
        return func(*args, **kwargs)
    except exceptions as e:
        if log_message:
            logger.error(f"{log_message}: {e}")
        return default


def safe_file_read(
    filepath: str,
    mode: str = 'r',
    default: Optional[T] = None,
    encoding: str = 'utf-8'
) -> Optional[str]:
    """Safely read a file with proper exception handling."""
    try:
        with open(filepath, mode, encoding=encoding, errors='replace') as f:
            return f.read()
    except FILE_IO_EXCEPTIONS as e:
        logger.error(f"Failed to read file {filepath}: {e}")
        return default


def safe_json_load(
    filepath: str,
    default: Optional[T] = None
) -> Optional[dict]:
    """Safely load JSON from file with proper exception handling."""
    content = safe_file_read(filepath, default=None)
    if content is None:
        return default
    
    try:
        return json.loads(content)
    except JSON_EXCEPTIONS as e:
        logger.error(f"Failed to parse JSON from {filepath}: {e}")
        return default


def safe_json_dump(
    data: dict,
    filepath: str,
    indent: int = 2,
    default: bool = False
) -> bool:
    """Safely write JSON to file with proper exception handling."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent)
        return True
    except FILE_IO_EXCEPTIONS + JSON_EXCEPTIONS as e:
        logger.error(f"Failed to write JSON to {filepath}: {e}")
        return default


def exception_handler(
    exceptions: Tuple[type, ...] = (Exception,),
    default: Optional[T] = None,
    log_message: Optional[str] = None,
    reraise: bool = False
):
    """
    Decorator for standardized exception handling.
    
    Args:
        exceptions: Tuple of exception types to catch
        default: Default value to return on exception
        log_message: Optional message to log
        reraise: Whether to re-raise the exception after logging
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                msg = log_message or f"Error in {func.__name__}"
                logger.error(f"{msg}: {e}")
                if reraise:
                    raise
                return default
        return wrapper
    return decorator


# Context manager for safe execution
class SafeContext:
    """Context manager for safe execution with automatic cleanup."""
    
    def __init__(
        self,
        exceptions: Tuple[type, ...] = (Exception,),
        log_message: Optional[str] = None,
        cleanup: Optional[Callable] = None
    ):
        self.exceptions = exceptions
        self.log_message = log_message
        self.cleanup = cleanup
        self.error = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and issubclass(exc_type, self.exceptions):
            self.error = exc_val
            if self.log_message:
                logger.error(f"{self.log_message}: {exc_val}")
            if self.cleanup:
                try:
                    self.cleanup()
                except Exception as e:
                    logger.error(f"Cleanup failed: {e}")
            return True  # Suppress exception
        return False  # Let other exceptions propagate


def validate_not_none(value: Optional[T], name: str) -> T:
    """Validate that a value is not None, raise ValueError if it is."""
    if value is None:
        raise ValueError(f"{name} cannot be None")
    return value


def validate_positive(value: Union[int, float], name: str) -> Union[int, float]:
    """Validate that a numeric value is positive."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value
