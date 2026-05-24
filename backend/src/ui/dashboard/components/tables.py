"""
Premium Dashboard Tables - Strictly Aligned & High Performance
══════════════════════════════════════════════════════════════
A high-fidelity table implementation for Python/CustomTkinter.
Supports sticky headers, zebra striping, and pixel-perfect grid alignment.
"""

import tkinter as tk
import customtkinter as ctk
from typing import List, Dict, Any, Optional, Callable
from src.ui.shared import COLORS

class PremiumTable(ctk.CTkFrame):
    """
    A high-performance table with sticky headers, zebra striping, 
    and proportional column weights using a strictly synchronized grid.
    """
    def __init__(self, master, columns: List[str], weights: List[float] = None, 
                 height: int = 400, on_select: Optional[Callable] = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.columns = columns
        self.weights = weights if weights else [1.0] * len(columns)
        self.on_select = on_select
        self.rows: List[ctk.CTkFrame] = []
        self.selected_row = None
        self.selected_index = -1
        
        # UI State
        self.row_height = 32 # Ultra-high data density
        self.header_height = 32
        
        self._setup_layout()
        
    def _setup_layout(self):
        """Create the rigid 2-layer grid structure."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # 1. HEADER (Pinned)
        self.header_frame = ctk.CTkFrame(self, fg_color="#0f172a", height=self.header_height, corner_radius=8)
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.header_frame.grid_propagate(False)
        
        # Configure Header Grid
        for i, (col, weight) in enumerate(zip(self.columns, self.weights)):
            self.header_frame.grid_columnconfigure(i, weight=int(weight * 100))
            lbl = ctk.CTkLabel(
                self.header_frame, text=col.upper(),
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLORS["accent_blue"],
                anchor=self._get_anchor(i, col)
            )
            lbl.grid(row=0, column=i, sticky="nsew", padx=12)
            
        # 2. SCROLLABLE BODY
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", 
            corner_radius=0, 
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_blue"]
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    def add_row(self, values: List[Any], tags: List[str] = None):
        """Add a row that perfectly mirrors the header grid configuration."""
        row_idx = len(self.rows)
        bg_color = "#0f172a" if row_idx % 2 == 0 else "#1e293b" # Zebra striping
        
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color, height=self.row_height, corner_radius=6)
        row_frame.pack(fill=tk.X, pady=2)
        row_frame.grid_propagate(False)
        
        # Internal Alignment
        for i, (val, weight) in enumerate(zip(values, self.weights)):
            row_frame.grid_columnconfigure(i, weight=int(weight * 100))
            
            # Color logic
            text_col = COLORS["text_main"]
            val_str = str(val).lower()
            if 'rs' in val_str:
                if '+' in val_str: text_col = COLORS["accent_green"]
                elif '-' in val_str: text_col = COLORS["accent_red"]
            elif '%' in val_str:
                if '+' in val_str: text_col = COLORS["accent_green"]
                elif '-' in val_str: text_col = COLORS["accent_red"]
            
            lbl = ctk.CTkLabel(
                row_frame, text=str(val),
                font=ctk.CTkFont(size=10), # Ultra-compact font
                text_color=text_col,
                anchor=self._get_anchor(i, str(val))
            )
            lbl.grid(row=0, column=i, sticky="nsew", padx=12)
            
            # Click events
            lbl.bind("<Button-1>", lambda e, r=row_frame, i=row_idx, v=values: self._on_row_click(r, i, v))
        
        row_frame.bind("<Button-1>", lambda e, r=row_frame, i=row_idx, v=values: self._on_row_click(r, i, v))
        self.rows.append(row_frame)

    def _on_row_click(self, frame, index, values):
        """Handle selection highlighting."""
        # Deselect old
        if self.selected_row:
            prev_bg = "#0f172a" if self.selected_index % 2 == 0 else "#1e293b"
            self.selected_row.configure(fg_color=prev_bg, border_width=0)
            
        # Select new
        self.selected_row = frame
        self.selected_index = index
        self.selected_row.configure(fg_color="#1d4ed8", border_width=1, border_color="#3b82f6") # Premium blue highlight
        
        if self.on_select:
            self.on_select(values)

    def _get_anchor(self, index, text):
        """Context-aware alignment for trading data."""
        text_clean = str(text).upper()
        # Financial/Technical data should be centered
        center_keywords = ['RS', '%', '+', '-', 'QTY', 'PRICE', 'EXIT', 'ENTRY', 'P&L', 'RETURNS']
        if any(x in text_clean for x in center_keywords):
            return tk.CENTER
        return tk.W # Left for Symbol, Side, Date

    def clear(self):
        """Performance optimized clear."""
        for row in self.rows:
            row.destroy()
        self.rows.clear()
        self.selected_row = None
        self.selected_index = -1
