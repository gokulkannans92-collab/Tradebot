"""TradeBot Dashboard - Main GUI (Compact ~300 lines)"""

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, ttk as ttk_orig
import time
import queue
import os
import sys
import logging
from typing import Callable, Dict, Any, Tuple
from datetime import datetime
from src.ui.shared import COLORS, IS_DARK, apply_theme, ToastNotification, restore_window_geometry
from src.ui.responsive import get_optimal_window_size, center_window_geometry, ScreenMetrics
from src.ui.dashboard.layout import HeaderManager, FooterManager, SidebarManager, RightSidebarManager
from src.ui.dashboard.constants import ACTIVE_TRADES_FILE
from src.config import UserSettings as UserConfig, UserManager as Config
from src.utils.bot_state import is_bot_running, request_stop, kill_bot_process
from src.utils.audio import AudioManager
from src.ui.lock_screen import LockScreen

# Import all views
from src.ui.views.overview_view import OverviewView
from src.ui.views.trades_view import TradesView
from src.ui.views.management_view import ManagementView
from src.ui.views.config_view import ConfigView
from src.ui.views.logs_view import LogsView
from src.ui.views.console_view import ConsoleView
from src.ui.views.notifications_view import NotificationsView
from src.ui.views.help_view import HelpView
from src.ui.views.market_analysis_view import MarketAnalysisView
from src.ui.views.jarvis_chat_view import JarvisChatView

logger = logging.getLogger("Dashboard")
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TradeBotGUI(ctk.CTk):
    def __init__(self, user_id="user_001", user_name="admin"):
        self._scheduled_ids = [] # MUST initialize before super().__init__
        super().__init__()
        self.title("TradeBot Dashboard")
        win_w, win_h = get_optimal_window_size(1400, 900, 1024, 700, 0.90, 0.90)
        metrics = ScreenMetrics()
        if metrics.is_large_screen:
            self.after(0, lambda: self.state('zoomed'))
            self.geometry(f"{win_w}x{win_h}")
        else:
            self.geometry(center_window_geometry(win_w, win_h))
        self.configure(fg_color=COLORS["bg_panel"])
        
        base_path = getattr(sys, '_MEIPASS', PROJECT_DIR)
        ico_path = os.path.join(base_path, "TradeBot.ico")
        if os.path.exists(ico_path):
            try: self.iconbitmap(ico_path)
            except Exception: pass
        
        self.current_user_name, self.current_user_id = user_name, user_id
        self.current_broker = "ZERODHA"  # Default broker
        self.bot_running, self.views, self.popped_tabs = False, {}, {}
        self.sidebar_left_visible = self.sidebar_right_visible = True
        self.last_active_trades_data, self.all_trades_cache = [], []
        self.last_trades_refresh = self.ui_locked_state = 0
        self.log_queue = queue.Queue()
        
        from src.ui.shared_state import initialize_shared_state
        self.shared_state = initialize_shared_state(self)
        
        # Apply dark theme to Treeview at startup
        apply_theme(True)
        ctk.set_appearance_mode("dark")
        
        # Synchronize SharedState with active user profile on boot
        user_profile = Config.get_user(self.current_user_id)
        if user_profile:
            self.shared_state.load_from_profile(user_profile)
            logger.info(f"Initialized SharedState from profile for {user_name}")

        self.v_nifty_on, self.v_bn_on = self.shared_state.nifty_enabled, self.shared_state.banknifty_enabled
        self.v_fn_on, self.v_paper = self.shared_state.finnifty_enabled, self.shared_state.paper_trading
        self.v_tsl, self.v_kill = tk.BooleanVar(value=True), tk.BooleanVar(value=False)
        
        self.bind("<Control-r>", lambda e: self._refresh_all() if not getattr(self, "ui_locked_state", 0) else "break")
        self.bind("<Control-e>", lambda e: self._export_current() if not getattr(self, "ui_locked_state", 0) else "break")
        
        self._setup_root_layout()
        self.header_manager = HeaderManager(self.header_frame, self)
        self.sidebar_manager = SidebarManager(self.sidebar_left, self)
        self.right_sidebar_manager = RightSidebarManager(self.sidebar_right, self)
        self.footer_manager = FooterManager(self.footer_frame, self)
        self._setup_content_area()
        self._switch_tab("Overview")
        self.after(500, self._deferred_init)
        
        # Setup auto-save for shared state variables
        self._setup_state_auto_save()
        
        try: restore_window_geometry(UserConfig, self)
        except Exception: pass
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_state_auto_save(self):
        """Add traces to shared state variables to auto-update the user profile."""
        settings_to_sync = [
            self.shared_state.min_signals,
            self.shared_state.strategy,
            self.shared_state.paper_trading,
            self.shared_state.candle_timeframe,
            self.shared_state.nifty_enabled,
            self.shared_state.banknifty_enabled,
            self.shared_state.nifty_lot,
            self.shared_state.banknifty_lot,
            self.shared_state.selected_category,
            self.shared_state.selected_instrument,
            self.shared_state.selected_lots,
            self.shared_state.brain_control
        ]
        
        for var in settings_to_sync:
            var.trace_add("write", lambda *a: self._sync_state_to_profile())

    def _sync_state_to_profile(self):
        """Update the UserManager profile with current shared state values."""
        if getattr(self.shared_state, '_loading', False):
            return
            
        # Debounce to avoid rapid file writes
        if hasattr(self, '_sync_timer'):
            self.after_cancel(self._sync_timer)
        
        self._sync_timer = self.after(1000, self._perform_profile_sync)

    def _perform_profile_sync(self):
        """Actually write the updated state to users.json in a background thread."""
        try:
            profile_updates = self.shared_state.to_profile_dict()
            
            def _write_worker():
                try:
                    Config.update_user(self.current_user_id, profile_updates)
                    logger.debug(f"Auto-saved profile updates for {self.current_user_name} in background thread")
                except Exception as e:
                    logger.error(f"Failed to auto-save profile in background thread: {e}")
                    
            import threading
            threading.Thread(target=_write_worker, daemon=True).start()
        except Exception as e:
            logger.error(f"Failed to initiate auto-save profile thread: {e}")

    def _deferred_init(self):
        """Perform one-time initialization tasks after the main window is ready."""
        self._check_bot_status()
        self._refresh_status_loop()
        self._start_throttled_ui_loop()
        ToastNotification(self, "Dashboard Ready", success=True)

    def _on_closing(self):
        if getattr(self, "ui_locked_state", 0):
            messagebox.showwarning("Locked", "Workstation is locked. Please enter your password to unlock before exiting.")
            return
        if is_bot_running() and messagebox.askyesno("Exit", "Bot is running. Stop and exit?"):
            request_stop("exit")
            self.after(2000, self._force_cleanup_and_exit)
        else:
            self._force_cleanup_and_exit()
    
    def _force_cleanup_and_exit(self):
        self._cancel_all_loops()
        kill_bot_process()
        from src.utils.bot_state import clear_pid
        clear_pid()
        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

    def after(self, ms: int, func: Callable, *args) -> str:
        """Override after to track tasks for safe cancellation."""
        task_id = super().after(ms, func, *args)
        if hasattr(self, '_scheduled_ids'):
            self._scheduled_ids.append(task_id)
        return task_id

    def _cancel_all_loops(self):
        """Cancel all scheduled after() callbacks to prevent 'invalid command name' errors."""
        for after_id in self._scheduled_ids:
            try: self.after_cancel(after_id)
            except Exception: pass
        self._scheduled_ids.clear()

    def _logout(self):
        if is_bot_running() and messagebox.askyesno("Logout", "Stop bot and logout?"):
            request_stop("exit")
            self.after(2000, self._cleanup_and_logout)
        elif messagebox.askyesno("Logout", "Are you sure?"):
            self._cleanup_and_logout()
    
    def _cleanup_and_logout(self):
        self._cancel_all_loops()
        kill_bot_process()
        self.destroy()
        from gui_launcher import LoginView
        LoginView().mainloop()

    def _lock_dashboard(self):
        """Activates the full-screen lock overlay."""
        AudioManager.play_click()
        self.ui_locked_state = 1
        LockScreen(self, self.current_user_id, self.current_user_name, self._on_unlock)
        logger.info(f"Workstation locked by {self.current_user_name}")

    def _on_unlock(self):
        """Callback for when the lock screen is successfully dismissed."""
        self.ui_locked_state = 0
        from src.ui.shared import ToastNotification
        ToastNotification(self, "Welcome back!", success=True)
        logger.info(f"Workstation unlocked by {self.current_user_name}")

    # ── Jarvis AI Control ──────────────────────────────────────────────

    def _on_brain_control_toggle(self):
        """Handle AI MARKET SELECTION toggle fired from SidebarManager."""
        state = self.shared_state

        if state.brain_control.get():
            # AI Mode Turned ON
            ToastNotification(self, "🧠 Jarvis AI taking control...")

            # Switch to Jarvis AI tab (creates view if not yet instantiated)
            self._switch_tab("Jarvis AI")

            # Delay slightly to allow tab render, then run analysis + start bot
            self.after(600, self._start_jarvis_ai_mode)
        else:
            # AI Mode Turned OFF
            if self.bot_running:
                if messagebox.askyesno("AI Mode Off", "Stop the bot?"):
                    self._stop_bot()
            ToastNotification(self, "AI Mode disabled")

    def _start_jarvis_ai_mode(self):
        """Run Jarvis AI market analysis and auto-start the bot."""
        # Access Jarvis view via views dict (self.jarvis_chat_view does NOT exist)
        jarvis_view = self.views.get("Jarvis AI")

        # If view not yet created, force creation now
        if jarvis_view is None:
            self._switch_tab("Jarvis AI")
            jarvis_view = self.views.get("Jarvis AI")

        if jarvis_view and hasattr(jarvis_view, "run_market_analysis"):
            # IMPORTANT: run_market_analysis() blocks for up to 60 seconds (Gemini API call).
            # Run it in a background thread so the GUI does NOT freeze.
            import threading

            def _run_in_background():
                analysis_result = jarvis_view.run_market_analysis()
                # Schedule the follow-up actions back on the main tkinter thread
                self.after(0, lambda: self._on_ai_analysis_complete(analysis_result))

            threading.Thread(target=_run_in_background, daemon=True).start()
        else:
            ToastNotification(self, "⚠️ Jarvis AI view not available", success=False)

    def _on_ai_analysis_complete(self, analysis_result):
        """
        Called on the main thread after AI market analysis completes.
        Updates shared state and auto-starts the bot if market is open.
        """
        if analysis_result:
            # Update shared state with AI-selected market
            self.shared_state.selected_category.set(
                analysis_result.get("category", "Options")
            )
            self.shared_state.selected_instrument.set(
                analysis_result.get("instrument", "NIFTY")
            )
            self.shared_state.selected_lots.set(
                str(analysis_result.get("lots", "1"))
            )
            
            # Check market hours before auto-starting
            from src.config import Settings
            if not Settings.is_market_open():
                market_time = Settings.MARKET_OPEN.strftime("%I:%M %p")
                ToastNotification(
                    self,
                    f"🧠 AI Selection: {analysis_result.get('instrument')}\nMarket Closed. Scheduled for {market_time}.",
                    success=True
                )
                
                # Schedule auto-start for market open (check every minute)
                def _wait_for_market():
                    if Settings.is_market_open():
                        self._auto_start_bot()
                    else:
                        # Re-check in 60 seconds
                        self.after(60000, _wait_for_market)
                
                self.after(60000, _wait_for_market)
                return

            ToastNotification(
                self,
                f"🧠 AI Selected: {analysis_result.get('instrument')} "
                f"(Confidence: {analysis_result.get('confidence', 0):.0f}%)",
                success=True
            )
        else:
            ToastNotification(self, "⚠️ AI analysis failed — using current market settings")

        # Auto-start bot with --brain flag, skipping the confirmation dialog
        self._auto_start_bot()

    def _auto_start_bot(self):
        """
        Start the bot in AI brain mode WITHOUT showing a confirmation dialog.
        Called only from the AI auto-start flow; user confirmed via the AI toggle.
        """
        if is_bot_running() or self.bot_running:
            ToastNotification(self, "⚠️ Bot is already running!", success=False)
            if hasattr(self, 'sidebar_manager'):
                self.sidebar_manager.set_bot_status(running=True)
            return

        AudioManager.play_click()

        try:
            import subprocess
            import threading
            from src.utils.paths import get_path
            from src.utils.bot_state import write_pid

            python_exe = sys.executable
            log_file = get_path("trade_bot.log")

            env = os.environ.copy()
            env["PYTHONPATH"] = PROJECT_DIR + os.pathsep + env.get("PYTHONPATH", "")
            env["LAUNCHED_FROM_DASHBOARD"] = "1"

            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            if hasattr(self, 'sidebar_manager') and self.sidebar_manager.start_btn:
                self.sidebar_manager.start_btn.configure(
                    text="⏳ Starting...",
                    state="disabled",
                    fg_color="#666666"
                )

            ToastNotification(self, "🧠 AI Bot starting...")
            self._switch_tab("Console")

            is_frozen = getattr(sys, 'frozen', False)
            cmd = [python_exe, "--bot"] if is_frozen else [python_exe, "main.py", "--bot"]

            cat = self.shared_state.selected_category.get()
            inst = self.shared_state.selected_instrument.get()
            lots = self.shared_state.selected_lots.get()

            if not cat or not inst or not lots:
                ToastNotification(self, "⚠️ AI failed to set market — please select manually", success=False)
                if hasattr(self, 'sidebar_manager'):
                    self.sidebar_manager.set_bot_status(running=False)
                return

            cmd.extend(["--category", cat, "--instrument", inst, "--lots", lots, "--brain"])
            logger.info("🧠 AI BRAIN: Starting bot with" + " ".join(cmd[-6:]))

            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            self.bot_process = subprocess.Popen(
                cmd, cwd=PROJECT_DIR, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=creationflags,
                text=True, encoding='utf-8', errors='replace', bufsize=1
            )

            threading.Thread(target=self._read_bot_output,
                             args=(self.bot_process, log_file), daemon=True).start()
            write_pid(self.bot_process.pid)

            start_time = time.time()
            def monitor_bot():
                self.bot_process.wait()
                exit_code = self.bot_process.returncode
                if (time.time() - start_time) < 7 and exit_code != 0:
                    self.after(500, lambda: self._switch_tab("Console"))
                    self.after(600, lambda: ToastNotification(
                        self, "Bot failed to start. Check Console.", success=False))
                self.after(100, self._check_bot_status)

            threading.Thread(target=monitor_bot, daemon=True).start()
            ToastNotification(self, "🧠 AI Bot started!", success=True)

        except Exception as e:
            logger.error(f"AI auto-start failed: {e}", exc_info=True)
            ToastNotification(self, f"⚠️ Failed to start bot: {e}", success=False)
            if hasattr(self, 'sidebar_manager'):
                self.sidebar_manager.set_bot_status(running=False)

    # ──────────────────────────────────────────────────────────────────

    def _setup_root_layout(self):
        for i in range(3): self.grid_rowconfigure(i, weight=(0,1,0)[i])
        for i in range(3): self.grid_columnconfigure(i, weight=(0,1,0)[i])
        self.header_frame = ctk.CTkFrame(self, height=65, corner_radius=0, fg_color=COLORS["bg_panel"])
        self.header_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=1, column=0, columnspan=3, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)  # Ensure vertical expansion
        self.main_container.grid_columnconfigure(0, weight=0)  # Left sidebar
        self.main_container.grid_columnconfigure(1, weight=1)  # Center content (EXPAND)
        self.main_container.grid_columnconfigure(2, weight=0)  # Right sidebar
        
        self.sidebar_left = ctk.CTkFrame(self.main_container, width=270, fg_color=COLORS["bg_panel"], border_width=1, border_color=COLORS["border"])
        self.sidebar_left.grid(row=0, column=0, sticky="ns")
        
        self.sidebar_right = ctk.CTkFrame(self.main_container, width=200, fg_color=COLORS["bg_panel"], border_width=1, border_color=COLORS["border"])
        self.sidebar_right.grid(row=0, column=2, sticky="ns")
        
        self.footer_frame = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=COLORS["bg_card"])
        self.footer_frame.grid(row=2, column=0, columnspan=3, sticky="ew")

    def _toggle_theme(self):
        global IS_DARK; IS_DARK = not IS_DARK; apply_theme(IS_DARK)
        if hasattr(self, 'theme_btn'): self.theme_btn.configure(text="☀️" if IS_DARK else "🌙")
        for win in self.popped_tabs.values():
            try: win.configure(fg_color="#0a0a0f" if IS_DARK else "#f8f9fa")
            except Exception: pass
        ToastNotification(self, "Theme: Dark" if IS_DARK else "Theme: Light")

    def _update_clock(self):
        if hasattr(self, 'clock_label'): self.clock_label.configure(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._schedule(1000, self._update_clock)

    def _refresh_all(self):
        ToastNotification(self, "Refreshing...")
        for attr in ['_refresh_overview_data', '_refresh_trades_table', '_refresh_users_table', '_refresh_trade_logs']:
            if hasattr(self, attr): getattr(self, attr)()

    def _export_current(self):
        """Export the current dashboard data to a CSV file."""
        try:
            data_source = None
            filename = None

            if self.last_active_trades_data:
                data_source = self.last_active_trades_data
                filename = f"TradeBot_active_trades_{datetime.now():%Y%m%d_%H%M%S}.csv"
            elif self.all_trades_cache:
                data_source = self.all_trades_cache
                filename = f"TradeBot_all_trades_{datetime.now():%Y%m%d_%H%M%S}.csv"

            if not data_source:
                messagebox.showinfo("Export", "No current dashboard data is available to export.")
                return

            export_path = os.path.join(os.path.expanduser("~"), filename)
            with open(export_path, "w", newline="", encoding="utf-8") as csv_file:
                if isinstance(data_source, list) and data_source:
                    first_item = data_source[0]
                    if isinstance(first_item, dict):
                        import csv
                        writer = csv.DictWriter(csv_file, fieldnames=list(first_item.keys()))
                        writer.writeheader()
                        for row in data_source:
                            writer.writerow(row)
                    else:
                        csv_file.write("\n".join(str(item) for item in data_source))
                else:
                    csv_file.write(str(data_source))

            messagebox.showinfo("Export", f"Current dashboard data exported to:\n{export_path}")
            logger.info(f"Exported current dashboard data to {export_path}")
        except Exception as e:
            logger.error(f"Failed to export current data: {e}", exc_info=True)
            messagebox.showerror("Export Failed", f"Unable to export current data. {e}")

    def _setup_content_area(self):
        self.content_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_container.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        
        self._view_container = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self._view_container.pack(fill=tk.BOTH, expand=True)
        # CRITICAL: Configure grid weights so child views can expand
        self._view_container.grid_columnconfigure(0, weight=1)
        self._view_container.grid_rowconfigure(0, weight=1)
        self.view_factories = {
            "Overview": lambda p: self._create_view(p, OverviewView),
            "Jarvis AI": lambda p: self._create_view(p, JarvisChatView),
            "Market Analysis": lambda p: self._create_view(p, MarketAnalysisView),
            "Active Trades": lambda p: self._create_view(p, TradesView),
            "Management": lambda p: self._create_view(p, ManagementView),
            "Config": lambda p: self._create_view(p, ConfigView),
            "Notifications": lambda p: self._create_view(p, NotificationsView),
            "Trade History": lambda p: self._create_view(p, LogsView),
            "Console": lambda p: self._create_view(p, ConsoleView),
            "Help": lambda p: self._create_view(p, HelpView)
        }
        self.views = {}

    def _create_view(self, parent, view_class):
        try:
            view = view_class(parent or self.content_container, controller=self, is_main=True)
            return view
        except Exception as e:
            logger.error(f"Failed to load view {view_class.__name__}: {e}")
            import traceback
            traceback.print_exc()
            error_frame = ctk.CTkFrame(parent or self.content_container)
            ctk.CTkLabel(error_frame, text=f"Error loading {view_class.__name__}: {e}", 
                        font=ctk.CTkFont(size=14), text_color="red", wraplength=400).pack(pady=20)
            return error_frame

    def _add_tab_header(self, parent, title, icon, allow_popout=True, is_main=True):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill=tk.X, pady=(0, 15))
        ctk.CTkLabel(f, text=f"{icon} {title.upper()}", font=ctk.CTkFont(size=18, weight="bold"), text_color=COLORS["accent_blue"]).pack(side=tk.LEFT)
        
        # Only allow pop-out for Trade History
        if allow_popout and is_main and title.upper() == "TRADE HISTORY":
            ctk.CTkButton(f, text="↗ Pop Out", width=90, command=lambda: self._pop_out_window(title), fg_color=COLORS["bg_card"]).pack(side=tk.RIGHT)
        return f

    def _pop_in_window(self, tab_name):
        if tab_name in self.popped_tabs:
            try: self.popped_tabs.pop(tab_name).destroy()
            except Exception: pass
        self._switch_tab(tab_name); self.focus_force()

    def _pop_out_window(self, tab_name):
        if tab_name in self.popped_tabs: return
        from src.ui.responsive import get_optimal_window_size
        win = ctk.CTkToplevel(self); win.title(f"TradeBot - {tab_name}")
        w, h = get_optimal_window_size(1100, 700, 800, 500, 0.85, 0.85)
        win.geometry(f"{w}x{h}")
        self._apply_window_theme(win); win.lift(); win.focus_force()
        
        # Maximize for Trade History as requested
        if tab_name.upper() == "TRADE HISTORY":
            win.after(100, lambda: win.state('zoomed'))
        container = ctk.CTkFrame(win, fg_color="transparent"); container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.popped_tabs[tab_name] = win
        win.protocol("WM_DELETE_WINDOW", lambda: self._on_popped_close(tab_name))
        win.after(100, lambda: self._render_popout(tab_name, container))

    def _render_popout(self, tab_name, container):
        if tab_name in self.view_factories:
            try: view = self.view_factories[tab_name](container, is_main=False); view.pack(fill=tk.BOTH, expand=True)
            except Exception: pass

    def _on_popped_close(self, name):
        if name in self.popped_tabs:
            try: self.popped_tabs[name].destroy()
            except Exception: pass
            self.popped_tabs.pop(name, None)

    def _apply_window_theme(self, window):
        try: window.configure(fg_color="#0a0a0f" if IS_DARK else "#f8f9fa")
        except Exception: pass

    def _switch_tab(self, name):
        self.right_sidebar_manager.set_active_tab(name)
        apply_theme(True)  # Ensure dark theme before showing view
        if name not in self.views and name in self.view_factories:
            try:
                self.views[name] = self.view_factories[name](self._view_container)
            except Exception as e:
                logger.error(f"Failed to create view {name}: {e}")
                import traceback
                traceback.print_exc()
        if name in self.views:
            for v in self.views.values():
                v.grid_remove()
            self.views[name].grid(row=0, column=0, sticky="nsew")

    def toggle_left_sidebar(self):
        if self.sidebar_left_visible:
            self.sidebar_left.grid_forget()
        else:
            self.sidebar_left.grid(row=0, column=0, sticky="ns")
        self.sidebar_left_visible = not self.sidebar_left_visible

    def toggle_right_sidebar(self):
        if self.sidebar_right_visible:
            self.sidebar_right.grid_forget()
        else:
            self.sidebar_right.grid(row=0, column=2, sticky="ns")
        self.sidebar_right_visible = not self.sidebar_right_visible

    def _refresh_status_loop(self):
        try:
            if not self.winfo_exists(): return
        except Exception: return
        self._check_bot_status()
        self.after(1000, self._refresh_status_loop)

    def _start_throttled_ui_loop(self):
        """Start the throttled UI rendering loop (4 Hz refresh)."""
        self._throttled_ui_update_loop()
        
    def _throttled_ui_update_loop(self):
        try:
            if not self.winfo_exists(): return
        except Exception: return
        
        try:
            mtime = os.path.getmtime(ACTIVE_TRADES_FILE) if os.path.exists(ACTIVE_TRADES_FILE) else 0
            if mtime != getattr(self, '_last_active_trades_mtime', 0):
                self._last_active_trades_mtime = mtime
                self._load_active_trades_async()
        except Exception:
            pass
            
        self.after(250, self._throttled_ui_update_loop)

    def _load_active_trades_async(self):
        """Asynchronously load active trades file to prevent GUI lags."""
        import threading
        import json
        
        def _read_worker():
            try:
                if not os.path.exists(ACTIVE_TRADES_FILE):
                    self.after(0, self._on_active_trades_loaded, [], 0.0)
                    return
                    
                with open(ACTIVE_TRADES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                active_trades = []
                if isinstance(data, dict):
                    active_trades = data.get("active_trades", [])
                elif isinstance(data, list):
                    active_trades = data
                    
                if not isinstance(active_trades, list):
                    active_trades = []
                    
                active_pnl = sum(float(t.get('pnl', 0)) for t in active_trades if isinstance(t, dict))
                self.after(0, self._on_active_trades_loaded, active_trades, active_pnl)
            except Exception as e:
                logger.debug(f"Failed to load active trades off-thread: {e}")
                
        threading.Thread(target=_read_worker, daemon=True).start()

    def _on_active_trades_loaded(self, active_trades, active_pnl):
        try:
            if not self.winfo_exists(): return
        except Exception: return
        
        self.last_active_trades_data = active_trades
        
        if hasattr(self, 'sidebar_manager'):
            max_trades = getattr(self.shared_state, 'max_trades', None)
            if max_trades is None:
                from src.config import Settings
                max_trades = Settings.MAX_TRADES
            self.sidebar_manager.update_trades_counter(len(active_trades), max_trades)
            self.sidebar_manager.update_pnl(active_pnl)
            
        self.refresh_overview_data()
        self.refresh_trades_table()

    def _check_bot_status(self):
        run = is_bot_running()
        # Force UI update if state changes or if we're not sure
        if self.bot_running == run: return
        self.bot_running = run
        
        # Update shared state so config view locks/unlocks automatically
        try:
            self.shared_state.bot_running.set(run)
        except Exception:
            pass
            
        if hasattr(self, 'sidebar_manager'): 
            self.sidebar_manager.set_bot_status(running=run)
        
        if hasattr(self, 'footer_manager'):
            self.footer_manager.set_status_message("● RUNNING" if run else "● IDLE", error=False)
            
        # Refresh management table to update action button visibility
        self.refresh_users_table()

    def _start_bot(self, auto_brain_mode=False):
        if is_bot_running() or self.bot_running:
            ToastNotification(self, "⚠️ Bot is already running!", success=False)
            if hasattr(self, 'sidebar_manager'):
                self.sidebar_manager.set_bot_status(running=True)
            return

        if not messagebox.askyesno("Start Bot", "Start trading bot?"):
            return
        
        AudioManager.play_click()

        try:
            import subprocess
            import sys
            import os
            import threading
            from src.utils.paths import get_path
            from src.utils.bot_state import write_pid
            
            # 1. Setup paths and environment
            python_exe = sys.executable
            log_file = get_path("trade_bot.log")
            
            env = os.environ.copy()
            # Ensure PROJECT_DIR is in PYTHONPATH for submodule imports
            env["PYTHONPATH"] = PROJECT_DIR + os.pathsep + env.get("PYTHONPATH", "")
            env["LAUNCHED_FROM_DASHBOARD"] = "1"
            
            # Ensure the directory for logs exists
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # 2. Immediate UI Feedback
            if hasattr(self, 'sidebar_manager') and self.sidebar_manager.start_btn:
                self.sidebar_manager.start_btn.configure(
                    text="⏳ Starting...", 
                    state="disabled",
                    fg_color="#666666"
                )
            
            ToastNotification(self, "Bot starting... Please wait.")
            self._switch_tab("Console")

            # 3. Launch the bot process
            # Determine if running as absolute EXE or python script
            is_frozen = getattr(sys, 'frozen', False)
            
            # Construct base command
            if is_frozen:
                cmd = [python_exe, "--bot"]
            else:
                cmd = [python_exe, "main.py", "--bot"]
            
            # Append focused market from shared state
            cat = self.shared_state.selected_category.get()
            inst = self.shared_state.selected_instrument.get()
            lots = self.shared_state.selected_lots.get()

            # VALIDATION: Block if market focus is missing
            if not cat or not inst or not lots:
                messagebox.showerror("Selection Required", "Please select a Market Category, Target Instrument, and Lot size before starting the bot.")
                # Reset start button state
                if hasattr(self, 'sidebar_manager') and self.sidebar_manager.start_btn:
                    self.sidebar_manager.set_bot_status(running=False)
                return
            
            cmd.extend([
                "--category", cat,
                "--instrument", inst,
                "--lots", lots
            ])

            # Append --brain flag if AI mode is active
            if auto_brain_mode or self.shared_state.brain_control.get():
                cmd.append("--brain")
                logger.info("🧠 AI MARKET SELECTION: --brain flag appended to bot command")
            
            logger.info("=" * 60)
            logger.info("  TRADEBOT INITIALIZATION STARTED")
            logger.info(f"  UI PARAMS - Category: {cat} | Instrument: {inst} | Lots: {lots}")
            logger.info("=" * 60)

            # Use PIPE to capture stdout/stderr in real-time
            try:
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                self.bot_process = subprocess.Popen(
                    cmd,
                    cwd=PROJECT_DIR,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, # Merge stderr into stdout
                    creationflags=creationflags,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1 # Line buffered
                )
                
                # Start real-time log reader thread
                threading.Thread(target=self._read_bot_output, args=(self.bot_process, log_file), daemon=True).start()
                
            except Exception as e:
                logger.error(f"Failed to spawn bot process: {e}")
                raise

            # 4. Immediate PID registration so UI polling detects success instantly
            write_pid(self.bot_process.pid)

            try:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{timestamp} [GUI] INFO - TradeBot system starting...\n")
            except Exception: pass

            # 5. Monitor thread to clean up if bot exits unexpectedly
            start_time = time.time()
            def monitor_bot():
                self.bot_process.wait()
                exit_code = self.bot_process.returncode
                duration = time.time() - start_time
                
                # If bot crashed early (within 7 seconds), it's likely a login or config error
                if duration < 7 and exit_code != 0:
                    logger.error(f"Bot exited early with code {exit_code} (Duration: {duration:.1f}s)")
                    self.after(500, lambda: self._switch_tab("Console"))
                    self.after(600, lambda: ToastNotification(self, "Bot failed to start. Check Console for details.", success=False))
                
                # On exit, trigger a status check to reset UI
                self.after(100, self._check_bot_status)
            
            threading.Thread(target=monitor_bot, daemon=True).start()
            
            # Final success toast
            ToastNotification(self, "Bot started successfully!", success=True)
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to start bot: {e}")
            
            # Reset UI state on failure
            if hasattr(self, 'sidebar_manager'):
                self.sidebar_manager.set_bot_status(running=False)

    def test_broker_connection(self, broker_type: str, creds: Dict[str, str]) -> Tuple[bool, str]:
        """Utility for Config view to test credentials without starting bot."""
        try:
            logger.info(f"Testing connection for {broker_type}...")
            if broker_type == "angel":
                from src.broker.angel_broker import AngelBroker
                b = AngelBroker(
                    api_key=creds.get("api_key", ""),
                    client_id=creds.get("client_id", ""),
                    password=creds.get("password", ""),
                    totp_secret=creds.get("totp_secret", ""),
                    is_paper_trading=False # Real login test
                )
            else:
                return False, f"Provider {broker_type} not supported for testing yet."
            
            # The AngelBroker.login() method now has robust error capturing
            success = b.login()
            if success:
                return True, "Authenticated"
            return False, "Login failed. Check logs for tips."
        except Exception as e:
            logger.error(f"Test connection failure: {e}")
            return False, str(e)

    def test_ai_connection(self, provider: str, key: str) -> Tuple[bool, str]:
        """Utility for Config view to test AI API keys."""
        try:
            logger.info(f"Testing AI connection for {provider}...")
            from src.brain.scoring.llm_analyzer import LLMAnalyzer
            import asyncio
            
            analyzer = LLMAnalyzer()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success, message = loop.run_until_complete(analyzer.test_connection(provider, key))
            loop.close()
            
            return success, message
        except Exception as e:
            logger.error(f"AI test connection failure: {e}")
            return False, str(e)

    def _read_bot_output(self, process, log_file):
        """Background thread to read bot process output and feed console queue."""
        logger.info(f"Log stream reader started for PID {process.pid}")
        try:
            # We also write to the file so it remains the source of truth
            with open(log_file, 'a', encoding='utf-8', buffering=1) as f:
                for line in iter(process.stdout.readline, ''):
                    if not line: break
                    
                    # 1. Feed the UI queue for instant streaming
                    if hasattr(self, 'log_queue'):
                        self.log_queue.put(line)
                    
                    # 2. Write to the permanent log file
                    f.write(line)
                    f.flush()
        except Exception as e:
            logger.error(f"Error in log stream reader: {e}")
        finally:
            logger.info(f"Log stream reader stopped for PID {process.pid}")

    def _stop_bot(self):
        try:
            # Prevent duplicate clicks
            if getattr(self, '_stopping', False):
                return
            
            # 1. Check for active trades
            active_count = len(getattr(self, 'last_active_trades_data', []))
            stop_preference = "keep"
            
            if active_count > 0:
                # 3-way Confirmation: Yes(Close), No(Keep), Cancel(Abort)
                ans = messagebox.askyesnocancel(
                    "Stop Bot - Active Trades", 
                    f"Warning: {active_count} active trades detected!\n\n"
                    "YES: Stop Bot and FORCE CLOSE all positions\n"
                    "NO: Stop Bot and KEEP positions open in broker\n"
                    "CANCEL: Abort stopping"
                )
                if ans is None: # Cancel
                    return
                if ans is True: # Yes -> Close All
                    stop_preference = "close_all"
                else: # No -> Keep running
                    stop_preference = "keep"
            else:
                # Standard simple confirmation
                if not messagebox.askyesno("Stop Bot", "Stop all trading?"):
                    return
            
            AudioManager.play_click()
            
            self._stopping = True
            
            # Immediate UI feedback
            if hasattr(self, 'sidebar_manager') and self.sidebar_manager.start_btn:
                self.sidebar_manager.start_btn.configure(
                    text="⏳ Stopping...", 
                    state="disabled",
                    fg_color="#666666"
                )
            
            # Log immediately and force console update
            from datetime import datetime
            from src.utils.paths import get_path
            log_file = get_path("trade_bot.log")
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
            
            # Boxed Header for Stop Request
            separator = "=" * 60
            log_entries = [
                f"\n{timestamp} [GUI] INFO - {separator}",
                f"{timestamp} [GUI] INFO -   TRADEBOT STOP REQUESTED ({stop_preference.upper()})",
                f"{timestamp} [GUI] INFO - {separator}\n"
            ]
            
            try:
                with open(log_file, "a", encoding='utf-8') as f:
                    for entry in log_entries:
                        f.write(entry + "\n")
            except Exception: pass
            
            # Send stop signal
            request_stop(stop_preference)
            
            # Auto-switch to Console view
            self._switch_tab("Console")
            
            # Force console refresh
            if hasattr(self, 'console_view'):
                self.console_view._reload_console()
                self.console_view._reload_console()
            
            ToastNotification(self, "Stop signal sent! Waiting for bot to stop...")
            
            # Schedule non-blocking UI reset using after() polling (no sleep threads)
            def _poll_for_stop(remaining_checks=30):
                """Poll bot status every 500ms via after() — no blocking thread needed."""
                try:
                    if not is_bot_running() or remaining_checks <= 0:
                        # Bot has stopped (or timed out) — reset UI on main thread
                        self._stopping = False
                        if hasattr(self, 'sidebar_manager'):
                            self.sidebar_manager.set_bot_status(False)
                        if hasattr(self, 'console_view'):
                            self.console_view._reload_console()
                        ToastNotification(self, "Bot stopped successfully!")
                    else:
                        # Still running — schedule next check
                        self.after(500, lambda: _poll_for_stop(remaining_checks - 1))
                except Exception as e:
                    logger.error(f"Error in _poll_for_stop: {e}")
                    self._stopping = False

            self.after(500, lambda: _poll_for_stop())
        
        except Exception as e:
            logger.error(f"Error in _stop_bot: {e}")
            self._stopping = False
            if hasattr(self, 'sidebar_manager') and self.sidebar_manager.start_btn:
                self.sidebar_manager.start_btn.configure(text="▶ START BOT", state="normal")

    def _pause_my_trades(self): ToastNotification(self, "Trading paused")
    def _resume_my_trades(self): ToastNotification(self, "Trading resumed")

    # View navigation methods (called by HeaderManager/RightSidebarManager)
    def _show_overview(self): self._switch_tab("Overview")
    def _show_jarvis(self): self._switch_tab("Jarvis AI")
    def _show_market_analysis(self): self._switch_tab("Market Analysis")
    def _show_trades(self): self._switch_tab("Active Trades")
    def _show_management(self): self._switch_tab("Management")
    def _show_config(self): self._switch_tab("Config")
    def _show_notifications(self): self._switch_tab("Notifications")
    def _show_logs(self): self._switch_tab("Trade History")
    def _show_console(self): self._switch_tab("Console")
    def _show_help(self): self._switch_tab("Help")
    def _show_quick_settings(self): self._switch_tab("Config")

    # ─── IViewController Implementation ───────────────────────────────────
    def set_period(self, period: str):
        """Called by OverviewView buttons."""
        self.selected_period_val = period
        if "Overview" in self.views and self.views["Overview"].winfo_exists():
            self.views["Overview"]._refresh_data()

    def refresh_overview_data(self):
        if "Overview" in self.views and self.views["Overview"].winfo_exists(): 
            self.views["Overview"]._refresh_data()

    def refresh_trades_table(self):
        if "Active Trades" in self.views and self.views["Active Trades"].winfo_exists(): 
            self.views["Active Trades"]._refresh_trades_table()

    def refresh_users_table(self):
        if "Management" in self.views and self.views["Management"].winfo_exists(): 
            self.views["Management"]._refresh_data()

    def refresh_trade_logs(self):
        if "Trade History" in self.views and self.views["Trade History"].winfo_exists(): 
            self.views["Trade History"]._refresh_data()

    def pop_out_view(self, view_name: str):
        self._pop_out_window(view_name)

    def load_config_values(self) -> Dict[str, Any]:
        """Fetch current user configuration from UserManager."""
        user_data = Config.get_user(self.current_user_id)
        if not user_data:
            return {}
        return user_data

    def save_config(self, config_dict: Dict[str, Any]) -> bool:
        """Save updated configuration for current user."""
        try:
            # We only update the current user's profile
            res = Config.update_user(self.current_user_id, config_dict)
            if res:
                ToastNotification(self, "Configuration saved permanently!", success=True)
                return True
            else:
                ToastNotification(self, "Failed to save configuration", success=False)
                return False
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            ToastNotification(self, f"Save Error: {e}", success=False)
            return False

if __name__ == "__main__":
    from gui_launcher import LoginView
    LoginView().mainloop()
