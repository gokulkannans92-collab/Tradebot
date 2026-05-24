"""
Monitoring Service

Main service that coordinates health checks, alerts, and metrics collection.
"""

import logging
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from src.monitoring import Alert, AlertLevel, HealthStatus
from src.monitoring.health_checker import HealthChecker, check_system_resources, check_network_connectivity, check_database_connectivity
from src.monitoring.alert_manager import AlertManager, send_critical_alert, send_error_alert, send_warning_alert
from src.monitoring.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


class MonitoringService:
    """Main monitoring service for TradeBot."""

    def __init__(self):
        self.health_checker = HealthChecker()
        self.alert_manager = AlertManager()
        self.metrics_collector = MetricsCollector()

        self._monitoring_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._check_interval = 60  # seconds
        self._last_health_status = HealthStatus.HEALTHY

        # Register built-in health checks
        self._register_builtin_checks()

    def _register_builtin_checks(self):
        """Register built-in health checks."""
        self.health_checker.register_check("system_resources", check_system_resources, 30)
        self.health_checker.register_check("network_connectivity", check_network_connectivity, 300)  # 5 minutes
        self.health_checker.register_check("database_connectivity", check_database_connectivity, 60)

    def start(self):
        """Start the monitoring service."""
        if self._is_running:
            return

        self._is_running = True
        self.metrics_collector.start_collection()

        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()

        logger.info("Monitoring service started")

    def stop(self):
        """Stop the monitoring service."""
        self._is_running = False
        self.metrics_collector.stop_collection()

        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=10)

        logger.info("Monitoring service stopped")

    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._is_running:
            try:
                self._perform_health_checks()
                self._check_for_alerts()
                time.sleep(self._check_interval)
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(10)

    def _perform_health_checks(self):
        """Perform all health checks."""
        results = self.health_checker.run_all_checks()

        # Check for status changes
        current_status = self.health_checker.get_health_status()

        if current_status != self._last_health_status:
            self._handle_health_status_change(current_status, self._last_health_status)
            self._last_health_status = current_status

        # Alert on unhealthy checks
        for result in results:
            if result.status == HealthStatus.UNHEALTHY:
                send_error_alert(
                    title=f"Health Check Failed: {result.name}",
                    message=result.message,
                    source="health_monitor",
                    details=result.details
                )

    def _handle_health_status_change(self, new_status: HealthStatus, old_status: HealthStatus):
        """Handle system health status changes."""
        if new_status == HealthStatus.UNHEALTHY:
            send_critical_alert(
                title="System Health Critical",
                message=f"System health changed from {old_status.value} to {new_status.value}",
                source="health_monitor"
            )
        elif new_status == HealthStatus.DEGRADED:
            send_warning_alert(
                title="System Health Degraded",
                message=f"System health changed from {old_status.value} to {new_status.value}",
                source="health_monitor"
            )
        else:
            # System recovered
            send_warning_alert(
                title="System Health Recovered",
                message=f"System health changed from {old_status.value} to {new_status.value}",
                source="health_monitor"
            )

    def _check_for_alerts(self):
        """Check for conditions that should trigger alerts."""
        try:
            # Check CPU usage
            cpu_metric = self.metrics_collector.get_latest_metric("system.cpu.percent")
            if cpu_metric and cpu_metric.value > 90:
                send_warning_alert(
                    title="High CPU Usage",
                    message=f"CPU usage is {cpu_metric.value:.1f}%",
                    source="metrics_monitor",
                    details={"cpu_percent": cpu_metric.value}
                )

            # Check memory usage
            mem_metric = self.metrics_collector.get_latest_metric("system.memory.percent")
            if mem_metric and mem_metric.value > 90:
                send_error_alert(
                    title="High Memory Usage",
                    message=f"Memory usage is {mem_metric.value:.1f}%",
                    source="metrics_monitor",
                    details={"memory_percent": mem_metric.value}
                )

            # Check daily P&L
            pnl_metric = self.metrics_collector.get_latest_metric("trading.pnl_today")
            if pnl_metric and pnl_metric.value < -5000:  # Example threshold
                send_warning_alert(
                    title="Significant Daily Loss",
                    message=f"Daily P&L is ₹{pnl_metric.value:.2f}",
                    source="trading_monitor",
                    details={"daily_pnl": pnl_metric.value}
                )

        except Exception as e:
            logger.error(f"Alert checking failed: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            "health_status": self.health_checker.get_health_status().value,
            "health_checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "timestamp": check.timestamp.isoformat(),
                    "details": check.details
                }
                for name, check in self.health_checker.get_last_results().items()
            },
            "recent_alerts": [
                {
                    "level": alert.level.value,
                    "title": alert.title,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "source": alert.source
                }
                for alert in self.alert_manager.get_recent_alerts(10)
            ],
            "metrics": {
                "system.cpu.percent": self.metrics_collector.get_latest_metric("system.cpu.percent"),
                "system.memory.percent": self.metrics_collector.get_latest_metric("system.memory.percent"),
                "trading.trades_today": self.metrics_collector.get_latest_metric("trading.trades_today"),
                "trading.pnl_today": self.metrics_collector.get_latest_metric("trading.pnl_today")
            }
        }

    def register_health_check(self, name: str, check_func: callable, interval: int = None):
        """Register a custom health check."""
        self.health_checker.register_check(name, check_func, interval)

    def record_custom_metric(self, name: str, value: float, unit: str, tags: Dict[str, str] = None):
        """Record a custom metric."""
        self.metrics_collector.record_metric(name, value, unit, tags)


# Global monitoring service instance
_monitoring_service = None


def get_monitoring_service() -> MonitoringService:
    """Get the global monitoring service instance."""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service


def start_monitoring():
    """Start the monitoring service."""
    service = get_monitoring_service()
    service.start()


def stop_monitoring():
    """Stop the monitoring service."""
    service = get_monitoring_service()
    service.stop()