import tkinter as tk
import customtkinter as ctk
from src.ui.shared import COLORS


class HelpView(ctk.CTkFrame):
    def __init__(self, parent, controller=None, is_main=True):
        super().__init__(parent, fg_color="transparent")
        
        self.controller = controller
        self.is_main = is_main
        self._live_components = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        self._add_header()
        self._add_content()
    
    def _add_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side=ctk.LEFT)
        
        ctk.CTkLabel(title_box, text="❓ HELP & FAQ", 
                    font=ctk.CTkFont(size=20, weight="bold"), 
                    text_color=COLORS["accent_blue"]).pack(side=ctk.LEFT)
        
    def _add_section_header(self, text, icon, color):
        """Helper to create consistent section headers"""
        header_frame = ctk.CTkFrame(self.scr, fg_color="transparent")
        header_frame.pack(fill=tk.X, padx=20, pady=(25, 10), expand=True)
        
        ctk.CTkLabel(header_frame, text=f"{icon} {text}", 
                    font=ctk.CTkFont(size=14, weight="bold"), 
                    text_color=color).pack(side=tk.LEFT)
        
        # Subtle line
        line = ctk.CTkFrame(header_frame, height=2, fg_color=COLORS["border"])
        line.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)
        return header_frame

    def _add_rule_card(self, title, description, icon="•", color=None):
        """Helper to create rule/instruction cards"""
        card = ctk.CTkFrame(self.scr, fg_color=COLORS["bg_card"], corner_radius=10, 
                           border_width=1, border_color=COLORS["border"])
        card.pack(fill=tk.X, padx=20, pady=4, expand=True)
        
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill=tk.X, padx=12, pady=(8, 4))
        
        ctk.CTkLabel(header, text=icon, font=ctk.CTkFont(size=12), text_color=color or COLORS["accent_blue"]).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=11, weight="bold"), 
                    text_color=COLORS["text_main"]).pack(side=tk.LEFT)
        
        ctk.CTkLabel(card, text=description, font=ctk.CTkFont(size=10), 
                    text_color=COLORS["text_dim"], justify=tk.LEFT, 
                    wraplength=500).pack(anchor=tk.W, padx=30, pady=(0, 8))

    def _add_content(self):
        # Use CTkScrollableFrame for content that may exceeds screen
        self.scr = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scr.pack(fill=tk.BOTH, expand=True)
        
        # 🔗 SYSTEM OVERVIEW
        overview_card = ctk.CTkFrame(self.scr, fg_color=COLORS["bg_card"], corner_radius=16, 
                                    border_width=1, border_color=COLORS["border"])
        overview_card.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkLabel(overview_card, text="🤖 TradeBot Pro v2.0.0", 
                    font=ctk.CTkFont(size=18, weight="bold"), 
                    text_color=COLORS["accent_blue"]).pack(pady=(15, 5))
        
        ctk.CTkLabel(overview_card, text="Professional Automated Options Trading System", 
                    font=ctk.CTkFont(size=12), 
                    text_color=COLORS["text_main"]).pack()
        
        stats_row = ctk.CTkFrame(overview_card, fg_color="transparent")
        stats_row.pack(fill=tk.X, pady=15, padx=20)
        
        features = ["✔️ Multi-broker", "✔️ Real-time Signals", "✔️ Risk Management", "✔️ Paper Trading"]
        for f in features:
            ctk.CTkLabel(stats_row, text=f, font=ctk.CTkFont(size=10), text_color=COLORS["accent_green"]).pack(side=tk.LEFT, expand=True)

        # 🛡️ RISK MANAGEMENT RULES
        self._add_section_header("Risk Management Rules", "🛡️", COLORS["accent_peach"])
        
        risk_rules = [
            ("Risk/Reward Ratio", "Fixed 1:2 ratio for all trades to ensure long-term profitability.", "⚖️"),
            ("Fixed Targets", "Profit Target: Rs 2,000 | Stop Loss: Rs 1,000 per trade.", "🎯"),
            ("Daily Trade Limit", "Bot stops automatically after 2 trades to prevent emotional overtrading.", "🛑"),
            ("15% Kill-Switch", "Total account loss exceeding 15% in a day triggers an immediate system halt.", "⚡")
        ]
        
        for title, desc, icon in risk_rules:
            self._add_rule_card(title, desc, icon, COLORS["accent_peach"])

        # 📈 TRAILING STOP LOSS (TSL)
        self._add_section_header("Trailing Stop Loss Ladder", "📈", COLORS["accent_green"])
        
        ctk.CTkLabel(self.scr, text="The bot uses a 4-level progressive ladder to lock in profits:", 
                    font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(anchor=tk.W, padx=25, pady=(0, 5))
        
        tsl_rules = [
            ("Level 1 (30% Profit)", "SL moves to Entry Price (Break-even). Zero-risk zone reached.", "1️⃣"),
            ("Level 2 (50% Profit)", "SL locks in 30% of target profit.", "2️⃣"),
            ("Level 3 (75% Profit)", "SL locks in 50% of target profit.", "3️⃣"),
            ("Level 4 (90% Profit)", "SL locks in 75% of target profit.", "4️⃣")
        ]
        
        for title, desc, icon in tsl_rules:
            self._add_rule_card(title, desc, icon, COLORS["accent_green"])

        # 🧩 TRADING STRATEGY LOGIC
        self._add_section_header("Strategy (Consensus Model)", "🧩", COLORS["accent_blue"])
        
        ctk.CTkLabel(self.scr, text="A trade is only taken if 2-out-of-3 strategies agree:", 
                    font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]).pack(anchor=tk.W, padx=25, pady=(0, 5))
        
        strat_rules = [
            ("EMA Crossover (9/21)", "Uses 9-period and 21-period exponential moving averages for trend confirmation.", "📉"),
            ("Breakout & Volume", "Monitors previous 5m candle breakout with >1.5x average volume spike.", "📊"),
            ("RSI (Relative Strength)", "Bullish signals above 60 RSI | Bearish signals below 40 RSI.", "🕒")
        ]
        
        for title, desc, icon in strat_rules:
            self._add_rule_card(title, desc, icon, COLORS["accent_blue"])

        # ⏰ OPERATIONAL SCHEDULE
        self._add_section_header("Operational Schedule", "⏰", "#cba6f7")
        
        ops_rules = [
            ("Trading Window", "New entries are only permitted between 9:30 AM and 2:30 PM IST.", "🕒"),
            ("Restricted Zone", "No trades during the 'Lunch Zone' (12:00 PM – 1:30 PM) due to low volume.", "🍴"),
            ("Auto-Squareoff", "All open positions are forcibly closed at 3:10 PM to avoid overnight risk.", "🏁"),
            ("Contract Selection", "Automatically selects ATM (At-The-Money) strikes for nearest weekly expiry.", "💎")
        ]
        
        for title, desc, icon in ops_rules:
            self._add_rule_card(title, desc, icon, "#cba6f7")

        # 📌 FAQ SECTION
        self._add_section_header("Frequently Asked Questions", "📌", COLORS["accent_peach"])
        
        faqs = [
            ("How to start trading?", "Configure your broker in settings, then click START BOT in the sidebar."),
            ("What is the 'Consensus Model'?", "It means the bot only trades when multiple technical indicators confirm the same trend."),
            ("Why and when does the bot stop?", "After hitting daily profit/loss, reaching 2 trades, or at 3:10 PM auto-exit."),
            ("Can I change the risk settings?", "Yes, navigate to Settings → Risk Management to adjust capital and limits."),
            ("Need urgent support?", "Contact the developer team via Telegram or support portal.")
        ]
        
        for q, a in faqs:
            frame = ctk.CTkFrame(self.scr, fg_color=COLORS["bg_card"], corner_radius=8)
            frame.pack(fill=tk.X, padx=20, pady=5)
            ctk.CTkLabel(frame, text=f"Q: {q}", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["accent_blue"]).pack(anchor=tk.W, padx=12, pady=(8, 4))
            ctk.CTkLabel(frame, text=f"A: {a}", font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"]).pack(anchor=tk.W, padx=12, pady=(0, 8))
        
        # Spacer
        ctk.CTkFrame(self.scr, height=50, fg_color="transparent").pack()

    @property
    def live_components(self):
        return self._live_components
