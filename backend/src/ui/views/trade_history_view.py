import tkinter as tk
import customtkinter as ctk
import csv
import os
from tkinter import filedialog
from typing import List, Dict, Any

from src.ui.shared import COLORS, IS_DARK, ToastNotification
from src.ui.dashboard.components.charts import StatCard, ModernTable
from src.utils.trade_logger import get_all_trades


class TradeHistoryView(ctk.CTkFrame):
    def __init__(self, parent, controller=None, is_main=True):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.is_main = is_main
        self._live_components = {}
        self._setup_ui()

    def _setup_ui(self):
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill=tk.X, pady=(0, 15))

        ctk.CTkLabel(self.header, text="📜 TRADE HISTORY",
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=COLORS["accent_blue"]).pack(side=tk.LEFT)

        ctk.CTkButton(self.header, text="📤 Export CSV", width=100, height=32,
                     fg_color=COLORS["accent_green"], text_color="white",
                     command=self._export_history).pack(side=tk.RIGHT, padx=5)

        ctk.CTkButton(self.header, text="🔄 Refresh", width=90, height=32,
                     fg_color=COLORS["border"], command=self._load_history).pack(side=tk.RIGHT, padx=5)

        self._add_stat_cards()
        self._add_table()
        
        # Initial load
        self.after(100, self._load_history)

    def _add_stat_cards(self):
        cards_container = ctk.CTkFrame(self, fg_color="transparent")
        cards_container.pack(fill=tk.X, pady=(0, 15))
        cards_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        c1 = StatCard(cards_container, "Total Trades", "0", "📊", COLORS["accent_blue"])
        c1.grid(row=0, column=0, padx=5)

        c2 = StatCard(cards_container, "Net P&L", "Rs0", "💰", COLORS["accent_green"])
        c2.grid(row=0, column=1, padx=5)

        c3 = StatCard(cards_container, "Win Rate", "0%", "🎯", COLORS["accent_peach"])
        c3.grid(row=0, column=2, padx=5)

        c4 = StatCard(cards_container, "Avg Trade", "Rs0", "📈", COLORS["text_dim"])
        c4.grid(row=0, column=3, padx=5)

        self._live_components["cards"] = [c1, c2, c3, c4]

    def _add_table(self):
        label = ctk.CTkLabel(
            self, text="📋 TRANSACTION LOG",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        label.pack(anchor=tk.W, pady=(5, 8))

        cols = ["Date", "Symbol", "Side", "Qty", "Entry", "Exit", "P&L", "Reason"]
        table = ModernTable(self, columns=cols, height=450)
        table.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        self._live_components["tree"] = table

    def _load_history(self):
        trades = get_all_trades()
        
        # Filter to only dict items
        valid_trades = [t for t in trades if isinstance(t, dict)]

        total_trades = len(valid_trades)
        total_pnl = sum(float(t.get('pnl', 0)) for t in valid_trades)
        win_trades = sum(1 for t in valid_trades if float(t.get('pnl', 0)) > 0)
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        avg_trade = total_pnl / total_trades if total_trades > 0 else 0

        cards = self._live_components["cards"]
        cards[0].update_value(str(total_trades))
        cards[1].update_value(f"Rs{total_pnl:+,.0f}")
        cards[2].update_value(f"{win_rate:.0f}%")
        cards[3].update_value(f"Rs{avg_trade:+,.0f}")

        color = COLORS["accent_green"] if total_pnl >= 0 else COLORS["accent_red"]
        cards[1].update_value(f"Rs{total_pnl:+,.0f}", color)

        table = self._live_components.get("tree")
        if not table or not hasattr(table, "clear"):
            return

        table.clear()
        for t in valid_trades:
            pnl = float(t.get('pnl', 0))
            tag = 'profit' if pnl > 0 else 'loss' if pnl < 0 else 'even'
            
            values = [
                t.get('date', 'N/A'),
                t.get('symbol', 'N/A'),
                t.get('side', 'N/A'),
                t.get('quantity', 0),
                f"Rs{float(t.get('entry_price', 0)):.0f}",
                f"Rs{float(t.get('exit_price', 0)):.0f}",
                f"Rs{pnl:+.0f}",
                t.get('exit_reason', 'Closed')
            ]
            table.add_row(values, tags=[tag])

    def _export_history(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if filepath:
            trades = get_all_trades()
            # Filter to only dict items
            valid_trades = [t for t in trades if isinstance(t, dict)]
            if valid_trades:
                with open(filepath, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=valid_trades[0].keys())
                    writer.writeheader()
                    writer.writerows(valid_trades)
                ToastNotification(self, "History exported successfully!")

    @property
    def live_components(self):
        return self._live_components
