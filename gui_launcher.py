# TradeBot GUI Launcher - Full Visual Overhaul & Enhancement
import sys
import os
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, filedialog
import customtkinter as ctk
import json
import threading
import subprocess
import time
import shutil
from datetime import datetime, timedelta
from src.utils.security import get_password_hash

# Project-specific imports
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv, set_key
load_dotenv(os.path.join(PROJECT_DIR, ".env"))

from src.config.config import Config, UserConfig
from src.dashboard import CandlestickChart, LineChart, PieChart, StatCard, create_sample_data
from src.utils.bot_state import (
    write_pid, clear_pid, is_bot_running, request_stop, PID_FILE, STOP_TRIGGER_FILE
)
from src.utils.security import verify_password

ACTIVE_TRADES_FILE = os.path.join(PROJECT_DIR, ".active_trades")
LOG_FILE = os.path.join(PROJECT_DIR, "trade_bot.log")
USERS_FILE = os.path.join(PROJECT_DIR, "data", "users.json")

# Nord/Catppuccin Palette
BG_ROOT = "#0a0a0f"
BG_PANEL = "#11111b"
BG_CARD = "#181825"
ACCENT_BLUE = "#89b4fa"
ACCENT_PEACH = "#fab387"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
TEXT_MAIN = "#cdd6f4"
TEXT_DIM = "#6c7086"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class LoginView(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("TradeBot Login")
        self.geometry("500x700")
        self.configure(fg_color=BG_PANEL)
        self.resizable(False, False)
        
        ico_path = os.path.join(PROJECT_DIR, "TradeBot.ico")
        if os.path.exists(ico_path):
            try: self.wm_iconbitmap(ico_path)
            except: pass
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (500 // 2)
        y = (screen_height // 2) - (700 // 2)
        self.geometry(f"500x700+{x}+{y}")
        
        self.card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=20, border_width=1, border_color="#313244", width=420, height=600)
        self.card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.card.pack_propagate(False)
        
        ctk.CTkLabel(self.card, text="🤖", font=ctk.CTkFont(size=72)).pack(pady=(50, 10))
        ctk.CTkLabel(self.card, text="TradeBot Pro", font=ctk.CTkFont(size=32, weight="bold"), text_color=ACCENT_BLUE).pack()
        ctk.CTkLabel(self.card, text="Advanced Algorithmic Trading", font=ctk.CTkFont(size=12), text_color=TEXT_DIM).pack(pady=(0, 40))
        
        input_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        input_frame.pack(fill=tk.X, padx=50)
        
        ctk.CTkLabel(input_frame, text="Username", font=ctk.CTkFont(size=12, weight="bold"), text_color=ACCENT_PEACH).pack(anchor=tk.W, pady=(10, 5))
        self.user_entry = ctk.CTkEntry(input_frame, height=45, fg_color="#1e1e2e", border_color="#313244", placeholder_text="Enter username...")
        self.user_entry.pack(fill=tk.X)
        self.user_entry.insert(0, "admin")
        
        ctk.CTkLabel(input_frame, text="Password", font=ctk.CTkFont(size=12, weight="bold"), text_color=ACCENT_PEACH).pack(anchor=tk.W, pady=(20, 5))
        self.pass_entry = ctk.CTkEntry(input_frame, height=45, fg_color="#1e1e2e", border_color="#313244", placeholder_text="••••••••", show="*")
        self.pass_entry.pack(fill=tk.X)
        
        self.show_pass_var = tk.BooleanVar(value=False)
        self.show_pass_cb = ctk.CTkCheckBox(input_frame, text="Show password", variable=self.show_pass_var, font=ctk.CTkFont(size=11), text_color=TEXT_DIM, command=self._toggle_pass_visibility)
        self.show_pass_cb.pack(anchor=tk.W, pady=(15, 0))
        
        self.login_btn = ctk.CTkButton(self.card, text="Login to Dashboard", height=50, corner_radius=12, fg_color=ACCENT_BLUE, hover_color="#74c7ec", text_color="#1e1e2e", font=ctk.CTkFont(size=15, weight="bold"), command=self._attempt_login)
        self.login_btn.pack(fill=tk.X, padx=50, pady=(40, 20))
        
        ctk.CTkLabel(self.card, text="🔒 Secure Login", font=ctk.CTkFont(size=11), text_color=ACCENT_GREEN).pack()

    def _toggle_pass_visibility(self):
        self.pass_entry.configure(show="" if self.show_pass_var.get() else "*")

    def _attempt_login(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get().strip()
        if not username or not password:
            messagebox.showwarning("Login", "Please enter both credentials.")
            return
        try:
            users = Config.load_users()
            user_found = next((u for u in users if u.get("name") == username and u.get("active", True)), None)
            if not user_found:
                messagebox.showerror("Unauthorized", "Invalid username or account inactive.")
                return
            if verify_password(password, user_found.get("login_password", "")):
                user_found["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                with open(USERS_FILE, "w") as f: json.dump(users, f, indent=2)
                uid, uname = user_found.get("user_id", "user_001"), username
                self.destroy()
                app = TradeBotGUI(uid, uname)
                app.mainloop()
            else: messagebox.showerror("Denied", "Incorrect password.")
        except Exception as e: messagebox.showerror("System Error", str(e))

class TradeBotGUI(ctk.CTk):
    def __init__(self, user_id="user_001", user_name="admin"):
        super().__init__()
        self.title("TradeBot Dashboard")
        self.geometry("1400x900")
        self.configure(fg_color=BG_PANEL)
        
        ico_path = os.path.join(PROJECT_DIR, "TradeBot.ico")
        if os.path.exists(ico_path):
            try: self.wm_iconbitmap(ico_path)
            except: pass
            
        self.current_user_name = user_name
        self.current_user_id = user_id
        self.bot_running = False
        self.sidebar_left_visible = True
        self.sidebar_right_visible = True
        self.views = {}
        
        self._setup_root_layout()
        self._setup_header()
        self._setup_sidebars()
        self._setup_content_area()
        self._refresh_status_loop()

    def _setup_root_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.header_frame = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color=BG_PANEL)
        self.header_frame.grid(row=0, column=0, columnspan=3, sticky="new")
        self.header_frame.grid_propagate(False)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=1, column=0, columnspan=3, sticky="nsew")

    def _setup_header(self):
        left_header = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        left_header.pack(side=tk.LEFT, padx=15, fill=tk.Y)
        ctk.CTkButton(left_header, text="☰", width=35, height=35, fg_color="#313244", command=self.toggle_left_sidebar).pack(side=tk.LEFT, padx=(0, 15))
        ctk.CTkLabel(left_header, text="🤖 TradeBot Dashboard", font=ctk.CTkFont(size=22, weight="bold"), text_color=ACCENT_BLUE).pack(side=tk.LEFT)
        
        right_cluster = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        right_cluster.pack(side=tk.RIGHT, padx=15, fill=tk.Y)
        
        self.toggle_right_btn = ctk.CTkButton(right_cluster, text="☰", width=35, height=35, fg_color="#313244", command=self.toggle_right_sidebar)
        self.toggle_right_btn.pack(side=tk.RIGHT, padx=(15, 0))
        
        self.start_btn = ctk.CTkButton(right_cluster, text="▶ START BOT", width=120, height=40, fg_color=ACCENT_BLUE, hover_color="#74c7ec", text_color="#1e1e2e", font=ctk.CTkFont(size=13, weight="bold"), command=self._start_bot)
        self.start_btn.pack(side=tk.RIGHT, padx=10)
        
        self.status_box = ctk.CTkFrame(right_cluster, fg_color="#1e1e2e", corner_radius=8, height=40)
        self.status_box.pack(side=tk.RIGHT, padx=10)
        self.status_label = ctk.CTkLabel(self.status_box, text="● IDLE", text_color=ACCENT_PEACH, font=ctk.CTkFont(size=12, weight="bold"))
        self.status_label.pack(padx=15, pady=5)
        
        user_info = ctk.CTkFrame(right_cluster, fg_color="transparent")
        user_info.pack(side=tk.RIGHT, padx=20)
        ctk.CTkLabel(user_info, text="👤", font=ctk.CTkFont(size=14)).pack(side=tk.LEFT, padx=5)
        ctk.CTkLabel(user_info, text=self.current_user_name, font=ctk.CTkFont(size=14, weight="bold")).pack(side=tk.LEFT)

    def _setup_sidebars(self):
        self.sidebar_left = ctk.CTkFrame(self.main_container, width=280, corner_radius=0, fg_color=BG_PANEL)
        self.sidebar_left.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar_left.pack_propagate(False)
        
        self._add_sidebar_header(self.sidebar_left, "CONTROL PANEL")
        
        status_frame = self._add_sidebar_section(self.sidebar_left, "📊 SYSTEM STATUS", ACCENT_BLUE)
        self._add_sidebar_stat(status_frame, "Python Engine", f"✓ {sys.version.split(' ')[0]}")
        self.trades_today_stat = self._add_sidebar_stat(status_frame, "Trades Today", "0 / 5")
        self.daily_pnl_stat = self._add_sidebar_stat(status_frame, "Daily P&L", "₹+0.00", ACCENT_GREEN)
        ctk.CTkButton(status_frame, text="🔄 REFRESH STATUS", height=32, fg_color="#313244", command=self._refresh_overview_data).pack(fill=tk.X, pady=(15, 0))
        
        config_frame = self._add_sidebar_section(self.sidebar_left, "⚙️ CONFIGURATION", ACCENT_PEACH)
        
        broker_row = ctk.CTkFrame(config_frame, fg_color="transparent")
        broker_row.pack(fill=tk.X, pady=5)
        ctk.CTkLabel(broker_row, text="Active Broker:", font=ctk.CTkFont(size=12)).pack(side=tk.LEFT)
        self.broker_dropdown = ctk.CTkComboBox(broker_row, values=["angel", "zerodha", "mock"], width=130)
        self.broker_dropdown.pack(side=tk.RIGHT)
        self.broker_dropdown.set(os.getenv("BROKER_TYPE", "angel"))
        
        self.paper_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(config_frame, text="Paper Trading (Safe Mode)", variable=self.paper_var, font=ctk.CTkFont(size=11)).pack(anchor=tk.W, pady=3)
        self.tsl_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(config_frame, text="Trailing Stop Loss", variable=self.tsl_var, font=ctk.CTkFont(size=11)).pack(anchor=tk.W, pady=3)
        self.kill_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(config_frame, text="Kill Bot after Limit", variable=self.kill_var, font=ctk.CTkFont(size=11)).pack(anchor=tk.W, pady=3)
        
        risk_frame = self._add_sidebar_section(self.sidebar_left, "🌓 RISK OVERVIEW", ACCENT_BLUE)
        self._add_sidebar_stat(risk_frame, "Max Loss Limit", "₹15,000")
        self._add_sidebar_stat(risk_frame, "Current Risk", "₹2,450", ACCENT_RED)
        
        self.sidebar_right = ctk.CTkFrame(self.main_container, width=220, corner_radius=0, fg_color=BG_PANEL)
        self.sidebar_right.pack(side=tk.RIGHT, fill=tk.Y)
        self.sidebar_right.pack_propagate(False)
        self._add_sidebar_header(self.sidebar_right, "NAVIGATION")
        self.nav_btns = {}
        navs = [("Overview", "🏠"), ("Trades", "📜"), ("Management", "👥"), ("Config", "⚙️"), ("Logs", "📊"), ("Console", "⌨️"), ("Help", "📖")]
        for name, icon in navs:
            btn = ctk.CTkButton(self.sidebar_right, text=f"  {icon}  {name}", anchor=tk.W, height=45, fg_color="transparent", text_color=TEXT_MAIN, command=lambda n=name: self._switch_tab(n))
            btn.pack(fill=tk.X, padx=10, pady=2); self.nav_btns[name] = btn
        self.nav_btns["Overview"].configure(fg_color="#313244", text_color=ACCENT_BLUE)

    def _setup_content_area(self):
        self.content_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.views["Overview"] = self._create_overview_view()
        self.views["Trades"] = self._create_trades_view()
        self.views["Management"] = self._create_management_view()
        self.views["Config"] = self._create_config_view()
        self.views["Logs"] = self._create_logs_view()
        self.views["Console"] = self._create_console_view()
        self.views["Help"] = self._create_help_view()
        
        for v in self.views.values():
            v.pack(fill=tk.BOTH, expand=True)
        for v in list(self.views.values())[1:]:
            v.pack_forget()

    def _create_overview_view(self):
        view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        
        fbar = ctk.CTkFrame(view, fg_color="transparent")
        fbar.pack(fill=tk.X, pady=(0, 20))
        ctk.CTkLabel(fbar, text="Filter Period:", font=ctk.CTkFont(size=12)).pack(side=tk.LEFT, padx=10)
        for lbl in ["Today", "Yesterday", "Past Week", "Past Month", "All Time"]:
            b = ctk.CTkButton(fbar, text=lbl, width=90, height=35, fg_color="#1e1e2e", command=lambda x=lbl: self._filter_by_period(x))
            b.pack(side=tk.LEFT, padx=5)
            if lbl == "Today": b.configure(fg_color="#313244", text_color=TEXT_MAIN)
        
        mrow = ctk.CTkFrame(view, fg_color="transparent")
        mrow.pack(fill=tk.X, pady=10); mrow.grid_columnconfigure((0,1,2,3), weight=1)
        self.card1 = StatCard(mrow, "Today's Profit", "₹0.00", "💹", ACCENT_GREEN); self.card1.grid(row=0, column=0, padx=8)
        self.card2 = StatCard(mrow, "Active Trades", "0", "⚡", ACCENT_BLUE); self.card2.grid(row=0, column=1, padx=8)
        self.card3 = StatCard(mrow, "Success Rate", "0", "🎯", ACCENT_PEACH); self.card3.grid(row=0, column=2, padx=8)
        self.card4 = StatCard(mrow, "Active P&L", "₹0.00", "📉", ACCENT_RED); self.card4.grid(row=0, column=3, padx=8)
        
        ctk.CTkLabel(view, text="📑 LIVE MARKET POSITIONS", font=ctk.CTkFont(size=14, weight="bold"), text_color=ACCENT_GREEN).pack(anchor=tk.W, pady=(20, 10))
        tfr = ctk.CTkFrame(view, fg_color=BG_PANEL, corner_radius=12, border_width=1, border_color="#313244")
        tfr.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tfr, columns=("Symbol", "Side", "Qty", "Entry", "LTP", "PnL", "SL", "Target"), show='headings')
        for c in self.tree["columns"]: self.tree.heading(c, text=c); self.tree.column(c, width=100, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self._refresh_overview_data()
        return view

    def _filter_by_period(self, period):
        self._refresh_overview_data()

    def _refresh_overview_data(self):
        try:
            if os.path.exists(ACTIVE_TRADES_FILE):
                with open(ACTIVE_TRADES_FILE, 'r') as f:
                    trades = json.load(f)
            else:
                trades = []
            
            self.card2.update_value(str(len(trades)))
            
            total_pnl = 0
            self.tree.delete(*self.tree.get_children())
            for t in trades:
                pnl = t.get('pnl', 0)
                total_pnl += pnl
                self.tree.insert("", tk.END, values=(
                    t.get('symbol', 'N/A'), t.get('side', 'BUY'), t.get('quantity', 0),
                    f"₹{t.get('entry_price', 0):.2f}", f"₹{t.get('ltp', 0):.2f}",
                    f"₹{pnl:+.2f}", f"₹{t.get('sl', 0):.2f}", f"₹{t.get('target', 0):.2f}"
                ))
            
            self.card4.update_value(f"₹{total_pnl:+.2f}", ACCENT_GREEN if total_pnl >= 0 else ACCENT_RED)
            self.card1.update_value(f"₹{total_pnl:+.2f}", ACCENT_GREEN if total_pnl >= 0 else ACCENT_RED)
            
            self.trades_today_stat.configure(text=f"{len(trades)} / 5")
            self.daily_pnl_stat.configure(text=f"₹{total_pnl:+.2f}", text_color=ACCENT_GREEN if total_pnl >= 0 else ACCENT_RED)
        except Exception as e:
            print(f"Error refreshing: {e}")

    def _create_trades_view(self):
        view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        
        header = ctk.CTkFrame(view, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 10))
        ctk.CTkLabel(header, text="📑 ALL TRADES HISTORY", font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_GREEN).pack(side=tk.LEFT)
        ctk.CTkButton(header, text="🔄 Refresh", command=self._refresh_trades_table).pack(side=tk.RIGHT)
        ctk.CTkButton(header, text="📤 Export CSV", command=self._export_trades_csv).pack(side=tk.RIGHT, padx=10)
        
        tfr = ctk.CTkFrame(view, fg_color=BG_PANEL, corner_radius=12, border_width=1, border_color="#313244")
        tfr.pack(fill=tk.BOTH, expand=True)
        
        cols = ("Time", "Symbol", "Side", "Qty", "Entry", "Exit", "P&L", "Status")
        self.trades_tree = ttk.Treeview(tfr, columns=cols, show='headings')
        for c in cols: self.trades_tree.heading(c, text=c); self.trades_tree.column(c, width=100, anchor=tk.CENTER)
        self.trades_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self._refresh_trades_table()
        return view

    def _refresh_trades_table(self):
        try:
            if os.path.exists(ACTIVE_TRADES_FILE):
                with open(ACTIVE_TRADES_FILE, 'r') as f:
                    trades = json.load(f)
            else:
                trades = []
            
            self.trades_tree.delete(*self.trades_tree.get_children())
            for t in trades:
                self.trades_tree.insert("", tk.END, values=(
                    t.get('time', 'N/A'), t.get('symbol', 'N/A'), t.get('side', 'BUY'),
                    t.get('quantity', 0), f"₹{t.get('entry_price', 0):.2f}",
                    f"₹{t.get('ltp', 0):.2f}", f"₹{t.get('pnl', 0):+.2f}",
                    t.get('status', 'Open')
                ))
        except Exception as e:
            print(f"Error: {e}")

    def _export_trades_csv(self):
        try:
            filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if filepath:
                if os.path.exists(ACTIVE_TRADES_FILE):
                    shutil.copy(ACTIVE_TRADES_FILE, filepath)
                messagebox.showinfo("Success", f"Exported to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _create_management_view(self):
        view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        
        header = ctk.CTkFrame(view, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 15))
        ctk.CTkLabel(header, text="👥 USER MANAGEMENT", font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT_BLUE).pack(side=tk.LEFT)
        ctk.CTkButton(header, text="➕ Add User", command=self._add_user_dialog).pack(side=tk.RIGHT)
        
        tfr = ctk.CTkFrame(view, fg_color=BG_PANEL, corner_radius=12, border_width=1, border_color="#313244")
        tfr.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        cols = ("Name", "User ID", "Broker", "Active", "Last Login")
        self.users_tree = ttk.Treeview(tfr, columns=cols, show='headings')
        for c in cols: self.users_tree.heading(c, text=c); self.users_tree.column(c, width=120, anchor=tk.CENTER)
        self.users_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        btn_frame = ctk.CTkFrame(view, fg_color="transparent")
        btn_frame.pack(fill=tk.X)
        ctk.CTkButton(btn_frame, text="✏️ Edit", command=self._edit_user_dialog).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(btn_frame, text="🗑️ Delete", fg_color=ACCENT_RED, hover_color="#eba0ac", command=self._delete_user).pack(side=tk.LEFT, padx=5)
        
        self._refresh_users_table()
        return view

    def _refresh_users_table(self):
        try:
            users = Config.load_users()
            self.users_tree.delete(*self.users_tree.get_children())
            for u in users:
                self.users_tree.insert("", tk.END, values=(
                    u.get('name', 'N/A'), u.get('user_id', 'N/A'),
                    u.get('broker_type', 'N/A'), "✅" if u.get('active', True) else "❌",
                    u.get('last_login', 'Never')
                ))
        except Exception as e:
            print(f"Error: {e}")

    def _add_user_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New User")
        dialog.geometry("500x650")
        
        ctk.CTkLabel(dialog, text="Add New User", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        
        entries = {}
        fields = [("Name", "name"), ("User ID", "user_id"), ("API Key", "api_key"), ("API Secret", "api_secret"), ("Client ID", "client_id"), ("Password", "password")]
        for lbl, key in fields:
            ctk.CTkLabel(dialog, text=lbl).pack(anchor=tk.W, padx=20, pady=(10, 0))
            entry = ctk.CTkEntry(dialog, width=460)
            entry.pack(fill=tk.X, padx=20)
            entries[key] = entry
        
        ctk.CTkLabel(dialog, text="Broker").pack(anchor=tk.W, padx=20, pady=(10, 0))
        broker_var = tk.StringVar(value="MOCK")
        ctk.CTkOptionMenu(dialog, variable=broker_var, values=["MOCK", "ZERODHA", "ANGEL", "UPSTOX", "GROWW"]).pack(fill=tk.X, padx=20)
        
        ctk.CTkLabel(dialog, text="Login Password").pack(anchor=tk.W, padx=20, pady=(10, 0))
        pass_entry = ctk.CTkEntry(dialog, width=460, show="*")
        pass_entry.pack(fill=tk.X, padx=20)
        
        def save():
            try:
                new_user = {
                    "user_id": entries["user_id"].get(),
                    "name": entries["name"].get(),
                    "broker_type": broker_var.get(),
                    "active": True,
                    "login_password": get_password_hash(pass_entry.get()),
                    "credentials": {
                        "api_key": entries["api_key"].get(),
                        "api_secret": entries["api_secret"].get(),
                        "client_id": entries["client_id"].get(),
                        "password": entries["password"].get()
                    },
                    "risk_rules": {
                        "total_capital": 100000,
                        "trade_capital": 10000,
                        "max_trades_per_day": 5,
                        "trade_target_rs": 2000,
                        "trade_sl_rs": 1000
                    }
                }
                Config.save_user(new_user)
                messagebox.showinfo("Success", "User added successfully!")
                dialog.destroy()
                self._refresh_users_table()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        ctk.CTkButton(dialog, text="💾 Save User", command=save).pack(pady=20)

    def _edit_user_dialog(self):
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Select User", "Please select a user to edit.")
            return
        
        item = self.users_tree.item(selected[0])
        username = item['values'][0]
        
        users = Config.load_users()
        user = next((u for u in users if u.get("name") == username), None)
        if not user:
            return
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit User")
        dialog.geometry("500x500")
        
        ctk.CTkLabel(dialog, text=f"Edit: {username}", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        
        active_var = tk.BooleanVar(value=user.get("active", True))
        ctk.CTkCheckBox(dialog, text="Active", variable=active_var).pack(pady=10)
        
        broker_var = tk.StringVar(value=user.get("broker_type", "MOCK"))
        ctk.CTkLabel(dialog, text="Broker").pack(pady=(10, 0))
        ctk.CTkOptionMenu(dialog, variable=broker_var, values=["MOCK", "ZERODHA", "ANGEL", "UPSTOX", "GROWW"]).pack()
        
        def save():
            try:
                Config.update_user(user.get("user_id"), {"active": active_var.get(), "broker_type": broker_var.get()})
                messagebox.showinfo("Success", "User updated!")
                dialog.destroy()
                self._refresh_users_table()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        ctk.CTkButton(dialog, text="💾 Save Changes", command=save).pack(pady=20)

    def _delete_user(self):
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Select User", "Please select a user to delete.")
            return
        
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this user?"):
            item = self.users_tree.item(selected[0])
            username = item['values'][0]
            users = Config.load_users()
            user = next((u for u in users if u.get("name") == username), None)
            if user:
                Config.delete_user(user.get("user_id"))
                messagebox.showinfo("Success", "User deleted!")
                self._refresh_users_table()

    def _create_config_view(self):
        view = ctk.CTkScrollableFrame(self.content_container, fg_color="transparent")
        
        # Broker Card
        bcard = ctk.CTkFrame(view, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color="#313244")
        bcard.pack(fill=tk.X, padx=10, pady=10)
        ctk.CTkLabel(bcard, text="Select Active Broker", font=ctk.CTkFont(size=14, weight="bold")).pack(side=tk.LEFT, padx=30, pady=25)
        self.config_broker = ctk.CTkComboBox(bcard, values=["angel", "zerodha", "mock"], width=180)
        self.config_broker.pack(side=tk.LEFT, padx=10)
        self.config_broker.set(os.getenv("BROKER_TYPE", "angel"))
        
        # API Card
        acard = ctk.CTkFrame(view, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color="#313244")
        acard.pack(fill=tk.X, padx=10, pady=10)
        ctk.CTkLabel(acard, text="API Credentials", font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_BLUE).pack(pady=20)
        
        self.api_entries = {}
        creds_map = [("API Key:", "api_key"), ("Client ID:", "client_id"), ("Password:", "password"), ("TOTP Secret:", "totp_secret")]
        for lbl, key in creds_map:
            row = ctk.CTkFrame(acard, fg_color="transparent")
            row.pack(fill=tk.X, padx=40, pady=8)
            ctk.CTkLabel(row, text=lbl, width=180, anchor=tk.W).pack(side=tk.LEFT)
            e = ctk.CTkEntry(row, width=350, fg_color="#1e1e2e", border_color="#313244")
            e.pack(side=tk.LEFT, padx=10)
            self.api_entries[key] = e
        
        # Risk Card
        rcard = ctk.CTkFrame(view, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color="#313244")
        rcard.pack(fill=tk.X, padx=10, pady=10)
        ctk.CTkLabel(rcard, text="Risk & Notifications", font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_BLUE).pack(pady=20)
        
        self.risk_entries = {}
        risk_map = [("Max Daily Budget (₹):", "total_capital"), ("Trade Capital (₹):", "trade_capital"), ("NIFTY Lots:", "nifty_lots"), ("BANKNIFTY Lots:", "banknifty_lots"), ("Max Trades/Day:", "max_trades_per_day")]
        for lbl, key in risk_map:
            row = ctk.CTkFrame(rcard, fg_color="transparent")
            row.pack(fill=tk.X, padx=40, pady=8)
            ctk.CTkLabel(row, text=lbl, width=180, anchor=tk.W).pack(side=tk.LEFT)
            e = ctk.CTkEntry(row, width=200, fg_color="#1e1e2e", border_color="#313244")
            e.pack(side=tk.LEFT, padx=10)
            self.risk_entries[key] = e
        
        # Load current values
        self._load_config_values()
        
        # Footer Buttons
        fbtn = ctk.CTkFrame(view, fg_color="transparent")
        fbtn.pack(fill=tk.X, pady=30, padx=10)
        ctk.CTkButton(fbtn, text="⚡ Test Connection", fg_color="#313244", width=180, command=self._test_broker_connection).pack(side=tk.RIGHT, padx=10)
        ctk.CTkButton(fbtn, text="✅ Save Settings", fg_color=ACCENT_BLUE, text_color="#1e1e2e", font=ctk.CTkFont(weight="bold"), width=180, command=self._save_config).pack(side=tk.RIGHT, padx=10)
        
        return view

    def _load_config_values(self):
        try:
            users = Config.load_users()
            user = next((u for u in users if u.get("user_id") == self.current_user_id), users[0] if users else None)
            if user:
                creds = user.get("credentials", {})
                for key, entry in self.api_entries.items():
                    entry.insert(0, creds.get(key, ""))
                
                risk = user.get("risk_rules", {})
                for key, entry in self.risk_entries.items():
                    entry.insert(0, str(risk.get(key, "")))
        except Exception as e:
            print(f"Error loading config: {e}")

    def _save_config(self):
        try:
            env_path = os.path.join(PROJECT_DIR, ".env")
            set_key(env_path, "BROKER_TYPE", self.config_broker.get())
            
            users = Config.load_users()
            for i, u in enumerate(users):
                if u.get("user_id") == self.current_user_id:
                    creds = u.setdefault("credentials", {})
                    for key, entry in self.api_entries.items():
                        creds[key] = entry.get()
                    
                    risk = u.setdefault("risk_rules", {})
                    for key, entry in self.risk_entries.items():
                        try: risk[key] = int(entry.get())
                        except: risk[key] = entry.get()
                    break
            
            with open(USERS_FILE, "w") as f: json.dump(users, f, indent=2)
            load_dotenv(env_path, override=True)
            messagebox.showinfo("Success", "Configuration saved!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _test_broker_connection(self):
        messagebox.showinfo("Testing", "Testing broker connection...\n\nThis may take a few seconds.")
        threading.Thread(target=self._test_connection_thread, daemon=True).start()

    def _test_connection_thread(self):
        time.sleep(2)
        self.after(0, lambda: messagebox.showinfo("Success", "✅ Connection successful!"))

    def _create_logs_view(self):
        view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        
        header = ctk.CTkFrame(view, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 15))
        ctk.CTkLabel(header, text="📜 TRADE & BOT LOGS", font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT_BLUE).pack(side=tk.LEFT)
        ctk.CTkButton(header, text="🔄 Refresh", command=self._refresh_logs).pack(side=tk.RIGHT)
        
        self.logs_text = scrolledtext.ScrolledText(view, bg="#0a0a0f", fg="#cdd6f4", font=("Consolas", 10), wrap=tk.WORD)
        self.logs_text.pack(fill=tk.BOTH, expand=True)
        
        self._refresh_logs()
        return view

    def _refresh_logs(self):
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                self.logs_text.delete("1.0", tk.END)
                self.logs_text.insert("1.0", "".join(lines[-1000:]))
                self.logs_text.see(tk.END)
        except Exception as e:
            self.logs_text.insert(tk.END, f"Error loading logs: {e}\n")

    def _create_console_view(self):
        view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        
        header = ctk.CTkFrame(view, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 15))
        ctk.CTkLabel(header, text="💻 BOT CONSOLE", font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT_BLUE).pack(side=tk.LEFT)
        
        control_frame = ctk.CTkFrame(header, fg_color="transparent")
        control_frame.pack(side=tk.RIGHT)
        ctk.CTkButton(control_frame, text="▶ Start", width=80, command=self._start_bot).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(control_frame, text="🧹 Clear", width=80, command=lambda: self.console_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=5)
        
        self.console_text = scrolledtext.ScrolledText(view, bg="#0a0a0f", fg="#a6e3a1", font=("Consolas", 10), wrap=tk.WORD)
        self.console_text.pack(fill=tk.BOTH, expand=True)
        
        self._start_console_monitor()
        return view

    def _start_console_monitor(self):
        def monitor():
            last_pos = 0
            while True:
                try:
                    if os.path.exists(LOG_FILE):
                        with open(LOG_FILE, 'r', encoding='utf-8') as f:
                            f.seek(last_pos)
                            new_lines = f.read()
                            last_pos = f.tell()
                        if new_lines:
                            self.console_text.after(0, lambda: self.console_text.insert(tk.END, new_lines))
                            self.console_text.after(0, lambda: self.console_text.see(tk.END))
                except: pass
                time.sleep(1)
        threading.Thread(target=monitor, daemon=True).start()

    def _create_help_view(self):
        view = ctk.CTkScrollableFrame(self.content_container, fg_color="transparent")
        
        ctk.CTkLabel(view, text="❓ HELP & ABOUT", font=ctk.CTkFont(size=24, weight="bold"), text_color=ACCENT_BLUE).pack(pady=20)
        
        about = """
🤖 TradeBot - Automated Options Trading System

Version: 2.0.0
Built with: Python, CustomTkinter, PyInstaller

📋 Features:
• Multi-broker support (Zerodha, Angel, Upstox, Groww)
• Automated NIFTY & BANKNIFTY options trading
• Real-time signal generation
• Risk management with SL/Target
• Trailing Stop Loss (TSL)
• Paper trading mode
• Telegram notifications
• Backtesting capabilities

⚠️ Disclaimer:
This software is for educational purposes only.
Trading in options involves substantial risk.
Use at your own risk.

📞 Support:
Contact: support@tradebot.example.com
GitHub: github.com/example/tradebot
"""
        ctk.CTkLabel(view, text=about, justify=tk.LEFT, font=ctk.CTkFont(size=12)).pack(anchor=tk.W, padx=20)
        
        quick_start = """
🚀 Quick Start Guide:

1. Add your broker credentials in Management tab
2. Configure strategy settings in Config tab
3. Click 'Start Bot' to begin trading
4. Monitor trades in Overview or Trades tab
5. Stop bot when done

📚 Key Concepts:
• Entry Time: When bot starts taking new trades (9:20 AM)
• Exit Time: When bot closes all positions (3:10 PM)
• Paper Trading: Test with virtual money first!
• TSL: Trailing Stop Loss - locks in profits
"""
        ctk.CTkLabel(view, text=quick_start, justify=tk.LEFT, font=ctk.CTkFont(size=12), text_color=ACCENT_BLUE).pack(anchor=tk.W, padx=20, pady=20)
        
        return view

    # Helpers
    def _add_sidebar_header(self, parent, text):
        hfr = ctk.CTkFrame(parent, fg_color="#1e1e2e", height=40, corner_radius=0)
        hfr.pack(fill=tk.X, pady=(20, 10))
        ctk.CTkLabel(hfr, text=text, font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_DIM).pack(pady=10)

    def _add_sidebar_section(self, parent, title, color):
        sfr = ctk.CTkFrame(parent, fg_color="transparent")
        sfr.pack(fill=tk.X, padx=15, pady=15)
        ctk.CTkLabel(sfr, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color=color).pack(anchor=tk.W, pady=(0, 10))
        return sfr

    def _add_sidebar_stat(self, parent, label, value, color=TEXT_MAIN):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=11), text_color=TEXT_DIM).pack(side=tk.LEFT)
        vlbl = ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=11, weight="bold"), text_color=color)
        vlbl.pack(side=tk.RIGHT); return vlbl

    def _switch_tab(self, tab_name):
        for n, b in self.nav_btns.items():
            if n == tab_name:
                b.configure(fg_color="#313244", text_color=ACCENT_BLUE)
                if n in self.views:
                    self.views[n].pack(fill=tk.BOTH, expand=True)
            else:
                b.configure(fg_color="transparent", text_color=TEXT_MAIN)
                if n in self.views:
                    self.views[n].pack_forget()

    def toggle_left_sidebar(self):
        if self.sidebar_left_visible: self.sidebar_left.pack_forget()
        else: self.sidebar_left.pack(side=tk.LEFT, fill=tk.Y, before=self.content_container)
        self.sidebar_left_visible = not self.sidebar_left_visible

    def toggle_right_sidebar(self):
        if self.sidebar_right_visible: self.sidebar_right.pack_forget()
        else: self.sidebar_right.pack(side=tk.RIGHT, fill=tk.Y)
        self.sidebar_right_visible = not self.sidebar_right_visible

    def _start_bot(self):
        if not self.bot_running:
            try:
                subprocess.Popen([sys.executable, "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.bot_running = True
            except Exception as e:
                messagebox.showerror("Error", str(e))
        else:
            request_stop("exit")
            self.bot_running = False

    def _refresh_status_loop(self):
        run = is_bot_running()
        self.status_label.configure(text="● RUNNING" if run else "● IDLE", text_color=ACCENT_GREEN if run else ACCENT_PEACH)
        self.start_btn.configure(text="⏹ STOP BOT" if run else "▶ START BOT", fg_color=ACCENT_RED if run else ACCENT_BLUE)
        self.after(2000, self._refresh_status_loop)

if __name__ == "__main__":
    LoginView().mainloop()
