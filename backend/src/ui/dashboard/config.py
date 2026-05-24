"""
Constants and configuration for TradeBot Dashboard
Extracted from dashboard_gui.py for better maintainability
"""

# Timing constants (in milliseconds)
REFRESH_INTERVAL_MS = 30000      # Main data refresh (30s)
STATUS_CHECK_MS = 2000            # Status loop check (2s)
TABLE_REFRESH_MS = 5000            # Table refresh (5s)
CHART_REFRESH_MS = 60000          # Chart refresh (60s)

# Application metadata
APP_NAME = "TradeBot Dashboard"
APP_VERSION = "1.0.0"
APP_GEOMETRY = "1400x900"

# UI Constants
SIDEBAR_WIDTH = 200
HEADER_HEIGHT = 65
FOOTER_HEIGHT = 28

# Treeview columns for different views
OVERVIEW_COLS = ("Symbol", "Side", "Qty", "Entry", "LTP", "P&L", "SL", "Target")
TRADES_COLS = ("Time", "Symbol", "Side", "Qty", "Entry", "LTP", "P&L", "SL", "Target", "Status")

# Period options
PERIOD_OPTIONS = ["All", "Today", "Yesterday", "This Week", "This Month", "Past Week", "Past Month"]

# Default values
DEFAULT_PERIOD = "Today"
DEFAULT_SEARCH = ""
MAX_TRADES_PER_DAY = 5