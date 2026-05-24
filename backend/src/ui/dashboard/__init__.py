"""
TradeBot Dashboard Module
=====================

Architecture:
- config.py          - Configuration constants (timing, UI settings)
- constants.py       - File paths
- data_manager.py    - Centralized data handling with caching
- view_factory.py   - View creation factory
- plugin_system.py - Strategy plugin system
- config_validator.py - Pydantic config validation
- dashboard_gui    - Main GUI class (must be imported directly)

Import example:
    from src.ui.dashboard_gui import TradeBotGUI
    
    # Or use the new modules:
    from src.ui.dashboard.data_manager import get_data_manager
    from src.ui.dashboard.view_factory import get_view_factory
    from src.ui.dashboard.plugin_system import get_plugin_manager
"""

__version__ = '1.0.0'