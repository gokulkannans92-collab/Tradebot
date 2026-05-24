"""
Connection Pool for Broker APIs

Provides connection pooling and session management for broker APIs.
"""

import time
import logging
import threading
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from queue import Queue, Empty
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class Connection:
    """Represents a pooled connection."""
    id: str
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    is_valid: bool = True


class ConnectionPool:
    """
    Thread-safe connection pool for broker APIs.
    
    Features:
    - Max connections per broker
    - Connection timeout/ttl
    - Automatic cleanup of stale connections
    - Connection request queueing
    """
    
    def __init__(
        self,
        max_connections: int = 5,
        max_idle_time: float = 300.0,  # 5 minutes
        connection_timeout: float = 30.0,
        cleanup_interval: float = 60.0
    ):
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.connection_timeout = connection_timeout
        self.cleanup_interval = cleanup_interval
        
        # Connection storage: broker_name -> list of Connection
        self._pools: Dict[str, list] = {}
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Background cleanup thread
        self._running = False
        self._cleanup_thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the connection pool."""
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("Connection pool started")
    
    def stop(self):
        """Stop the connection pool and cleanup."""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        logger.info("Connection pool stopped")
    
    def _cleanup_loop(self):
        """Background cleanup of stale connections."""
        while self._running:
            time.sleep(self.cleanup_interval)
            self._cleanup_stale_connections()
    
    def _cleanup_stale_connections(self):
        """Remove connections that have been idle too long."""
        with self._lock:
            current_time = time.time()
            for broker_name, connections in self._pools.items():
                original_count = len(connections)
                self._pools[broker_name] = [
                    c for c in connections
                    if c.is_valid and (current_time - c.last_used) < self.max_idle_time
                ]
                removed = original_count - len(self._pools[broker_name])
                if removed > 0:
                    logger.debug(f"Cleaned up {removed} stale connections for {broker_name}")
    
    def acquire(self, broker_name: str, factory: Callable) -> Any:
        """
        Acquire a connection from the pool.
        
        Args:
            broker_name: Name of the broker
            factory: Callable that creates a new connection if needed
        
        Returns:
            A connection object from the pool or newly created
        """
        with self._lock:
            # Initialize pool for this broker if needed
            if broker_name not in self._pools:
                self._pools[broker_name] = []
            
            # Try to get an existing valid connection
            pool = self._pools[broker_name]
            current_time = time.time()
            
            for conn in pool:
                if conn.is_valid and (current_time - conn.last_used) < self.max_idle_time:
                    conn.last_used = current_time
                    conn.use_count += 1
                    logger.debug(f"Reusing connection {conn.id} for {broker_name}")
                    return factory(reuse=True)
            
            # Check if we can create a new connection
            if len(pool) < self.max_connections:
                new_conn = Connection(
                    id=f"{broker_name}_{len(pool)}_{int(current_time)}"
                )
                pool.append(new_conn)
                logger.debug(f"Created new connection {new_conn.id} for {broker_name}")
                return factory(reuse=False)
            
            # Pool is full, wait for one to become available
            logger.warning(f"Connection pool full for {broker_name}, waiting...")
            time.sleep(1)
            return self.acquire(broker_name, factory)  # Retry
    
    def release(self, broker_name: str):
        """Release a connection back to the pool (called after use)."""
        with self._lock:
            if broker_name in self._pools and self._pools[broker_name]:
                # Just mark the most recently used as available
                pass  # Connections stay in pool, marked by last_used
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            stats = {}
            for broker_name, connections in self._pools.items():
                stats[broker_name] = {
                    "total": len(connections),
                    "active": sum(1 for c in connections if c.is_valid),
                    "total_uses": sum(c.use_count for c in connections)
                }
            return stats


# Global connection pool instance
_global_pool: Optional[ConnectionPool] = None


def get_connection_pool() -> ConnectionPool:
    """Get or create the global connection pool."""
    global _global_pool
    if _global_pool is None:
        _global_pool = ConnectionPool()
        _global_pool.start()
    return _global_pool


class BrokerConnectionMixin:
    """
    Mixin class that adds connection pooling to broker implementations.
    """
    
    def __init__(self, *args, use_pool: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self._use_pool = use_pool
        self._pool = get_connection_pool() if use_pool else None
        self._connection_count = 0
    
    def _get_with_pool(self, operation: str, fallback_result: Any) -> Any:
        """Execute an operation with connection pooling."""
        if not self._pool:
            return fallback_result
        
        try:
            return self._pool.acquire(
                self.__class__.__name__,
                lambda reuse: self._execute_operation(operation, reuse)
            )
        except Exception as e:
            logger.error(f"Pooled operation {operation} failed: {e}")
            return fallback_result
    
    def _execute_operation(self, operation: str, reuse: bool) -> Any:
        """Actual operation execution (to be implemented by subclass)."""
        # Subclass should override this or implement directly
        self._connection_count += 1
        return None
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        if self._pool:
            return self._pool.get_stats()
        return {"pool_enabled": False}