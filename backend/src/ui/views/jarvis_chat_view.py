"""
Jarvis AI Chat View
- Gemini-only (no Ollama)
- Persistent chat history (survives EXE rebuilds via get_path)
- Timestamps + date separators on every message
- Daily learning: reads & appends to jarvis_brain.md
- Report generation (daily P&L, trade history)
"""

import tkinter as tk
import customtkinter as ctk
import asyncio
import threading
import logging
import json
import os
import re
import queue as q_module
from datetime import datetime, date
from typing import Any, Optional, List, Dict

from src.ui.views.base import BaseView
from src.ui.shared import COLORS, ToastNotification
from src.brain.scoring.llm_analyzer import LLMAnalyzer
from src.utils.paths import get_path, get_data_dir

logger = logging.getLogger("JarvisChatView")

HISTORY_FILE = None   # resolved lazily so get_path works at runtime
MAX_HISTORY_MESSAGES = 200   # Cap stored messages to keep file small


def _history_path() -> str:
    return get_path("jarvis_chat_history.json")


def _brain_path() -> str:
    """jarvis_brain.md lives in data/ — persistent across EXE rebuilds."""
    return os.path.join(get_data_dir(), "jarvis_brain.md")


def _preprocess_markdown(text: Any) -> str:
    """
    Convert common Gemini markdown to clean display text for CTkLabel.
    """
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
        
    lines = text.split('\n')
    result = []
    for line in lines:
        if line.startswith('### '):
            line = '  › ' + line[4:]
        elif line.startswith('## '):
            line = '▸ ' + line[3:]
        elif line.startswith('# '):
            line = '━━ ' + line[2:].upper() + ' ━━'
        elif re.match(r'^[-*] ', line):
            line = '  • ' + line[2:]
        elif re.match(r'^\d+\. ', line):
            line = '  ' + line
        result.append(line)
    text = '\n'.join(result)
    # Bold: **text** → text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Inline code: `code` → [code]
    text = re.sub(r'`(.+?)`', r'[\1]', text)
    # Horizontal rules
    text = re.sub(r'^---+$', '─' * 36, text, flags=re.MULTILINE)
    return text.strip()

import textwrap

def _wrap_text(text: str, width: int = 75) -> str:
    lines = []
    for line in text.split('\n'):
        if not line.strip():
            lines.append("")
        else:
            lines.extend(textwrap.wrap(line, width=width, replace_whitespace=False))
    return "\n".join(lines)


class JarvisChatView(BaseView):
    def __init__(self, parent, controller=None, is_main=True):
        # Start async loop BEFORE super().__init__ (which calls _add_content)
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_event_loop, daemon=True).start()

        # Define layout and state variables before super().__init__ (which calls _add_content)
        self.selected_session_date = None
        self.sidebar_visible = True
        self.session_buttons = {}

        super().__init__(parent, "Jarvis AI", icon="🧠", controller=controller, is_main=is_main)

        self.analyzer = LLMAnalyzer()   # Reads GEMINI_API_KEY via os.getenv / AppSettings
        self.history: List[Dict] = []   # In-memory conversation history for context
        self._is_thinking = False
        self._last_rendered_date: Optional[date] = None

        # Load persisted chat on startup (deferred until mapped to ensure correct layout size calculation)
        self._history_loaded = False
        self.bind("<Map>", self._on_map)

        # Weekly brain summarization (runs in background, non-blocking)
        asyncio.run_coroutine_threadsafe(self._maybe_summarize_brain(), self.loop)

        # Auto-briefing in background
        asyncio.run_coroutine_threadsafe(self._auto_briefing(), self.loop)
        
        # Voice Assistant setup
        from src.utils.audio import HandsFreeVoiceAssistant
        self.voice_assistant = HandsFreeVoiceAssistant(self._on_voice_command, wake_word="jarvis")
        
        # Monitor Voice Mode toggle to start/stop voice
        if self.controller and hasattr(self.controller, "shared_state"):
            self.controller.shared_state.voice_assistant_enabled.trace_add("write", self._on_voice_assistant_enabled_changed)
            # Sync initial state in case it was toggled before view creation
            self.after(100, self._on_voice_assistant_enabled_changed)

    def _on_voice_assistant_enabled_changed(self, *args):
        try:
            state = self.controller.shared_state.voice_assistant_enabled.get()
            if state:
                self.voice_assistant.start()
                if hasattr(self, 'voice_status_label'):
                    if self.voice_assistant.is_listening:
                        self.voice_status_label.configure(text="[ VOICE: LISTENING ]", text_color="#00ff41")
                        if hasattr(self, 'arc_reactor'):
                            self.arc_reactor.start()
                    else:
                        self.voice_status_label.configure(text="[ ERROR: DEPENDENCIES ]", text_color="#ff3333")
                        self.after(50, lambda: self._add_bubble("assistant", "⚠️ **Voice Dependencies Missing**\n\nThe required packages (`SpeechRecognition`) could not be loaded. Please install them to use the voice feature."))
            else:
                self.voice_assistant.stop()
                if hasattr(self, 'voice_status_label'):
                    self.voice_status_label.configure(text="[ VOICE: OFFLINE ]", text_color="#ff3333")
                if hasattr(self, 'arc_reactor'):
                    self.arc_reactor.stop()
                    self.arc_reactor.set(0)
        except Exception as e:
            logger.error(f"Error toggling voice assistant: {e}")

    def _on_voice_command(self, command: str):
        if command == "setup_calibrating":
            self.after(0, lambda: self._add_bubble("assistant", "🎙️ **Voice Setup**: Calibrating ambient room noise... please remain quiet."))
            return

        if command == "setup_listening":
            self.after(0, lambda: self._add_bubble("assistant", "🎙️ **Voice Setup**: Calibration complete! Please say my name **'jarvis'** into your microphone to verify."))
            return

        if command == "setup_complete":
            self.after(0, lambda: self._add_bubble("assistant", "🎙️ **Voice Setup Complete**\n\nAmbient noise calibrated and voice profile verified. I am ready for your commands."))
            return
            
        if command == "wake_only":
            self.after(0, lambda: self._add_bubble("assistant", "Yes sir? I am listening."))
            return
            
        self.after(0, lambda: self._quick_ask(command))

    def _trigger_voice_setup(self):
        """Manually trigger voice calibration setup."""
        setup_file = get_path("voice_setup.json")
        if os.path.exists(setup_file):
            try:
                os.remove(setup_file)
            except Exception:
                pass
        
        if hasattr(self, 'voice_assistant') and self.voice_assistant.is_listening:
            self.voice_assistant.stop()
            self.after(500, self.voice_assistant.start)
            self._add_bubble("assistant", "🎙️ **Voice Setup Initializing...**\n\nPlease wait a moment and then remain quiet for 3 seconds to let me calibrate the background noise.")
        else:
            self._add_bubble("assistant", "⚠️ **Voice Assistant Offline**\n\nPlease enable the 'VOICE MODE' toggle on the top HUD bar first to start the voice assistant, then click Setup Voice again.")


    # ── Event Loop ──────────────────────────────────────────────────────

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    # ── Persistence ─────────────────────────────────────────────────────

    def _on_map(self, event):
        """Callback fired when the view is mapped to screen. Triggers history load once layout is ready."""
        if not self._history_loaded:
            self._history_loaded = True
            self.after(100, self._load_history)

    def _load_history(self):
        """Initial startup history loader. Selects the most recent session date automatically."""
        path = _history_path()
        most_recent_date = datetime.now().strftime("%Y-%m-%d")
        
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                messages = saved if isinstance(saved, list) else []
                if messages:
                    # Find the last message's date
                    last_ts = messages[-1].get("timestamp", "")
                    if last_ts:
                        most_recent_date = last_ts.split()[0]
            except Exception as e:
                logger.error(f"Error reading history for initial load: {e}")
                
        self.selected_session_date = most_recent_date
        self._refresh_history_sidebar()
        self._select_session_date(most_recent_date)

    def _toggle_sidebar(self):
        """Toggle left history panel visibility and update button text/colors."""
        if self.sidebar_visible:
            self.sidebar_frame.pack_forget()
            self.sidebar_visible = False
            self.toggle_btn.configure(text="📁 History", fg_color=COLORS["bg_card"], text_color=COLORS["text_main"])
        else:
            self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), before=self.chat_main_frame)
            self.sidebar_visible = True
            self.toggle_btn.configure(text="📂 History", fg_color="#0a1a2f", text_color="#00d2ff")

    def _format_date_label(self, date_str: str) -> str:
        """Format YYYY-MM-DD date string into a sleek user-friendly label."""
        try:
            from datetime import datetime, timedelta
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now().date()
            if dt.date() == today:
                return "📅 Today"
            elif dt.date() == today - timedelta(days=1):
                return "📅 Yesterday"
            return dt.strftime("📅 %d %b %Y")
        except Exception:
            return f"📅 {date_str}"

    def _refresh_history_sidebar(self):
        """Parse persistent history log, group messages by unique dates, and update sidebar list."""
        path = _history_path()
        unique_dates = set()
        
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                messages = saved if isinstance(saved, list) else []
                
                # Extract date YYYY-MM-DD from timestamp
                for m in messages:
                    t_str = m.get("timestamp", "")
                    if t_str:
                        try:
                            d_str = t_str.split()[0]
                            unique_dates.add(d_str)
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Error loading unique dates: {e}")

        # Clear existing buttons from sidebar scrollable container
        for child in self.history_list_scroll.winfo_children():
            child.destroy()
            
        self.session_buttons = {}

        # Add buttons for each unique date, sorted in reverse order (newest first)
        sorted_dates = sorted(list(unique_dates), reverse=True)
        
        # If no dates exist, ensure a default active session is created
        if not sorted_dates:
            today_str = datetime.now().strftime("%Y-%m-%d")
            sorted_dates = [today_str]
            
        for d_str in sorted_dates:
            lbl_text = self._format_date_label(d_str)
            
            # Determine highlighting color
            is_active = (self.selected_session_date == d_str)
            bg_color = "#0a1a2f" if is_active else "transparent"
            border_c = "#00d2ff" if is_active else "#181825"
            text_c = "#00d2ff" if is_active else COLORS["text_main"]
            
            btn = ctk.CTkButton(
                self.history_list_scroll, text=lbl_text, height=30,
                fg_color=bg_color, border_width=1, border_color=border_c,
                text_color=text_c, hover_color="#1a2f4c",
                anchor="w",
                font=ctk.CTkFont(size=11),
                command=lambda d=d_str: self._select_session_date(d)
            )
            btn.pack(fill=tk.X, pady=2, padx=2)
            self.session_buttons[d_str] = btn

    def _select_session_date(self, date_str: str):
        """Switch to a specific historical session date, loading only its messages."""
        self.selected_session_date = date_str
        self._clear_chat_ui()
        
        path = _history_path()
        day_messages = []
        
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                messages = saved if isinstance(saved, list) else []
                
                # Filter messages belonging to selected date
                for m in messages:
                    t_str = m.get("timestamp", "")
                    if t_str and t_str.split()[0] == date_str:
                        day_messages.append(m)
            except Exception as e:
                logger.error(f"Error loading session for {date_str}: {e}")

        # Update Gemini context memory (last 20 turns of that specific date)
        self.history = [
            {"role": m["role"], "content": m["content"]}
            for m in day_messages[-20:]
            if m.get("role") in ("user", "assistant")
        ]
        
        # Render the filtered bubbles in the UI
        for msg in day_messages:
            self._render_bubble(
                role=msg.get("role", "assistant"),
                text=msg.get("content", ""),
                timestamp_str=msg.get("timestamp", ""),
                skip_save=True,
                auto_scroll=False
            )
            
        self.after(50, self._scroll_to_bottom)
        
        # Refresh sidebar highlighting
        for d, btn in self.session_buttons.items():
            if d == date_str:
                btn.configure(fg_color="#0a1a2f", border_color="#00d2ff", text_color="#00d2ff")
            else:
                btn.configure(fg_color="transparent", border_color="#181825", text_color=COLORS["text_main"])

    def _start_new_chat(self):
        """Clear active conversation context to start a fresh today's session."""
        self._clear_chat_ui()
        self.history = []
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.selected_session_date = today_str
        self._refresh_history_sidebar()
        
        # Render a welcoming bubble from Jarvis
        self._render_bubble(
            role="assistant",
            text="Greetings sir! How can I assist you with your options trading today?",
            timestamp_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            skip_save=True,
            auto_scroll=True
        )

    def _clear_chat_ui(self):
        """Safely destroy all rendered elements in the chat scroll container."""
        for child in self.chat_scroll.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self._last_rendered_date = None

    def _save_message(self, role: str, text: str, timestamp_str: str):
        """Append a single message to the persistent JSON history file and update sidebar."""
        path = _history_path()
        try:
            messages = []
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            messages.append({"role": role, "content": text, "timestamp": timestamp_str})
            # Keep file capped
            if len(messages) > MAX_HISTORY_MESSAGES:
                messages = messages[-MAX_HISTORY_MESSAGES:]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            self._refresh_history_sidebar()
        except Exception as e:
            logger.error(f"Failed to save chat message: {e}")

    # ── Daily Learning ───────────────────────────────────────────────────

    def _learn_from_trade(self, symbol: str, direction: str, pnl: float, reason: str):
        """
        Append a trade outcome lesson to jarvis_brain.md.
        Called after every trade closes so Jarvis learns day by day.
        """
        path = _brain_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            outcome = "Great success!" if pnl >= 0 else "Need to improve entry timing."
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = (
                f"\n- Lesson Learned ({timestamp}): Traded {symbol} ({direction}). "
                f"Result: Rs{pnl:.2f}. Reason: {reason}. {outcome}\n"
            )
            with open(path, "a", encoding="utf-8") as f:
                f.write(entry)
            logger.info(f"Jarvis learned from trade: {symbol} {direction} Rs{pnl:.2f}")
        except Exception as e:
            logger.error(f"Failed to write lesson to jarvis_brain.md: {e}")

    def _read_brain_context(self) -> str:
        """Read jarvis_brain.md for use as Gemini system context."""
        path = _brain_path()
        # Fallback: check source tree (dev mode)
        if not os.path.exists(path):
            src_path = os.path.join("data", "jarvis_brain.md")
            if os.path.exists(src_path):
                path = src_path
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Only pass last 4000 chars to avoid token overrun
                return content[-4000:] if len(content) > 4000 else content
            except Exception:
                pass
        return "You are Jarvis, a professional Indian options trading assistant."

    # ── UI Builder ───────────────────────────────────────────────────────

    def _add_content(self):
        """Build the Iron Man Jarvis HUD split into Sidebar & Chat Panel."""
        outer = ctk.CTkFrame(self, fg_color="#050508") # Deep Space Black
        outer.pack(fill=tk.BOTH, expand=True)

        # ── Top HUD Bar ──
        hud_bar = ctk.CTkFrame(outer, fg_color="transparent", height=60)
        hud_bar.pack(fill=tk.X, pady=(10, 5), padx=15)
        hud_bar.pack_propagate(False)

        # Toggle Sidebar Button at far left
        self.toggle_btn = ctk.CTkButton(
            hud_bar, text="📂 History", width=80, height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0a1a2f", border_width=1, border_color="#00d2ff",
            text_color="#00d2ff", hover_color="#1a2f4c",
            command=self._toggle_sidebar
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=(0, 15))

        ctk.CTkLabel(hud_bar, text="J.A.R.V.I.S  CORE",
                     font=ctk.CTkFont(family="Orbitron", size=24, weight="bold"),
                     text_color="#00d2ff").pack(side=tk.LEFT)

        # Arc Reactor Visualizer
        self.arc_reactor = ctk.CTkProgressBar(hud_bar, width=100, height=8, fg_color="#112233", progress_color="#00d2ff")
        self.arc_reactor.pack(side=tk.RIGHT, padx=15)
        self.arc_reactor.set(0)

        # Voice Mode Toggle Switch
        if self.controller and hasattr(self.controller, "shared_state"):
            state = self.controller.shared_state
            self.voice_switch = ctk.CTkSwitch(
                hud_bar,
                text="VOICE MODE",
                variable=state.voice_assistant_enabled,
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                progress_color="#00d2ff",
                text_color="#89b4fa"
            )
            self.voice_switch.pack(side=tk.RIGHT, padx=15)

        # Voice Assistant Status
        self.voice_status_label = ctk.CTkLabel(hud_bar, text="[ VOICE: OFFLINE ]",
                     font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                     text_color="#ff3333")
        self.voice_status_label.pack(side=tk.RIGHT, padx=10)

        # ── Body Container (Split into Sidebar & Main Chat) ──
        self.body_container = ctk.CTkFrame(outer, fg_color="transparent")
        self.body_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        # 1. Left Sidebar Panel (Chat History list)
        self.sidebar_frame = ctk.CTkFrame(self.body_container, width=180, fg_color="#0b0b10", border_width=1, border_color="#181825")
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.sidebar_frame.pack_propagate(False)

        # Sleek [+ New Chat] button with glowing highlights
        new_chat_btn = ctk.CTkButton(
            self.sidebar_frame, text="+ New Chat", height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0a1a2f", border_width=1, border_color="#00d2ff",
            text_color="#00d2ff", hover_color="#1a2f4c",
            command=self._start_new_chat
        )
        new_chat_btn.pack(fill=tk.X, padx=10, pady=10)

        # Label: SESSIONS
        ctk.CTkLabel(
            self.sidebar_frame, text="💬 SESSIONS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#89b4fa"
        ).pack(anchor="w", padx=12, pady=(5, 5))

        # Scrollable container for dates
        self.history_list_scroll = ctk.CTkScrollableFrame(
            self.sidebar_frame, fg_color="transparent", corner_radius=0, border_width=0
        )
        self.history_list_scroll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 2. Right Main Chat Panel (Contains the Chat Area, Quick Actions & Input)
        self.chat_main_frame = ctk.CTkFrame(self.body_container, fg_color="transparent")
        self.chat_main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Chat Area
        self.chat_scroll = ctk.CTkScrollableFrame(
            self.chat_main_frame, fg_color="transparent", corner_radius=10, border_width=1, border_color="#00d2ff")
        self.chat_scroll.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # ── Quick-Action Buttons ──
        quick = ctk.CTkFrame(self.chat_main_frame, fg_color="transparent")
        quick.pack(fill=tk.X, pady=(0, 6))

        quick_prompts = [
            ("📊 Today's Report",  self._generate_report),
            ("📈 Market Scan",     lambda: self._quick_ask("Scan NIFTY and BANKNIFTY right now. What is the current trend, VIX reading, and your recommendation for today?")),
            ("⚠️ Risk Check",      lambda: self._quick_ask("Review my current risk exposure. Check my daily loss limits, position sizing, and whether I should continue trading today.")),
            ("💡 Strategy Tip",    lambda: self._quick_ask("Give me one high-conviction trading tip for today based on my rules and recent lesson history.")),
            ("🎙️ Setup Voice",     self._trigger_voice_setup),
        ]
        for label, cmd in quick_prompts:
            ctk.CTkButton(
                quick, text=label, height=30,
                fg_color=COLORS["bg_card"],
                text_color=COLORS["text_main"],
                border_width=1, border_color=COLORS["border"],
                hover_color=COLORS["accent_blue"],
                font=ctk.CTkFont(size=11),
                command=cmd
            ).pack(side=tk.LEFT, padx=(0, 6))

        # ── Input Row ──
        inp = ctk.CTkFrame(self.chat_main_frame, fg_color="transparent")
        inp.pack(fill=tk.X)

        self.msg_entry = ctk.CTkEntry(
            inp, placeholder_text="Ask Jarvis anything — market, strategy, report...",
            height=46, corner_radius=10,
            fg_color=COLORS["bg_card"],
            border_width=1, border_color=COLORS["border"])
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.msg_entry.bind("<Return>", lambda e: self._send_message())

        self.send_btn = ctk.CTkButton(
            inp, text="Send ➤", width=90, height=46,
            corner_radius=10,
            fg_color=COLORS["accent_blue"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._send_message)
        self.send_btn.pack(side=tk.RIGHT)

    # ── Chat Rendering ───────────────────────────────────────────────────

    def _add_bubble(self, role: str, text: Any):
        """Public API: add a new bubble, save to disk, render in UI."""
        # Safety: ensure text is string
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
            
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._render_bubble(role, text, timestamp_str, skip_save=False)

    def _render_bubble(self, role: str, text: Any,
                       timestamp_str: str, skip_save: bool = False,
                       auto_scroll: bool = True):
        """Render one chat bubble with timestamp and date separator."""
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        # Parse timestamp
        try:
            ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            ts = datetime.now()
            timestamp_str = ts.strftime("%Y-%m-%d %H:%M:%S")

        msg_date = ts.date()
        display_time = ts.strftime("%I:%M %p")   # 07:31 AM

        # ── Date Separator ──
        if self._last_rendered_date != msg_date:
            self._last_rendered_date = msg_date
            sep_frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
            sep_frame.pack(fill=tk.X, pady=(12, 4))

            ctk.CTkFrame(sep_frame, fg_color=COLORS["border"],
                         height=1).pack(fill=tk.X, side=tk.LEFT, expand=True, pady=8, padx=(0, 8))

            date_label = "Today" if msg_date == date.today() else \
                         "Yesterday" if (date.today() - msg_date).days == 1 else \
                         msg_date.strftime("%d %b %Y")

            ctk.CTkLabel(sep_frame, text=date_label,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=COLORS["text_dim"]).pack(side=tk.LEFT)

            ctk.CTkFrame(sep_frame, fg_color=COLORS["border"],
                         height=1).pack(fill=tk.X, side=tk.LEFT, expand=True, pady=8, padx=(8, 0))

        # ── Bubble ──
        is_user = (role == "user")
        bg = COLORS["accent_blue"] if is_user else COLORS["bg_card"]
        txt_color = "#FFFFFF" if is_user else COLORS["text_main"]
        time_color = "#E0E0E0" if is_user else COLORS["text_dim"]
        
        # User bubbles align right (ne), Jarvis bubbles align left (nw)
        padx = (60, 15) if is_user else (15, 60)
        anchor = "ne" if is_user else "nw"

        bubble = ctk.CTkFrame(self.chat_scroll, fg_color=bg, corner_radius=14)
        bubble.pack(padx=padx, pady=4, anchor=anchor)

        # Meta Row (Name + Timestamp)
        meta = ctk.CTkFrame(bubble, fg_color="transparent")
        meta.pack(fill=tk.X, padx=12, pady=(10, 0))

        name = "YOU" if is_user else "🧠 JARVIS"
        name_color = "#FFFFFF" if is_user else COLORS["accent_blue"]
        
        ctk.CTkLabel(meta, text=name,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=name_color
                     ).pack(side=tk.LEFT)

        ctk.CTkLabel(meta, text=display_time,
                     font=ctk.CTkFont(size=9),
                     text_color=time_color
                     ).pack(side=tk.RIGHT)

        # Message text
        display_text = _preprocess_markdown(text) if role == "assistant" else text
        if not display_text:
            display_text = "..." # Fallback for empty messages

        content_lbl = ctk.CTkLabel(bubble, text=display_text,
                                   font=ctk.CTkFont(size=13),
                                   text_color=txt_color,
                                   justify=tk.LEFT,
                                   anchor="w",
                                   wraplength=450)
        content_lbl.pack(padx=12, pady=(5, 12))

        # Auto-scroll to bottom
        if auto_scroll:
            self.after(50, self._scroll_to_bottom)

        # Persist (unless loading from disk)
        if not skip_save:
            self._save_message(role, text, timestamp_str)
            # Update in-memory history for Gemini context
            self.history.append({"role": role, "content": text})
            if len(self.history) > 20:
                self.history = self.history[-20:]

    def _scroll_to_bottom(self):
        """Force scroll region update and scroll to bottom."""
        try:
            self.chat_scroll.update_idletasks()
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    # ── Auto-Briefing ────────────────────────────────────────────────────

    async def _auto_briefing(self):
        """Morning briefing using Gemini + today's brain context.
        Only fires once per calendar day — skipped if history already has today's briefing.
        """
        # ── Dedup guard: skip if we already sent a briefing today ──
        today_str = datetime.now().strftime("%d %b %Y")
        briefing_tag = f"MORNING BRIEFING — {today_str}"
        for msg in self.history[-5:]:
            if briefing_tag in msg.get("content", ""):
                logger.info("Auto-briefing already sent today — skipping.")
                return

        try:
            brain = self._read_brain_context()
            today_long = datetime.now().strftime("%A, %d %B %Y")

            # Pull model from SharedState so it matches the interactive chat
            model_id = "gemini-3.1-flash-lite"
            if self.controller and hasattr(self.controller, "shared_state"):
                model_id = self.controller.shared_state.gemini_model.get() or model_id

            prompt = (
                f"Today is {today_long}.\n\n"
                f"My Trading Memory & Rules:\n{brain}\n\n"
                "Give me a short Morning Briefing (4-5 lines): current market sentiment "
                "for NIFTY & BANKNIFTY, one key risk to watch today, and a motivational "
                "trading tip. Be concise and professional."
            )
            response = await self.analyzer._call_gemini(
                prompt,
                api_key_override=self._get_api_key(),
                model_id_override=model_id
            )
            self.after(0, lambda r=response: self._add_bubble(
                "assistant",
                f"🌅 **MORNING BRIEFING — {today_str}**\n\n{r}"
            ))
        except Exception as e:
            logger.error(f"Auto-briefing failed: {e}")
            self.after(0, lambda: self._add_bubble(
                "assistant",
                "Good morning! I'm online and ready. Ask me anything about today's market."
            ))

    # ── Report Generation ────────────────────────────────────────────────

    def _generate_report(self):
        """Generate a Gemini AI report from trade history."""
        self._add_bubble("user", "📊 Generate my daily trading report")
        self._set_thinking(True)

        def _run():
            asyncio.run_coroutine_threadsafe(
                self._build_report(), self.loop
            ).result(timeout=60)

        threading.Thread(target=_run, daemon=True).start()

    async def _build_report(self):
        """Read trade history and generate report via Gemini."""
        try:
            trades_log = get_path("trades_log_history.csv")
            audit_log  = get_path("audit_ledger.jsonl")

            # Collect recent trade data
            recent_trades = []
            if os.path.exists(trades_log):
                with open(trades_log, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                # Last 20 lines
                recent_trades = [l.strip() for l in lines[-21:] if l.strip()]

            recent_events = []
            if os.path.exists(audit_log):
                with open(audit_log, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                recent_events = [l.strip() for l in lines[-10:] if l.strip()]

            today_str = datetime.now().strftime("%d %B %Y")
            brain = self._read_brain_context()

            prompt = (
                f"Today is {today_str}. You are Jarvis, a trading analytics AI.\n\n"
                f"Recent Trade Log (CSV):\n" + "\n".join(recent_trades[-15:]) + "\n\n"
                f"Recent Events:\n" + "\n".join(recent_events[-5:]) + "\n\n"
                f"My Trading Rules:\n{brain[:1500]}\n\n"
                "Generate a concise DAILY TRADING REPORT with:\n"
                "1. 📈 Today's P&L Summary (total wins, losses, net)\n"
                "2. 🏆 Best Trade & Worst Trade\n"
                "3. 📊 Win Rate\n"
                "4. ⚠️ Risk Observations (what went wrong / what worked)\n"
                "5. 🧠 Jarvis Recommendation for tomorrow\n"
                "Format with clear sections. Use ₹ for currency."
            )

            # Use model from SharedState so report uses same model as interactive chat
            model_id = "gemini-3.1-flash-lite"
            if self.controller and hasattr(self.controller, "shared_state"):
                model_id = self.controller.shared_state.gemini_model.get() or model_id
            response = await self.analyzer._call_gemini(
                prompt,
                api_key_override=self._get_api_key(),
                model_id_override=model_id
            )
            self.after(0, lambda r=response: (
                self._add_bubble("assistant", r),
                self._set_thinking(False)
            ))

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            self.after(0, lambda: (
                self._add_bubble("assistant", f"⚠️ Report generation failed: {e}"),
                self._set_thinking(False)
            ))

    # ── Market Context Injection ─────────────────────────────────────────

    def _inject_market_context(self):
        """Pull live data from shared state and inject into input."""
        parts = []
        if self.controller and hasattr(self.controller, "shared_state"):
            s = self.controller.shared_state
            try:
                inst = s.selected_instrument.get()
                cat  = s.selected_category.get()
                lots = s.selected_lots.get()
                if inst: parts.append(f"Active: {cat} → {inst} ({lots} lot)")
            except Exception:
                pass
            try:
                pnl = s.total_pnl.get()
                parts.append(f"Session P&L: ₹{pnl:,.2f}")
            except Exception:
                pass

        ctx = " | ".join(parts) if parts else "NIFTY | Session: Active"
        self.msg_entry.delete(0, tk.END)
        self.msg_entry.insert(0, f"Analyze current position: {ctx}. What should I do?")

    # ── Chat Send / Receive ──────────────────────────────────────────────

    def _quick_ask(self, prompt: str):
        """Pre-fill input with a prompt and send immediately."""
        if self._is_thinking:
            return
        self.msg_entry.delete(0, tk.END)
        self.msg_entry.insert(0, prompt)
        self._send_message()

    def _send_message(self):
        if self._is_thinking:
            return
        msg = self.msg_entry.get().strip()
        if not msg:
            return
        self.msg_entry.delete(0, tk.END)
        self._add_bubble("user", msg)
        self._set_thinking(True)
        
        # Pull Gemini API Key & Model from SharedState (on main thread)
        api_key = self._get_api_key()
        model_id = "gemini-3.1-flash-lite"
        if self.controller and hasattr(self.controller, "shared_state"):
            model_id = self.controller.shared_state.gemini_model.get()
        if not model_id:
            model_id = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

        # Use real Gemini streaming for live typing effect
        self._start_streaming_response(msg, api_key, model_id)

    # ── Streaming Response ───────────────────────────────────────────────

    def _start_streaming_response(self, message: str, api_key: str, model_id: str):
        """
        Stream Gemini response token-by-token using a background thread + queue.
        Creates a mutable bubble and updates it as chunks arrive via self.after() polling.
        """
        brain = self._read_brain_context()
        
        # ── Inject System Context ──
        now = datetime.now()
        current_time_str = now.strftime("%I:%M %p")
        current_date_str = now.strftime("%d %B %Y")
        
        recent_trades = ""
        trades_log = get_path("trades_log_history.csv")
        if os.path.exists(trades_log):
            try:
                with open(trades_log, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    recent_trades = "".join(lines[-10:]) if lines else "No trades logged today."
            except Exception:
                recent_trades = "Unable to read trade logs."
        else:
            recent_trades = "No trades logged yet."
            
        system_context = (
            f"[System Environment]\n"
            f"Current Date: {current_date_str}\n"
            f"Current Time: {current_time_str}\n"
            f"Role: You are Jarvis, a highly advanced trading AI.\n\n"
            f"[Recent Trades Log (CSV)]\n{recent_trades}\n\n"
        )
        
        history_text = "\n".join(
            f"{'User' if h['role'] == 'user' else 'Jarvis'}: {h['content']}"
            for h in self.history[-8:]
        )
        
        full_prompt = (
            f"{system_context}"
            f"[Jarvis Memory & Rules]\n{brain[-1500:]}\n\n"
            f"[Conversation History]\n{history_text}\n\n"
            f"User: {message}\nJarvis:"
        )

        # ── Create mutable streaming bubble ──
        display_time = datetime.now().strftime("%I:%M %p")
        msg_date = datetime.now().date()
        if self._last_rendered_date != msg_date:
            self._last_rendered_date = msg_date
            sep = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
            sep.pack(fill=tk.X, pady=(12, 4))
            ctk.CTkFrame(sep, fg_color=COLORS["border"], height=1).pack(
                fill=tk.X, side=tk.LEFT, expand=True, pady=8, padx=(0, 8))
            ctk.CTkLabel(sep, text="Today", font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
            ctk.CTkFrame(sep, fg_color=COLORS["border"], height=1).pack(
                fill=tk.X, side=tk.LEFT, expand=True, pady=8, padx=(8, 0))

        bubble = ctk.CTkFrame(self.chat_scroll, fg_color=COLORS["bg_card"], corner_radius=14)
        bubble.pack(padx=(10, 60), pady=(2, 2), anchor="nw")
        meta = ctk.CTkFrame(bubble, fg_color="transparent")
        meta.pack(fill=tk.X, padx=12, pady=(8, 0))
        ctk.CTkLabel(meta, text="🧠 JARVIS", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=COLORS["accent_blue"]).pack(side=tk.LEFT)
        ctk.CTkLabel(meta, text=display_time, font=ctk.CTkFont(size=9),
                     text_color=COLORS["text_dim"]).pack(side=tk.RIGHT)
        self.after(50, self._scroll_to_bottom)

        content_label = ctk.CTkLabel(bubble, text="▌",
                                     font=ctk.CTkFont(size=13),
                                     text_color=COLORS["text_main"],
                                     justify=tk.LEFT, anchor="w",
                                     wraplength=600)
        content_label.pack(padx=12, pady=(4, 10), anchor=tk.W)

        # ── Stream from background thread ──
        stream_queue = q_module.Queue()
        accumulated = [""]
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def _producer():
            try:
                if not api_key:
                    stream_queue.put(("error", "Gemini API Key missing. Check Settings -> AI Intelligence."))
                    return
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Strip models/ prefix if present
                clean_model = model_id.replace("models/", "")
                
                stream_queue.put(("status", "Jarvis is thinking..."))
                
                model = genai.GenerativeModel(clean_model)
                response = model.generate_content(full_prompt, stream=True)
                for chunk in response:
                    if chunk.text:
                        stream_queue.put(("chunk", chunk.text))
                stream_queue.put(("done", None))
            except Exception as e:
                stream_queue.put(("error", str(e)))

        threading.Thread(target=_producer, daemon=True).start()

        def _poll():
            try:
                while True:
                    kind, data = stream_queue.get_nowait()
                    if kind == "status":
                        content_label.configure(text=data)
                    elif kind == "chunk":
                        if accumulated[0] == "":
                            content_label.configure(text="") # Clear "Thinking..."
                        accumulated[0] += str(data)
                        display_text = _preprocess_markdown(accumulated[0]) + " ▌"
                        content_label.configure(text=display_text)
                        self.after(20, self._scroll_to_bottom)
                    elif kind == "done":
                        final = _preprocess_markdown(accumulated[0])
                        content_label.configure(text=final)
                        self._save_message("assistant", accumulated[0], timestamp_str)
                        self.history.append({"role": "assistant", "content": accumulated[0]})
                        if len(self.history) > 20:
                            self.history = self.history[-20:]
                        self._set_thinking(False)
                        
                        # Add TTS playback
                        from src.utils.audio import AudioManager
                        # Clean markdown for TTS (remove bold/code artifacts)
                        clean_tts = re.sub(r'[\*\#\[\]\─]', '', accumulated[0])
                        AudioManager.speak(clean_tts)
                        
                        return
                    elif kind == "error":
                        err_msg = str(data)
                        if "429" in err_msg:
                            friendly = "⚠️ Quota exceeded (429). Please wait a minute or upgrade your Gemini tier."
                        elif "400" in err_msg:
                            friendly = "⚠️ Token limit or request error (400). Try a shorter question."
                        elif "404" in err_msg:
                            friendly = f"⚠️ Model '{model_id}' not found (404). Check AI Settings."
                        else:
                            friendly = f"⚠️ Error: {err_msg}"
                            
                        content_label.configure(text=friendly, text_color=COLORS["accent_red"])
                        self._set_thinking(False)
                        return
            except q_module.Empty:
                pass
            self.after(50, _poll)

        self.after(50, _poll)

    def _handle_response(self, text: str):
        """Used by non-streaming paths (auto-briefing, report)."""
        self._add_bubble("assistant", text)
        self._set_thinking(False)

    # ── Weekly Brain Summarization ───────────────────────────────────────

    async def _maybe_summarize_brain(self):
        """
        Summarize raw trade lessons in jarvis_brain.md if:
        - There are > 50 lesson lines, OR
        - It's Sunday and we haven't summarized this week.
        Replaces the raw lessons with a concise weekly insight summary.
        """
        try:
            brain_path = _brain_path()
            meta_path = get_path("jarvis_brain_meta.json")
            if not os.path.exists(brain_path):
                return

            with open(brain_path, "r", encoding="utf-8") as f:
                content = f.read()

            lesson_lines = [l for l in content.split('\n')
                            if l.strip().startswith('- Lesson Learned')]

            meta = {}
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    meta = json.load(f)

            today = date.today()
            last_summarized = meta.get("last_summarized", "")
            is_sunday = today.weekday() == 6
            already_done = last_summarized == today.isoformat()

            if already_done:
                return
            if len(lesson_lines) < 50 and not is_sunday:
                return

            logger.info(f"🧠 Jarvis: summarizing {len(lesson_lines)} lessons...")
            raw_lessons = "\n".join(lesson_lines[-100:])
            prompt = (
                f"You are Jarvis, a trading AI. Summarize these trade lessons into "
                f"5-8 concise bullet-point insights that will improve future trading.\n\n"
                f"Lessons:\n{raw_lessons}\n\n"
                "Output ONLY the bullet points — no intro, no conclusion."
            )
            model_id = "gemini-3.1-flash-lite"
            if self.controller and hasattr(self.controller, "shared_state"):
                model_id = self.controller.shared_state.gemini_model.get() or model_id
            summary = await self.analyzer._call_gemini(
                prompt,
                api_key_override=self._get_api_key(),
                model_id_override=model_id
            )

            # Replace raw lessons with summary in brain file
            # Keep everything before the first lesson line
            first_lesson_idx = content.find('- Lesson Learned')
            base = content[:first_lesson_idx].rstrip() if first_lesson_idx > 0 else content
            week_str = today.strftime("%d %b %Y")
            new_content = (
                f"{base}\n\n"
                f"## Weekly Summary ({week_str}) — {len(lesson_lines)} trades analysed\n"
                f"{summary}\n"
            )
            with open(brain_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Save meta
            meta["last_summarized"] = today.isoformat()
            meta["last_lesson_count"] = len(lesson_lines)
            with open(meta_path, "w") as f:
                json.dump(meta, f)

            logger.info("🧠 Jarvis brain summarized and compacted successfully.")
        except Exception as e:
            logger.error(f"Brain summarization failed: {e}")

    # ── AI Market Selection (called from dashboard) ──────────────────────

    def run_market_analysis(self) -> Optional[Dict]:
        """
        Run full multi-market AI analysis.
        Called from a background thread (NOT main thread) — safe to block.
        """
        self.after(0, lambda: self._add_bubble(
            "assistant",
            "🔍 **AI MARKET SELECTION ACTIVE**\n"
            "Analyzing NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY...\n"
            "This takes up to 60 seconds. The UI will stay responsive."
        ))
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._perform_market_analysis(), self.loop)
            result = future.result(timeout=60)

            if result:
                msg = (
                    f"✅ **AI MARKET SELECTION COMPLETE**\n"
                    f"Selected: **{result.get('instrument')}**\n"
                    f"Strategy: {result.get('strategy')}\n"
                    f"Confidence: {result.get('confidence', 0):.0f}%\n"
                    f"Sentiment: {result.get('sentiment')}"
                )
                self.after(0, lambda m=msg: self._add_bubble("assistant", m))
            return result

        except Exception as e:
            logger.error(f"Market analysis failed: {e}")
            self.after(0, lambda: self._add_bubble(
                "assistant",
                "⚠️ Analysis timed out. Falling back to NIFTY with defaults."
            ))
            return {"category": "Options", "instrument": "NIFTY", "lots": "1",
                    "confidence": 0, "strategy": "WAIT_AND_WATCH", "sentiment": "NEUTRAL"}

    async def _perform_market_analysis(self) -> Dict:
        """Multi-market analysis via DecisionEngine with capital awareness."""
        from src.brain.decision_engine import DecisionEngine
        from src.config import UserManager, UserSettings

        capital_context = None

        try:
            # 1. Build Capital Context
            if self.controller and hasattr(self.controller, "current_user_id"):
                user_id = self.controller.current_user_id
                profile = UserManager.get_user(user_id)
                if profile:
                    settings = UserSettings(profile)
                    capital_context = {
                        "capital": settings.TRADE_CAPITAL,
                        "trade_sl": settings.TRADE_SL_RS,
                        "user_lots": settings.NIFTY_LOTS,
                    }

                    # 2. Fetch Live Margin if NOT paper trading
                    if not settings.PAPER_TRADING:
                        self.after(0, lambda: self._add_bubble("assistant", "⏳ **Connecting to broker** to fetch live margin for accurate lot sizing..."))
                        try:
                            broker_type = settings.broker_type.value.lower()
                            broker = None

                            if broker_type == "zerodha":
                                from src.broker.zerodha_broker import ZerodhaBroker
                                broker = ZerodhaBroker(api_key=settings.API_KEY, access_token=settings.ACCESS_TOKEN, is_paper_trading=False)
                            elif broker_type == "angel":
                                from src.broker.angel_broker import AngelBroker
                                broker = AngelBroker(api_key=settings.API_KEY, client_id=settings.CLIENT_ID, password=settings.PASSWORD, totp_secret=settings.TOTP_SECRET, is_paper_trading=False)
                            elif broker_type == "upstox":
                                from src.broker.upstox_broker import UpstoxBroker
                                broker = UpstoxBroker(api_key=settings.API_KEY, api_secret=settings.API_SECRET, access_token=settings.ACCESS_TOKEN, is_paper_trading=False)

                            if broker and broker.login():
                                live_bal = broker.get_balance()
                                if live_bal and live_bal > 0:
                                    capital_context["capital"] = live_bal
                                    self.after(0, lambda b=live_bal: self._add_bubble("assistant", f"✅ **Live Margin Fetched:** ₹{b:,.2f}"))
                                else:
                                    self.after(0, lambda: self._add_bubble("assistant", "⚠️ Could not fetch live margin, falling back to config budget."))
                            else:
                                self.after(0, lambda: self._add_bubble("assistant", "⚠️ Broker login failed. Falling back to config budget."))
                        except Exception as be:
                            logger.error(f"Broker connection failed for capital fetch: {be}")
                            self.after(0, lambda: self._add_bubble("assistant", "⚠️ Broker connection error. Falling back to config budget."))
        except Exception as e:
            logger.error(f"Failed to build capital context: {e}")

        engine = DecisionEngine(settings=None)
        markets = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
        results = await engine.analyze_all_markets(markets, capital_context=capital_context)

        best, best_score = None, -1
        for r in results:
            if r.get("strategy") != "WAIT_AND_WATCH":
                score = float(r.get("confidence", 0))
                if r.get("risk_level") == "LOW":
                    score += 10
                if score > best_score:
                    best_score, best = score, r

        if not best:
            best = results[0] if results else {"selected_market": "NIFTY"}

        return {
            "category": "Options",
            "instrument": best.get("selected_market", "NIFTY"),
            "lots": str(best.get("recommended_lots", "1")),
            "confidence": best.get("confidence", 0),
            "strategy": best.get("strategy", "WAIT_AND_WATCH"),
            "reasoning": best.get("reason", []),
            "sentiment": best.get("ai_consensus", "NEUTRAL")
        }

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_api_key(self) -> str:
        """Safely retrieve the Gemini API key from SharedState or Environment."""
        try:
            if self.controller and hasattr(self.controller, "shared_state"):
                key = self.controller.shared_state.gemini_key.get()
                if key: return key
        except Exception:
            pass
        return os.getenv("GEMINI_API_KEY", "")

    def _set_thinking(self, thinking: bool):
        self._is_thinking = thinking
        self.send_btn.configure(
            text="Thinking..." if thinking else "Send ➤",
            state="disabled" if thinking else "normal"
        )

    def _clear_history(self):
        """Wipe UI and disk history."""
        for child in self.chat_scroll.winfo_children():
            child.destroy()
        self._last_rendered_date = None
        self.history = []
        # Clear file
        try:
            path = _history_path()
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        self._add_bubble("assistant", "Chat history cleared. How can I help you?")
        ToastNotification(self, "Chat history cleared.")
