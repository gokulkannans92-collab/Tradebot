"""
Dashboard UI Components

Reusable UI components for the TradeBot dashboard.
Extracted from src/dashboard/__init__.py as part of Phase 1 modularization.
"""

from .charts import (
    CandlestickChart,
    LineChart,
    PieChart,
    StatCard,
    ThemeToggle,
    TVLiveAreaChart  # Alias for backwards compatibility
)

from .layout import (
    Header,
    Footer,
    Sidebar,
    ResponsiveContainer,
    create_standard_layout
)

__all__ = [
    # Charts
    'CandlestickChart',
    'LineChart',
    'PieChart',
    'StatCard',
    'ThemeToggle',
    'TVLiveAreaChart',
    # Layout
    'Header',
    'Footer',
    'Sidebar',
    'ResponsiveContainer',
    'create_standard_layout',
]
