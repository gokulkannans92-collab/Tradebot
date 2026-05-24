"""
Cache Manager

Provides efficient in-memory caching with batch persistence.
Replaces frequent file writes with memory-first approach.
"""

import json
import threading
import time
from typing import Any, Dict, Optional, Callable
from datetime import datetime
from collections import deque
import logging

logger = logging.getLogger(__name__)


class TimedCache:
    """
    In-memory cache with automatic batch persistence.
    
    Reduces file I/O by:
    1. Keeping data in memory
    2. Only writing to disk every N seconds or M changes
    3. Using background thread for persistence
    """
    
    def __init__(
        self,
        filepath: Optional[str] = None,
        flush_interval: float = 30.0,  # Write to disk every 30 seconds
        max_changes: int = 100,  # Or every 100 changes
        on_flush: Optional[Callable[[Any], None]] = None
    ):
        self._data: Dict[str, Any] = {}
        self._filepath = filepath
        self._flush_interval = flush_interval
        self._max_changes = max_changes
        self._on_flush = on_flush
        
        self._change_count = 0
        self._last_flush = time.time()
        self._lock = threading.RLock()
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None
        
        # Load initial data if file exists
        if filepath:
            self._load_from_disk()
    
    def start(self):
        """Start background flush thread."""
        if self._running:
            return
        
        self._running = True
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            name="TimedCache-Flush",
            daemon=True
        )
        self._flush_thread.start()
        logger.info(f"TimedCache started for {self._filepath}")
    
    def stop(self):
        """Stop background thread and flush remaining data."""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=2.0)
        self._flush(force=True)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        with self._lock:
            return self._data.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set value in cache (marks for persistence)."""
        with self._lock:
            self._data[key] = value
            self._change_count += 1
        
        # Check if we should flush
        if self._change_count >= self._max_changes:
            self._flush()
    
    def update(self, data: Dict[str, Any]):
        """Batch update multiple values."""
        with self._lock:
            self._data.update(data)
            self._change_count += len(data)
        
        if self._change_count >= self._max_changes:
            self._flush()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all cached data."""
        with self._lock:
            return self._data.copy()
    
    def clear(self):
        """Clear all cached data."""
        with self._lock:
            self._data.clear()
            self._change_count += 1
    
    def _flush_loop(self):
        """Background thread that periodically flushes to disk."""
        while self._running:
            time.sleep(1.0)  # Check every second
            
            elapsed = time.time() - self._last_flush
            if elapsed >= self._flush_interval:
                self._flush()
    
    def _flush(self, force: bool = False):
        """Write cache to disk if needed."""
        with self._lock:
            if not self._filepath:
                return
            
            if not force and self._change_count == 0:
                return
            
            try:
                with open(self._filepath, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, indent=2)
                
                self._change_count = 0
                self._last_flush = time.time()
                
                if self._on_flush:
                    self._on_flush(self._data)
                
                logger.debug(f"Cache flushed to {self._filepath}")
                
            except (IOError, OSError) as e:
                logger.error(f"Failed to flush cache: {e}")
    
    def _load_from_disk(self):
        """Load initial data from disk."""
        if not self._filepath:
            return
        
        try:
            with open(self._filepath, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._data = loaded
                else:
                    logger.warning(f"Cache file {self._filepath} is not a dictionary. Clearing it.")
                    self._data = {}
            logger.info(f"Loaded cache from {self._filepath}")
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}
        except (IOError, OSError) as e:
            logger.error(f"Failed to load cache: {e}")
            self._data = {}


class RingBuffer:
    """
    Fixed-size ring buffer for efficient data storage.
    
    Replaces DataFrame concatenation with O(1) append/remove.
    """
    
    def __init__(self, capacity: int, dtype: type = dict):
        self.capacity = capacity
        self.dtype = dtype
        self._buffer: deque = deque(maxlen=capacity)
        self._lock = threading.RLock()
    
    def append(self, item: Any):
        """Add item to buffer (drops oldest if full)."""
        with self._lock:
            self._buffer.append(item)
    
    def extend(self, items: list):
        """Add multiple items."""
        with self._lock:
            for item in items:
                self._buffer.append(item)
    
    def get_all(self) -> list:
        """Get all items as list (oldest first)."""
        with self._lock:
            return list(self._buffer)
    
    def get_last(self, n: int = 1) -> list:
        """Get last N items."""
        with self._lock:
            return list(self._buffer)[-n:]
    
    def get_range(self, start: int, end: int) -> list:
        """Get items in range [start, end)."""
        with self._lock:
            items = list(self._buffer)
            return items[start:end]
    
    def clear(self):
        """Clear all items."""
        with self._lock:
            self._buffer.clear()
    
    def __len__(self) -> int:
        return len(self._buffer)
    
    def is_full(self) -> bool:
        """Check if buffer is at capacity."""
        return len(self._buffer) >= self.capacity
    
    def to_dataframe(self):
        """Convert to pandas DataFrame if items are dicts."""
        import pandas as pd
        with self._lock:
            if not self._buffer:
                return pd.DataFrame()
            return pd.DataFrame(list(self._buffer))


class ActiveTradesCache:
    """
    Specialized cache for active trades data.
    
    Optimized for frequent reads, infrequent writes.
    """
    
    def __init__(self, filepath: Optional[str] = None, max_age_seconds: float = 5.0):
        self._cache = TimedCache(
            filepath=filepath,
            flush_interval=1.0,  # Reduced from 30s to 1s for live dashboard
            max_changes=1        # Flush on every single change
        )
        self._max_age = max_age_seconds
        self._last_update = 0.0
        self._lock = threading.RLock()
        
        # Pre-serialized JSON for GUI reads
        self._json_cache: str = "[]"
        self._json_dirty = True
    
    def start(self):
        self._cache.start()
    
    def stop(self):
        self._cache.stop()
    
    def update_trades(self, trades: list):
        """Update trades data (batched)."""
        with self._lock:
            self._cache.set("active_trades", trades)
            self._last_update = time.time()
            self._json_dirty = True
    
    def get_trades(self) -> list:
        """Get current trades (from memory)."""
        return self._cache.get("active_trades", [])
    
    def get_trades_json(self) -> str:
        """Get pre-serialized JSON for GUI (avoids repeated serialization)."""
        with self._lock:
            if self._json_dirty:
                trades = self.get_trades()
                self._json_cache = json.dumps(trades)
                self._json_dirty = False
            return self._json_cache
    
    def is_stale(self) -> bool:
        """Check if data is older than max_age."""
        return (time.time() - self._last_update) > self._max_age


# Global cache instances for shared use
_caches: Dict[str, TimedCache] = {}
_caches_lock = threading.Lock()


def get_cache(name: str, filepath: Optional[str] = None) -> TimedCache:
    """Get or create a named cache instance."""
    with _caches_lock:
        if name not in _caches:
            _caches[name] = TimedCache(filepath=filepath)
        return _caches[name]


def shutdown_all_caches():
    """Shutdown all global caches."""
    with _caches_lock:
        for cache in _caches.values():
            cache.stop()
        _caches.clear()
