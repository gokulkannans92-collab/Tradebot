import tkinter as tk
import customtkinter as ctk
from datetime import datetime, timedelta
import os
import glob
import queue
import logging
from src.ui.shared import COLORS
from src.utils.paths import get_path

logger = logging.getLogger(__name__)

class ConsoleView(ctk.CTkFrame):
    def __init__(self, parent, controller=None, is_main=True):
        super().__init__(parent, fg_color="#1a1a24", height=480)
        
        self.controller = controller
        self.is_main = is_main
        self._live_components = {}
        
        # State tracking for smart updates
        self._last_file_size = 0
        self._last_file_mtime = 0
        self._loaded_lines = set()  # Track loaded line hashes to avoid duplicates
        self._is_selecting = False
        self._file_sync_tick = 0
        
        self.log_queue = queue.Queue() # Fallback local queue
        self.compact_mode_var = tk.BooleanVar(value=True) # Default to compact for senior dev feel
        
        self._setup_ui()
        
        # Register components for real-time updates
        if self.controller:
            self.controller.console_text = self.console_text
        
        # Bind selection events to track user interaction
        self.console_text.bind("<ButtonPress-1>", self._on_selection_start)
        self.console_text.bind("<ButtonRelease-1>", self._on_selection_end)
        self.console_text.bind("<B1-Motion>", self._on_selection_drag)
            
        self._refresh_after_id = None
        
        # Start automatic refresh loop (100ms for Real-time feel)
        self._refresh_loop()
        
    def destroy(self):
        """Clean up background tasks before destruction."""
        if self._refresh_after_id:
            self.after_cancel(self._refresh_after_id)
        super().destroy()
    
    def _refresh_loop(self):
        """Periodically check for NEW logs and append from Queue if available."""
        if not self.winfo_exists():
            return
            
        # 1. High-priority real-time queue processing
        # Prefer the controller's queue if it exists (shared across app)
        target_queue = getattr(self.controller, 'log_queue', self.log_queue)
        
        lines = []
        try:
            # Drain the queue up to a safe batch limit of 100 lines per tick
            count = 0
            while not target_queue.empty() and count < 100:
                line = target_queue.get_nowait()
                lines.append(line)
                count += 1
        except queue.Empty:
            pass
            
        if lines:
            self._append_batch_to_ui(lines)
        
        # 2. Occasional file-sync (for historical/reload sync)
        self._file_sync_tick += 1
        if self._file_sync_tick >= 10: # Sync with file every 1 second (10 * 100ms)
            self._append_new_logs()
            self._file_sync_tick = 0
            
        # Fast 100ms refresh for terminal feel
        self._refresh_after_id = self.after(100, self._refresh_loop)

    def _on_selection_start(self, event):
        self._is_selecting = True

    def _on_selection_end(self, event):
        self.after(500, lambda: setattr(self, '_is_selecting', False))

    def _on_selection_drag(self, event):
        self._is_selecting = True

    def _has_active_selection(self):
        try: return bool(self.console_text.tag_ranges("sel"))
        except: return False

    def _setup_ui(self):
        self._add_header()
        self._add_content()
    
    def _add_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side=ctk.LEFT)
        ctk.CTkLabel(title_box, text="💻 CONSOLE", font=ctk.CTkFont(size=18, weight="bold"), text_color=COLORS["accent_blue"]).pack(side=ctk.LEFT)
        
    def _add_content(self):
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        self._add_controls()
        self._add_console_area()
    
    def _add_controls(self):
        header = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 10))
        
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side=ctk.LEFT)
        self.title_label = ctk.CTkLabel(left, text="⚡ BOT LIVE CONSOLE", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["accent_blue"])
        self.title_label.pack(side=ctk.LEFT)
        self.file_label = ctk.CTkLabel(left, text=" 📁 live_stream", font=ctk.CTkFont(size=9), text_color=COLORS["text_dim"])
        self.file_label.pack(side=tk.LEFT, padx=10)
        
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side=ctk.RIGHT)
        self.log_day_var = tk.StringVar(value="Today")
        ctk.CTkSegmentButton = ctk.CTkSegmentedButton # Handle potential version diff
        self.day_toggle = ctk.CTkSegmentedButton(right, values=["Today", "Yesterday"], variable=self.log_day_var, command=lambda _: self._reload_console(), font=ctk.CTkFont(size=10), height=24, width=140)
        self.day_toggle.pack(side=ctk.LEFT, padx=5)
        ctk.CTkButton(right, text="🔄 Reload", width=70, height=24, fg_color=COLORS["border"], command=self._reload_console).pack(side=ctk.LEFT, padx=2)
        ctk.CTkButton(right, text="🧹 Clear", width=70, height=24, fg_color=COLORS["border"], command=self._clear_console).pack(side=ctk.LEFT, padx=2)
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(right, text="Auto-scroll", variable=self.auto_scroll_var, font=ctk.CTkFont(size=10)).pack(side=ctk.LEFT, padx=5)
        ctk.CTkCheckBox(right, text="Compact", variable=self.compact_mode_var, font=ctk.CTkFont(size=10)).pack(side=ctk.LEFT, padx=5)

    def _add_console_area(self):
        tfr = ctk.CTkFrame(self.content_frame, fg_color="#0d1117", corner_radius=12, border_width=1, border_color=COLORS["border"])
        tfr.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.console_text = tk.Text(tfr, bg="#0d1117", fg="#39d353", font=("Consolas", 10), wrap=tk.WORD, borderwidth=0, highlightthickness=0)
        self.console_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        scrollbar = tk.Scrollbar(tfr, orient=tk.VERTICAL, command=self.console_text.yview, bg="#0d1117", troughcolor="#21262d", highlightthickness=0, width=12, relief=tk.FLAT)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        self.console_text.config(yscrollcommand=scrollbar.set)
        self.console_text.tag_config("err", foreground="#f85149", font=("Consolas", 10, "bold"))     # Red
        self.console_text.tag_config("signal", foreground="#3fb950")  # Brighter Green
        self.console_text.tag_config("warn", foreground="#d29922")    # Amber
        self.console_text.tag_config("ts_dim", foreground="#484f58")  # Dim Gray for timestamps
        self.console_text.tag_config("default", foreground="#c9d1d9") # Off-white
        self.console_text.configure(state=tk.DISABLED)

    def _clear_console(self):
        self.console_text.configure(state=tk.NORMAL)
        self.console_text.delete("1.0", tk.END)
        self.console_text.configure(state=tk.DISABLED)
        self._loaded_lines.clear()
        self._last_file_size = 0

    def _is_user_at_bottom(self):
        try:
            view_start, view_end = self.console_text.yview()
            return view_end > 0.98
        except: return True

    def _append_line_to_ui(self, line: str):
        self._append_batch_to_ui([line])

    def _append_batch_to_ui(self, lines: list):
        if not lines: return
        
        import re
        valid_inserts = []
        
        for line in lines:
            if not line: continue
            
            # --- COMPACT MODE FILTERING ---
            if self.compact_mode_var.get():
                skip_keywords = ["SmartConnect", "SmartApi", "urllib3", "DEBUG", "pooling", "read_bot_output", "websocket", "Ping received", "Pong sent"]
                if any(k in line for k in skip_keywords) and "ERROR" not in line and "CRITICAL" not in line:
                    continue
                high_value = [
                    "TRADE", "SIGNAL", "✅", "🚨", "⚠️", "INITIALIZING", "INITIALIZED", 
                    "STARTING", "SHUTDOWN", "SUCCESS", "FOCUS", "TARGET", "ANALYZING", 
                    "ANALYSIS", "🔍", "📡", "LTP", "CANDLE", "CONNECTING", "INDICATOR", 
                    "STRATEGY", "EMA", "RSI", "VOLUME", "BREAKOUT", "LOT", "TSL", "STOP LOSS"
                ]
                if not any(k in line.upper() for k in high_value) and "ERROR" not in line and "CRITICAL" not in line:
                    continue

            # --- FUTURISTIC FORMATTING ---
            clean_line = line.strip()
            
            # 1. Intelligent Extraction
            match = re.search(r'(\d{2}:\d{2}:\d{2}).*?\s+(?:INFO|ERROR|WARNING|DEBUG|CRITICAL|LOG)?\s*[-:]?\s*(.*)', clean_line)
            if match:
                ts, msg = match.group(1), match.group(2)
            else:
                ts_match = re.search(r'(\d{2}:\d{2}:\d{2})', clean_line)
                ts = ts_match.group(1) if ts_match else ""
                msg = clean_line
                if ts:
                    msg = re.sub(r'.*?' + re.escape(ts) + r'.*?[-:]\s*', '', msg).strip()

            # 2. Path Masking
            def _clean_path(m):
                p = m.group(0).strip()
                if len(p) < 8: return p
                try: return os.path.basename(p.replace("/", "\\"))
                except: return p

            msg = re.sub(r'[A-Za-z]:\\[^ \t\n\r]*', _clean_path, msg)
            msg = re.sub(r'/[^ \t\n\r]+/[^ \t\n\r]+', _clean_path, msg)
            msg = re.sub(r'^\[.*?\]\s*', '', msg).strip()

            tag = "default"
            prefix = "» "
            if "ERROR" in line or "CRITICAL" in line:
                tag, prefix = "err", "✖ "
            elif "WARNING" in line:
                tag, prefix = "warn", "⚠ "
            elif any(k in line.upper() for k in ["TRADE", "SIGNAL", "✅"]):
                tag, prefix = "signal", "✔ "
                
            valid_inserts.append((clean_line, ts, prefix, msg, tag))

        if not valid_inserts:
            return

        was_at_bottom = self._is_user_at_bottom()
        self.console_text.configure(state=tk.NORMAL)
        
        for clean_line, ts, prefix, msg, tag in valid_inserts:
            if ts: self.console_text.insert(tk.END, f"{ts} ", "ts_dim")
            self.console_text.insert(tk.END, prefix, tag)
            self.console_text.insert(tk.END, f"{msg}\n", tag)
            self._loaded_lines.add(hash(clean_line))
            
        num_lines = int(self.console_text.index('end-1c').split('.')[0])
        if num_lines > 1000:
            self.console_text.delete("1.0", f"{num_lines - 1000}.0")
            
        self.console_text.configure(state=tk.DISABLED)
        
        if was_at_bottom and self.auto_scroll_var.get() and not self._is_selecting:
            self.console_text.see(tk.END)

    def _append_new_logs(self):
        """Sync from file to capture external writes or historical data."""
        try:
            if self._is_selecting or self._has_active_selection(): return
            
            bot_log = get_path('trade_bot.log')
            if not os.path.exists(bot_log): return
            
            curr_size = os.path.getsize(bot_log)
            curr_mtime = os.path.getmtime(bot_log)
            
            if curr_size == self._last_file_size and curr_mtime == self._last_file_mtime: return
            
            new_lines = []
            with open(bot_log, 'r', encoding='utf-8', errors='replace') as f:
                if self._last_file_size == 0:
                    # Initial load: read last 100 lines
                    f.seek(0, os.SEEK_END)
                    f.seek(max(0, f.tell() - 20480))
                    lines = f.readlines()
                    for line in lines[-100:]:
                        line_hash = hash(line.strip())
                        if line_hash not in self._loaded_lines:
                            new_lines.append(line)
                elif curr_size > self._last_file_size:
                    f.seek(self._last_file_size)
                    for line in f:
                        line_hash = hash(line.strip())
                        if line_hash not in self._loaded_lines:
                            new_lines.append(line)
                else:
                    # File rotated
                    self._loaded_lines.clear()
                    self._last_file_size = 0
                    
            if new_lines:
                self._append_batch_to_ui(new_lines)
                    
            self._last_file_size = curr_size
            self._last_file_mtime = curr_mtime
        except Exception as e:
            logger.debug(f"File sync error: {e}")

    def _reload_console(self):
        """Manual full reload from file."""
        self._clear_console()
        self._append_new_logs()

    def _parse_log_timestamp(self, line):
        try:
            if len(line) > 23:
                return datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f")
        except ValueError as e:
            logger.debug(f"Failed to parse log timestamp: {e}")
        return datetime.min

    def _sort_lines_by_timestamp(self, lines):
        return sorted(lines, key=self._parse_log_timestamp)
