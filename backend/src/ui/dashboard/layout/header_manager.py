"""
Header Manager

Manages the dashboard header section including logo, tabs, and user controls.
Extracted from dashboard_gui.py
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional, Dict, Any

from src.ui.shared import COLORS


class HeaderManager:
    """
    Manages dashboard header layout and controls.
    
    Responsibilities:
    - Logo and branding
    - Tab navigation buttons
    - User info display
    - Tooltip buttons
    """
    
    def __init__(self, parent: ctk.CTkFrame, controller: Any):
        """
        Initialize header manager.
        
        Args:
            parent: Parent frame (header_frame from main window)
            controller: Main TradeBotGUI instance for callbacks
        """
        self.parent = parent
        self.controller = controller
        self.current_tab: str = "Overview"
        
        self._setup_header()
    
    def _setup_header(self):
        """Setup header layout."""
        # Left section - Logo
        left = ctk.CTkFrame(self.parent, fg_color="transparent")
        left.pack(side=tk.LEFT, padx=15, fill=tk.Y)
        
        # Logo
        logo_frame = ctk.CTkFrame(left, fg_color="transparent")
        logo_frame.pack(side=tk.LEFT, padx=(0, 15))
        
        ctk.CTkLabel(
            logo_frame,
            text="📊",
            font=ctk.CTkFont(size=20)
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            logo_frame,
            text="TradeBot",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(side=tk.LEFT, padx=(5, 0))
        
        ctk.CTkLabel(
            logo_frame,
            text="Pro",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["accent_blue"]
        ).pack(side=tk.LEFT, padx=(2, 0))
        
        # Right section - User controls (tab buttons removed - using right sidebar nav)
        right = ctk.CTkFrame(self.parent, fg_color="transparent")
        right.pack(side=tk.RIGHT, padx=15, fill=tk.Y)
        
        # Help button
        self._create_tooltip_btn(
            right, "❓", "Help & Documentation",
            self.controller._show_help
        ).pack(side=tk.LEFT, padx=2)
        
        # Settings button
        self._create_tooltip_btn(
            right, "⚙️", "Quick Settings",
            self.controller._show_quick_settings
        ).pack(side=tk.LEFT, padx=2)
        
        # Lock button
        self._create_tooltip_btn(
            right, "🔒", "Lock Workstation",
            self.controller._lock_dashboard
        ).pack(side=tk.LEFT, padx=2)
        
        # Logout button
        self._create_tooltip_btn(
            right, "🚪", "Logout",
            self.controller._logout
        ).pack(side=tk.LEFT, padx=2)
        
        # User info
        user_frame = ctk.CTkFrame(right, fg_color="transparent")
        user_frame.pack(side=tk.LEFT, padx=(10, 0))
        
        ctk.CTkLabel(
            user_frame,
            text="👤",
            font=ctk.CTkFont(size=13)
        ).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkLabel(
            user_frame,
            text=self.controller.current_user_name,
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side=tk.LEFT)
    
    def _create_tooltip_btn(self, parent: ctk.CTkFrame, icon: str, tooltip: str, command: Callable):
        """Create a button with tooltip."""
        btn = ctk.CTkButton(
            parent,
            text=icon,
            width=35,
            height=35,
            fg_color=COLORS["border"],
            command=command
        )
        btn._tooltip = tooltip
        return btn
    
    def set_active_tab(self, name: str):
        """Set active tab (header tabs removed - using right sidebar nav)."""
        # Header tab buttons removed - navigation handled by right sidebar
        self.current_tab = name
    
    def update_user_name(self, name: str):
        """Update displayed user name."""
        self.controller.current_user_name = name
        # Refresh header would go here
