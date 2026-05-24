"""
Layout Components

Provides reusable layout components:
- Header: Top application bar
- Footer: Status bar at bottom
- Sidebar: Side navigation panels
"""

import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable, List
from src.ui.shared import COLORS


class Header(ctk.CTkFrame):
    """Application header bar with title, navigation, and actions."""
    
    def __init__(self, master, title: str = "TradeBot", 
                 on_navigate: Optional[Callable[[str], None]] = None,
                 **kwargs):
        super().__init__(master, **kwargs)
        
        self.title_text = title
        self.on_navigate = on_navigate
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup header UI components."""
        self.configure(fg_color=COLORS["bg_card"], height=50)
        
        # Left section - Logo/Title
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side=tk.LEFT, padx=15, fill=tk.Y)
        
        self.logo_label = ctk.CTkLabel(
            left, 
            text=f"🤖 {self.title_text}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        self.logo_label.pack(side=tk.LEFT, pady=10)
        
        # Center section - Navigation tabs (placeholder)
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(side=tk.LEFT, padx=20, fill=tk.Y, expand=True)
        
        # Right section - Actions
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side=tk.RIGHT, padx=15, fill=tk.Y)
        
        self.refresh_btn = ctk.CTkButton(
            right,
            text="🔄",
            width=35,
            height=35,
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            font=ctk.CTkFont(size=14)
        )
        self.refresh_btn.pack(side=tk.RIGHT, padx=5)
    
    def add_nav_button(self, text: str, command: Callable):
        """Add a navigation button to the header."""
        btn = ctk.CTkButton(
            self.nav_frame,
            text=text,
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            font=ctk.CTkFont(size=12),
            command=command
        )
        btn.pack(side=tk.LEFT, padx=5)
        return btn
    
    def set_title(self, title: str):
        """Update header title."""
        self.logo_label.configure(text=f"🤖 {title}")


class Footer(ctk.CTkFrame):
    """Status bar footer with connection info and market status."""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup footer UI components."""
        self.configure(fg_color=COLORS["bg_card"], height=28)
        
        # Connection status
        self.connection_status = ctk.CTkLabel(
            self,
            text="🟢 Connected",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["accent_green"]
        )
        self.connection_status.pack(side=tk.LEFT, padx=15)
        
        # Market status
        self.market_status = ctk.CTkLabel(
            self,
            text="🟢 NSE: Open",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["accent_green"]
        )
        self.market_status.pack(side=tk.LEFT, padx=10)
        
        # Version info (right aligned)
        self.version_label = ctk.CTkLabel(
            self,
            text="v2.0",
            font=ctk.CTkFont(size=9),
            text_color=COLORS["text_dim"]
        )
        self.version_label.pack(side=tk.RIGHT, padx=15)
    
    def set_connection_status(self, connected: bool, message: str = ""):
        """Update connection status indicator."""
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
    
    def set_market_status(self, is_open: bool):
        """Update market status indicator."""
        if is_open:
            self.market_status.configure(
                text="🟢 NSE: Open",
                text_color=COLORS["accent_green"]
            )
        else:
            self.market_status.configure(
                text="🔴 NSE: Closed",
                text_color=COLORS["accent_red"]
            )


class Sidebar(ctk.CTkFrame):
    """Collapsible sidebar with navigation and controls."""
    
    def __init__(self, master, width: int = 270, 
                 on_toggle: Optional[Callable[[bool], None]] = None,
                 **kwargs):
        super().__init__(master, width=width, **kwargs)
        
        self.sidebar_width = width
        self.collapsed_width = 60
        self.is_collapsed = False
        self.on_toggle = on_toggle
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup sidebar UI components."""
        self.configure(
            fg_color=COLORS["bg_panel"],
            border_width=1,
            border_color=COLORS["border"]
        )
        
        # Toggle button at top
        self.toggle_btn = ctk.CTkButton(
            self,
            text="◀",
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            command=self._toggle
        )
        self.toggle_btn.pack(anchor="ne", padx=5, pady=5)
        
        # Navigation buttons container
        self.nav_container = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.nav_buttons: List[ctk.CTkButton] = []
    
    def add_nav_button(self, icon: str, text: str, command: Callable) -> ctk.CTkButton:
        """Add a navigation button to the sidebar."""
        btn = ctk.CTkButton(
            self.nav_container,
            text=f"{icon} {text}" if not self.is_collapsed else icon,
            anchor="w",
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            font=ctk.CTkFont(size=12),
            command=command
        )
        btn.pack(fill=tk.X, pady=2)
        self.nav_buttons.append(btn)
        return btn
    
    def _toggle(self):
        """Toggle sidebar collapse/expand."""
        self.is_collapsed = not self.is_collapsed
        
        if self.is_collapsed:
            self.configure(width=self.collapsed_width)
            self.toggle_btn.configure(text="▶")
            # Update all nav buttons to show only icons
            for btn in self.nav_buttons:
                text = btn.cget("text")
                # Extract icon (first emoji character)
                icon = text.split()[0] if text else "•"
                btn.configure(text=icon)
        else:
            self.configure(width=self.sidebar_width)
            self.toggle_btn.configure(text="◀")
            # Restore full text on buttons would require storing original text
        
        if self.on_toggle:
            self.on_toggle(self.is_collapsed)
    
    def collapse(self):
        """Collapse sidebar to minimal width."""
        if not self.is_collapsed:
            self._toggle()
    
    def expand(self):
        """Expand sidebar to full width."""
        if self.is_collapsed:
            self._toggle()


class ResponsiveContainer(ctk.CTkFrame):
    """Container that adapts its layout based on available space."""
    
    def __init__(self, master, min_width: int = 800, **kwargs):
        super().__init__(master, **kwargs)
        
        self.min_width = min_width
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup responsive container."""
        self.configure(fg_color="transparent")
        
        # Bind to resize events
        self.bind("<Configure>", self._on_resize)
    
    def _on_resize(self, event):
        """Handle resize events to adjust layout."""
        width = event.width
        
        # Could implement responsive layout changes here
        # e.g., switch from horizontal to vertical layout
        pass


# Convenience function to create standard layout
def create_standard_layout(parent, title: str = "TradeBot"):
    """
    Create a standard application layout with header, sidebar, content area, and footer.
    
    Returns:
        Dict with references to all layout components
    """
    # Configure grid
    parent.grid_columnconfigure(0, weight=0)  # Sidebar
    parent.grid_columnconfigure(1, weight=1)  # Content
    parent.grid_rowconfigure(0, weight=0)  # Header
    parent.grid_rowconfigure(1, weight=1)  # Main content
    parent.grid_rowconfigure(2, weight=0)  # Footer
    
    # Header
    header = Header(parent, title=title)
    header.grid(row=0, column=0, columnspan=2, sticky="ew")
    
    # Sidebar
    sidebar = Sidebar(parent)
    sidebar.grid(row=1, column=0, sticky="ns")
    
    # Content area placeholder
    content = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"])
    content.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
    
    # Footer
    footer = Footer(parent)
    footer.grid(row=2, column=0, columnspan=2, sticky="ew")
    
    return {
        "header": header,
        "sidebar": sidebar,
        "content": content,
        "footer": footer
    }
