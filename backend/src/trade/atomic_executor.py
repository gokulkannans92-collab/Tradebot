"""
Atomic Trade Executor

Prevents race conditions in trade execution with proper locking.
Implements check-and-act atomicity for trade entry decisions.
"""

import threading
import logging
from typing import Optional, Callable, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TradeExecutionLock:
    """
    Per-session trade execution lock.
    
    Ensures atomic check-and-act for trade decisions:
    1. Check if can trade
    2. If yes, lock and execute
    3. If no, skip without locking
    
    This prevents TOCTOU (Time-of-Check-Time-of-Use) race conditions
    where two threads could both pass the check before either executes.
    """
    
    _locks: dict = {}
    _master_lock = threading.Lock()
    
    @classmethod
    def get_lock(cls, session_id: str) -> threading.Lock:
        """Get or create a lock for a specific session."""
        with cls._master_lock:
            if session_id not in cls._locks:
                cls._locks[session_id] = threading.Lock()
            return cls._locks[session_id]
    
    @classmethod
    def remove_lock(cls, session_id: str):
        """Remove a lock when session ends."""
        with cls._master_lock:
            if session_id in cls._locks:
                del cls._locks[session_id]


class AtomicTradeChecker:
    """
    Atomic checker for trade preconditions.
    
    Combines all trade validation checks into a single atomic operation
    with proper locking to prevent race conditions.
    """
    
    def __init__(self, session):
        self.session = session
        self._lock = TradeExecutionLock.get_lock(session.user_id)
    
    def can_execute_trade(
        self,
        strategy_type: str,  # "NIFTY" or "BANKNIFTY"
        check_cooldown: Callable[[], bool],
        on_execute: Optional[Callable[[], Any]] = None
    ) -> bool:
        """
        Atomically check if trade can be executed and acquire lock if yes.
        
        Args:
            strategy_type: Which strategy is attempting to trade
            check_cooldown: Function that returns True if cooldown has passed
            on_execute: Optional callback to execute if checks pass (within lock)
            
        Returns:
            True if trade was/will be executed, False otherwise
        """
        # Quick pre-check without locking (performance optimization)
        tracker = getattr(self.session, f"{strategy_type.lower()}_tracker", None)
        if tracker and tracker.active_trades:
            logger.debug(f"[{self.session.name}] Already has active {strategy_type} trade")
            return False
        
        if not self.session.risk.can_trade():
            logger.debug(f"[{self.session.name}] Risk manager blocked trade")
            return False
        
        if not check_cooldown():
            logger.debug(f"[{self.session.name}] Cooldown not elapsed")
            return False
        
        # Acquire lock before executing (non-blocking)
        if not self._lock.acquire(blocking=False):
            logger.warning(f"[{self.session.name}] Trade execution already in progress, skipping")
            return False
        
        try:
            # Re-check conditions within lock (they may have changed)
            tracker = getattr(self.session, f"{strategy_type.lower()}_tracker", None)
            if tracker and tracker.active_trades:
                logger.debug(f"[{self.session.name}] Race condition avoided: {strategy_type} trade active")
                return False
            
            if not self.session.risk.can_trade():
                logger.debug(f"[{self.session.name}] Race condition avoided: risk blocked")
                return False
            
            # All checks passed - execute trade (while holding lock)
            if on_execute:
                try:
                    on_execute()
                    return True
                except Exception as e:
                    logger.error(f"[{self.session.name}] Trade execution failed: {e}")
                    return False
            return True
            
        finally:
            self._lock.release()
    
    def execute_with_lock(self, operation: Callable[[], Any], timeout: float = 5.0) -> Optional[Any]:
        """
        Execute an operation with trade lock held.
        
        Args:
            operation: Function to execute
            timeout: Maximum time to wait for lock
            
        Returns:
            Result of operation, or None if lock couldn't be acquired
        """
        if not self._lock.acquire(timeout=timeout):
            logger.error(f"[{self.session.name}] Could not acquire trade lock within {timeout}s")
            return None
        
        try:
            return operation()
        except Exception as e:
            logger.error(f"[{self.session.name}] Operation failed: {e}")
            raise
        finally:
            self._lock.release()


@contextmanager
def trade_execution_context(session, strategy_type: str):
    """
    Context manager for atomic trade execution.
    
    Usage:
        with trade_execution_context(session, "NIFTY") as can_trade:
            if can_trade:
                execute_trade()
    
    Args:
        session: UserSession instance
        strategy_type: "NIFTY" or "BANKNIFTY"
        
    Yields:
        bool: True if trade can proceed (lock acquired and pre-checks passed)
    """
    checker = AtomicTradeChecker(session)
    lock = checker._lock
    
    # Pre-checks
    tracker = getattr(session, f"{strategy_type.lower()}_tracker", None)
    if tracker and tracker.active_trades:
        yield False
        return
    
    if not session.risk.can_trade():
        yield False
        return
    
    # Try to acquire lock
    if not lock.acquire(blocking=False):
        logger.warning(f"[{session.name}] Trade execution contested, skipping")
        yield False
        return
    
    try:
        # Re-check within lock
        tracker = getattr(session, f"{strategy_type.lower()}_tracker", None)
        if tracker and tracker.active_trades:
            yield False
            return
        
        if not session.risk.can_trade():
            yield False
            return
            
        yield True
        
    finally:
        lock.release()


class RateLimiter:
    """
    Simple rate limiter for broker API calls.
    
    Prevents hitting API rate limits by tracking call timestamps
    and enforcing minimum intervals between calls.
    """
    
    def __init__(self, calls_per_second: float = 1.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0.0
        self._lock = threading.Lock()
    
    def acquire(self, timeout: float = 10.0) -> bool:
        """
        Wait until rate limit allows another call.
        
        Args:
            timeout: Maximum seconds to wait
            
        Returns:
            True if allowed, False if timeout
        """
        import time
        start = time.time()
        
        while True:
            with self._lock:
                now = time.time()
                elapsed = now - self.last_call_time
                
                if elapsed >= self.min_interval:
                    self.last_call_time = now
                    return True
                
                wait_time = self.min_interval - elapsed
            
            if time.time() - start + wait_time > timeout:
                return False
            
            time.sleep(min(wait_time, 0.1))
    
    def try_acquire(self) -> bool:
        """Non-blocking attempt to acquire rate limit."""
        import time
        with self._lock:
            now = time.time()
            if now - self.last_call_time >= self.min_interval:
                self.last_call_time = now
                return True
            return False


class CircuitBreaker:
    """
    Circuit breaker pattern for handling network failures and API errors.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failure threshold exceeded, requests fail fast
    - HALF_OPEN: Testing if service recovered
    """
    
    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._lock = threading.Lock()
    
    @property
    def state(self) -> str:
        """Current circuit breaker state."""
        with self._lock:
            return self._state
    
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        import time
        
        with self._lock:
            if self._state == self.STATE_CLOSED:
                return True
            
            if self._state == self.STATE_OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = self.STATE_HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit breaker entering HALF_OPEN state")
                    return True
                return False
            
            if self._state == self.STATE_HALF_OPEN:
                return self._success_count < self.half_open_max_calls
            
            return True
    
    def record_success(self):
        """Record successful execution."""
        with self._lock:
            if self._state == self.STATE_HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    logger.info("Circuit breaker CLOSED - service recovered")
                    self._state = self.STATE_CLOSED
                    self._failure_count = 0
            else:
                self._failure_count = 0
    
    def record_failure(self):
        """Record failed execution."""
        import time
        
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == self.STATE_HALF_OPEN:
                logger.warning("Circuit breaker OPEN - failure in half-open state")
                self._state = self.STATE_OPEN
            elif self._failure_count >= self.failure_threshold:
                logger.warning(f"Circuit breaker OPEN - {self.failure_threshold} failures")
                self._state = self.STATE_OPEN
    
    def execute(self, operation: Callable[[], Any], default: Any = None) -> Any:
        """
        Execute operation with circuit breaker protection.
        
        Args:
            operation: Function to execute
            default: Default value to return if circuit is open
            
        Returns:
            Result of operation, or default if circuit is open
        """
        if not self.can_execute():
            logger.debug("Circuit breaker blocked execution (state: OPEN)")
            return default
        
        try:
            result = operation()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
