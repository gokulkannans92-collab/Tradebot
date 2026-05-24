"""
Dashboard Layout Managers

Split from dashboard_gui.py to reduce monolithic structure.
"""

from .header_manager import HeaderManager
from .footer_manager import FooterManager
from .sidebar_manager import SidebarManager, RightSidebarManager

__all__ = [
    'HeaderManager',
    'FooterManager',
    'SidebarManager',
    'RightSidebarManager',
]
