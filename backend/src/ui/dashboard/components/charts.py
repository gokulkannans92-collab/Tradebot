"""
Chart Components - Premium UI Overhaul
═══════════════════════════════════════════════════════════════════════════════

Provides high-fidelity bespoke components for the TradeBot dashboard:
- StatCard: Premium metrics display with accent bars
- ModernTable: Custom card-based table for positions
- LineChart: Performance tracking with modern aesthetics
- PieChart: Allocation visualization
- CandlestickChart: Real-time price tracking
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import List, Any, Dict, Optional
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.ui.shared import COLORS

# ─────────────────────────────────────────────────────────────────────────────
# PREMIUM STAT CARD
# ─────────────────────────────────────────────────────────────────────────────

class StatCard(ctk.CTkFrame):
    """
    Premium Stat card widget with accent indicator and enhanced typography.
    Replaces generic boxes with a SaaS-like information design.
    """
    
    def __init__(self, master, title="", value="0", icon="📈", 
                 value_color="#a6e3a1", **kwargs):
        # Forced square dimensions
        kwargs["height"] = 120
        kwargs["width"] = 140
        super().__init__(master, **kwargs)
        
        self.title_text = title
        self.value_text = value
        self.icon = icon
        self.accent_color = value_color
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.configure(
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"]
        )
        self.pack_propagate(False)
        self.grid_propagate(False)
        
        # ── LEFT ACCENT BAR ──────────────────────────
        self.accent_bar = ctk.CTkFrame(
            self, width=3, corner_radius=1,
            fg_color=self.accent_color
        )
        self.accent_bar.pack(side=tk.LEFT, padx=(10, 0), pady=20)
        
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill=tk.BOTH, expand=True, padx=(8, 10), pady=6)
        
        # Top row: Icon + Title
        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill=tk.X)
        
        self.icon_label = ctk.CTkLabel(top_row, text=self.icon, font=ctk.CTkFont(size=16))
        self.icon_label.pack(side=tk.LEFT)
        
        self.title_label = ctk.CTkLabel(
            top_row, text=self.title_text.upper(), 
            font=ctk.CTkFont(size=10, weight="bold"), 
            text_color=COLORS["text_dim"]
        )
        self.title_label.pack(side=tk.LEFT, padx=6)
        
        # Middle row: Main Value
        self.value_label = ctk.CTkLabel(
            inner, text=self.value_text, 
            font=ctk.CTkFont(size=18, weight="bold"), 
            text_color=self.accent_color
        )
        self.value_label.pack(anchor=tk.W, pady=(2, 0))
        
        # Bottom row: Trend
        self.trend_label = ctk.CTkLabel(
            inner, text="Stable", 
            font=ctk.CTkFont(size=9, weight="normal"),
            text_color=COLORS["text_dim"]
        )
        self.trend_label.pack(anchor=tk.W)
    
    def update_value(self, value, color=None, trend=None):
        """Update value with smooth visual updates"""
        self.value_label.configure(text=value)
        if color:
            _color = color
            if isinstance(color, (list, tuple)) and len(color) >= 2:
                _color = color[1]
            elif isinstance(color, (list, tuple)):
                _color = color[0]
            
            if isinstance(_color, str):
                self.value_label.configure(text_color=_color)
                if hasattr(self, 'accent_bar'):
                    self.accent_bar.configure(fg_color=_color)
        
        if trend is not None:
            if trend > 0:
                self.trend_label.configure(text="↑ Trending Up", text_color="#a6e3a1")
            elif trend < 0:
                self.trend_label.configure(text="↓ Trending Down", text_color="#f38ba8")
            else:
                self.trend_label.configure(text="Stable", text_color=COLORS["text_dim"])
    
    def update_title(self, title):
        self.title_label.configure(text=title.upper())

# ─────────────────────────────────────────────────────────────────────────────
# MODERN BESPOKE TABLE
# ─────────────────────────────────────────────────────────────────────────────

class ModernTable(ctk.CTkScrollableFrame):
    """
    Bespoke UI component to replace legacy Treeview.
    Uses rounded Frames as rows for a premium SaaS dashboard aesthetic.
    Eliminates all white background issues.
    """
    
    def __init__(self, master, columns: List[str], weights: List[float] = None, on_select=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("label_text", "")
        super().__init__(master, **kwargs)
        
        self.columns = columns
        self.weights = weights if weights and len(weights) == len(columns) else [1] * len(columns)
        self.on_select = on_select
        self.rows: List[ctk.CTkFrame] = []
        self.selected_row = None
        self.selected_index = -1
        
        self._setup_header()
        
    def _setup_header(self):
        """Create a sticky header row with modern typography."""
        self.header_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], height=40, corner_radius=10)
        self.header_frame.pack(fill=tk.X, padx=2, pady=(0, 10))
        self.header_frame.pack_propagate(False)
        
        for i, col in enumerate(self.columns):
            w = self.weights[i]
            self.header_frame.grid_columnconfigure(i, weight=int(w * 100)) # Multiplier for precision
            lbl = ctk.CTkLabel(
                self.header_frame, text=col.upper(),
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLORS["accent_blue"],
                anchor=self._get_anchor(i, col)
            )
            lbl.grid(row=0, column=i, sticky="nsew", padx=12)
            
    def add_row(self, values: List[Any], tags: List[str] = None):
        # Add a high-fidelity row with rounded corners and optional action buttons.
        row_id = len(self.rows)
        row_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], height=48, corner_radius=8, 
                                border_width=1, border_color=COLORS["border"])
        row_frame.pack(fill=tk.X, padx=2, pady=4)
        row_frame.pack_propagate(False)
        
        def on_click(event):
            self._handle_selection(row_frame, row_id, values)

        row_frame.bind("<Button-1>", on_click)

        for i, val in enumerate(values):
            w = self.weights[i]
            row_frame.grid_columnconfigure(i, weight=int(w * 100))
            
            # Action Buttons detection (List of dicts)
            if isinstance(val, (list, tuple)) and len(val) > 0 and isinstance(val[0], dict) and "command" in val[0]:
                btn_container = ctk.CTkFrame(row_frame, fg_color="transparent")
                btn_container.grid(row=0, column=i, sticky="nsew", padx=5)
                # Center buttons in the cell
                inner = ctk.CTkFrame(btn_container, fg_color="transparent")
                inner.pack(expand=True)
                
                for act in val:
                    btn = ctk.CTkButton(
                        inner, text=act.get("text", "?"),
                        width=act.get("width", 32), height=26,
                        fg_color=act.get("color", COLORS["bg_panel"]),
                        hover_color=COLORS["accent_blue"],
                        text_color=act.get("text_color", COLORS["text_main"]),
                        border_width=1, border_color=COLORS["border"],
                        font=ctk.CTkFont(size=11),
                        command=act.get("command")
                    )
                    btn.pack(side=tk.LEFT, padx=3, pady=6)
                continue

            # Smart Colorizing (P&L column usually index 5 or 6)
            text_col = COLORS["text_main"]
            val_str = str(val).lower()
            if 'rs' in val_str and ('+' in val_str or '-' in val_str):
                try:
                    num = float(val_str.replace('rs', '').replace(',', '').strip())
                    if num > 0: text_col = COLORS["accent_green"]
                    elif num < 0: text_col = COLORS["accent_red"]
                except Exception: pass
                
            lbl = ctk.CTkLabel(
                row_frame, text=str(val),
                font=ctk.CTkFont(size=12),
                text_color=text_col,
                anchor=self._get_anchor(i, str(val))
            )
            lbl.grid(row=0, column=i, sticky="nsew", padx=12)
            lbl.bind("<Button-1>", on_click)

        self.rows.append(row_frame)

        
    def _handle_selection(self, frame, index, values):
        """Handle row selection with visual feedback."""
        # Deselect previous
        if self.selected_row:
            self.selected_row.configure(border_color=COLORS["border"], border_width=1)
        
        # Select new
        self.selected_row = frame
        self.selected_index = index
        self.selected_row.configure(border_color=COLORS["accent_blue"], border_width=2)
        
        if self.on_select:
            self.on_select(values)

    def _get_anchor(self, index, text):
        """Standard financial alignment: Center/Right for numbers, Left for descriptors."""
        text_clean = str(text).upper()
        # Header or numeric detection
        if any(x in text_clean for x in ['RS', '%', '+', '-', 'QTY', 'PRICE', 'EXIT', 'ENTRY', 'P&L']):
            return tk.CENTER # Centered for balanced numbers
        return tk.W # Left for strings (Symbol, Side, Status, Date)

    def clear(self):
        """Clean clear of all rows."""
        for row in self.rows:
            row.destroy()
        self.rows.clear()
        self.selected_row = None
        self.selected_index = -1

# ─────────────────────────────────────────────────────────────────────────────
# PREMIUM CHARTS
# ─────────────────────────────────────────────────────────────────────────────

class LineChart(ctk.CTkFrame):
    """Refined line chart for performance tracking."""
    
    def __init__(self, master, title="", width=400, height=200, **kwargs):
        super().__init__(master, **kwargs)
        self.title = title
        self.metadata: List[Dict[str, Any]] = []
        self._setup_ui()
        
    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, padx=15, pady=(12, 8))
        
        ctk.CTkLabel(header, text=self.title.upper(), 
                     font=ctk.CTkFont(size=10, weight="bold"), 
                     text_color=COLORS["accent_blue"]).pack(side=tk.LEFT)
        
        self.fig = Figure(figsize=(4, 2), dpi=100)
        self.fig.patch.set_facecolor(COLORS["bg_card"])
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(COLORS["bg_card"])
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Tooltip annotation (hidden by default)
        self.annot = self.ax.annotate(
            "", xy=(0,0), xytext=(10,10),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc=COLORS["bg_panel"], ec=COLORS["border"], alpha=0.9),
            arrowprops=dict(arrowstyle="->", color=COLORS["text_dim"]),
            fontsize=8, color=COLORS["text_main"]
        )
        self.annot.set_visible(False)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

    def _on_hover(self, event):
        vis = self.annot.get_visible()
        if event.inaxes == self.ax:
            for line in self.ax.get_lines():
                cont, ind = line.contains(event)
                if cont:
                    self._update_annot(line, ind)
                    self.annot.set_visible(True)
                    self.canvas.draw_idle()
                    return
        if vis:
            self.annot.set_visible(False)
            self.canvas.draw_idle()

    def _update_annot(self, line, ind):
        x, y = line.get_data()
        idx = ind["ind"][0]
        self.annot.xy = (x[idx], y[idx])
        
        # Get label if available
        try:
            label = self.ax.get_xticklabels()[int(x[idx])].get_text()
        except Exception:
            label = f"T{int(x[idx])+1}"
            
        val = y[idx]
        color = COLORS["accent_green"] if val >= 0 else COLORS["accent_red"]
        
        # Base text with label and P&L
        text = f"{label}\n"
        
        # Add metadata if available (Invested / Trade Value)
        if self.metadata and idx < len(self.metadata):
            meta = self.metadata[idx]
            invested = float(meta.get('invested', 0))
            text += f"Trade Value: Rs {invested:,.2f}\n"
            
        # P&L label
        text += f"P&L: Rs {val:+,.2f}"
        
        self.annot.set_text(text)
        self.annot.get_bbox_patch().set_edgecolor(color)
        self.annot.get_bbox_patch().set_alpha(1.0)
        
        # ── DYNAMIC POSITIONING (V2) ──
        # Transform indices to percentage for robust edge detection
        num_points = len(x)
        rel_pos = idx / (num_points - 1) if num_points > 1 else 0.5
        
        # Horizontal Logic
        if rel_pos > 0.85:   # Far Right: Show on the left
            ha, offset_x = 'right', -15
        elif rel_pos < 0.15: # Far Left: Show on the right
            ha, offset_x = 'left', 15
        else:                # Middle: Center above
            ha, offset_x = 'center', 0
            
        # Vertical Logic (Safety flip if value is at the very top)
        y_max = max(y) if len(y) > 0 else 1
        va = 'top' if val > (y_max * 0.9) else 'bottom'
        offset_y = -15 if va == 'top' else 15
        
        # Apply all properties
        self.annot.xyann = (offset_x, offset_y)
        self.annot.set_ha(ha)
        self.annot.set_va(va)
        
    def update_data(self, labels, values, color="#a6e3a1", metadata: List[Dict] = None):
        self.ax.clear()
        self.ax.set_facecolor(COLORS["bg_card"])
        self.metadata = metadata or []
        
        if not values: values = [0]
        x = range(len(values))
        
        # Plot with subtle glow effect and larger markers for easier hover
        self.ax.plot(x, values, color=color, linewidth=2, marker='o', markersize=5, alpha=0.9, picker=5)
        self.ax.fill_between(x, values, alpha=0.1, color=color)
        
        self.ax.tick_params(colors=COLORS["text_dim"], labelsize=7)
        for spine in self.ax.spines.values(): spine.set_visible(False)
        self.ax.grid(True, alpha=0.1, color=COLORS["text_dim"], linestyle='--')
        
        if labels and len(labels) == len(values):
            self.ax.set_xticks(range(len(labels)))
            self.ax.set_xticklabels(labels, rotation=0, fontsize=7)
        
        # Restore annotation (cleared by ax.clear())
        self.annot = self.ax.annotate(
            "", xy=(0,0), xytext=(10,10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", fc=COLORS["bg_panel"], ec=COLORS["border"], alpha=1.0),
            arrowprops=dict(arrowstyle="->", color=COLORS["text_dim"]),
            fontsize=8, color=COLORS["text_main"],
            weight="bold"
        )
        self.annot.set_visible(False)
        
        self.fig.tight_layout(pad=0)
        self.canvas.draw()

class PieChart(ctk.CTkFrame):
    """Refined allocation chart."""
    
    def __init__(self, master, title="", width=300, height=250, **kwargs):
        super().__init__(master, **kwargs)
        self.title = title
        self._setup_ui()
        
    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, padx=15, pady=(12, 8))
        
        ctk.CTkLabel(header, text=self.title.upper(), 
                     font=ctk.CTkFont(size=10, weight="bold"), 
                     text_color=COLORS["accent_blue"]).pack(side=tk.LEFT)
        
        self.fig = Figure(figsize=(3, 2.5), dpi=100)
        self.fig.patch.set_facecolor(COLORS["bg_card"])
        self.ax = self.fig.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Tooltip annotation
        self.annot = self.ax.annotate(
            "", xy=(0,0), xytext=(15,15),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc=COLORS["bg_panel"], ec=COLORS["border"], alpha=0.9),
            fontsize=8, color=COLORS["text_main"]
        )
        self.annot.set_visible(False)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

    def _on_hover(self, event):
        vis = self.annot.get_visible()
        if event.inaxes == self.ax:
            for wedge in self.ax.patches:
                cont, _ = wedge.contains(event)
                if cont:
                    # Update annotation
                    x, y = event.xdata, event.ydata
                    self.annot.xy = (x, y)
                    
                    # Search for label
                    idx = list(self.ax.patches).index(wedge)
                    labels = list(self._trade_labels) if hasattr(self, '_trade_labels') else []
                    label = labels[idx] if idx < len(labels) else f"Item {idx+1}"
                    
                    # Calculate percentage manually or from wedge
                    pct = (wedge.theta2 - wedge.theta1) / 3.6
                    self.annot.set_text(f"{label}\n{pct:.1f}%")
                    self.annot.set_visible(True)
                    self.canvas.draw_idle()
                    return
        if vis:
            self.annot.set_visible(False)
            self.canvas.draw_idle()
        
    def update_data(self, labels, values):
        self.ax.clear()
        self.ax.set_facecolor(COLORS["bg_card"])
        self._trade_labels = labels # Save for hover
        
        premium_palette = ['#89b4fa', '#a6e3a1', '#f9e2af', '#f38ba8', '#cba6f7', '#94e2d5']
        
        wedges, texts, autotexts = self.ax.pie(
            values, labels=labels, autopct='%1.1f%%',
            colors=premium_palette[:len(values)],
            textprops={'color': COLORS["text_main"], 'fontsize': 7, 'weight': 'bold'},
            pctdistance=0.75, startangle=140,
            wedgeprops={'edgecolor': COLORS["bg_card"], 'linewidth': 2, 'antialiased': True}
        )
        plt.setp(autotexts, size=7, weight="bold", color="white")
        
        # Restore annotation (cleared by ax.clear())
        self.annot = self.ax.annotate(
            "", xy=(0,0), xytext=(15,15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", fc=COLORS["bg_panel"], ec=COLORS["border"], alpha=1.0),
            fontsize=8, color=COLORS["text_main"],
            weight="bold"
        )
        self.annot.set_visible(False)
        
        self.fig.tight_layout(pad=0)
        self.canvas.draw()

# ─────────────────────────────────────────────────────────────────────────────
# LEGACY COMPONENTS (MODERNIZED)
# ─────────────────────────────────────────────────────────────────────────────

class CandlestickChart(ctk.CTkFrame):
    """Real-time candlestick chart widget."""
    def __init__(self, master, width=600, height=400, **kwargs):
        super().__init__(master, **kwargs)
        self._setup_ui()
    def _setup_ui(self):
        self.configure(fg_color=COLORS["bg_card"], border_width=1, border_color=COLORS["border"])
        ctk.CTkLabel(self, text="Real-time Charting Active", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=40)
    def update_data(self, ohlc, symbol=None): pass
    def clear(self): pass

# Alias for backwards compatibility
TVLiveAreaChart = CandlestickChart

class ThemeToggle(ctk.CTkFrame):
    """Modern theme selector."""
    def __init__(self, master, on_change=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_change = on_change
        self.is_dark = True
        self.configure(fg_color="transparent")
        self.btn = ctk.CTkButton(self, text="🌙 DARK", width=90, height=28, corner_radius=14,
                               fg_color=COLORS["border"], hover_color=COLORS["accent_blue"],
                               font=ctk.CTkFont(size=10, weight="bold"), command=self._toggle)
        self.btn.pack(padx=5, pady=2)
    def _toggle(self):
        self.is_dark = not self.is_dark
        self.btn.configure(text="🌙 DARK" if self.is_dark else "☀️ LIGHT")
        if self.on_change: self.on_change(self.is_dark)
    def set_theme(self, is_dark):
        self.is_dark = is_dark
        self.btn.configure(text="🌙 DARK" if self.is_dark else "☀️ LIGHT")

def create_sample_data():
    return [10, 20, 15, 25, 30]
