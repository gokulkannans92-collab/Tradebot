"""
Market Analysis View - Jarvis Intelligence Dashboard
═══════════════════════════════════════════════════════════════════════════════
"""

import tkinter as tk
import logging
import customtkinter as ctk
import asyncio
import threading
import os
import json
from datetime import datetime
from typing import Dict, List, Any

from src.ui.shared import COLORS, ToastNotification
from src.ui.modern_components import GlassCard, PulseIndicator, SkeletonLoader
from src.brain.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)

class JarvisDashboard(ctk.CTkFrame):
    """Futuristic Jarvis-style market intelligence dashboard."""
    
    def __init__(self, parent, controller=None, is_main: bool = True):
        super().__init__(parent, fg_color="#0a0a0f") # Deep space black
        self.controller = controller
        self.is_main = is_main
        self.is_scanning = False
        self._console_lines = []
        
        self._setup_ui()
        self._load_scan_state()
        
    def _setup_ui(self):
        # 1. TOP HUD (Header)
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=60)
        self.header.pack(fill=tk.X, pady=(10, 20), padx=20)
        
        self.title_label = ctk.CTkLabel(
            self.header, text="CORE INTELLIGENCE SYSTEM",
            font=ctk.CTkFont(family=["Orbitron", "Impact", "Segoe UI Black", "Arial Black"], size=24, weight="bold"),
            text_color="#00d2ff" # Jarvis Cyan
        )
        self.title_label.pack(side=tk.LEFT)
        
        self.pulse = PulseIndicator(self.header, color="#00d2ff")
        self.pulse.pack(side=tk.LEFT, padx=15)
        self.pulse.start_pulse()
        
        self.status_label = ctk.CTkLabel(
            self.header, text="SYSTEM READY",
            font=ctk.CTkFont(size=12),
            text_color="#00ff41" # Matrix Green
        )
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.analyze_btn = ctk.CTkButton(
            self.header, text="⚡ INITIATE SCAN", 
            font=ctk.CTkFont(weight="bold"),
            fg_color="transparent",
            border_width=2,
            border_color="#00d2ff",
            hover_color="#004e5f",
            width=150,
            command=self._refresh_analysis
        )
        self.analyze_btn.pack(side=tk.RIGHT)
        self._last_scan_time = 0
        self._scan_cooldown = 30 # Seconds between scans to respect 5 RPM limit

        # 2. MAIN HUD AREA (Reduced padding to gain horizontal space)
        self.main_hud = ctk.CTkFrame(self, fg_color="transparent")
        self.main_hud.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Split into 2 Columns: Left Column (Pulse & Tactical), Right Column (Intelligence Console Feed)
        self.main_hud.columnconfigure(0, weight=0, minsize=260) # Left Panel (Pulse & Tactical Overview)
        self.main_hud.columnconfigure(1, weight=1)              # Flexible Right Panel (AI Reasoning Console)
        self.main_hud.rowconfigure(0, weight=1)

        # LEFT COLUMN: Container for MARKET PULSE & TACTICAL OVERVIEW
        self.left_panel = ctk.CTkFrame(self.main_hud, fg_color="transparent", width=260)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=10)
         # MARKET PULSE Card
        self.biometrics_frame = GlassCard(self.left_panel)
        self.biometrics_frame.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(self.biometrics_frame, text="MARKET PULSE", 
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#00d2ff").pack(pady=(15, 5))
        
        # Scrollbar-equipped Market Pulse frame
        self.pulse_scroll = ctk.CTkScrollableFrame(
            self.biometrics_frame, fg_color="transparent", height=155, corner_radius=0
        )
        self.pulse_scroll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.market_stats = {}
        
        # Populate initial/default values with all available markets
        default_results = [
            {"selected_market": "NIFTY", "score": 50},
            {"selected_market": "BANKNIFTY", "score": 50},
            {"selected_market": "FINNIFTY", "score": 50},
            {"selected_market": "MIDCPNIFTY", "score": 50},
            {"selected_market": "GOLD", "score": 50},
            {"selected_market": "SILVER", "score": 50},
            {"selected_market": "CRUDEOIL", "score": 50},
            {"selected_market": "RELIANCE", "score": 50},
            {"selected_market": "HDFCBANK", "score": 50}
        ]
        self._render_market_pulse(default_results)

        # TACTICAL OVERVIEW Card (Stretches to fill the remaining height of left column beautifully)
        self.tactical_frame = GlassCard(self.left_panel)
        self.tactical_frame.pack(fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(self.tactical_frame, text="TACTICAL OVERVIEW", font=ctk.CTkFont(size=11, weight="bold"), text_color="#00d2ff").pack(pady=(25, 10))
        
        self.decision_label = ctk.CTkLabel(
            self.tactical_frame, text="PENDING",
            font=ctk.CTkFont(family="Orbitron", size=24, weight="bold"),
            text_color="#ffffff"
        )
        self.decision_label.pack(pady=(15, 5))
        
        self.strategy_label = ctk.CTkLabel(
            self.tactical_frame, text="SYSTEM READY",
            font=ctk.CTkFont(size=12),
            text_color="#00d2ff"
        )
        self.strategy_label.pack(pady=(5, 10))

        self.tactical_scan_time_label = ctk.CTkLabel(
            self.tactical_frame, text="LAST SCAN: NEVER",
            font=ctk.CTkFont(size=10),
            text_color="#8b8ba8"
        )
        self.tactical_scan_time_label.pack(pady=(0, 25))

        # RIGHT COLUMN: MAIN INTELLIGENCE FEED
        self.center_frame = GlassCard(self.main_hud)
        self.center_frame.grid(row=0, column=1, sticky="nsew", padx=10)
        
        ctk.CTkLabel(self.center_frame, text="AI REASONING CONSOLE", 
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#00d2ff").pack(pady=(15, 5))

        self.console_scan_time_label = ctk.CTkLabel(
            self.center_frame, text="LAST SCAN: NEVER",
            font=ctk.CTkFont(size=10),
            text_color="#8b8ba8"
        )
        self.console_scan_time_label.pack(pady=(0, 5))

        # Container for text + scrollbar to save space and display beautifully
        console_container = ctk.CTkFrame(self.center_frame, fg_color="transparent")
        console_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.console_text = tk.Text(
            console_container, 
            bg="#0d1117", fg="#c9d1d9", # GitHub Dark style for better reading
            font=("Segoe UI", 11), # Better typography
            borderwidth=0, highlightthickness=0,
            padx=20, pady=20, # Reduced internal padding to save space
            spacing1=6, spacing2=2, wrap=tk.WORD
        )
        self.console_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ctk.CTkScrollbar(console_container, command=self.console_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.console_text.configure(yscrollcommand=scrollbar.set)
        
        self.console_text.tag_config("prompt", foreground="#58a6ff", font=("Consolas", 11, "bold"))
        self.console_text.tag_config("system", foreground="#00ff41", font=("Consolas", 10))
        self.console_text.tag_config("highlight", foreground="#00d2ff", font=("Segoe UI", 11, "bold"))
        
        self.console_text.insert(tk.END, "> Initializing Jarvis Brain...\n", "system")
        self.console_text.insert(tk.END, "> System status: ONLINE\n", "system")
        self.console_text.insert(tk.END, "> Awaiting deep market scan...\n", "system")
        self.console_text.config(state=tk.DISABLED)


        # 3. BOTTOM TICKER
        self.footer = ctk.CTkFrame(self, fg_color="#1a1a2e", height=30)
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.ticker_label = ctk.CTkLabel(
            self.footer, text="LIVE INTEL: SYSTEM ONLINE | GLOBAL MARKETS: SCANNING... | NEWS FEED: CONNECTED",
            font=ctk.CTkFont(size=10),
            text_color="#00d2ff"
        )
        self.ticker_label.pack(pady=5)



    def _refresh_analysis(self):
        if self.is_scanning: return
        
        # Enforce Cooldown
        import time
        elapsed = time.time() - self._last_scan_time
        if elapsed < self._scan_cooldown:
            wait = int(self._scan_cooldown - elapsed)
            ToastNotification(self, f"System Cooling Down: Wait {wait}s", success=False)
            return

        self.is_scanning = True
        self._last_scan_time = time.time()
        
        self.analyze_btn.configure(text="🛰️ SCANNING...", state="disabled")
        self.status_label.configure(text="ANALYZING DATA", text_color="#fab387")
        
        # Clear previous scan messages from the console
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete("1.0", tk.END)
        self.console_text.config(state=tk.DISABLED)
        
        self._log_to_console("Initiating deep market scan...")
        self._log_to_console("Querying Gemini & Global News sources...")
        
        def run_analysis():
            try:
                from src.config import UserManager, UserSettings
                profile = UserManager.get_user(self.controller.current_user_id)
                settings = UserSettings(profile)
                engine = DecisionEngine(settings=settings)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Parallel Analysis of all 9 markets
                markets_to_scan = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "GOLD", "SILVER", "CRUDEOIL", "RELIANCE", "HDFCBANK"]
                results = loop.run_until_complete(engine.analyze_all_markets(markets_to_scan))
                
                # Trigger Gemini for Strategic Selection
                from src.brain.scoring.llm_analyzer import LLMAnalyzer
                analyzer = LLMAnalyzer(settings)
                gemini_prompt = f"Analyze these market results: {results}. \n" \
                               f"Identify the #1 BEST market to trade today and give 3 high-impact bullet points why."
                gemini_insights = loop.run_until_complete(analyzer.chat(gemini_prompt, provider="gemini"))
                
                loop.close()
                self.after(0, lambda: self._update_ui(results, gemini_insights))
            except Exception as e:
                logger.error(f"Analysis error: {e}")
                self.after(0, self._handle_error)
            
        threading.Thread(target=run_analysis, daemon=True).start()

    def _update_ui(self, results: List[Dict], gemini_insights: str = ""):
        self.is_scanning = False
        self.analyze_btn.configure(text="⚡ INITIATE SCAN", state="normal")
        self.status_label.configure(text="ANALYSIS COMPLETE", text_color="#00ff41")
        
        # Display live scan time in Tactical Overview and AI Console
        scan_time = datetime.now().strftime("%I:%M:%S %p")
        self.tactical_scan_time_label.configure(text=f"LAST SCAN: {scan_time}")
        self.console_scan_time_label.configure(text=f"LAST SCAN: {scan_time}")
        
        # Primary focus analysis for Hero Display
        primary = results[0]
        
        # Detect if AI recommended a specific instrument in the summary
        best_market = primary['selected_market']
        if "XAU/USD" in gemini_insights or "GOLD" in gemini_insights:
            best_market = "XAU/USD (GOLD)"
        elif "SILVER" in gemini_insights:
            best_market = "SILVER"

        self.decision_label.configure(
            text=best_market,
            text_color="#00ff41" if primary['confidence'] > 50 else "#ffffff"
        )
        self.strategy_label.configure(text=f"{primary['strategy']} ({primary['confidence']}%)")
        
        # Update and sort Market Pulse by top performers
        self._render_market_pulse(results)

        # Log AI insights to console with highlighting
        self._log_to_console(f"Consensus achieved: {primary['ai_consensus']}", "highlight")
        for reason in primary.get('ai_reasoning', []):
            if reason.strip():
                self._log_to_console(f"> {reason}")
                
        if gemini_insights:
            self._log_to_console("🧠 JARVIS STRATEGIC INTEL:", "highlight")
            for line in gemini_insights.split("\n"):
                if line.strip():
                    self._log_to_console(line.strip())
                    
        self._log_to_console("Intelligence Scan: SUCCESS. Awaiting triggers.", "system")
        
        # Save scan state to file for persistence across application restarts
        self._save_scan_state(results, gemini_insights, scan_time)


    def _render_market_pulse(self, results: List[Dict]):
        """Render Market Pulse items sorted by score (top performers first)."""
        # Clear existing items inside the scrollable frame
        for child in self.pulse_scroll.winfo_children():
            child.destroy()
        
        self.market_stats = {}
        
        # Sort results by score in descending order (highest score first)
        sorted_results = sorted(results, key=lambda x: x.get("score", 50), reverse=True)
        
        for r in sorted_results:
            market = r.get("selected_market", "UNKNOWN")
            score = r.get("score", 50)
            
            f = ctk.CTkFrame(self.pulse_scroll, fg_color="transparent")
            f.pack(fill=tk.X, padx=5, pady=8)
            
            # Label showing Name + Score percentage
            ctk.CTkLabel(f, text=f"{market} ({score}%)", font=ctk.CTkFont(size=10, weight="bold")).pack(side=tk.LEFT)
            
            # Progress bar as a gauge
            pb = ctk.CTkProgressBar(f, height=6, fg_color="#1a1a2e", progress_color="#00d2ff")
            pb.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
            
            # Set color and value based on performance
            val = score / 100.0
            pb.set(val)
            color = "#00ff41" if score > 60 else "#f38ba8" if score < 40 else "#00d2ff"
            pb.configure(progress_color=color)
            
            self.market_stats[market] = pb


    def _log_to_console(self, message: str, tag: str = None):
        self.console_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}] "
        
        # Save to history for persistence across restarts
        self._console_lines.append({"message": message, "tag": tag, "timestamp": timestamp})
        
        self.console_text.insert(tk.END, prefix, "system")
        self.console_text.insert(tk.END, f"{message}\n", tag)
        
        # Force geometry refresh and scroll to bottom
        self.console_text.update_idletasks()
        self.console_text.see(tk.END)
        self.console_text.config(state=tk.DISABLED)
    def _save_scan_state(self, results: List[Dict], gemini_insights: str, scan_time: str):
        try:
            import json
            from src.utils.paths import get_path
            path = get_path("last_market_scan.json")
            state = {
                "scan_time": scan_time,
                "results": results,
                "gemini_insights": gemini_insights,
                "console_lines": self._console_lines
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save last scan state: {e}")

    def _load_scan_state(self):
        try:
            import json
            from src.utils.paths import get_path
            path = get_path("last_market_scan.json")
            if not os.path.exists(path):
                return
            
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            scan_time = state.get("scan_time")
            results = state.get("results", [])
            gemini_insights = state.get("gemini_insights", "")
            console_lines = state.get("console_lines", [])
            
            if not results:
                return
            
            # 1. Update Labels
            self.tactical_scan_time_label.configure(text=f"LAST SCAN: {scan_time}")
            self.console_scan_time_label.configure(text=f"LAST SCAN: {scan_time}")
            
            primary = results[0]
            best_market = primary['selected_market']
            if "XAU/USD" in gemini_insights or "GOLD" in gemini_insights:
                best_market = "XAU/USD (GOLD)"
            elif "SILVER" in gemini_insights:
                best_market = "SILVER"
                
            self.decision_label.configure(
                text=best_market,
                text_color="#00ff41" if primary.get('confidence', 50) > 50 else "#ffffff"
            )
            self.strategy_label.configure(text=f"{primary.get('strategy', '')} ({primary.get('confidence', 50)}%)")
            
            # 2. Render Market Pulse
            self._render_market_pulse(results)
            
            # 3. Populate Console
            self.console_text.config(state=tk.NORMAL)
            self.console_text.delete("1.0", tk.END)
            self._console_lines = []
            
            for line in console_lines:
                msg = line.get("message", "")
                tag = line.get("tag")
                ts = line.get("timestamp", "")
                
                # Re-add to memory
                self._console_lines.append({"message": msg, "tag": tag, "timestamp": ts})
                
                # Insert to widget
                self.console_text.insert(tk.END, f"[{ts}] ", "system")
                self.console_text.insert(tk.END, f"{msg}\n", tag)
            
            self.console_text.update_idletasks()
            self.console_text.see(tk.END)
            self.console_text.config(state=tk.DISABLED)
            self.after(10, lambda: self.console_text.see(tk.END))
            
        except Exception as e:
            logger.warning(f"Failed to load last scan state: {e}")

    def _handle_error(self):
        self.is_scanning = False
        self.analyze_btn.configure(text="⚡ INITIATE SCAN", state="normal")
        self.status_label.configure(text="SCAN ERROR", text_color="#f38ba8")
        self._log_to_console("!!! ERROR: CONNECTION FAILED TO INTELLIGENCE CORE")

class MarketAnalysisView(JarvisDashboard):
    """Bridge for the main app to load the JarvisDashboard."""
    pass
