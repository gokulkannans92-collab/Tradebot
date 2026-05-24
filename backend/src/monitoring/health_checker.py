"""
Health Checker

Performs system health checks and monitors critical components.
"""

import logging
import time
import psutil
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.monitoring import HealthCheck, HealthStatus

logger = logging.getLogger(__name__)


class HealthChecker:
    """Performs comprehensive health checks on the trading system."""

    def __init__(self):
        self._checks: Dict[str, callable] = {}
        self._check_interval = 30  # seconds
        self._last_results: Dict[str, HealthCheck] = {}

    def register_check(self, name: str, check_func: callable, interval: int = None):
        """Register a health check function."""
        self._checks[name] = {
            'func': check_func,
            'interval': interval or self._check_interval,
            'last_run': 0
        }
        logger.info(f"Registered health check: {name}")

    def run_all_checks(self) -> List[HealthCheck]:
        """Run all registered health checks."""
        results = []
        current_time = time.time()

        for name, check_info in self._checks.items():
            if current_time - check_info['last_run'] >= check_info['interval']:
                try:
                    result = check_info['func']()
                    if isinstance(result, HealthCheck):
                        check_result = result
                    else:
                        # Assume it's a status tuple (status, message, details)
                        status, message, details = result
                        check_result = HealthCheck(
                            name=name,
                            status=status,
                            message=message,
                            timestamp=datetime.now(),
                            details=details
                        )

                    self._last_results[name] = check_result
                    check_info['last_run'] = current_time
                    results.append(check_result)

                except Exception as e:
                    error_check = HealthCheck(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Health check failed: {str(e)}",
                        timestamp=datetime.now(),
                        details={'error': str(e)}
                    )
                    self._last_results[name] = error_check
                    results.append(error_check)
                    logger.error(f"Health check '{name}' failed: {e}")

        return results

    def get_health_status(self) -> HealthStatus:
        """Get overall system health status."""
        if not self._last_results:
            return HealthStatus.UNHEALTHY

        statuses = [check.status for check in self._last_results.values()]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def get_last_results(self) -> Dict[str, HealthCheck]:
        """Get the last results of all health checks."""
        return self._last_results.copy()


# Built-in health check functions

def check_system_resources() -> tuple:
    """Check system resource usage."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        status = HealthStatus.HEALTHY
        message = "System resources OK"
        details = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'disk_percent': disk.percent
        }

        # Check thresholds
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 95:
            status = HealthStatus.UNHEALTHY
            message = "System resources critically high"
        elif cpu_percent > 70 or memory.percent > 80 or disk.percent > 85:
            status = HealthStatus.DEGRADED
            message = "System resources elevated"

        return status, message, details

    except Exception as e:
        return HealthStatus.UNHEALTHY, f"System resource check failed: {e}", {'error': str(e)}


def check_network_connectivity() -> tuple:
    """Check network connectivity to critical services."""
    try:
        # Test connection to a reliable endpoint
        response = requests.get("https://www.google.com", timeout=5)
        if response.status_code == 200:
            return HealthStatus.HEALTHY, "Network connectivity OK", {'latency_ms': response.elapsed.total_seconds() * 1000}
        else:
            return HealthStatus.DEGRADED, f"Network response: {response.status_code}", {'status_code': response.status_code}
    except Exception as e:
        return HealthStatus.UNHEALTHY, f"Network connectivity failed: {e}", {'error': str(e)}


def check_database_connectivity() -> tuple:
    """Check database connectivity."""
    try:
        from src.persistence.database import get_database
        db = get_database()

        # Simple query to test connection
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            count = cursor.fetchone()[0]

        return HealthStatus.HEALTHY, "Database connectivity OK", {'trade_count': count}

    except Exception as e:
        return HealthStatus.UNHEALTHY, f"Database connectivity failed: {e}", {'error': str(e)}