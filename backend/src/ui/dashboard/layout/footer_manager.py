"""
Footer Manager

Manages the dashboard footer section including connection status and market status.
Extracted from dashboard_gui.py
"""

import tkinter as tk
import customtkinter as ctk
from datetime import datetime, time
from typing import Any, Optional

from src.ui.shared import COLORS
from src.config import Settings


class FooterManager:
    """
    Manages dashboard footer layout and status displays.
    
    Responsibilities:
    - Connection status indicator
    - Market status (open/closed)
    - System status messages
    """
    
    def __init__(self, parent: ctk.CTkFrame, controller: Any):
        """
        Initialize footer manager.
        
        Args:
            parent: Parent frame (footer_frame from main window)
            controller: Main TradeBotGUI instance for callbacks
        """
        self.parent = parent
        self.controller = controller
        
        self.connection_status: Optional[ctk.CTkLabel] = None
        self.market_status_label: Optional[ctk.CTkLabel] = None
        self.status_message: Optional[ctk.CTkLabel] = None
        
        self._setup_footer()
        self._start_status_updates()
    
    def _setup_footer(self):
        """Setup footer layout."""
        # Connection status (left)
        self.connection_status = ctk.CTkLabel(
            self.parent,
            text="🟢 Connected",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["accent_green"]
        )
        self.connection_status.pack(side=tk.LEFT, padx=15)
        
        # Market status (center-left)
        self.market_status_label = ctk.CTkLabel(
            self.parent,
            text="🟢 NSE: Open",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["accent_green"]
        )
        self.market_status_label.pack(side=tk.LEFT, padx=15)
        
        # System message (center)
        self.status_message = ctk.CTkLabel(
            self.parent,
            text="System Ready",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_dim"]
        )
        self.status_message.pack(side=tk.LEFT, expand=True)
        
        # Version info (right)
        version_label = ctk.CTkLabel(
            self.parent,
            text="v2.1.0",
            font=ctk.CTkFont(size=9),
            text_color=COLORS["text_dim"]
        )
        version_label.pack(side=tk.RIGHT, padx=15)
    
    def _start_status_updates(self):
        """Start periodic status updates."""
        self._update_market_status()
    
    def _update_market_status(self):
        """Update market open/closed status."""
        now = datetime.now().time()
        
        is_market_hours = (
            Settings.MARKET_OPEN <= now <= Settings.MARKET_CLOSE
        )
        
        if is_market_hours:
            self.market_status_label.configure(
                text="🟢 NSE: Open",
                text_color=COLORS["accent_green"]
            )
        else:
            self.market_status_label.configure(
                text="🔴 NSE: Closed",
                text_color=COLORS["accent_red"]
            )
        
        # Schedule next update (every 30 seconds)
        self.controller.after(30000, self._update_market_status)
    
    def set_connection_status(self, connected: bool, message: str = ""):
        """
        Update connection status display.
        
        Args:
            connected: Whether connection is active
            message: Optional status message
        """
        if connected:
            self.connection_status.configure(
                text=f"🟢 {message or 'Connected'}",
                text_color=COLORS["accent_green"]
            )
        else:
            self.connection_status.configure(
                text=f"🔴 {message or 'Disconnected'}",
                text_color=COLORS["accent_red"]
            )
    
    def set_status_message(self, message: str, error: bool = False):
        """
        Update status message.
        
        Args:
            message: Status message to display
            error: If True, show in red
        """
        color = COLORS["accent_red"] if error else COLORS["text_dim"]
        self.status_message.configure(text=message, text_color=color)
