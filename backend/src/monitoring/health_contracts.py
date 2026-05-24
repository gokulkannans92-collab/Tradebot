"""
Health Contracts Module

Defines health check interfaces and implementations for each subsystem.
Each subsystem implements a health check contract.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    component: str
    status: HealthStatus
    message: str
    timestamp: float
    details: Dict[str, Any]
    latency_ms: float


class HealthCheck(ABC):
    """Base class for health checks."""
    
    @abstractmethod
    def check(self) -> HealthCheckResult:
        """Perform health check."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Component name."""
        pass


class BrokerHealthCheck(HealthCheck):
    """Health check for broker connectivity."""
    
    def __init__(self, broker):
        self.broker = broker
    
    @property
    def name(self) -> str:
        return "broker"
    
    def check(self) -> HealthCheckResult:
        start = time.time()
        
        try:
            # Test basic connectivity
            quote = self.broker.get_quote("NIFTY")
            
            if quote and quote.get("last_price", 0) > 0:
                latency = (time.time() - start) * 1000
                return HealthCheckResult(
                    component=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Broker connected and responding",
                    timestamp=time.time(),
                    details={"last_quote": quote.get("last_price")},
                    latency_ms=latency
                )
            else:
                return HealthCheckResult(
                    component=self.name,
                    status=HealthStatus.DEGRADED,
                    message="Broker responding but no data",
                    timestamp=time.time(),
                    details={},
                    latency_ms=(time.time() - start) * 1000
                )
                
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Broker error: {str(e)}",
                timestamp=time.time(),
                details={"error": str(e)},
                latency_ms=(time.time() - start) * 1000
            )


class DatabaseHealthCheck(HealthCheck):
    """Health check for database connectivity."""
    
    def __init__(self, database):
        self.database = database
    
    @property
    def name(self) -> str:
        return "database"
    
    def check(self) -> HealthCheckResult:
        start = time.time()
        
        try:
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.HEALTHY,
                message="Database connected and responsive",
                timestamp=time.time(),
                details={},
                latency_ms=latency
            )
            
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                timestamp=time.time(),
                details={"error": str(e)},
                latency_ms=(time.time() - start) * 1000
            )


class WebSocketHealthCheck(HealthCheck):
    """Health check for WebSocket feed."""
    
    def __init__(self, ws_feed):
        self.ws_feed = ws_feed
    
    @property
    def name(self) -> str:
        return "websocket"
    
    def check(self) -> HealthCheckResult:
        start = time.time()
        
        try:
            if not hasattr(self.ws_feed, 'is_connected'):
                return HealthCheckResult(
                    component=self.name,
                    status=HealthStatus.UNKNOWN,
                    message="WebSocket feed not available",
                    timestamp=time.time(),
                    details={},
                    latency_ms=0
                )
            
            is_connected = self.ws_feed.is_connected
            
            if is_connected:
                # Check for recent ticks
                tick = self.ws_feed.get_tick("NIFTY 50")
                if tick:
                    return HealthCheckResult(
                        component=self.name,
                        status=HealthStatus.HEALTHY,
                        message="WebSocket connected and receiving data",
                        timestamp=time.time(),
                        details={"tick_age_ms": (time.time() - tick.get("_ts", 0)) * 1000},
                        latency_ms=(time.time() - start) * 1000
                    )
                else:
                    return HealthCheckResult(
                        component=self.name,
                        status=HealthStatus.DEGRADED,
                        message="Connected but no recent ticks",
                        timestamp=time.time(),
                        details={},
                        latency_ms=(time.time() - start) * 1000
                    )
            else:
                return HealthCheckResult(
                    component=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="WebSocket disconnected",
                    timestamp=time.time(),
                    details={},
                    latency_ms=(time.time() - start) * 1000
                )
                
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"WebSocket error: {str(e)}",
                timestamp=time.time(),
                details={"error": str(e)},
                latency_ms=(time.time() - start) * 1000
            )


class RiskManagerHealthCheck(HealthCheck):
    """Health check for risk manager."""
    
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
    
    @property
    def name(self) -> str:
        return "risk_manager"
    
    def check(self) -> HealthCheckResult:
        start = time.time()
        
        try:
            can_trade = self.risk_manager.can_trade()
            
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.HEALTHY if can_trade else HealthStatus.DEGRADED,
                message="Risk manager operational" if can_trade else "Risk limits reached",
                timestamp=time.time(),
                details={},
                latency_ms=(time.time() - start) * 1000
            )
            
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Risk manager error: {str(e)}",
                timestamp=time.time(),
                details={"error": str(e)},
                latency_ms=(time.time() - start) * 1000
            )


class HealthCheckRegistry:
    """Registry for all health checks."""
    
    def __init__(self):
        self._checks: Dict[str, HealthCheck] = {}
    
    def register(self, check: HealthCheck):
        """Register a health check."""
        self._checks[check.name] = check
    
    def check_all(self) -> List[HealthCheckResult]:
        """Run all health checks."""
        results = []
        for name, check in self._checks.items():
            try:
                result = check.check()
                results.append(result)
            except Exception as e:
                results.append(HealthCheckResult(
                    component=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(e)}",
                    timestamp=time.time(),
                    details={"error": str(e)},
                    latency_ms=0
                ))
        return results
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all health checks."""
        results = self.check_all()
        
        healthy = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
        degraded = sum(1 for r in results if r.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for r in results if r.status == HealthStatus.UNHEALTHY)
        
        return {
            "total": len(results),
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "overall": "unhealthy" if unhealthy > 0 else "degraded" if degraded > 0 else "healthy",
            "checks": [r.__dict__ for r in results]
        }


# Global health check registry
_health_registry: Optional[HealthCheckRegistry] = None


def get_health_registry() -> HealthCheckRegistry:
    """Get the global health check registry."""
    global _health_registry
    if _health_registry is None:
        _health_registry = HealthCheckRegistry()
    return _health_registry