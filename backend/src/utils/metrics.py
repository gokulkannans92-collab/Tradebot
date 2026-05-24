"""
Comprehensive Logging and Metrics System

Provides structured logging, performance metrics, and monitoring.
"""

import time
import logging
import threading
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from pathlib import Path


class TradeBotMetrics:
    """
    Metrics collector for the trading bot.
    Tracks performance, latency, errors, and trading stats.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._start_time = time.time()
        
        # Counters
        self._counters: Dict[str, int] = defaultdict(int)
        self._errors: Dict[str, int] = defaultdict(int)
        
        # Timing metrics
        self._timings: Dict[str, List[float]] = defaultdict(list)
        self._timing_locks: Dict[str, threading.Lock] = {}
        
        # Trade metrics
        self._trades_total = 0
        self._trades_won = 0
        self._trades_lost = 0
        self._total_pnl = 0.0
        
        # API call metrics
        self._api_calls = 0
        self._api_errors = 0
        self._api_latencies: List[float] = []
        
        # Thread safety
        self._metrics_lock = threading.Lock()
    
    def _get_timing_lock(self, name: str) -> threading.Lock:
        """Get or create a lock for timing metrics."""
        if name not in self._timing_locks:
            self._timing_locks[name] = threading.Lock()
        return self._timing_locks[name]
    
    # ── Counters ────────────────────────────────────────────────────────
    
    def increment(self, name: str, value: int = 1):
        """Increment a counter."""
        with self._metrics_lock:
            self._counters[name] += value
    
    def get_counter(self, name: str) -> int:
        """Get counter value."""
        with self._metrics_lock:
            return self._counters.get(name, 0)
    
    # ── Timing ──────────────────────────────────────────────────────────
    
    def record_timing(self, name: str, duration_ms: float):
        """Record a timing metric in milliseconds."""
        lock = self._get_timing_lock(name)
        with lock:
            self._timings[name].append(duration_ms)
            # Keep only last 1000 timings to prevent memory growth
            if len(self._timings[name]) > 1000:
                self._timings[name] = self._timings[name][-1000:]
    
    def get_timing_stats(self, name: str) -> Dict[str, float]:
        """Get timing statistics for a metric."""
        lock = self._get_timing_lock(name)
        with lock:
            timings = self._timings.get(name, [])
            if not timings:
                return {"count": 0, "min": 0, "max": 0, "avg": 0, "p95": 0}
            
            sorted_timings = sorted(timings)
            count = len(sorted_timings)
            
            return {
                "count": count,
                "min": sorted_timings[0],
                "max": sorted_timings[-1],
                "avg": sum(sorted_timings) / count,
                "p95": sorted_timings[int(count * 0.95)] if count > 0 else 0,
                "p99": sorted_timings[int(count * 0.99)] if count > 0 else 0
            }
    
    def time_operation(self, name: str):
        """Context manager for timing operations."""
        return TimingContext(self, name)
    
    # ── Trade Metrics ──────────────────────────────────────────────────
    
    def record_trade(self, pnl: float):
        """Record a completed trade."""
        with self._metrics_lock:
            self._trades_total += 1
            self._total_pnl += pnl
            if pnl > 0:
                self._trades_won += 1
            else:
                self._trades_lost += 1
    
    def get_trade_stats(self) -> Dict[str, Any]:
        """Get trade statistics."""
        with self._metrics_lock:
            win_rate = (self._trades_won / self._trades_total * 100) if self._trades_total > 0 else 0
            return {
                "total_trades": self._trades_total,
                "won": self._trades_won,
                "lost": self._trades_lost,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(self._total_pnl, 2),
                "avg_pnl": round(self._total_pnl / self._trades_total, 2) if self._trades_total > 0 else 0
            }
    
    # ── API Metrics ───────────────────────────────────────────────────
    def record_api_call(self, latency_ms: float, success: bool = True):
        """Record an API call."""
        with self._metrics_lock:
            self._api_calls += 1
            if not success:
                self._api_errors += 1
            self._api_latencies.append(latency_ms)
            if len(self._api_latencies) > 1000:
                self._api_latencies = self._api_latencies[-1000:]
    
    def get_api_stats(self) -> Dict[str, Any]:
        """Get API call statistics."""
        with self._metrics_lock:
            error_rate = (self._api_errors / self._api_calls * 100) if self._api_calls > 0 else 0
            avg_latency = sum(self._api_latencies) / len(self._api_latencies) if self._api_latencies else 0
            return {
                "total_calls": self._api_calls,
                "errors": self._api_errors,
                "error_rate": round(error_rate, 2),
                "avg_latency_ms": round(avg_latency, 2)
            }
    
    # ── Error Tracking ─────────────────────────────────────────────────
    def record_error(self, error_type: str):
        """Record an error occurrence."""
        with self._metrics_lock:
            self._errors[error_type] += 1
    
    def get_errors(self) -> Dict[str, int]:
        """Get error counts."""
        with self._metrics_lock:
            return dict(self._errors)
    
    # ── Summary ─────────────────────────────────────────────────────────
    def get_summary(self) -> Dict[str, Any]:
        """Get complete metrics summary."""
        uptime = time.time() - self._start_time
        
        return {
            "uptime_seconds": round(uptime, 2),
            "uptime_hours": round(uptime / 3600, 2),
            "counters": dict(self._counters),
            "trade_stats": self.get_trade_stats(),
            "api_stats": self.get_api_stats(),
            "errors": self.get_errors()
        }
    
    def reset(self):
        """Reset all metrics."""
        with self._metrics_lock:
            self._counters.clear()
            self._errors.clear()
            self._timings.clear()
            self._trades_total = 0
            self._trades_won = 0
            self._trades_lost = 0
            self._total_pnl = 0.0
            self._api_calls = 0
            self._api_errors = 0
            self._api_latencies.clear()


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, metrics: TradeBotMetrics, name: str):
        self.metrics = metrics
        self.name = name
        self.start_time = 0
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        self.metrics.record_timing(self.name, duration_ms)


class StructuredLogger:
    """
    Structured logging wrapper for the trading bot.
    Provides JSON-based logging with contextual information.
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Set contextual information for logging."""
        self._context.update(kwargs)
    
    def clear_context(self):
        """Clear contextual information."""
        self._context.clear()
    
    def _format_message(self, msg: str, extra: Dict = None) -> str:
        """Format message with context."""
        context = {**self._context, **(extra or {})}
        if context:
            return f"{msg} | {json.dumps(context)}"
        return msg
    
    def debug(self, msg: str, **kwargs):
        self.logger.debug(self._format_message(msg, kwargs))
    
    def info(self, msg: str, **kwargs):
        self.logger.info(self._format_message(msg, kwargs))
    
    def warning(self, msg: str, **kwargs):
        self.logger.warning(self._format_message(msg, kwargs))
    
    def error(self, msg: str, **kwargs):
        self.logger.error(self._format_message(msg, kwargs))
    
    def critical(self, msg: str, **kwargs):
        self.logger.critical(self._format_message(msg, kwargs))


# Global metrics instance
_metrics: Optional[TradeBotMetrics] = None


def get_metrics() -> TradeBotMetrics:
    """Get or create the global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = TradeBotMetrics()
    return _metrics


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger."""
    return StructuredLogger(name)


# Convenience function for timing
def timed(name: str):
    """Decorator for timing functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                get_metrics().record_timing(name, duration_ms)
        return wrapper
    return decorator