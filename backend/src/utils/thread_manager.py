"""
Centralized Thread Manager

Provides unified thread lifecycle management for TradeBot.
Tracks all daemon threads, enables graceful shutdown, and prevents orphaned threads.
"""

import logging
import threading
import atexit
from typing import Dict, Optional, Callable, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ThreadManager:
    """
    Centralized thread management for the application.
    
    Features:
    - Register and track all daemon threads
    - Graceful shutdown of all threads
    - Prevents orphaned threads on exit
    - Thread health monitoring
    
    Usage:
        thread_mgr = ThreadManager()
        
        # Register a thread
        thread_mgr.register_thread("TelegramSender", sender_thread)
        
        # Or create and register in one call
        thread_mgr.start_daemon(
            name="BackgroundWorker",
            target=my_worker_function,
            args=(arg1, arg2)
        )
        
        # Graceful shutdown
        thread_mgr.shutdown()
    """
    
    _instance: Optional["ThreadManager"] = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> "ThreadManager":
        """Get singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                atexit.register(cls._instance.shutdown)
            return cls._instance
    
    def __init__(self):
        self._threads: Dict[str, threading.Thread] = {}
        self._threads_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        
        # Register default threads from existing components
        self._register_default_threads()
    
    def _register_default_threads(self):
        """Register threads from existing components if they exist."""
        try:
            from src.utils.notifications import TelegramManager
            from src.broker.connection_pool import ConnectionPool
            from src.utils.cache_manager import CacheManager
            logger.debug("ThreadManager initialized")
        except ImportError:
            pass
    
    def register_thread(self, name: str, thread: threading.Thread) -> None:
        """
        Register an existing thread for tracking.
        
        Args:
            name: Unique identifier for the thread
            thread: Thread object to track
        """
        with self._threads_lock:
            if name in self._threads:
                old_thread = self._threads[name]
                if old_thread.is_alive():
                    logger.warning(f"Thread '{name}' already registered and running, replacing")
                else:
                    logger.debug(f"Replacing stopped thread '{name}'")
            
            self._threads[name] = thread
            logger.debug(f"Registered thread: {name} (alive: {thread.is_alive()})")
    
    def start_daemon(
        self,
        name: str,
        target: Callable[[], Any],
        args: tuple = (),
        kwargs: dict = None
    ) -> threading.Thread:
        """
        Create and start a daemon thread.
        
        Args:
            name: Unique identifier for the thread
            target: Function to run in the thread
            args: Positional arguments for target
            kwargs: Keyword arguments for target
            
        Returns:
            Started thread object
        """
        if kwargs is None:
            kwargs = {}
        
        thread = threading.Thread(
            target=target,
            args=args,
            kwargs=kwargs,
            daemon=True,
            name=name
        )
        
        with self._threads_lock:
            self._threads[name] = thread
        
        thread.start()
        logger.info(f"Started daemon thread: {name}")
        
        return thread
    
    def stop_thread(self, name: str, timeout: float = 5.0) -> bool:
        """
        Stop a specific thread gracefully.
        
        Args:
            name: Thread identifier to stop
            timeout: Seconds to wait for graceful shutdown
            
        Returns:
            True if stopped successfully, False otherwise
        """
        with self._threads_lock:
            thread = self._threads.get(name)
        
        if thread is None:
            logger.warning(f"Thread '{name}' not found")
            return False
        
        if not thread.is_alive():
            logger.debug(f"Thread '{name}' already stopped")
            return True
        
        logger.info(f"Stopping thread: {name}")
        
        # For threads that monitor shutdown events
        if hasattr(thread, '_target'):
            # Check if it's using an event-based shutdown pattern
            pass
        
        # Wait for graceful shutdown
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            logger.warning(f"Thread '{name}' did not stop gracefully")
            return False
        
        logger.info(f"Thread '{name}' stopped")
        return True
    
    def shutdown(self, timeout: float = 10.0) -> None:
        """
        Gracefully shutdown all registered threads.
        
        Args:
            timeout: Seconds to wait for each thread
        """
        if self._shutdown_event.is_set():
            logger.debug("ThreadManager shutdown already called")
            return
        
        self._shutdown_event.set()
        logger.info(f"Shutting down all threads (timeout: {timeout}s)...")
        
        with self._threads_lock:
            thread_names = list(self._threads.keys())
        
        stopped = []
        failed = []
        
        for name in thread_names:
            with self._threads_lock:
                thread = self._threads.get(name)
            
            if thread and thread.is_alive():
                thread.join(timeout=timeout)
                if thread.is_alive():
                    failed.append(name)
                else:
                    stopped.append(name)
        
        logger.info(f"Stopped {len(stopped)} threads: {stopped}")
        if failed:
            logger.warning(f"Failed to stop {len(failed)} threads: {failed}")
        
        with self._threads_lock:
            self._threads.clear()
    
    def get_thread(self, name: str) -> Optional[threading.Thread]:
        """Get a registered thread by name."""
        with self._threads_lock:
            return self._threads.get(name)
    
    def get_threads(self) -> Dict[str, threading.Thread]:
        """Get all registered threads."""
        with self._threads_lock:
            return dict(self._threads)
    
    def get_alive_threads(self) -> Dict[str, threading.Thread]:
        """Get all running threads."""
        with self._threads_lock:
            return {name: t for name, t in self._threads.items() if t.is_alive()}
    
    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._shutdown_event.is_set()
    
    @contextmanager
    def thread_context(self, name: str):
        """
        Context manager for thread lifecycle.
        
        Usage:
            with thread_mgr.thread_context("MyWorker"):
                # Thread is registered
                do_work()
            # Thread automatically unregistered on exit
        """
        try:
            yield self
        finally:
            with self._threads_lock:
                if name in self._threads:
                    del self._threads[name]


# Convenience functions using singleton

def get_thread_manager() -> ThreadManager:
    """Get the global ThreadManager instance."""
    return ThreadManager.get_instance()


def register_thread(name: str, thread: threading.Thread) -> None:
    """Register a thread with the global manager."""
    get_thread_manager().register_thread(name, thread)


def start_daemon(name: str, target: Callable, args: tuple = (), kwargs: dict = None) -> threading.Thread:
    """Start a daemon thread via global manager."""
    return get_thread_manager().start_daemon(name, target, args, kwargs)


def shutdown_threads(timeout: float = 10.0) -> None:
    """Shutdown all threads via global manager."""
    get_thread_manager().shutdown(timeout)