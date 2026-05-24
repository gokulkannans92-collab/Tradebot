import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from src.ui.shared import COLORS, ToastNotification, ModernTimePicker
from src.ui.shared_state import get_shared_state
from src.config import UserManager as Config, Settings
from os import getenv
import os
import logging

logger = logging.getLogger(__name__)


class ConfigView(ctk.CTkFrame):
    def __init__(self, parent, controller=None, is_main=True):
        super().__init__(parent, fg_color="transparent")
        
        self.controller = controller
        self.is_main = is_main
        self._live_components = {}
        self._lockable_widgets = []  # Widgets to disable when bot is running
        
        self._setup_ui()
        
        # Watch bot running & AI autopilot state and lock/unlock accordingly
        state = get_shared_state()
        state.bot_running.trace_add("write", lambda *a: self._apply_lock_state())
        state.brain_control.trace_add("write", lambda *a: self._apply_lock_state())
        self._apply_lock_state()


        # Load existing data
        self.after(200, self._load_data)
    
    def _setup_ui(self):
        self._add_header()
        self._add_content()
    
    def _add_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side=ctk.LEFT)
        
        ctk.CTkLabel(title_box, text="⚙️ CONFIGURATION", 
                    font=ctk.CTkFont(size=20, weight="bold"), 
                    text_color=COLORS["accent_blue"]).pack(side=ctk.LEFT)
        
    def _add_content(self):
        # Use CTkScrollableFrame for content that exceeds screen
        self.scr = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scr.pack(fill=tk.BOTH, expand=True)
        
        # Section cards with improved styling
        self._add_broker_card()
        self._add_strategy_card()
        self._add_risk_card()
        self._add_market_focus_card()
        self._add_notifications_card()
        self._add_ai_intelligence_card()
        self._add_footer()
    
    def _create_section_card(self, title: str, icon: str, color: str, description: str = ""):
        """Create a styled card for a config section."""
        card = ctk.CTkFrame(self.scr, fg_color=COLORS["bg_card"], corner_radius=12, 
                           border_width=1, border_color=COLORS["border"])
        card.pack(fill=tk.X, pady=(0, 12), expand=True)
        
        header = ctk.CTkFrame(card, fg_color=COLORS["bg_panel"], corner_radius=12)
        header.pack(fill=tk.X, padx=12, pady=(12, 8))
        
        ctk.CTkLabel(header, text=f"{icon} {title}", font=ctk.CTkFont(size=14, weight="bold"), 
                    text_color=color).pack(side=tk.LEFT, padx=10, pady=8)
        
        if description:
            ctk.CTkLabel(header, text=description, font=ctk.CTkFont(size=10), 
                        text_color=COLORS["text_dim"]).pack(side=tk.RIGHT, padx=10)
        
        return card
    
    def _create_setting_row(self, parent, label_text, widget, tooltip=""):
        """Create a styled settings row"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill=tk.X, padx=20, pady=6)
        
        label = ctk.CTkLabel(row, text=label_text, font=ctk.CTkFont(size=11), 
                            text_color=COLORS["text_main"], width=140, anchor=tk.W)
        label.pack(side=tk.LEFT)
        
        widget.pack(side=tk.LEFT)
        
        return row
    
    def _add_broker_card(self):
        card = self._create_section_card("Broker Connection", "🏦", "#89b4fa", "Connect to your broker")
        state = get_shared_state()
        
        # Broker selection (shared with sidebar)
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row1, text="🔽 Broker", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.config_broker = ctk.CTkComboBox(row1, values=["angel","zerodha","upstox","mock"], 
                                              width=200, height=32, variable=state.broker)
        self.config_broker.pack(side=tk.LEFT, padx=10)
        self._lockable_widgets.append(self.config_broker)
        
        # Mode toggle - synced with paper_trading shared var
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row2, text="🎯 Mode", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.api_mode = ctk.CTkSegmentedButton(row2, values=["Paper", "Live"],
                                               fg_color=COLORS["border"],
                                               selected_color=COLORS["accent_green"],
                                               command=self._on_mode_change)
        self.api_mode.pack(side=tk.LEFT, padx=10)
        self.api_mode.set("Paper" if state.paper_trading.get() else "Live")
        # Sync mode segmented button when paper_trading changes
        state.paper_trading.trace_add("write", lambda *a: self.api_mode.set("Paper" if state.paper_trading.get() else "Live"))
        self._lockable_widgets.append(self.api_mode)
        
        # Candle period (shared with sidebar)
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row3, text="🕐 Candle", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.config_candle = ctk.CTkComboBox(row3, values=["1m", "3m", "5m", "15m", "30m", "1h"], 
                                              width=100, height=32, variable=state.candle_timeframe)
        self.config_candle.pack(side=tk.LEFT, padx=10)
        self._lockable_widgets.append(self.config_candle)
        
        row4 = ctk.CTkFrame(card, fg_color="transparent")
        row4.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row4, text="📅 History", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.time_period = ctk.CTkComboBox(row4, values=["1 Day", "1 Week", "1 Month", "3 Months"], 
                                            width=130, height=32)
        self.time_period.pack(side=tk.LEFT, padx=10)
        self.time_period.set("1 Month")

        if self.is_main and self.controller:
            self.controller.config_broker = self.config_broker
            self.controller.api_mode = self.api_mode
            self.controller.config_candle = self.config_candle


    def _add_strategy_card(self):
        card = self._create_section_card("Strategy Configuration", "📈", "#a6e3a1", "Configure trading logic")
        
        # Strategy selection
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row1, text="🎯 Strategy", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        state_strat = get_shared_state()
        self.strategy_select = ctk.CTkSegmentedButton(row1,
            values=["Combined", "EMA-VWAP", "Nifty Options", "ML Pattern"],
            fg_color=COLORS["border"],
            selected_color=COLORS["accent_blue"],
            command=lambda v: state_strat.strategy.set(v))
        self.strategy_select.pack(side=tk.LEFT, padx=10)
        self.strategy_select.set(state_strat.strategy.get())
        state_strat.strategy.trace_add("write", lambda *a: self.strategy_select.set(state_strat.strategy.get()))
        self._lockable_widgets.append(self.strategy_select)
        
        # Min signals
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row2, text="📊 Min Signals", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        state = get_shared_state()
        # Cap at 3 signals to match Combined strategy logic
        self.config_min_signals = ctk.CTkSegmentedButton(row2, values=["1", "2", "3"],
            fg_color=COLORS["border"],
            selected_color=COLORS["accent_blue"],
            command=lambda v: state.min_signals.set(v))
        self.config_min_signals.pack(side=tk.LEFT, padx=10)
        self.config_min_signals.set(state.min_signals.get())
        
        ctk.CTkLabel(row2, text="(Max 3 for Combined)", font=ctk.CTkFont(size=10, slant="italic"), 
                    text_color=COLORS["text_dim"]).pack(side=tk.LEFT, padx=5)
        
        # Sync when shared var changes
        state.min_signals.trace_add("write", lambda *a: self.config_min_signals.set(state.min_signals.get()))
        self._lockable_widgets.append(self.config_min_signals)
        
        # Time windows
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row3, text="🕐 Entry Start", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.entry_start_time = ModernTimePicker(row3)
        self.entry_start_time.pack(side=tk.LEFT, padx=10)
        
        row4 = ctk.CTkFrame(card, fg_color="transparent")
        row4.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row4, text="🕐 Entry End", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.entry_end_time = ModernTimePicker(row4, default_time="14:30")
        self.entry_end_time.pack(side=tk.LEFT, padx=10)
        
        row5 = ctk.CTkFrame(card, fg_color="transparent")
        row5.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row5, text="🏁 EOD Exit", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.eod_exit_time = ModernTimePicker(row5, default_time="15:10")
        self.eod_exit_time.pack(side=tk.LEFT, padx=10)
        
        # Add time pickers to lockables
        self._lockable_widgets.append(self.entry_start_time)
        self._lockable_widgets.append(self.entry_end_time)
        self._lockable_widgets.append(self.eod_exit_time)
        
        if self.is_main and self.controller:
            self.controller.strategy_select = self.strategy_select
            self.controller.config_min_signals = self.config_min_signals
            self.controller.entry_start_time = self.entry_start_time
            self.controller.entry_end_time = self.entry_end_time
            self.controller.eod_exit_time = self.eod_exit_time
    
    def _add_risk_card(self):
        card = self._create_section_card("Risk Management", "⚖️", "#fab387", "Protect your capital")
        state = get_shared_state()
        
        # Capital settings (not shared - local only)
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row1, text="💰 Max Capital", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.risk_capital = ctk.CTkEntry(row1, width=120, height=32, placeholder_text="1000")
        self.risk_capital.pack(side=tk.LEFT, padx=10)
        
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row2, text="💵 Trade Capital", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.risk_trade = ctk.CTkEntry(row2, width=120, height=32, placeholder_text="1000")
        self.risk_trade.pack(side=tk.LEFT, padx=10)
        
        # Target (shared with sidebar)
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row3, text="🎯 Target (Rs)", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.risk_target = ctk.CTkEntry(row3, width=100, height=32, textvariable=state.risk_target)
        self.risk_target.pack(side=tk.LEFT, padx=10)
        self.risk_target.bind("<KeyRelease>", lambda e: self._auto_update_sl())

        # Stop Loss (shared)
        row4 = ctk.CTkFrame(card, fg_color="transparent")
        row4.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row4, text="🛑 Stop Loss (Rs)", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.risk_sl = ctk.CTkEntry(row4, width=100, height=32, textvariable=state.risk_sl)
        self.risk_sl.pack(side=tk.LEFT, padx=10)
        ctk.CTkLabel(row4, text=" (Locked 1:2 Ratio)", font=ctk.CTkFont(size=10), text_color=COLORS["accent_peach"]).pack(side=tk.LEFT, padx=5)

        # Max trades/day (shared)
        row5 = ctk.CTkFrame(card, fg_color="transparent")
        row5.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row5, text="📊 Max Trades/Day", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.risk_max_trades = ctk.CTkEntry(row5, width=80, height=32, textvariable=state.risk_max_trades)
        self.risk_max_trades.pack(side=tk.LEFT, padx=10)
        
        # Max consecutive SL (shared)
        row6 = ctk.CTkFrame(card, fg_color="transparent")
        row6.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row6, text="⚠️ Max Cons. SL", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.risk_max_sl = ctk.CTkEntry(row6, width=80, height=32, textvariable=state.risk_max_cons_sl)
        self.risk_max_sl.pack(side=tk.LEFT, padx=10)
        
        # Max daily loss (shared)
        row7 = ctk.CTkFrame(card, fg_color="transparent")
        row7.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row7, text="📉 Max Daily Loss", font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
        
        self.risk_daily_loss = ctk.CTkEntry(row7, width=100, height=32, textvariable=state.risk_max_daily_loss)
        self.risk_daily_loss.pack(side=tk.LEFT, padx=10)
        
        # Kill switch (shared)
        row8 = ctk.CTkFrame(card, fg_color="transparent")
        row8.pack(fill=tk.X, padx=20, pady=10)
        state = get_shared_state()
        self.kill_switch_var = state.kill_bot_limit
        kill_cb = ctk.CTkCheckBox(row8, text="🛑 Enable Kill Switch (stop after daily loss limit)",
                       variable=self.kill_switch_var, font=ctk.CTkFont(size=11))
        kill_cb.pack(anchor=tk.W)
        self._lockable_widgets.append(kill_cb)

        # All risk entry fields are lockable
        for w in [self.risk_capital, self.risk_trade, self.risk_target, self.risk_sl,
                  self.risk_max_trades, self.risk_max_sl, self.risk_daily_loss]:
            self._lockable_widgets.append(w)
        
        # Assign to controller after all widgets created
        if self.is_main and self.controller:
            self.controller.risk_target = self.risk_target
            self.controller.risk_sl = self.risk_sl
            self.controller.risk_capital = self.risk_capital
            self.controller.risk_trade = self.risk_trade
            self.controller.risk_max_trades = self.risk_max_trades
            self.controller.risk_max_sl = self.risk_max_sl
            self.controller.risk_daily_loss = self.risk_daily_loss
            self.controller.kill_switch_var = self.kill_switch_var

    def _add_market_focus_card(self):
        card = self._create_section_card("Active Trading Focus", "🎯", "#ff00ff", "Select Market, Instrument & Lots")
        state = get_shared_state()
        
        self.market_map = {
            "Options": ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
            "Commodity": ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER"],
            "Equity": ["RELIANCE", "HDFCBANK", "INFY", "ICICIBANK", "TCS"]
        }
        
        # Dropdown 1: Market Category
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row1, text="🌐 Select Market", font=ctk.CTkFont(size=12), width=140, anchor=tk.W).pack(side=tk.LEFT)
        self.market_dropdown = ctk.CTkOptionMenu(row1, values=list(self.market_map.keys()),
                                               variable=state.selected_category,
                                               command=self._on_market_change,
                                               width=200, height=32, fg_color=COLORS["bg_panel"])
        self.market_dropdown.pack(side=tk.LEFT, padx=10)
        self._lockable_widgets.append(self.market_dropdown)
        
        # Dropdown 2: Specific Instrument
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row2, text="📊 Select Instrument", font=ctk.CTkFont(size=12), width=140, anchor=tk.W).pack(side=tk.LEFT)
        current_cat = state.selected_category.get()
        if current_cat not in self.market_map: current_cat = "Options"
        self.instrument_dropdown = ctk.CTkOptionMenu(row2, values=self.market_map[current_cat],
                                                   variable=state.selected_instrument,
                                                   width=200, height=32, fg_color=COLORS["bg_panel"])
        self.instrument_dropdown.pack(side=tk.LEFT, padx=10)
        self._lockable_widgets.append(self.instrument_dropdown)
        
        # Dropdown 3: Lots
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill=tk.X, padx=20, pady=8)
        ctk.CTkLabel(row3, text="📦 Select Lots", font=ctk.CTkFont(size=12), width=140, anchor=tk.W).pack(side=tk.LEFT)
        lot_values = [str(i) for i in range(1, 51)]
        self.lots_dropdown = ctk.CTkOptionMenu(row3, values=lot_values,
                                              variable=state.selected_lots,
                                              width=200, height=32, fg_color=COLORS["bg_panel"])
        self.lots_dropdown.pack(side=tk.LEFT, padx=10)
        self._lockable_widgets.append(self.lots_dropdown)

        # Synchronize from external changes (Sidebar or Jarvis AI selection)
        state.selected_category.trace_add("write", lambda *a: self._sync_config_dropdowns())
        state.selected_instrument.trace_add("write", lambda *a: self._sync_instrument_display())
        state.selected_lots.trace_add("write", lambda *a: self._sync_lots_display())

    def _on_market_change(self, selected_market):
        """Update instrument dropdown based on selected market."""
        state = get_shared_state()
        state.selected_category.set(selected_market)
        new_values = self.market_map.get(selected_market, [])
        self.instrument_dropdown.configure(values=new_values)
        if new_values:
            self.instrument_dropdown.set(new_values[0])
            state.selected_instrument.set(new_values[0])

    def _sync_instrument_display(self):
        """Update instrument option menu when selected_instrument changes externally."""
        try:
            state = get_shared_state()
            inst = state.selected_instrument.get()
            cat = state.selected_category.get()
            values = list(self.market_map.get(cat, []))
            if inst and inst not in values:
                values.append(inst)
                self.instrument_dropdown.configure(values=values)
            self.instrument_dropdown.set(inst)
        except Exception:
            pass

    def _sync_lots_display(self):
        """Update lots option menu when selected_lots changes externally."""
        try:
            state = get_shared_state()
            lots = state.selected_lots.get()
            self.lots_dropdown.set(lots)
        except Exception:
            pass

    def _sync_config_dropdowns(self):
        """Ensure config dropdowns match shared state when changed elsewhere (category change)."""
        try:
            state = get_shared_state()
            cat = state.selected_category.get()
            self.market_dropdown.set(cat)
            new_values = self.market_map.get(cat, [])
            inst = state.selected_instrument.get()
            if inst and inst not in new_values:
                new_values = list(new_values) + [inst]
            self.instrument_dropdown.configure(values=new_values)
            self.instrument_dropdown.set(inst)
        except Exception:
            pass


    def _add_notifications_card(self):
        card = self._create_section_card("Notifications", "🔔", "#f9e2af", "Stay informed")
        
        # Alert toggles
        alert_row = ctk.CTkFrame(card, fg_color="transparent")
        alert_row.pack(fill=tk.X, padx=20, pady=12)
        
        self.telegram_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(alert_row, text="📱 Telegram Alerts", variable=self.telegram_var, 
                       font=ctk.CTkFont(size=11)).pack(side=tk.LEFT, padx=10)
        
        self.trade_alerts_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(alert_row, text="📊 Trade Alerts", variable=self.trade_alerts_var, 
                       font=ctk.CTkFont(size=11)).pack(side=tk.LEFT, padx=10)
        
        self.error_alerts_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(alert_row, text="❌ Error Alerts", variable=self.error_alerts_var, 
                       font=ctk.CTkFont(size=11)).pack(side=tk.LEFT, padx=10)
                       
        if self.is_main and self.controller:
            self.controller.telegram_var = self.telegram_var
            self.controller.trade_alerts_var = self.trade_alerts_var
            self.controller.error_alerts_var = self.error_alerts_var
            
        # Add to lockables
        for w in [self.telegram_var, self.trade_alerts_var, self.error_alerts_var]:
            self._lockable_widgets.append(w)
            
    def _add_ai_intelligence_card(self):
        card = self._create_section_card("AI Intelligence", "🧠", "#00d2ff", "Gemini 3 Flash Integration")
        state = get_shared_state()
        
        # Enable Switch
        switch_frame = ctk.CTkFrame(card, fg_color="transparent")
        switch_frame.pack(fill=tk.X, padx=20, pady=(10, 5))
        
        ctk.CTkLabel(switch_frame, text="Enable Jarvis AI Brain", font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=COLORS["text_main"]).pack(side=tk.LEFT)
        
        self.ai_brain_switch = ctk.CTkSwitch(switch_frame, text="", variable=state.ai_brain_enabled,
                                           progress_color=COLORS["accent_blue"])
        self.ai_brain_switch.pack(side=tk.RIGHT)
        self._lockable_widgets.append(self.ai_brain_switch)
        
        # Model Selection Row
        model_row = ctk.CTkFrame(card, fg_color="transparent")
        model_row.pack(fill=tk.X, padx=20, pady=5)
        
        ctk.CTkLabel(model_row, text="🤖 AI Model", font=ctk.CTkFont(size=11), 
                     text_color=COLORS["text_main"], width=120, anchor=tk.W).pack(side=tk.LEFT)
        
        model_options = ["gemini-3.1-flash-lite", "gemini-1.5-flash", "gemini-1.5-pro"]
        self.model_dropdown = ctk.CTkOptionMenu(model_row, values=model_options,
                                               variable=state.gemini_model,
                                               width=200, height=32, fg_color=COLORS["bg_panel"])
        self.model_dropdown.pack(side=tk.LEFT)
        
        self._lockable_widgets.append(self.model_dropdown)
        
        ctk.CTkLabel(card, text="Note: Gemini 3.1 Flash (Lite) is used for high-speed market selection.\nYour account has been verified for this next-gen model.",
                    font=ctk.CTkFont(size=10, slant="italic"), 
                    text_color=COLORS["text_dim"], justify=tk.LEFT).pack(pady=(5, 12))
    
    def _add_footer(self):
        footer = ctk.CTkFrame(self.scr, fg_color="transparent")
        footer.pack(fill=tk.X, pady=(20, 50))
        
        # Action buttons
        btn_frame = ctk.CTkFrame(footer, fg_color=COLORS["bg_card"], corner_radius=12,
                                border_width=1, border_color=COLORS["border"])
        btn_frame.pack(fill=tk.X)
        
        self.save_btn = ctk.CTkButton(btn_frame, text="💾 Save Configuration", width=180, height=44, 
                     fg_color=COLORS["accent_blue"], text_color="white",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     command=self._save_config)
        self.save_btn.pack(side=tk.LEFT, padx=15, pady=12)
        
        self.reset_btn = ctk.CTkButton(btn_frame, text="🔄 Reset to Defaults", width=150, height=44, 
                     fg_color=COLORS["border"], text_color=COLORS["text_main"],
                     font=ctk.CTkFont(size=11),
                     command=self._reset_config)
        self.reset_btn.pack(side=tk.LEFT, padx=5, pady=12)
        
        # Add control buttons to lockables
        self._lockable_widgets.append(self.save_btn)
        self._lockable_widgets.append(self.reset_btn)

    
    def _auto_update_sl(self):
        """Automatically set Stop-Loss to 50% of Target (1:2 Risk:Reward)"""
        try:
            target_text = self.risk_target.get().strip()
            if target_text and target_text.isdigit():
                target_val = int(target_text)
                sl_val = target_val // 2
                self.risk_sl.delete(0, tk.END)
                self.risk_sl.insert(0, str(sl_val))
        except (ValueError, tk.TclError) as e:
            logger.debug(f"Failed to update SL value: {e}")

    def _on_mode_change(self, value):
        """Sync Paper/Live segmented button with shared paper_trading var."""
        state = get_shared_state()
        state.paper_trading.set(value == "Paper")
    
    def _apply_lock_state(self):
        """Disable widgets when bot is running or AI autopilot is active; enable when stopped."""
        state = get_shared_state()
        try:
            running = state.bot_running.get()
        except Exception:
            running = False

        try:
            ai_active = state.brain_control.get()
        except Exception:
            ai_active = False

        locked = running or ai_active
        new_state = "disabled" if locked else "normal"
        for widget in self._lockable_widgets:
            try:
                widget.configure(state=new_state)
            except Exception:
                pass
        
        # Show a banner at top of config when locked
        if not hasattr(self, '_lock_banner'):
            self._lock_banner = ctk.CTkLabel(
                self.header_frame,
                text="🔒 Config locked - Stop the bot to edit",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLORS["warning"],
                fg_color=COLORS["bg_card"],
                corner_radius=6
            )
        
        if locked:
            if running:
                self._lock_banner.configure(text="🔒 Config locked - Stop the bot to edit")
            else:
                self._lock_banner.configure(text="🧠 Config locked - Jarvis AI Autopilot active")
            self._lock_banner.pack(side=tk.RIGHT, padx=10)
        else:
            self._lock_banner.pack_forget()

    
    def _save_config(self):
        if not self.controller:
            return
        try:
            # Collect data from UI with safety fallbacks
            def safe_get(attr, default=""):
                obj = getattr(self, attr, None)
                if obj and hasattr(obj, "get"): return obj.get()
                return default

            config = {
                "broker_type": safe_get("config_broker", "angel").lower(),
                "risk_rules": {
                    "total_capital": safe_get("risk_capital"),
                    "trade_capital": safe_get("risk_trade"),
                    "trade_target_rs": safe_get("risk_target"),
                    "trade_sl_rs": safe_get("risk_sl"),
                    "max_trades_per_day": safe_get("risk_max_trades", "5"),
                    "max_consecutive_sl": safe_get("risk_max_sl", "3"),
                    "max_daily_loss_rs": safe_get("risk_daily_loss", "2000"),
                    "kill_switch": getattr(self, "kill_switch_var", tk.BooleanVar()).get()
                },
                "broker_settings": {
                    "api_mode": safe_get("api_mode", "Paper"),
                    "candle_period": safe_get("config_candle", "5m"),
                    "time_period": safe_get("time_period", "1 Month"),
                    "paper_trading": safe_get("api_mode", "Paper") == "Paper"
                },
                "strategy": {
                    "name": safe_get("strategy_select", "Combined"),
                    "min_signals": safe_get("config_min_signals", "3"),
                    "entry_start": getattr(self.entry_start_time, "get_time", lambda: "09:15")() if hasattr(self, "entry_start_time") else "09:15",
                    "entry_end": getattr(self.entry_end_time, "get_time", lambda: "14:30")() if hasattr(self, "entry_end_time") else "14:30",
                    "eod_exit": getattr(self.eod_exit_time, "get_time", lambda: "15:10")() if hasattr(self, "eod_exit_time") else "15:10"
                },
                "notifications": {
                    "enabled": getattr(self, "telegram_var", tk.BooleanVar()).get(),
                    "trade_alerts": getattr(self, "trade_alerts_var", tk.BooleanVar()).get(),
                    "error_alerts": getattr(self, "error_alerts_var", tk.BooleanVar()).get()
                },
                "ai_intelligence": {
                    "ai_brain_enabled": self.controller.shared_state.ai_brain_enabled.get() if self.controller else True
                },
                "selected_category": self.controller.shared_state.selected_category.get() if self.controller else "Options",
                "selected_instrument": self.controller.shared_state.selected_instrument.get() if self.controller else "NIFTY",
                "selected_lots": self.controller.shared_state.selected_lots.get() if self.controller else "1"
            }
            
            logger.info(f"UI-SYNC: ConfigView collecting for save")
            
            # Save through controller
            if self.controller and self.controller.save_config(config):
                logger.info("Configuration saved successfully")
            else:
                logger.error("Failed to save configuration")
                
        except Exception as e:
            logger.error(f"Error in _save_config: {e}")
            from src.ui.shared import ToastNotification
            ToastNotification(self.controller, f"Save Error: {str(e)[:50]}", success=False)

    def _load_data(self):
        """Load user data from controller and populate fields."""
        if not self.controller:
            return
            
        data = self.controller.load_config_values()
        if not data:
            return
            
        logger.info(f"Loading configuration for user: {data.get('name', 'unknown')}")
        
        # 1. Broker Connection
        if "broker_type" in data:
            self.config_broker.set(data["broker_type"])
            
        bs = data.get("broker_settings", {})
        if "api_mode" in bs:
            self.api_mode.set(bs["api_mode"])
        if "candle_period" in bs:
            self.config_candle.set(bs["candle_period"])
        if "time_period" in bs:
            self.time_period.set(bs["time_period"])
            
        # 3. Risk Rules - Fallback to UserSettings defaults if missing
        risk = data.get("risk_rules", {})
        
        def populate_risk(widget, key, default):
            val = risk.get(key, default)
            widget.delete(0, tk.END)
            widget.insert(0, str(val))

        populate_risk(self.risk_capital, "total_capital", "1000")
        populate_risk(self.risk_trade, "trade_capital", "1000")
        populate_risk(self.risk_target, "trade_target_rs", "2000")
        populate_risk(self.risk_sl, "trade_sl_rs", "1000")
        populate_risk(self.risk_max_trades, "max_trades_per_day", "5")
        populate_risk(self.risk_max_sl, "max_consecutive_sl", "3")
        populate_risk(self.risk_daily_loss, "max_daily_loss_rs", "5000")
        
        if "kill_switch" in risk:
            self.kill_switch_var.set(risk["kill_switch"])
        else:
            self.kill_switch_var.set(Settings.KILL_AFTER_DAILY_LIMIT if hasattr(Settings, 'KILL_AFTER_DAILY_LIMIT') else False)
            
        # 4. Strategy Settings
        strat = data.get("strategy", {})
        self.strategy_select.set(strat.get("name", "Combined"))
        self.config_min_signals.set(str(strat.get("min_signals", "3")))
        self.entry_start_time.set_time(strat.get("entry_start", "09:15"))
        self.entry_end_time.set_time(strat.get("entry_end", "14:30"))
        self.eod_exit_time.set_time(strat.get("eod_exit", "15:10"))
            
        # 5. Notifications
        notif = data.get("notifications", {})

        # 6. AI Intelligence
        ai = data.get("ai_intelligence", {})
        if "ai_brain_enabled" in ai:
            self.ai_brain_switch.select() if ai["ai_brain_enabled"] else self.ai_brain_switch.deselect()

        # 7. Synchronize SharedState for Sidebar
        self.controller.shared_state.load_from_profile(data)
        logger.info(f"UI-SYNC: ConfigView loaded data - Nifty:{self.controller.shared_state.nifty_lot.get()}, BN:{self.controller.shared_state.banknifty_lot.get()}")
        if "enabled" in notif:
            self.telegram_var.set(notif["enabled"])
        if "trade_alerts" in notif:
            self.trade_alerts_var.set(notif["trade_alerts"])
        if "error_alerts" in notif:
            self.error_alerts_var.set(notif["error_alerts"])
    
    def _reset_config(self):
        if messagebox.askyesno("Reset", "Reset all settings to default values?"):
            ToastNotification(self.controller, "Settings reset to defaults")
    

    
    @property
    def live_components(self):
        return self._live_components
