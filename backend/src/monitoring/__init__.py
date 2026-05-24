"""
Monitoring Module

Provides real-time monitoring, health checks, and alerting for TradeBot.
"""

import logging
import time
import threading
import psutil
import os
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthStatus(Enum):
    """System health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    """Represents a health check result."""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


@dataclass
class Alert:
    """Represents an alert notification."""
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class Metric:
    """Represents a performance metric."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Optional[Dict[str, str]] = None


# Import main classes for easy access
from .health_checker import HealthChecker
from .alert_manager import AlertManager
from .metrics_collector import MetricsCollector
from .monitoring_service import MonitoringService, get_monitoring_service, start_monitoring, stop_monitoring

__all__ = [
    'AlertLevel',
    'HealthStatus',
    'HealthCheck',
    'Alert',
    'Metric',
    'HealthChecker',
    'AlertManager',
    'MetricsCollector',
    'MonitoringService',
    'get_monitoring_service',
    'start_monitoring',
    'stop_monitoring'
]