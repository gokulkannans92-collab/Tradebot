"""
Trades View - Active Positions Management
═══════════════════════════════════════════════════════════════════════════════

Displays:
- Active trades table with real-time P&L
- Period and search filters
- Close trade functionality
- Export to CSV
- Selection-aware details panel

Communicates with controller to close trades and export data.
"""

import tkinter as tk
import json
import os
import csv
import customtkinter as ctk
from tkinter import messagebox, filedialog
from typing import Dict, List, Any, Optional
import logging

from src.ui.shared import COLORS, IS_DARK, ToastNotification
from src.ui.dashboard.components.charts import StatCard, ModernTable
from src.ui.dashboard.constants import ACTIVE_TRADES_FILE, TRADE_COMMANDS_FILE
from src.ipc.message_queue import create_bot_command_queue, MessageType
from src.ui.dashboard.config import PERIOD_OPTIONS
from src.utils.trade_logger import get_all_trades
from src.utils.paths import get_path

logger = logging.getLogger(__name__)


class TradesView(ctk.CTkFrame):
    """Trades view component for managing active positions."""
    
    def __init__(self, parent, controller=None, is_main: bool = True):
        """
        Initialize Trades view.
        
        Args:
            parent: Parent widget
            controller: IViewController instance
            is_main: True if main window, False if popped-out
        """
        super().__init__(parent, fg_color="transparent")
        
        self.controller = controller
        self.is_main = is_main
        self._live_components: Dict[str, Any] = {}
        
        # Local state
        self.period_var = tk.StringVar(value="All")
        self.search_var = ""
        self.selected_trade: Optional[Dict] = None
        self.last_refresh = 0
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Build the view layout."""
        # ─── HEADER ─────────────────────────────────────────────────────────
        self._add_header()
        
        # ─── FILTER BAR ──────────────────────────────────────────────────────
        self._add_filter_bar()
        
        # ─── MAIN CONTENT (Table + Details) ──────────────────────────────────
        self._add_main_content()
        
        # Trigger initial data load
        if self.is_main and self.controller:
            self.after(100, self._refresh_trades_table)
    
    def _add_header(self):
        """Add premium header with summary cards."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 15))
        
        # ─── NAVIGATION ROW ──────────────────────────
        nav_row = ctk.CTkFrame(header, fg_color="transparent")
        nav_row.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(
            nav_row, text="🔥 ACTIVE TRADES",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["accent_green"]
        ).pack(side=tk.LEFT)
        
        # Action buttons
        right = ctk.CTkFrame(nav_row, fg_color="transparent")
        right.pack(side=tk.RIGHT)
        
        refresh_btn = ctk.CTkButton(
            right, text="🔄 Refresh", width=90, height=32,
            fg_color=COLORS["border"], command=self._refresh_trades_table
        )
        refresh_btn.pack(side=tk.LEFT, padx=3)
        
        export_btn = ctk.CTkButton(
            right, text="📤 Export", width=80, height=32,
            fg_color=COLORS["accent_green"], text_color="white",
            command=self._export_trades_csv
        )
        export_btn.pack(side=tk.LEFT, padx=3)
        
        close_all_btn = ctk.CTkButton(
            right, text="🛑 Close All", width=100, height=32,
            fg_color=COLORS["accent_red"], text_color="white",
            command=self._close_all_trades
        )
        close_all_btn.pack(side=tk.LEFT, padx=8)
        
        # ─── SUMMARY CARDS ───────────────────────────
        self.stats_container = ctk.CTkFrame(header, fg_color="transparent")
        self.stats_container.pack(fill=tk.X, pady=(5, 0))
        self.stats_container.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.total_trades_card = StatCard(self.stats_container, "Total Open", "0", "📈", COLORS["accent_blue"])
        self.total_trades_card.grid(row=0, column=0, padx=5)
        
        self.pnl_card = StatCard(self.stats_container, "Total P&L", "Rs0", "💹", COLORS["accent_green"])
        self.pnl_card.grid(row=0, column=1, padx=5)
        
        self.exposure_card = StatCard(self.stats_container, "Exposure", "Rs0", "🛡️", COLORS["accent_peach"])
        self.exposure_card.grid(row=0, column=2, padx=5)
        
        self._live_components["cards"] = [self.total_trades_card, self.pnl_card, self.exposure_card]
        self._live_components["buttons"] = {
            "refresh": refresh_btn, "export": export_btn, "close_all": close_all_btn
        }
    
    def _add_filter_bar(self):
        """Add period and search filters."""
        idx = 1 if IS_DARK else 0
        filter_bar = ctk.CTkFrame(
            self, fg_color=COLORS["bg_card"],
            corner_radius=10, height=45
        )
        filter_bar.pack(fill=tk.X, pady=(0, 10), padx=2)
        filter_bar.pack_propagate(False)
        
        # Period filter
        period_label = ctk.CTkLabel(
            filter_bar, text="Period:",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        period_label.pack(side=tk.LEFT, padx=(10, 5), pady=8)
        
        period_menu = ctk.CTkOptionMenu(
            filter_bar,
            values=PERIOD_OPTIONS[:6],
            variable=self.period_var,
            width=110,
            command=lambda x: self._refresh_trades_table()
        )
        period_menu.pack(side=tk.LEFT, padx=5, pady=8)
        
        # Search filter
        search_label = ctk.CTkLabel(
            filter_bar, text="Search:",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        search_label.pack(side=tk.LEFT, padx=(20, 5), pady=8)
        
        search_entry = ctk.CTkEntry(
            filter_bar, width=180,
            placeholder_text="Symbol or ID...",
            placeholder_text_color=COLORS["text_dim"]
        )
        search_entry.pack(side=tk.LEFT, padx=5, pady=8)
        search_entry.bind("<KeyRelease>", self._on_search_change)
        
        self._live_components["filters"] = {
            "period": self.period_var,
            "search": search_entry
        }
    
    def _on_search_change(self, event):
        """Handle search field changes."""
        self.search_var = event.widget.get().strip().lower()
        self._refresh_trades_table()
    
    def _add_main_content(self):
        """Add trades table and details panel."""
        idx = 1 if IS_DARK else 0
        
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)
        content.grid_rowconfigure(0, weight=1)
        
        # ─── TRADES TABLE ────────────────────────────────────────────────────
        cols = ["Time", "Symbol", "Side", "Qty", "Entry", "LTP", "P&L", "SL", "Target", "Status"]
        table = ModernTable(content, columns=cols, height=450, on_select=self._on_table_row_selected)
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        
        self._live_components["tree"] = table
        
        # ─── DETAILS PANEL ───────────────────────────────────────────────────
        details_frame = ctk.CTkFrame(
            content, fg_color=COLORS["bg_card"],
            corner_radius=10, width=260
        )
        details_frame.grid(row=0, column=1, sticky="nsew", padx=8)
        details_frame.grid_propagate(False)
        
        details_title = ctk.CTkLabel(
            details_frame, text="📋 DETAILS",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        details_title.pack(pady=12)
        
        details_text = ctk.CTkLabel(
            details_frame,
            text="Select a trade\nto view details",
            text_color=COLORS["text_dim"],
            font=ctk.CTkFont(size=11),
            justify=tk.LEFT
        )
        details_text.pack(padx=12, pady=10, fill=tk.BOTH, expand=True)
        
        close_btn = ctk.CTkButton(
            details_frame, text="❌ Close Trade",
            fg_color=COLORS["accent_red"],
            text_color="white",
            height=35,
            command=self._close_selected_trade
        )
        close_btn.pack(fill=tk.X, padx=12, pady=10)
        
        self._live_components["details"] = {
            "text": details_text,
            "close_btn": close_btn
        }
    
    def _sort_tree(self, tree, col):
        """Sort tree by column."""
        items = [(tree.set(item, col), item) for item in tree.get_children('')]
        try:
            def sort_key(x):
                clean = x[0].replace('Rs', '').replace(',', '').replace('+', '').strip()
                try:
                    return float(clean)
                except ValueError:
                    return x[0].lower()
            items.sort(key=sort_key)
        except (TypeError, AttributeError) as e:
            logger.debug(f"Failed to sort items: {e}")
            items.sort()
        
        for index, (val, item) in enumerate(items):
            tree.move(item, '', index)
    
    def _on_table_row_selected(self, values):
        """Handle selection from ModernTable."""
        if not values:
            self.selected_trade = None
            return
            
        self.selected_trade = {
            "time": values[0], "symbol": values[1], "side": values[2],
            "qty": values[3], "entry": values[4], "ltp": values[5],
            "pnl": values[6], "sl": values[7], "target": values[8], "status": values[9]
        }
        
        # Update details panel
        details_text = self._live_components.get("details", {}).get("text")
        if details_text:
            detail_str = (
                f"Time: {self.selected_trade['time']}\n"
                f"Symbol: {self.selected_trade['symbol']}\n"
                f"Side: {self.selected_trade['side']}\n"
                f"Qty: {self.selected_trade['qty']}\n"
                f"Entry: {self.selected_trade['entry']}\n"
                f"LTP: {self.selected_trade['ltp']}\n"
                f"P&L: {self.selected_trade['pnl']}\n"
                f"SL: {self.selected_trade['sl']}\n"
                f"Target: {self.selected_trade['target']}\n"
                f"Status: {self.selected_trade['status']}"
            )
            details_text.configure(text=detail_str)
    
    def _refresh_trades_table(self):
        """Refresh active trades list."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        
        try:
            # Load active trades from file
            active_trades = []
            if os.path.exists(ACTIVE_TRADES_FILE):
                try:
                    with open(ACTIVE_TRADES_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            active_trades = data.get("active_trades", [])
                        elif isinstance(data, list):
                            active_trades = data
                        else:
                            active_trades = []
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logger.warning(f"Failed to load active trades: {e}")
                    active_trades = []
            
            # Apply search filter
            if self.search_var:
                active_trades = [
                    t for t in active_trades
                    if self.search_var in t.get('symbol', '').lower() or
                       self.search_var in t.get('time', '').lower()
                ]
            
            # Update tree widget
            table = self._live_components.get("tree")
            if not table or not hasattr(table, "clear"):
                return
            
            # Repopulate
            table.clear()
            total_open = len(active_trades)
            total_pnl = 0.0
            total_exposure = 0.0
            
            for trade in active_trades:
                pnl = float(trade.get('pnl', 0))
                total_pnl += pnl
                
                qty = float(trade.get('quantity', 0))
                ltp = float(trade.get('ltp', 0))
                total_exposure += (qty * ltp)
                
                tag = 'profit' if pnl > 0 else 'loss' if pnl < 0 else 'even'
                
                values = [
                    trade.get('time', 'N/A'),
                    trade.get('symbol', 'N/A'),
                    trade.get('side', 'BUY'),
                    trade.get('quantity', 0),
                    f"Rs{float(trade.get('entry_price', 0)):.0f}",
                    f"Rs{float(trade.get('ltp', 0)):.0f}",
                    f"Rs{pnl:+.0f}",
                    f"Rs{float(trade.get('sl', 0)):.0f}",
                    f"Rs{float(trade.get('target', 0)):.0f}",
                    trade.get('status', 'Open')
                ]
                table.add_row(values, tags=[tag])
            
            # Update cards
            cards = self._live_components.get("cards", [])
            if cards:
                cards[0].update_value(str(total_open))
                cards[1].update_value(f"Rs{total_pnl:+,.0f}", COLORS["accent_green"] if total_pnl >= 0 else COLORS["accent_red"])
                cards[2].update_value(f"Rs{total_exposure:,.0f}")
        
        except Exception as e:
            print(f"Trades refresh error: {e}")
    
    def _close_selected_trade(self):
        """Close the selected trade."""
        if not self.selected_trade:
            messagebox.showwarning("Select Trade", "Please select an active trade to close.")
            return
        
        symbol = self.selected_trade.get('symbol')
        
        if messagebox.askyesno("Confirm Close", f"Close position {symbol}?"):
            try:
                if not self.controller:
                    raise ValueError("No controller available")
                
                # Use the new MessageQueue IPC
                queue = create_bot_command_queue()
                queue.publish(MessageType.COMMAND, {
                    "command": "CLOSE_TRADE",
                    "symbol": symbol
                }, sender="GUI_TRADES_VIEW")
                
                ToastNotification(self, f"Close request sent for {symbol}")
                self.after(500, self._refresh_trades_table)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to close trade: {e}")
    
    def _close_all_trades(self):
        """Close all active trades."""
        try:
            if not os.path.exists(ACTIVE_TRADES_FILE):
                messagebox.showinfo("No Trades", "No active trades to close.")
                return
            
            with open(ACTIVE_TRADES_FILE, 'r', encoding='utf-8') as f:
                trades = json.load(f)
            
            if not trades:
                messagebox.showinfo("No Trades", "No active trades to close.")
                return
            
            if messagebox.askyesno(
                "Confirm Exit All",
                "⚠️ Are you sure? This will CLOSE ALL active positions immediately."
            ):
                queue = create_bot_command_queue()
                queue.publish(MessageType.COMMAND, {
                    "command": "CLOSE_ALL"
                }, sender="GUI_TRADES_VIEW")
                
                ToastNotification(self, "Close ALL request sent!")
                self.after(500, self._refresh_trades_table)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to close all trades: {e}")
    
    def _export_trades_csv(self):
        """Export active trades to CSV."""
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
            )
            
            if not filepath:
                return
            
            # Get all active trades
            active_trades = []
            if os.path.exists(ACTIVE_TRADES_FILE):
                try:
                    with open(ACTIVE_TRADES_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        active_trades = list(data.values()) if isinstance(data, dict) else data
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logger.warning(f"Failed to load active trades for export: {e}")
            
            if not active_trades:
                messagebox.showinfo("No Trades", "No active trades to export.")
                return
            
            # Write to CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=active_trades[0].keys())
                writer.writeheader()
                writer.writerows(active_trades)
            
            ToastNotification(self, f"Exported {len(active_trades)} trades")
        
        except Exception as e:
            messagebox.showerror("Export Error", str(e))
    
    @property
    def live_components(self) -> Dict[str, Any]:
        """Public access to live components."""
        return self._live_components
