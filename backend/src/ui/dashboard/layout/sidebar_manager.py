"""
Sidebar Manager

Manages the dashboard left sidebar including settings panels.
Extracted from dashboard_gui.py
"""

import tkinter as tk
import customtkinter as ctk
from typing import Any, Callable, Optional, Dict, List

from src.ui.shared import COLORS
from src.ui.shared_state import get_shared_state
from src.config import Settings


class SidebarManager:
    """
    Manages dashboard sidebar with configuration panels.
    
    Responsibilities:
    - Bot control buttons (Start/Stop/Pause)
    - Broker settings panel
    - Strategy settings panel
    - Active markets panel
    - Risk parameters panel
    """
    
    def __init__(self, parent: ctk.CTkFrame, controller: Any):
        """
        Initialize sidebar manager.
        
        Args:
            parent: Parent frame (sidebar_left from main window)
            controller: Main TradeBotGUI instance for callbacks
        """
        self.parent = parent
        self.controller = controller
        
        self.bot_status_label: Optional[ctk.CTkLabel] = None
        self.start_btn: Optional[ctk.CTkButton] = None
        self.pause_btn: Optional[ctk.CTkButton] = None
        self._lockable_widgets: List[tk.Widget] = [] # Track widgets to disable during trading
        
        self._setup_sidebar()
        
        # Trace update for autopilot switch
        state = get_shared_state()
        state.brain_control.trace_add("write", lambda *a: self._lock_sidebar_for_ai(state.brain_control.get()))
        self._lock_sidebar_for_ai(state.brain_control.get())

    
    def _setup_sidebar(self):
        """Setup sidebar layout."""
        # Fixed status header section
        self._setup_status_header()
        
        # Scrollable settings section
        self._setup_settings_section()
    
    def _setup_status_header(self):
        """Setup the fixed status header at top of sidebar."""
        fixed_status = ctk.CTkFrame(
            self.parent,
            fg_color=COLORS["bg_card"],
            corner_radius=0
        )
        fixed_status.pack(side=tk.TOP, fill=tk.X)
        
        # Trades + P&L counters row
        counter_frame = ctk.CTkFrame(fixed_status, fg_color="transparent")
        counter_frame.pack(fill=tk.X, padx=15, pady=(12, 8))
        
        self.trades_label = ctk.CTkLabel(
            counter_frame,
            text="Trades: 0/5",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"]
        )
        self.trades_label.pack(side=tk.LEFT)
        
        self.pnl_label = ctk.CTkLabel(
            counter_frame,
            text="P&L: ₹+0",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["accent_green"]
        )
        self.pnl_label.pack(side=tk.RIGHT)
        
        # Centered bot status indicator
        self.bot_status_label = ctk.CTkLabel(
            fixed_status,
            text="● IDLE",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["warning"]
        )
        self.bot_status_label.pack(pady=(0, 4))
        
        # Master Intelligence Switch (Auto-Pilot)
        state = get_shared_state()
        self.brain_switch = ctk.CTkSwitch(
            fixed_status,
            text="AI MARKET SELECTION",
            variable=state.brain_control,
            font=ctk.CTkFont(size=10, weight="bold"),
            progress_color=COLORS["accent_blue"],
            text_color=COLORS["text_dim"],
            command=self._on_brain_switch_toggle  # Phase 1.2: AI toggle callback
        )
        self.brain_switch.pack(pady=(0, 10))
        self._lockable_widgets.append(self.brain_switch)
        
        # Large START BOT button
        self.start_btn = ctk.CTkButton(
            fixed_status,
            text="▶ START BOT",
            fg_color="#89b4fa",
            hover_color="#6c9ae6",
            text_color="#ffffff",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._toggle_bot,
            height=44,
            corner_radius=8
        )
        self.start_btn.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        # Pause Trades button
        self.pause_btn = ctk.CTkButton(
            fixed_status,
            text="⏸ Pause Trades",
            fg_color="#fab387",
            hover_color="#e09b6e",
            text_color="#1e1e2e",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.controller._pause_my_trades,
            height=36,
            corner_radius=8
        )
        self.pause_btn.pack(fill=tk.X, padx=15, pady=(0, 12))
    
    def _on_brain_switch_toggle(self):
        """
        Handle AI MARKET SELECTION toggle.
        Locks/unlocks the sidebar immediately on toggle, then notifies the controller.
        """
        if self.controller:
            ai_active = self.controller.shared_state.brain_control.get()
            self._lock_sidebar_for_ai(ai_active)
            self.controller._on_brain_control_toggle()

    def _lock_sidebar_for_ai(self, lock: bool):
        """
        Lock/unlock sidebar widgets when AI mode is active.

        brain_switch itself is intentionally excluded so the user can
        always turn AI mode off, even while it is active.
        """
        target_state = "disabled" if lock else "normal"
        for widget in self._lockable_widgets:
            if widget is self.brain_switch:
                continue  # Must stay interactive — user must be able to turn AI off
            try:
                widget.configure(state=target_state)
            except Exception:
                pass

    def _toggle_bot(self):
        """Toggle between Start and Stop based on current state."""
        current_text = self.start_btn.cget("text")
        
        # Block if already in transition states (Starting or Stopping)
        if "STARTING" in current_text.upper() or "STOPPING" in current_text.upper():
            return
        
        if "START" in current_text:
            self.controller._start_bot()
        elif "STOP" in current_text:
            # Prevent multiple clicks - disable immediately and show stopping
            self.start_btn.configure(
                text="⏳ Stopping...",
                state="disabled",
                fg_color="#666666"
            )
            self.controller._stop_bot()
    
    def _setup_settings_section(self):
        """Setup the scrollable settings section."""
        scrollable = ctk.CTkScrollableFrame(
            self.parent,
            fg_color="transparent"
        )
        scrollable.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Track dropdowns for explicit updates
        self._strategy_dropdown: Optional[ctk.CTkComboBox] = None
        self._min_signals_dropdown: Optional[ctk.CTkComboBox] = None
        self._candle_dropdown: Optional[ctk.CTkComboBox] = None
        
        # 1. Broker Settings
        self._create_section(
            scrollable,
            "� BROKER SETTINGS",
            "#a6e3a1",
            self._create_broker_settings
        )
        
        # 2. Strategy Settings
        self._create_section(
            scrollable,
            "🎯 STRATEGY SETTINGS",
            "#89b4fa",
            self._create_strategy_settings
        )
        
        # 3. Active Markets
        self._create_section(
            scrollable,
            "📑 ACTIVE MARKETS",
            "#fab387",
            self._create_markets_settings
        )
        
        # 4. Risk Rules (read-only summary - edit in Config view)
        self._create_section(
            scrollable,
            "⚖️ RISK RULES",
            "#f38ba8",
            self._create_risk_summary
        )
    
    def _create_section(
        self,
        parent: ctk.CTkScrollableFrame,
        title: str,
        color: str,
        content_factory: Callable
    ):
        """Create a collapsible settings section."""
        # Section header
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill=tk.X, pady=(10, 0))
        
        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=color
        ).pack(anchor=tk.W, padx=12)
        
        # Content frame
        content = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=8)
        content.pack(fill=tk.X, pady=4, padx=12)
        
        # Fill content
        content_factory(content)
    def _create_broker_settings(self, parent: ctk.CTkFrame):
        """Create broker settings panel. Shared state already has persisted values."""
        state = get_shared_state()
        
        # Broker dropdown (shared)
        broker_dropdown = ctk.CTkComboBox(
            parent,
            values=["angel", "zerodha", "upstox", "fyers"],
            variable=state.broker,
            height=32
        )
        broker_dropdown.pack(fill=tk.X, padx=10, pady=(10, 8))
        broker_dropdown.set(state.broker.get()) # Explicit init
        self._lockable_widgets.append(broker_dropdown)
        
        # Trace update from config to sidebar
        state.broker.trace_add("write", lambda *a: broker_dropdown.set(state.broker.get()))
        
        cb1 = ctk.CTkCheckBox(
            parent,
            text="Paper Trading",
            variable=state.paper_trading
        )
        cb1.pack(anchor=tk.W, padx=10, pady=4)
        self._lockable_widgets.append(cb1)
        
        # Trailing SL checkbox (shared)
        cb2 = ctk.CTkCheckBox(
            parent,
            text="Trailing SL",
            variable=state.use_tsl
        )
        cb2.pack(anchor=tk.W, padx=10, pady=4)
        self._lockable_widgets.append(cb2)
        
        # Kill Bot (Limit) checkbox (shared)
        cb3 = ctk.CTkCheckBox(
            parent,
            text="Kill Bot (Limit)",
            variable=state.kill_bot_limit
        )
        cb3.pack(anchor=tk.W, padx=10, pady=(4, 10))
        self._lockable_widgets.append(cb3)
    
    def _create_strategy_settings(self, parent: ctk.CTkFrame):
        """Create strategy settings panel. Shared state already has persisted values."""
        state = get_shared_state()
        
        # Strategy dropdown (shared with config)
        strat_row = ctk.CTkFrame(parent, fg_color="transparent")
        strat_row.pack(fill=tk.X, padx=10, pady=(10, 6))
        
        ctk.CTkLabel(
            strat_row,
            text="Strategy:",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"]
        ).pack(side=tk.LEFT)
        
        self.strat_combo = ctk.CTkComboBox(
            strat_row,
            values=["Combined", "EMA-VWAP", "Nifty Options", "ML Pattern"],
            variable=state.strategy,
            width=130,
            height=28
        )
        self.strat_combo.pack(side=tk.RIGHT)
        self.strat_combo.set(state.strategy.get()) # Explicit init
        self._lockable_widgets.append(self.strat_combo)
        
        # Trace update from config to sidebar
        state.strategy.trace_add("write", lambda *a: self.strat_combo.set(state.strategy.get()))
        
        # Candle timeframe row
        candle_row = ctk.CTkFrame(parent, fg_color="transparent")
        candle_row.pack(fill=tk.X, padx=10, pady=(6, 6))
        
        ctk.CTkLabel(
            candle_row,
            text="Candle:",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"]
        ).pack(side=tk.LEFT)
        
        self.candle_combo = ctk.CTkComboBox(
            candle_row,
            values=["1m", "3m", "5m", "15m", "30m", "1h"],
            variable=state.candle_timeframe,
            width=80,
            height=28
        )
        self.candle_combo.pack(side=tk.RIGHT)
        self.candle_combo.set(state.candle_timeframe.get()) # Explicit init
        self._lockable_widgets.append(self.candle_combo)
        
        # Trace update from config to sidebar
        state.candle_timeframe.trace_add("write", lambda *a: self.candle_combo.set(state.candle_timeframe.get()))
        
        # Min Signals row
        sig_row = ctk.CTkFrame(parent, fg_color="transparent")
        sig_row.pack(fill=tk.X, padx=10, pady=(6, 10))
        
        ctk.CTkLabel(
            sig_row,
            text="Min Sig:",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"]
        ).pack(side=tk.LEFT)
        
        self.sig_combo = ctk.CTkComboBox(
            sig_row,
            values=["1", "2", "3"],
            variable=state.min_signals,
            width=80,
            height=28
        )
        self.sig_combo.pack(side=tk.RIGHT)
        self.sig_combo.set(state.min_signals.get()) # Explicit init
        self._lockable_widgets.append(self.sig_combo)
        
        # Trace update from config to sidebar
        state.min_signals.trace_add("write", lambda *a: self.sig_combo.set(state.min_signals.get()))
    
    def _create_markets_settings(self, parent: ctk.CTkFrame):
        """Create active market focus panel with dynamic dropdowns."""
        state = get_shared_state()
        
        self.market_map = {
            "Options": ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
            "Commodity": ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER"],
            "Equity": ["RELIANCE", "HDFCBANK", "INFY", "ICICIBANK", "TCS"]
        }
        
        # Dropdown 1: Market Category
        row1 = ctk.CTkFrame(parent, fg_color="transparent")
        row1.pack(fill=tk.X, padx=10, pady=(10, 6))
        ctk.CTkLabel(row1, text="Market:", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.sidebar_market_dropdown = ctk.CTkComboBox(row1, values=list(self.market_map.keys()),
                                                     variable=state.selected_category,
                                                     command=self._on_sidebar_market_change,
                                                     width=110, height=28)
        self.sidebar_market_dropdown.pack(side=tk.RIGHT)
        self.sidebar_market_dropdown.set(state.selected_category.get())
        self._lockable_widgets.append(self.sidebar_market_dropdown)
        
        # Dropdown 2: Specific Instrument
        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill=tk.X, padx=10, pady=(6, 6))
        ctk.CTkLabel(row2, text="Target:", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        current_cat = state.selected_category.get()
        if current_cat not in self.market_map: current_cat = "Options"
        
        self.sidebar_instrument_dropdown = ctk.CTkComboBox(row2, values=self.market_map[current_cat],
                                                         variable=state.selected_instrument,
                                                         command=lambda v: state.selected_instrument.set(v),
                                                         width=110, height=28)
        self.sidebar_instrument_dropdown.pack(side=tk.RIGHT)
        self.sidebar_instrument_dropdown.set(state.selected_instrument.get())
        self._lockable_widgets.append(self.sidebar_instrument_dropdown)

        # Dropdown 3: Lots
        row3 = ctk.CTkFrame(parent, fg_color="transparent")
        row3.pack(fill=tk.X, padx=10, pady=(6, 10))
        ctk.CTkLabel(row3, text="Lots:", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        lot_values = [str(i) for i in range(1, 51)]
        self.sidebar_lots_dropdown = ctk.CTkComboBox(row3, values=lot_values,
                                                    variable=state.selected_lots,
                                                    command=lambda v: state.selected_lots.set(v),
                                                    width=110, height=28)
        self.sidebar_lots_dropdown.pack(side=tk.RIGHT)
        self.sidebar_lots_dropdown.set(state.selected_lots.get())
        self._lockable_widgets.append(self.sidebar_lots_dropdown)

        # Sync from Config / AI brain to Sidebar — trace all three variables
        state.selected_category.trace_add("write", lambda *a: self._sync_sidebar_dropdowns())
        state.selected_instrument.trace_add("write", lambda *a: self._sync_instrument_display())
        state.selected_lots.trace_add("write", lambda *a: self.sidebar_lots_dropdown.set(state.selected_lots.get()))

    def _on_sidebar_market_change(self, selected_market):
        """Update instrument list when market changes in sidebar."""
        state = get_shared_state()
        state.selected_category.set(selected_market) # Force update the StringVar
        
        new_values = self.market_map.get(selected_market, [])
        self.sidebar_instrument_dropdown.configure(values=new_values)
        if new_values:
            # Update both the widget and the underlying StringVar
            self.sidebar_instrument_dropdown.set(new_values[0])
            state.selected_instrument.set(new_values[0])

    def _sync_instrument_display(self):
        """Update instrument dropdown display when selected_instrument changes externally (e.g. AI brain)."""
        try:
            state = get_shared_state()
            inst = state.selected_instrument.get()
            cat = state.selected_category.get()
            values = list(self.market_map.get(cat, []))
            # Ensure the AI-selected instrument is in the list
            if inst and inst not in values:
                values.append(inst)
                self.sidebar_instrument_dropdown.configure(values=values)
            self.sidebar_instrument_dropdown.set(inst)
        except Exception:
            pass

    def _sync_sidebar_dropdowns(self):
        """Ensure sidebar dropdowns match shared state when changed elsewhere (category change)."""
        try:
            state = get_shared_state()
            cat = state.selected_category.get()
            self.sidebar_market_dropdown.set(cat)
            new_values = self.market_map.get(cat, [])
            inst = state.selected_instrument.get()
            # If AI selected something not in the standard list, add it
            if inst and inst not in new_values:
                new_values = list(new_values) + [inst]
            self.sidebar_instrument_dropdown.configure(values=new_values)
            self.sidebar_instrument_dropdown.set(inst)
        except Exception:
            pass
    
    def _create_risk_summary(self, parent: ctk.CTkFrame):
        """Create read-only risk rules summary (edit in Config view)."""
        state = get_shared_state()
        
        # Hint label
        ctk.CTkLabel(
            parent,
            text="Quick view · Edit in Config",
            font=ctk.CTkFont(size=9, slant="italic"),
            text_color=COLORS["text_dim"]
        ).pack(anchor=tk.W, padx=10, pady=(8, 4))
        
        rules = [
            ("🎯 Target", state.risk_target, "₹"),
            ("🛑 Stop Loss", state.risk_sl, "₹"),
            ("📊 Max Trades", state.risk_max_trades, "/day"),
            ("⚠️ Max Cons. SL", state.risk_max_cons_sl, ""),
            ("📉 Max Daily Loss", state.risk_max_daily_loss, "₹"),
        ]
        
        for label_text, var, suffix in rules:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill=tk.X, padx=10, pady=2)
            
            ctk.CTkLabel(
                row,
                text=label_text,
                font=ctk.CTkFont(size=10),
                text_color=COLORS["text_dim"]
            ).pack(side=tk.LEFT)
            
            # Value label that auto-updates with shared var
            val_label = ctk.CTkLabel(
                row,
                text=self._format_risk_value(var.get(), suffix),
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=COLORS["text_main"]
            )
            val_label.pack(side=tk.RIGHT)
            
            # Update label when shared var changes
            var.trace_add("write", lambda *a, lbl=val_label, v=var, s=suffix: lbl.configure(text=self._format_risk_value(v.get(), s)))
        
        # Kill switch status
        kill_row = ctk.CTkFrame(parent, fg_color="transparent")
        kill_row.pack(fill=tk.X, padx=10, pady=(6, 10))
        
        ctk.CTkLabel(
            kill_row,
            text="🔒 Kill Switch",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_dim"]
        ).pack(side=tk.LEFT)
        
        kill_status = ctk.CTkLabel(
            kill_row,
            text="ON" if state.kill_bot_limit.get() else "OFF",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["accent_green"] if state.kill_bot_limit.get() else COLORS["text_dim"]
        )
        kill_status.pack(side=tk.RIGHT)
        
        def _update_kill(*a):
            on = state.kill_bot_limit.get()
            kill_status.configure(
                text="ON" if on else "OFF",
                text_color=COLORS["accent_green"] if on else COLORS["text_dim"]
            )
        state.kill_bot_limit.trace_add("write", _update_kill)
    
    @staticmethod
    def _format_risk_value(value: str, suffix: str) -> str:
        """Format a risk value with its suffix."""
        value = value or "—"
        if suffix == "₹":
            return f"₹{value}"
        return f"{value}{suffix}"
    
    def update_trades_counter(self, current: int, max_trades: int):
        """Update the trades counter display."""
        if hasattr(self, 'trades_label'):
            self.trades_label.configure(text=f"Trades: {current}/{max_trades}")
    
    def _update_lot_entry(self, entry: ctk.CTkEntry, var: tk.StringVar):
        """Helper to sync lot entry with variable."""
        try:
            val = var.get()
            if entry.get() != val:
                entry.delete(0, tk.END)
                entry.insert(0, val)
        except Exception: pass

    def update_pnl(self, pnl: float):
        """Update the P&L display."""
        if hasattr(self, 'pnl_label'):
            sign = "+" if pnl >= 0 else ""
            color = COLORS["accent_green"] if pnl >= 0 else COLORS["accent_red"]
            self.pnl_label.configure(text=f"P&L: ₹{sign}{pnl:.0f}", text_color=color)
    
    def set_bot_status(self, running: bool, paused: bool = False):
        """
        Update bot status display.
        
        Args:
            running: Whether bot is running
            paused: Whether bot is paused
        """
        # Block if already in transition state (Stopping), but ONLY if bot is still reportedly running
        current_text = self.start_btn.cget("text")
        if running and "STOPPING" in current_text.upper():
            return  # Don't interrupt stopping state if still active
        
        if running and not paused:
            self.bot_status_label.configure(
                text="● RUNNING",
                text_color=COLORS["accent_green"]
            )
            self.start_btn.configure(
                text="⏹ STOP BOT",
                fg_color=COLORS["accent_red"],
                hover_color="#c94a5c",
                state="normal"
            )
        elif paused:
            self.bot_status_label.configure(
                text="● PAUSED",
                text_color=COLORS["warning"]
            )
        else:
            # Bot stopped - reset to START BOT
            self.bot_status_label.configure(
                text="● IDLE",
                text_color=COLORS["warning"]
            )
            self.start_btn.configure(
                text="▶ START BOT",
                fg_color="#89b4fa",
                hover_color="#6c9ae6",
                state="normal"
            )
        
        # Lock or unlock configurable settings widgets
        target_state = "disabled" if running else "normal"
        for widget in self._lockable_widgets:
            try:
                widget.configure(state=target_state)
            except Exception:
                pass


class RightSidebarManager:
    """
    Manages the right sidebar navigation panel.
    
    Responsibilities:
    - Navigation buttons for all views
    - Tab switching
    - Active tab highlighting
    """
    
    def __init__(self, parent: ctk.CTkFrame, controller: Any):
        """
        Initialize right sidebar manager.
        
        Args:
            parent: Parent frame (sidebar_right from main window)
            controller: Main TradeBotGUI instance for callbacks
        """
        self.parent = parent
        self.controller = controller
        
        self.nav_btns: Dict[str, ctk.CTkButton] = {}
        self.current_tab: str = "Overview"
        
        self._setup_navigation()
    
    def _setup_navigation(self):
        """Setup the right sidebar navigation."""
        # Navigation header
        nav_header = ctk.CTkFrame(self.parent, fg_color=COLORS["bg_card"], height=40)
        nav_header.pack(fill=tk.X)
        ctk.CTkLabel(
            nav_header,
            text="📍 NAVIGATION",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_dim"]
        ).pack(pady=10)
        
        # Navigation items
        navs = [
            ("Overview", "🏠", "#89b4fa"),
            ("Jarvis AI", "🧠", "#cba6f7"), # New Jarvis AI Tab
            ("Market Analysis", "🌍", "#89dceb"),
            ("Active Trades", "📊", "#a6e3a1"),
            ("Management", "👥", "#fab387"),
            ("Config", "⚙️", "#cba6f7"),
            ("Notifications", "🔔", "#f9e2af"),
            ("Trade History", "📜", "#94e2d5"),
            ("Console", "💻", "#74c7ec"),
            ("Help", "❓", "#6c7086")
        ]
        
        for name, icon, active_color in navs:
            btn = ctk.CTkButton(
                self.parent,
                text=f"  {icon}  {name}",
                anchor=tk.W,
                height=42,
                fg_color="transparent",
                text_color=COLORS["text_main"],
                font=ctk.CTkFont(size=11),
                command=lambda n=name: self._on_nav_click(n)
            )
            btn.pack(fill=tk.X, padx=10, pady=2)
            self.nav_btns[name] = btn
            # Store the active color for hover effect
            btn._active_color = active_color
        
        # Set default active tab
        self.set_active_tab("Overview")
    
    def _prompt_password_for_management(self, success_callback: Callable):
        """Show a premium modal dialog to authenticate for the Management view."""
        from src.config import UserManager as Config
        from src.utils.security import verify_password
        from tkinter import messagebox
        
        # Get active user ID from controller
        user_id = getattr(self.controller, "current_user_id", "user_001")
        user_profile = Config.get_user(user_id)
        if not user_profile:
            messagebox.showerror("Error", "Active user session not found.")
            return

        parent_win = self.controller
        dialog = ctk.CTkToplevel(parent_win)
        dialog.title("Authorization Required")
        dialog.geometry("380x260")
        dialog.resizable(False, False)
        dialog.transient(parent_win)
        dialog.grab_set()
        dialog.lift()
        
        # Centering dialog
        dialog.update_idletasks()
        screen_w = dialog.winfo_screenwidth()
        screen_h = dialog.winfo_screenheight()
        x = (screen_w // 2) - (380 // 2)
        y = (screen_h // 2) - (260 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Apply theme
        if hasattr(self.controller, "_apply_window_theme"):
            self.controller._apply_window_theme(dialog)
        else:
            dialog.configure(fg_color=COLORS["bg_panel"])

        # Main frame
        frame = ctk.CTkFrame(dialog, fg_color=COLORS["bg_card"], corner_radius=16, border_width=1, border_color=COLORS["border"])
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Icon & Title
        ctk.CTkLabel(frame, text="🔒", font=("Segoe UI", 32)).pack(pady=(15, 5))
        
        ctk.CTkLabel(
            frame, 
            text="Enter Admin Password", 
            font=ctk.CTkFont(size=14, weight="bold"), 
            text_color=COLORS["accent_blue"]
        ).pack()
        
        ctk.CTkLabel(
            frame, 
            text="Authorization is required to access Management features.", 
            font=ctk.CTkFont(size=10), 
            text_color=COLORS["text_dim"]
        ).pack(pady=(2, 10))

        # Password Entry
        e_pass = ctk.CTkEntry(frame, width=240, height=36, show="●", placeholder_text="Enter password")
        e_pass.pack(pady=5)
        e_pass.focus_set()

        err_label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=10), text_color=COLORS["accent_red"])
        err_label.pack(pady=2)

        def verify():
            pw = e_pass.get().strip()
            if not pw:
                err_label.configure(text="Password cannot be empty")
                return
            
            stored_pw = user_profile.get("login_password", "")
            if verify_password(pw, stored_pw):
                dialog.destroy()
                success_callback()
            else:
                err_label.configure(text="❌ Invalid password")
                e_pass.delete(0, tk.END)

        e_pass.bind("<Return>", lambda e: verify())

        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=(10, 15))
        
        btn_cancel = ctk.CTkButton(
            btn_frame, 
            text="Cancel", 
            width=90, 
            height=30,
            fg_color="transparent", 
            border_width=1, 
            border_color=COLORS["border"],
            text_color=COLORS["text_main"],
            command=dialog.destroy
        )
        btn_cancel.pack(side=tk.LEFT, padx=(30, 5))
        
        btn_auth = ctk.CTkButton(
            btn_frame, 
            text="Authorize", 
            width=110, 
            height=30,
            fg_color=COLORS["accent_blue"],
            command=verify
        )
        btn_auth.pack(side=tk.LEFT, padx=(5, 30))

    def _on_nav_click(self, name: str):
        """Handle navigation button click."""
        if name == "Management":
            def switch():
                self.set_active_tab(name)
                self.controller._switch_tab(name)
            self._prompt_password_for_management(switch)
        else:
            self.set_active_tab(name)
            self.controller._switch_tab(name)
    
    def set_active_tab(self, name: str):
        """Set active tab styling."""
        # Reset all tabs
        for tab_name, btn in self.nav_btns.items():
            btn.configure(
                fg_color="transparent",
                text_color=COLORS["text_main"]
            )
        
        # Highlight active tab
        if name in self.nav_btns:
            active_color = self.nav_btns[name]._active_color
            self.nav_btns[name].configure(
                fg_color=COLORS["border"],
                text_color=active_color
            )
        
        self.current_tab = name
    
    def get_active_tab(self) -> str:
        """Get currently active tab name."""
        return self.current_tab
    
    def get_nav_buttons(self) -> Dict[str, ctk.CTkButton]:
        """Get all navigation buttons dict."""
        return self.nav_btns
