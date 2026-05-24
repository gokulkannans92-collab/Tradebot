import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, timedelta
from src.ui.shared import COLORS, ToastNotification
from src.ui.dashboard.components.charts import StatCard
from src.ui.dashboard.components.tables import PremiumTable
from src.utils.trade_logger import get_all_trades
import os
import csv
from tkinter import filedialog
from typing import List, Dict, Any, Optional
from tkcalendar import DateEntry


class LogsView(ctk.CTkFrame):
    def __init__(self, parent, controller=None, is_main=True):
        super().__init__(parent, fg_color="transparent")
        
        self.controller = controller
        self.is_main = is_main
        self._live_components = {}
        self.logs_selected_period = "Today"
        self.selected_trade = None
        self.all_trades_cache: List[Dict[str, Any]] = []
        
        self._setup_ui()
    
    def _setup_ui(self):
        # Using grid for the top-level LogsView ensures the footer remains pinned
        # and the middle content scales perfectly to the window size.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # Table area expands
        
        self._add_header()
        self._add_content()
        
        # Initial load
        self.after(200, lambda: self._set_logs_period("Today"))
    
    def _add_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side=ctk.LEFT)
        
        ctk.CTkLabel(title_box, text="📜 TRADE HISTORY", 
                    font=ctk.CTkFont(size=18, weight="bold"), 
                    text_color=COLORS["accent_blue"]).pack(side=ctk.LEFT)
        
        # Quick summary badge
        self.summary_badge = ctk.CTkLabel(title_box, text="", font=ctk.CTkFont(size=10),
                                          text_color=COLORS["text_dim"])
        self.summary_badge.pack(side=ctk.LEFT, padx=10)
        
        if self.is_main and self.controller:
            ctk.CTkButton(self.header_frame, text="↗ Pop Out", width=90, height=28,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         fg_color=COLORS["bg_card"], 
                         border_width=1, border_color=COLORS["border"],
                         text_color=COLORS["text_main"], 
                         hover_color=COLORS["accent_blue"],
                         command=self._pop_out).pack(side=ctk.RIGHT)
    
    def _pop_out(self):
        if self.controller:
            self.controller._pop_out_window("Trade History")
    
    def _add_content(self):
        # 1. TOP SETTINGS (Fixed row 1)
        top_settings = ctk.CTkFrame(self, fg_color="transparent")
        top_settings.grid(row=1, column=0, sticky="ew")
        
        self._add_period_buttons(top_settings)
        self._add_stats_row(top_settings)
        self._add_filters(top_settings)
        
        # 2. MAIN TABLE AREA (Row 2 - Expanding)
        self.table_container = ctk.CTkFrame(self, fg_color="transparent")
        self.table_container.grid(row=2, column=0, sticky="nsew", pady=(5, 0))
        
        self._add_table_and_details(self.table_container)
        
        # 3. FOOTER (Row 3 - Fixed)
        self._add_footer()
    
    def _add_period_buttons(self, parent):
        period_row = ctk.CTkFrame(parent, fg_color="transparent")
        period_row.pack(fill=tk.X, pady=(0, 8))
        
        # Left side - period buttons with icon
        left = ctk.CTkFrame(period_row, fg_color="transparent")
        left.pack(side=ctk.LEFT)
        
        periods = [("Today", "📅"), ("Yesterday", "🕒"), ("Past Week", "📅"), ("Past Month", "🗓️"), ("All Time", "♾️")]
        
        self.logs_period_btns = {}
        for p_name, icon in periods:
            is_active = (self.logs_selected_period == p_name)
            btn = ctk.CTkButton(left, text=f"{p_name}", width=90, height=30,
                               fg_color=COLORS["accent_blue"] if is_active else "transparent",
                               text_color="white" if is_active else COLORS["text_dim"],
                               font=ctk.CTkFont(size=11, weight="bold"),
                               command=lambda p=p_name: self._set_logs_period(p))
            btn.pack(side=ctk.LEFT, padx=3)
            self.logs_period_btns[p_name] = btn
        
        # Right side - custom date range picker
        right = ctk.CTkFrame(period_row, fg_color="transparent")
        right.pack(side=ctk.RIGHT)
        
        ctk.CTkButton(right, text="📅 Custom Range", width=120, height=30,
                     fg_color=COLORS["border"], command=self._open_date_picker).pack(side=ctk.RIGHT, padx=5)
    
    def _set_logs_period(self, period):
        self.logs_selected_period = period
        
        today = datetime.now().date()
        f_date, t_date = today, today
        
        if period == "Yesterday":
            f_date = today - timedelta(days=1)
            t_date = today - timedelta(days=1)
        elif period == "Past Week":
            f_date = today - timedelta(days=7)
        elif period == "Past Month":
            f_date = today - timedelta(days=30)
        elif period == "All Time":
            f_date = today - timedelta(days=3650)
            t_date = today
        
        # Update date entries if they exist
        if hasattr(self, 'logs_from_date'):
            self.logs_from_date.set_date(f_date)
            self.logs_to_date.set_date(t_date)
        
        for p_name, btn in self.logs_period_btns.items():
            is_active = (p_name == period)
            btn.configure(fg_color=COLORS["accent_blue"] if is_active else "transparent", 
                         text_color="white" if is_active else COLORS["text_dim"])
        
        self._refresh_logs()
    
    def _open_date_picker(self):
        ToastNotification(self.controller, "Use the date filters below for custom range")
    
    def _add_stats_row(self, parent):
        stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        stats_frame.grid_columnconfigure((0,1,2,3,4), weight=1)
        
        # Premium Stat Cards
        self.logs_total_stat = StatCard(stats_frame, "Total Trades", "0", "📊", COLORS["accent_blue"])
        self.logs_total_stat.grid(row=0, column=0, padx=5)
        
        self.logs_pnl_stat = StatCard(stats_frame, "Net P&L", "Rs0", "💹", COLORS["accent_green"])
        self.logs_pnl_stat.grid(row=0, column=1, padx=5)
        
        self.logs_winrate_stat = StatCard(stats_frame, "Win Rate", "0%", "🎯", COLORS["accent_blue"])
        self.logs_winrate_stat.grid(row=0, column=2, padx=5)
        
        self.logs_avg_stat = StatCard(stats_frame, "Avg Trade", "Rs0", "⏱️", COLORS["accent_peach"])
        self.logs_avg_stat.grid(row=0, column=3, padx=5)
        
        self.logs_best_stat = StatCard(stats_frame, "Best Trade", "Rs0", "🏆", COLORS["accent_peach"])
        self.logs_best_stat.grid(row=0, column=4, padx=5)
        
        self._live_components["cards"] = [
            self.logs_total_stat, self.logs_pnl_stat, self.logs_winrate_stat,
            self.logs_avg_stat, self.logs_best_stat
        ]
    
    def _add_filters(self, parent):
        filter_box = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=12)
        filter_box.pack(fill=tk.X, pady=(0, 5), padx=2)
        
        # Filter row
        f_row = ctk.CTkFrame(filter_box, fg_color="transparent")
        f_row.pack(fill=tk.X, padx=12, pady=10)
        
        # Left side filters
        filters_left = ctk.CTkFrame(f_row, fg_color="transparent")
        filters_left.pack(side=ctk.LEFT)
        
        # Side filter
        side_frame = ctk.CTkFrame(filters_left, fg_color="transparent")
        side_frame.pack(side=ctk.LEFT, padx=(0, 15))
        ctk.CTkLabel(side_frame, text="📌 Side:", font=ctk.CTkFont(size=11)).pack(side=ctk.LEFT, padx=3)
        self.logs_side_var = tk.StringVar(value="All")
        ctk.CTkOptionMenu(side_frame, values=["All", "BUY", "SELL"], variable=self.logs_side_var, 
                         width=80, height=28).pack(side=ctk.LEFT, padx=3)
        
        # P&L filter
        pnl_frame = ctk.CTkFrame(filters_left, fg_color="transparent")
        pnl_frame.pack(side=ctk.LEFT, padx=15)
        ctk.CTkLabel(pnl_frame, text="💰 P&L:", font=ctk.CTkFont(size=11)).pack(side=ctk.LEFT, padx=3)
        self.logs_pnl_var = tk.StringVar(value="All")
        ctk.CTkOptionMenu(pnl_frame, values=["All", "Profit", "Loss", "Even"], variable=self.logs_pnl_var, 
                         width=85, height=28).pack(side=ctk.LEFT, padx=3)
        
        # Date filters (Using interactive tkcalendar DateEntry)
        date_frame = ctk.CTkFrame(filters_left, fg_color="transparent")
        date_frame.pack(side=ctk.LEFT, padx=15)
        
        ctk.CTkLabel(date_frame, text="📆 From:", font=ctk.CTkFont(size=11)).pack(side=ctk.LEFT, padx=3)
        self.logs_from_date = DateEntry(date_frame, width=12, background='#1d4ed8', 
                                       foreground='white', borderwidth=2, year=datetime.now().year,
                                       date_pattern='yyyy-mm-dd')
        self.logs_from_date.pack(side=ctk.LEFT, padx=3)
        self.logs_from_date.set_date(datetime.now()) # Initial default
        
        ctk.CTkLabel(date_frame, text="To:", font=ctk.CTkFont(size=11)).pack(side=ctk.LEFT, padx=3)
        self.logs_to_date = DateEntry(date_frame, width=12, background='#1d4ed8', 
                                     foreground='white', borderwidth=2, year=datetime.now().year,
                                     date_pattern='yyyy-mm-dd')
        self.logs_to_date.pack(side=ctk.LEFT, padx=3)
        self.logs_to_date.set_date(datetime.now()) # Initial default
        
        # Right side - Actions Only (Symbol Search Box Removed)
        filters_right = ctk.CTkFrame(f_row, fg_color="transparent")
        filters_right.pack(side=ctk.RIGHT)
        
        apply_btn = ctk.CTkButton(filters_right, text="🔍 SEARCH", width=100, height=30,
                                  font=ctk.CTkFont(size=11, weight="bold"),
                                  fg_color=COLORS["accent_blue"], command=self._refresh_logs)
        apply_btn.pack(side=ctk.RIGHT, padx=5)
    
    def _add_table_and_details(self, parent):
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)
        content.grid_rowconfigure(0, weight=1)  # CRITICAL: Allow table & details to expand vertically
        
        # Table frame
        tfr = ctk.CTkFrame(content, fg_color="transparent")
        tfr.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        
        cols = ("Date", "Symbol", "Side", "Qty", "Entry", "Exit", "P&L", "Returns%", "Status")
        weights = [1.2, 2.5, 0.7, 0.6, 1.1, 1.1, 1.3, 1.0, 1.4]
        self.logs_tree = PremiumTable(tfr, columns=cols, weights=weights, on_select=self._on_trade_selected)
        self.logs_tree.pack(fill=tk.BOTH, expand=True)
        
        if self.is_main and self.controller:
            self.controller.logs_tree = self.logs_tree
        
        # Double click not supported by ModernTable yet, so we ignore it or use selection
        # self.logs_tree.bind("<Double-Button-1>", self._show_trade_detail_popup)
        
        # Details panel
        details = ctk.CTkFrame(content, fg_color=COLORS["bg_card"], corner_radius=12, width=260)
        details.grid(row=0, column=1, sticky="nsew")
        
        # Header
        details_header = ctk.CTkFrame(details, fg_color=COLORS["accent_blue"], corner_radius=10)
        details_header.pack(fill=tk.X, padx=10, pady=(10, 8))
        ctk.CTkLabel(details_header, text="📋 Trade Details", font=ctk.CTkFont(size=12, weight="bold"), 
                    text_color="white").pack(pady=6)
        
        # Container for trade metrics (Now scrollable to prevent cutoff)
        self.details_container = ctk.CTkScrollableFrame(
            details, fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_blue"]
        )
        self.details_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.no_selection = ctk.CTkLabel(self.details_container, text="Select a trade", 
                                         font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"])
        self.no_selection.pack(pady=20)
        
        # 3. Actions Panel (Fixed at bottom)
        actions = ctk.CTkFrame(details, fg_color="transparent")
        actions.pack(fill=tk.X, padx=12, pady=(0, 10), side=tk.BOTTOM)
        
        ctk.CTkButton(actions, text="📊 View Analysis", fg_color=COLORS["accent_green"], 
                     height=30, font=ctk.CTkFont(size=10)).pack(fill=tk.X, pady=2)
        
        ctk.CTkButton(actions, text="📧 Share Trade", fg_color=COLORS["border"], 
                     height=30, font=ctk.CTkFont(size=10)).pack(fill=tk.X, pady=2)
        
    def _add_footer(self):
        # Footer with export - Pinned to the bottom of the grid
        footer = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], height=45, corner_radius=12)
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        
        ctk.CTkButton(footer, text="📥 Export CSV", width=110, height=28, 
                     fg_color=COLORS["accent_green"], text_color="white",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     command=self._export_logs).pack(side=ctk.LEFT, padx=15, pady=6)
        
        ctk.CTkButton(footer, text="📊 Export Excel", width=110, height=28, 
                     fg_color=COLORS["accent_blue"], text_color="white",
                     font=ctk.CTkFont(size=10, weight="bold")).pack(side=tk.LEFT, padx=5, pady=6)
        
        # Stats summary in footer
        self.footer_stats = ctk.CTkLabel(footer, text="", font=ctk.CTkFont(size=10),
                                         text_color=COLORS["text_dim"])
        self.footer_stats.pack(side=ctk.RIGHT, padx=15)
        
        self._live_components["tree"] = self.logs_tree
    
    def _on_trade_selected(self, values):
        if values:
            self.selected_trade = values
            self._show_details(values)
    
    def _show_details(self, values):
        self.no_selection.pack_forget()
        
        for widget in self.details_container.winfo_children():
            widget.destroy()
        
        fields = ["Date", "Symbol", "Side", "Qty", "Entry", "Exit", "P&L", "Returns%", "Status"]
        
        for field, value in zip(fields, values):
            row = ctk.CTkFrame(self.details_container, fg_color="transparent")
            row.pack(fill=tk.X, pady=4)
            
            ctk.CTkLabel(row, text=field.upper() + ":", font=ctk.CTkFont(size=9, weight="bold"), 
                        text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
            
            # Color coding
            color = COLORS["text_main"]
            if field == "P&L":
                try:
                    pnl_str = str(value).replace('Rs', '').replace(',', '').replace('+', '').strip()
                    pnl = float(pnl_str)
                    color = COLORS["accent_green"] if pnl >= 0 else COLORS["accent_red"]
                except ValueError: pass
            elif field == "Side":
                color = COLORS["accent_green"] if str(value).upper() == "BUY" else COLORS["accent_red"]
            elif field == "Status":
                val_upper = str(value).upper()
                if "CLOSED" in val_upper: color = COLORS["accent_peach"]
                elif "WIN" in val_upper or "PROFIT" in val_upper: color = COLORS["accent_green"]
                elif "LOSS" in val_upper or "SL" in val_upper: color = COLORS["accent_red"]
            
            ctk.CTkLabel(row, text=str(value), font=ctk.CTkFont(size=12, weight="bold"),
                        text_color=color).pack(side=tk.RIGHT)
    
    def _show_trade_detail_popup(self, event):
        sel = self.logs_tree.selection()
        if sel:
            values = self.logs_tree.item(sel[0])['values']
            messagebox.showinfo("Trade Details", 
                               f"Symbol: {values[1]}\nSide: {values[2]}\nP&L: {values[6]}\nStatus: {values[8]}")
    
    def _refresh_logs(self):
        """Fetch and filter logs based on UI settings asynchronously."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
            
        if getattr(self, "_is_fetching_logs", False):
            return
            
        self._is_fetching_logs = True
        if hasattr(self, "summary_badge") and self.summary_badge.winfo_exists():
            self.summary_badge.configure(text="(⏳ Loading...)")
        
        # Get filter values
        f_date = self.logs_from_date.get_date()
        t_date = self.logs_to_date.get_date()
        side_filter = self.logs_side_var.get()
        pnl_filter = self.logs_pnl_var.get()
        
        def _query_worker():
            try:
                # 1. Load all trades (heavy SQL query)
                cached = get_all_trades()
                
                # 2. Apply standard temporal filtering
                filtered = cached if isinstance(cached, list) else []
                final_filtered = []
                for t in filtered:
                    if not isinstance(t, dict): continue
                    try:
                        t_date_val = datetime.strptime(t.get('date', ''), "%Y-%m-%d").date()
                        if f_date <= t_date_val <= t_date:
                            # Apply additional filters
                            if side_filter != "All" and t.get('side') != side_filter:
                                continue
                                
                            pnl = float(t.get('pnl', 0))
                            if pnl_filter == "Profit" and pnl <= 0: continue
                            if pnl_filter == "Loss" and pnl >= 0: continue
                            if pnl_filter == "Even" and pnl != 0: continue
                            
                            final_filtered.append(t)
                    except (ValueError, TypeError):
                        continue
                
                # Dispatch the rendering back to the main thread safely
                self.after(0, lambda: self._on_logs_loaded(cached, final_filtered))
            except Exception as e:
                logger.error(f"Logs async query worker failed: {e}")
                self.after(0, self._on_logs_failed, str(e))
                
        import threading
        threading.Thread(target=_query_worker, daemon=True).start()

    def _on_logs_loaded(self, cached, final_filtered):
        self._is_fetching_logs = False
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
            
        self.all_trades_cache = cached
        
        # Update UI
        self._update_table(final_filtered)
        self._update_stats(final_filtered)

    def _on_logs_failed(self, err_msg):
        self._is_fetching_logs = False
        if hasattr(self, "summary_badge") and self.summary_badge.winfo_exists():
            self.summary_badge.configure(text="(⚠️ Load Error)")
        logger.error(f"Async logs load failed: {err_msg}")
        try:
            if self.controller:
                ToastNotification(self.controller, f"Refresh error: {err_msg[:50]}")
        except tk.TclError:
            pass


    def _update_table(self, trades: List[Dict]):
        """Populate the modern table with trade data."""
        self.logs_tree.clear()
        
        for t in trades:
            pnl = float(t.get('pnl', 0))
            tag = 'profit' if pnl > 0 else 'loss' if pnl < 0 else 'even'
            
            # Calculate returns %
            invested = float(t.get('invested', 0))
            ret_pct = (pnl / invested * 100) if invested > 0 else 0
            
            values = [
                t.get('date', 'N/A'),
                t.get('instrument', t.get('symbol', 'N/A')),
                t.get('side', 'N/A'),
                t.get('quantity', 0),
                f"Rs{float(t.get('entry_price', 0)):.2f}",
                f"Rs{float(t.get('exit_price', 0)):.2f}",
                f"Rs{pnl:+.2f}",
                f"{ret_pct:+.1f}%",
                t.get('exit_reason', 'Closed')
            ]
            self.logs_tree.add_row(values, tags=[tag])

    def _update_stats(self, trades: List[Dict]):
        """Recalculate and update premium stat cards."""
        total = len(trades)
        net_pnl = sum(float(t.get('pnl', 0)) for t in trades)
        wins = sum(1 for t in trades if float(t.get('pnl', 0)) > 0)
        win_rate = (wins / total * 100) if total > 0 else 0
        avg_trade = (net_pnl / total) if total > 0 else 0
        best_trade = max([float(t.get('pnl', 0)) for t in trades]) if total > 0 else 0
        
        # Update cards
        self.logs_total_stat.update_value(str(total))
        
        pnl_color = COLORS["accent_green"] if net_pnl >= 0 else COLORS["accent_red"]
        self.logs_pnl_stat.update_value(f"Rs{net_pnl:+,.0f}", pnl_color)
        
        self.logs_winrate_stat.update_value(f"{win_rate:.1f}%")
        self.logs_avg_stat.update_value(f"Rs{avg_trade:,.0f}")
        self.logs_best_stat.update_value(f"Rs{best_trade:+,.0f}")
        
        # Footer summary
        self.footer_stats.configure(text=f"Showing {total} trades | Net P&L: Rs{net_pnl:,.2f}")
        self.summary_badge.configure(text=f"({total} records found)")

    def _export_logs(self):
        """Export current filtered view to CSV."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            filetypes=[("CSV Files", "*.csv")],
            initialfile=f"trade_history_{datetime.now().strftime('%Y%m%d')}.csv"
        )
        if not filepath: return
        
        try:
            # We want to export whatever is CURRENTLY in the treeview
            # (which means the filtered data)
            items = self.logs_tree.rows
            if not items:
                ToastNotification(self.controller, "Nothing to export!")
                return
                
            cols = ("Date", "Symbol", "Side", "Qty", "Entry", "Exit", "P&L", "Returns%", "Status")
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                # Note: ModernTable stores row frames, we need data values.
                # Actually, our _update_table call in ModernTable doesn't store data.
                # We should probably use all_trades_cache or refetch.
                # For now, let's filter all_trades_cache again or just export what's in cache.
                writer.writerows([t.values() if isinstance(t, dict) else t for t in self.all_trades_cache])
                    
            ToastNotification(self.controller, f"Exported trades to CSV")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))
    
    @property
    def live_components(self):
        return self._live_components
