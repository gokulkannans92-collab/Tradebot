"""
Overview View - Dashboard Statistics & Positions
═══════════════════════════════════════════════════════════════════════════════

Displays:
- Stat cards (P&L, Positions, Success Rate, Active P&L, Total Trades)
- Period filter buttons (Today, Yesterday, Week, Month, All)
- Live positions table with colors
- Charts (P&L trend, allocation)

Communicates with controller to load/refresh data.
Handles both main window and popped-out windows.
"""

import tkinter as tk
import json
import os
import time
import logging
import customtkinter as ctk
from datetime import datetime, timedelta
from tkinter import ttk as ttk_orig
from typing import Dict, List, Any, Optional

from src.ui.shared import COLORS, IS_DARK, ToastNotification
from src.ui.dashboard.constants import ACTIVE_TRADES_FILE, NIFTY_CHART_FILE, BANKNIFTY_CHART_FILE
from src.ui.dashboard.components.charts import StatCard, LineChart, PieChart, CandlestickChart, ModernTable, create_sample_data
from src.utils.trade_logger import get_all_trades

logger = logging.getLogger(__name__)


class OverviewView(ctk.CTkFrame):
    """Overview view component showing trading dashboard statistics."""
    
    def __init__(self, parent, controller=None, is_main: bool = True):
        """
        Initialize Overview view.
        
        Args:
            parent: Parent widget
            controller: IViewController instance (main app or mock for testing)
            is_main: True if this is the main window, False if popped-out
        """
        super().__init__(parent, fg_color="transparent")
        
        self.controller = controller
        self.is_main = is_main
        self._live_components: Dict[str, Any] = {}
        
        # Local state
        self.selected_period = "Today"
        self.period_btns: Dict[str, ctk.CTkButton] = {}
        self.last_active_mtime = 0
        self.last_trades_refresh = 0
        self.all_trades_cache: List[Dict[str, Any]] = []
        self.is_fetching_chart = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Build the view layout."""
        # ─── HEADER (Pinned at top) ────────────────────────────────────────
        self._add_header()
        
        # ─── SCROLLABLE CONTENT AREA ───────────────────────────────────────
        self.scrollable_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_container.pack(fill=tk.BOTH, expand=True)
        
        # ─── PERIOD FILTER BUTTONS ─────────────────────────────────────────
        self._add_period_filters()
        
        # ─── STAT CARDS ────────────────────────────────────────────────────
        self._add_stat_cards()
        
        # ─── CHARTS (Optional if charting enabled) ─────────────────────────
        self._add_charts()
        
        # ─── ACTIVE POSITIONS TABLE ────────────────────────────────────────
        self._add_positions_table()
        
        # Trigger initial data load
        if self.is_main and self.controller:
            self.after(100, self._refresh_data)
    
    def _add_header(self):
        """Add header with title and refresh button."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 15))
        
        title = ctk.CTkLabel(
            header, text="🏠 OVERVIEW",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        title.pack(side=tk.LEFT)
        
        refresh_btn = ctk.CTkButton(
            header, text="🔄 Refresh", width=90, height=32,
            fg_color=COLORS["border"],
            command=self._refresh_data
        )
        refresh_btn.pack(side=tk.RIGHT, padx=5)
        
        self._live_components["refresh_btn"] = refresh_btn
    
    def _add_period_filters(self):
        """Add period selection buttons."""
        filter_frame = ctk.CTkFrame(self.scrollable_container, fg_color="transparent")
        filter_frame.pack(fill=tk.X, pady=(0, 15))
        
        periods = [
            ("Today", "📅"),
            ("Yesterday", "🕒"),
            ("Past Week", "📅"),
            ("Past Month", "🗓️"),
            ("All Time", "♾️")
        ]
        
        for period_name, icon in periods:
            is_selected = (period_name == self.selected_period)
            btn = ctk.CTkButton(
                filter_frame,
                text=f"{icon} {period_name}",
                width=110, height=32,
                fg_color=COLORS["border"] if is_selected else "transparent",
                text_color=COLORS["accent_blue"] if is_selected else COLORS["text_dim"],
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda p=period_name: self._set_period(p)
            )
            btn.pack(side=tk.LEFT, padx=4)
            self.period_btns[period_name] = btn
    
    def _add_stat_cards(self):
        """Add 5 stat cards showing key metrics."""
        idx = 1 if IS_DARK else 0
        cards_frame = ctk.CTkFrame(self.scrollable_container, fg_color="transparent", height=120)
        cards_frame.pack(fill=tk.X, pady=(0, 12))
        cards_frame.pack_propagate(False)
        cards_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        
        # Card 1: Period P&L
        c1 = StatCard(cards_frame, "Period P&L", "Rs0", "💹", value_color=COLORS["accent_green"])
        c1.grid(row=0, column=0, padx=4)
        
        c2 = StatCard(cards_frame, "Trades (Period)", "0", "📊", value_color=COLORS["accent_blue"])
        c2.grid(row=0, column=1, padx=4)
        
        c3 = StatCard(cards_frame, "Success Rate", "0%", "🎯", value_color=COLORS["accent_peach"])
        c3.grid(row=0, column=2, padx=4)
        
        c4 = StatCard(cards_frame, "Active P&L", "Rs0", "📈", value_color=COLORS["accent_blue"])
        c4.grid(row=0, column=3, padx=4)
        
        c5 = StatCard(cards_frame, "Positions", "0", "⚡", value_color=COLORS["text_dim"])
        c5.grid(row=0, column=4, padx=4)
        
        self._live_components["cards"] = [c1, c2, c3, c4, c5]
    
    def _add_charts(self):
        """Add chart widgets (P&L trend, allocation)."""
        try:
            # ─── CHARTS ────────────────────────────────────────────────────────
            charts_frame = ctk.CTkFrame(self.scrollable_container, fg_color="transparent")
            charts_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
            
            # Configure grid expansion for charts_frame children
            charts_frame.grid_columnconfigure((0, 1), weight=1)
            charts_frame.grid_rowconfigure(0, weight=1)
            
            # P&L Chart
            pnl_frame = ctk.CTkFrame(
                charts_frame, fg_color=COLORS["bg_card"],
                border_width=1, border_color=COLORS["border"]
            )
            pnl_frame.grid(row=0, column=0, padx=4, sticky="nsew")
            
            pnl_chart = LineChart(pnl_frame, title="P&L Trend", height=200)
            pnl_chart.pack(fill=tk.BOTH, expand=True)
            
            # Allocation Chart
            alloc_frame = ctk.CTkFrame(
                charts_frame, fg_color=COLORS["bg_card"],
                border_width=1, border_color=COLORS["border"]
            )
            alloc_frame.grid(row=0, column=1, padx=4, sticky="nsew")
            
            alloc_chart = PieChart(alloc_frame, title="Instrument Allocation", height=200)
            alloc_chart.pack(fill=tk.BOTH, expand=True)
            
            self._live_components["pnl_chart"] = pnl_chart
            self._live_components["alloc_chart"] = alloc_chart
            
        except Exception as e:
            print(f"Warning: Could not load charts: {e}")
    
    def _add_positions_table(self):
        """Add bespoke ModernTable showing active positions."""
        label = ctk.CTkLabel(
            self.scrollable_container, text="📋 LIVE POSITIONS",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["accent_green"]
        )
        label.pack(anchor=tk.W, pady=(10, 8))
        
        cols = ["Symbol", "Side", "Qty", "Entry", "LTP", "P&L", "SL", "Target"]
        # height=300 for the scrollable area
        table = ModernTable(self.scrollable_container, columns=cols, height=350)
        table.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        self._live_components["tree"] = table
    
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
            logger.debug(f"Failed to sort: {e}")
            items.sort()
        
        for index, (val, item) in enumerate(items):
            tree.move(item, '', index)

    def _set_period(self, period: str):
        """Set active period and refresh data."""
        self.selected_period = period
        
        # Update button styles
        for name, btn in self.period_btns.items():
            if name == period:
                btn.configure(
                    fg_color=COLORS["border"],
                    text_color=COLORS["accent_blue"]
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLORS["text_dim"]
                )
        
        if self.controller:
            try:
                self.controller.set_period(period)
            except AttributeError:
                pass
        
        self._refresh_data()
        ToastNotification(self.controller or self, f"Filtered: {period}")

    def _setup_treeview_dark_style(self, tree):
        """Deprecated: Now using ModernTable component."""
        pass
    
    def _refresh_data(self):
        """Refresh all view data asynchronously."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
            
        if getattr(self, "_is_fetching_data", False):
            return
        
        self._is_fetching_data = True
        if "refresh_btn" in self._live_components:
            self._live_components["refresh_btn"].configure(text="⏳ Loading...", state="disabled")
            
        def _query_worker():
            try:
                # 1. Load active trades
                active_trades = []
                if os.path.exists(ACTIVE_TRADES_FILE):
                    try:
                        with open(ACTIVE_TRADES_FILE, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, dict):
                                active_trades = data.get("active_trades", [])
                            elif isinstance(data, list):
                                active_trades = data
                    except Exception as e:
                        logger.debug(f"Failed to load active trades: {e}")
                
                # Ensure active_trades is a list of dicts
                if not isinstance(active_trades, list):
                    active_trades = []
                active_pnl = sum(float(t.get('pnl', 0)) for t in active_trades if isinstance(t, dict))
                
                # 2. Load historical trades (with caching)
                now_ts = time.time()
                if now_ts - self.last_trades_refresh > 60 or not self.all_trades_cache:
                    cached = get_all_trades()
                    trades_cache = cached if isinstance(cached, list) else []
                    refresh_time = now_ts
                else:
                    trades_cache = self.all_trades_cache
                    refresh_time = self.last_trades_refresh
                
                # Dispatch the rendering back to the main thread safely
                self.after(0, lambda: self._on_data_loaded(active_trades, active_pnl, trades_cache, refresh_time))
            except Exception as e:
                logger.error(f"Async query worker failed: {e}")
                self.after(0, self._on_data_failed, str(e))
                
        import threading
        threading.Thread(target=_query_worker, daemon=True).start()

    def _on_data_loaded(self, active_trades, active_pnl, trades_cache, refresh_time):
        self._is_fetching_data = False
        if "refresh_btn" in self._live_components:
            self._live_components["refresh_btn"].configure(text="🔄 Refresh", state="normal")
            
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
            
        self.all_trades_cache = trades_cache
        self.last_trades_refresh = refresh_time
        
        all_trades = self.all_trades_cache
        if not isinstance(all_trades, list):
            all_trades = []
            self.all_trades_cache = []
        
        # 3. Filter by period
        filtered_trades = self._filter_trades_by_period(all_trades)

        # 4. Calculate stats (ensure only dicts)
        valid_filtered = [t for t in filtered_trades if isinstance(t, dict)]
        period_pnl = sum(float(t.get('pnl', 0)) for t in valid_filtered)
        total_count = len(valid_filtered)
        wins = len([t for t in valid_filtered if float(t.get('pnl', 0)) > 0])
        success_rate = (wins / total_count * 100) if total_count > 0 else 0
        
        # 5. Update cards
        self._update_cards(period_pnl, total_count, success_rate, active_pnl)
        
        # 6. Update positions table
        self._update_positions_table(active_trades)
        
        # 7. Update charts
        self._update_charts(filtered_trades)

    def _on_data_failed(self, err_msg):
        self._is_fetching_data = False
        if "refresh_btn" in self._live_components:
            self._live_components["refresh_btn"].configure(text="🔄 Refresh", state="normal")
        logger.error(f"Async data load failed: {err_msg}")
        try:
            if self.controller:
                ToastNotification(self.controller, f"Refresh error: {err_msg[:50]}")
        except tk.TclError:
            pass

    
    def _filter_trades_by_period(self, all_trades: List[Dict]) -> List[Dict]:
        """Filter trades based on selected period."""
        today = datetime.now().date()

        # Filter out non-dict items
        valid_trades = [t for t in all_trades if isinstance(t, dict)]

        if self.selected_period == "Today":
            date_str = today.strftime("%Y-%m-%d")
            return [t for t in valid_trades if t.get('date') == date_str]

        elif self.selected_period == "Yesterday":
            date_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            return [t for t in valid_trades if t.get('date') == date_str]

        elif self.selected_period == "Past Week":
            week_ago = today - timedelta(days=7)
            result = []
            for t in valid_trades:
                try:
                    trade_date = datetime.strptime(t.get('date', ''), "%Y-%m-%d").date()
                    if trade_date >= week_ago:
                        result.append(t)
                except ValueError as e:
                    logger.debug(f"Failed to parse trade date: {e}")
            return result

        elif self.selected_period == "Past Month":
            month_ago = today - timedelta(days=30)
            result = []
            for t in valid_trades:
                try:
                    trade_date = datetime.strptime(t.get('date', ''), "%Y-%m-%d").date()
                    if trade_date >= month_ago:
                        result.append(t)
                except ValueError as e:
                    logger.debug(f"Failed to parse trade date: {e}")
            return result

        else:  # All Time
            return valid_trades
    
    def _update_cards(self, period_pnl: float, total_count: int, success_rate: float, active_pnl: float):
        """Update stat card values."""
        cards = self._live_components.get("cards", [])
        if not cards or len(cards) < 5:
            return
        
        idx = 1 if IS_DARK else 0
        
        # Card 0: Period P&L
        try:
            pnl_color = COLORS["accent_green"] if period_pnl >= 0 else COLORS["accent_red"]
            cards[0].update_value(f"Rs{period_pnl:+.0f}", pnl_color)
        except (IndexError, AttributeError) as e:
            logger.debug(f"Failed to update P&L card: {e}")
        
        # Card 1: Total Trades (Period)
        try:
            cards[1].update_value(str(total_count))
        except (IndexError, AttributeError) as e:
            logger.debug(f"Failed to update trades card: {e}")
        
        # Card 2: Success Rate
        try:
            cards[2].update_value(f"{success_rate:.1f}%")
        except (IndexError, AttributeError) as e:
            logger.debug(f"Failed to update rate card: {e}")
        
        # Card 3: Active P&L
        try:
            active_color = COLORS["accent_green"] if active_pnl >= 0 else COLORS["accent_red"]
            cards[3].update_value(f"Rs{active_pnl:+.0f}", active_color)
        except (IndexError, AttributeError) as e:
            logger.debug(f"Failed to update active P&L card: {e}")
        
        # Card 4: Positions Count
        try:
            cards[4].update_value(str(total_count))
        except (IndexError, AttributeError) as e:
            logger.debug(f"Failed to update position count card: {e}")
    
    def _update_positions_table(self, active_trades: List[Dict]):
        """Update ModernTable with active positions."""
        table = self._live_components.get("tree")
        if not table or not hasattr(table, "clear"):
            return
        
        table.clear()
        
        for trade in active_trades:
            if not isinstance(trade, dict): continue
            pnl = float(trade.get('pnl', 0))
            tag = 'profit' if pnl > 0 else 'loss' if pnl < 0 else 'even'
            
            values = [
                trade.get('symbol', 'N/A'),
                trade.get('side', 'BUY'),
                trade.get('quantity', 0),
                f"Rs{float(trade.get('entry_price', 0)):.0f}",
                f"Rs{float(trade.get('ltp', 0)):.0f}",
                f"Rs{pnl:+.0f}",
                f"Rs{float(trade.get('sl', 0)):.0f}",
                f"Rs{float(trade.get('target', 0)):.0f}"
            ]
            table.add_row(values, tags=[tag])
    
    def _update_charts(self, trades: List[Dict]):
        """Update P&L and allocation charts."""
        pnl_chart = self._live_components.get("pnl_chart")
        alloc_chart = self._live_components.get("alloc_chart")
        
        if not pnl_chart or not alloc_chart:
            return
        
        try:
            if trades and isinstance(trades, list):
                # P&L Trend (last 15 trades)
                recent_trades = [t for t in trades[-15:] if isinstance(t, dict)]
                pnl_values = [float(t.get('pnl', 0)) for t in recent_trades]
                metadata = [{'invested': t.get('invested', 0)} for t in recent_trades]
                
                # Create short labels like #10, #11...
                total_t = len(trades)
                labels = [f"#{total_t - len(recent_trades) + i + 1}" for i in range(len(recent_trades))]
                pnl_chart.update_data(labels, pnl_values, COLORS["accent_green"], metadata=metadata)
                
                # Allocation by instrument
                instruments = {}
                for t in trades:
                    if not isinstance(t, dict): continue
                    inst = str(t.get('instrument', 'Unknown')).upper()
                    if 'NIFTY' in inst and 'BANK' not in inst:
                        key = 'NIFTY'
                    elif 'BANK' in inst:
                        key = 'BANKNIFTY'
                    elif 'FIN' in inst:
                        key = 'FINNIFTY'
                    else:
                        key = inst.split(' ')[0][:8]
                    
                    instruments[key] = instruments.get(key, 0) + 1
                
                if instruments:
                    alloc_chart.update_data(list(instruments.keys()), list(instruments.values()))
                else:
                    alloc_chart.update_data(['No Data'], [1])
            else:
                pnl_chart.update_data(['T1', 'T2', 'T3'], [0, 0, 0], COLORS["accent_green"])
                alloc_chart.update_data(['No Data'], [1])
        except Exception as e:
            logger.debug(f"Chart update skip: {e}")
    
    @property
    def live_components(self) -> Dict[str, Any]:
        """Public access to live components (for popped windows, testing)."""
        return self._live_components

