"""
Metrics Collector

Collects and stores performance metrics for monitoring and analysis.
"""

import logging
import time
import threading
import psutil
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
from src.monitoring import Metric
from src.utils.paths import get_data_dir

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and manages performance metrics."""

    def __init__(self):
        self._metrics: List[Metric] = []
        self._max_metrics = 10000  # Keep last 10k metrics
        self._collection_interval = 60  # seconds
        self._is_collecting = False
        self._collection_thread: Optional[threading.Thread] = None

    def start_collection(self):
        """Start automatic metrics collection."""
        if self._is_collecting:
            return

        self._is_collecting = True
        self._collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._collection_thread.start()
        logger.info("Metrics collection started")

    def stop_collection(self):
        """Stop automatic metrics collection."""
        self._is_collecting = False
        if self._collection_thread:
            self._collection_thread.join(timeout=5)
        logger.info("Metrics collection stopped")

    def _collection_loop(self):
        """Main collection loop."""
        while self._is_collecting:
            try:
                self._collect_system_metrics()
                self._collect_trade_metrics()
                time.sleep(self._collection_interval)
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                time.sleep(10)  # Wait before retrying

    def _collect_system_metrics(self):
        """Collect system-level metrics."""
        try:
            # CPU metrics
            self.record_metric("system.cpu.percent", psutil.cpu_percent(interval=1), "percent")

            # Memory metrics
            memory = psutil.virtual_memory()
            self.record_metric("system.memory.used", memory.used / 1024 / 1024, "MB")
            self.record_metric("system.memory.percent", memory.percent, "percent")

            # Disk metrics
            disk = psutil.disk_usage('/')
            self.record_metric("system.disk.used", disk.used / 1024 / 1024 / 1024, "GB")
            self.record_metric("system.disk.percent", disk.percent, "percent")

            # Network metrics
            net = psutil.net_io_counters()
            self.record_metric("system.network.bytes_sent", net.bytes_sent / 1024 / 1024, "MB")
            self.record_metric("system.network.bytes_recv", net.bytes_recv / 1024 / 1024, "MB")

        except Exception as e:
            logger.error(f"System metrics collection failed: {e}")

    def _collect_trade_metrics(self):
        """Collect trading-related metrics."""
        try:
            from src.persistence.database import get_database
            db = get_database()

            with db.get_connection() as conn:
                cursor = conn.cursor()

                # Trade count metrics
                cursor.execute("SELECT COUNT(*) FROM trades WHERE date(entry_time) = date('now')")
                today_trades = cursor.fetchone()[0]
                self.record_metric("trading.trades_today", today_trades, "count")

                # P&L metrics
                cursor.execute("SELECT SUM(pnl) FROM trades WHERE date(entry_time) = date('now')")
                today_pnl = cursor.fetchone()[0] or 0
                self.record_metric("trading.pnl_today", today_pnl, "currency")

                # Active positions
                cursor.execute("SELECT COUNT(*) FROM positions WHERE 1=1")
                active_positions = cursor.fetchone()[0]
                self.record_metric("trading.active_positions", active_positions, "count")

        except Exception as e:
            logger.error(f"Trade metrics collection failed: {e}")

    def record_metric(self, name: str, value: float, unit: str, tags: Dict[str, str] = None):
        """Record a metric."""
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            tags=tags or {}
        )

        self._metrics.append(metric)

        # Maintain size limit
        if len(self._metrics) > self._max_metrics:
            self._metrics = self._metrics[-self._max_metrics:]

    def get_metrics(self, name: str = None, since: datetime = None, limit: int = 100) -> List[Metric]:
        """Get metrics with optional filtering."""
        metrics = self._metrics

        if name:
            metrics = [m for m in metrics if m.name == name]

        if since:
            metrics = [m for m in metrics if m.timestamp >= since]

        return metrics[-limit:] if limit > 0 else metrics

    def get_latest_metric(self, name: str) -> Optional[Metric]:
        """Get the latest value for a metric."""
        metrics = [m for m in self._metrics if m.name == name]
        return metrics[-1] if metrics else None

    def get_metric_stats(self, name: str, hours: int = 24) -> Dict[str, float]:
        """Get statistics for a metric over the last N hours."""
        since = datetime.now() - timedelta(hours=hours)
        metrics = self.get_metrics(name, since)

        if not metrics:
            return {}

        values = [m.value for m in metrics]
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'latest': values[-1]
        }