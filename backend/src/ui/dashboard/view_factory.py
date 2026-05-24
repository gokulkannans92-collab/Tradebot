"""
ViewFactory - Factory for creating UI views
================================
Centralized view creation to eliminate duplicate code.
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import ttk as ttk_orig

from src.ui.shared import COLORS, IS_DARK
from src.ui.dashboard.config import OVERVIEW_COLS, TRADES_COLS
from src.dashboard import StatCard


class ViewFactory:
    """
    Factory for creating consistent UI views.
    Use this instead of inline view creation code.
    """
    
    @staticmethod
    def create_stat_card(parent, title: str, value: str, icon: str = "📊", 
                    color: str = None, width: int = None) -> StatCard:
        """Create a standardized stat card."""
        card = StatCard(parent, title, value, icon, color)
        if width:
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        return card
    
    @staticmethod
    def create_treeview(parent, columns: tuple, style: str = "Custom.Treeview",
                   height: int = 0) -> ttk_orig.Treeview:
        """Create a standardized treeview."""
        tree = ttk_orig.Treeview(
            parent, 
            columns=columns, 
            show='headings',
            style=style,
            height=height
        )
        
        # Configure columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=80, anchor=tk.CENTER)
        
        return tree
    
    @staticmethod
    def create_filter_bar(parent, callback=None) -> tuple:
        """
        Create a standard filter bar with period dropdown and search.
        
        Returns:
            (filter_frame, period_var, search_entry)
        """
        filter_frame = ctk.CTkFrame(parent, fg_color="transparent")
        filter_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Period dropdown
        ctk.CTkLabel(filter_frame, text="Period:", font=ctk.CTkFont(size=11)).pack(side=tk.LEFT, padx=5)
        period_var = tk.StringVar(value="Today")
        period_menu = ctk.CTkOptionMenu(
            filter_frame, 
            values=["All", "Today", "Yesterday", "This Week", "This Month"],
            variable=period_var,
            width=110
        )
        if callback:
            period_menu.configure(command=lambda x: callback())
        period_menu.pack(side=tk.LEFT, padx=5)
        
        # Search entry
        ctk.CTkLabel(filter_frame, text="Search:", font=ctk.CTkFont(size=11)).pack(side=tk.LEFT, padx=(20, 5))
        search_entry = ctk.CTkEntry(filter_frame, width=180)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        return filter_frame, period_var, search_entry
    
    @staticmethod
    def create_action_bar(parent, buttons: list) -> ctk.CTkFrame:
        """
        Create a standard action bar.
        
        Args:
            buttons: List of (text, command, width, color) tuples
            
        Returns:
            CTkFrame containing the buttons
        """
        action_bar = ctk.CTkFrame(parent, fg_color="transparent")
        action_bar.pack(side=tk.RIGHT)
        
        for btn_spec in buttons:
            text = btn_spec[0]
            command = btn_spec[1]
            width = btn_spec[2] if len(btn_spec) > 2 else 80
            color = btn_spec[3] if len(btn_spec) > 3 else None
            
            btn = ctk.CTkButton(action_bar, text=text, width=width, command=command)
            if color:
                btn.configure(fg_color=color)
            btn.pack(side=tk.LEFT, padx=3)
        
        return action_bar
    
    @staticmethod
    def create_card(parent, title: str, icon: str = "📋") -> tuple:
        """
        Create a titled card frame.
        
        Returns:
            (frame, label)
        """
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_panel"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        label = ctk.CTkLabel(
            frame, 
            text=f"{icon} {title}", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        return frame, label
    
    @staticmethod
    def create_header(parent, title: str, icon: str = "") -> ctk.CTkLabel:
        """Create a standard section header."""
        text = f"{icon} {title}".strip()
        return ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["accent_blue"]
        )


# Singleton-like accessor
_view_factory = None

def get_view_factory() -> ViewFactory:
    """Get the ViewFactory instance."""
    global _view_factory
    if _view_factory is None:
        _view_factory = ViewFactory()
    return _view_factory