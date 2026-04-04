"""
TradeBot Dashboard Module
Provides enhanced visualization and analytics capabilities
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


class CandlestickChart(ctk.CTkFrame):
    """Real-time candlestick chart widget for the dashboard"""
    
    def __init__(self, master, width=600, height=400, **kwargs):
        super().__init__(master, **kwargs)
        
        self.width = width
        self.height = height
        self.data = []
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.title_label = ctk.CTkLabel(header, text="📈 Price Chart", 
                                         font=("Segoe UI", 12, "bold"), text_color="#89b4fa")
        self.title_label.pack(side=tk.LEFT)
        
        self.symbol_label = ctk.CTkLabel(header, text="", 
                                         font=("Segoe UI", 11), text_color="#a6e3a1")
        self.symbol_label.pack(side=tk.LEFT, padx=10)
        
        # Chart container
        self.chart_frame = ctk.CTkFrame(self, fg_color="#0a0a0f", corner_radius=8)
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Setup matplotlib figure with dark theme
        plt.style.use('dark_background')
        self.fig = Figure(figsize=(6, 4), dpi=80)
        self.fig.patch.set_facecolor('#0a0a0f')
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#0a0a0f')
        
        # Style the axes
        self.ax.tick_params(colors='#cdd6f4', labelsize=8)
        self.ax.xaxis.label.set_color('#cdd6f4')
        self.ax.yaxis.label.set_color('#cdd6f4')
        self.ax.spines['bottom'].set_color('#45475a')
        self.ax.spines['top'].set_color('#0a0a0f')
        self.ax.spines['left'].set_color('#45475a')
        self.ax.spines['right'].set_color('#0a0a0f')
        self.ax.grid(True, alpha=0.2, color='#45475a')
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Info bar
        info_bar = ctk.CTkFrame(self, fg_color="transparent")
        info_bar.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        self.ohlc_label = ctk.CTkLabel(info_bar, text="O: --  H: --  L: --  C: --  Vol: --",
                                       font=("Consolas", 10), text_color="#6c7086")
        self.ohlc_label.pack(side=tk.LEFT)
        
        self.change_label = ctk.CTkLabel(info_bar, text="--",
                                         font=("Segoe UI", 11, "bold"), text_color="#6c7086")
        self.change_label.pack(side=tk.RIGHT)
        
    def update_data(self, ohlc_data, symbol=None):
        """Update chart with OHLC data
        Args:
            ohlc_data: list of dicts with keys ['time', 'open', 'high', 'low', 'close', 'volume']
        """
        if not ohlc_data:
            return
            
        self.data = ohlc_data
        
        if symbol:
            self.symbol_label.configure(text=symbol)
        
        self._draw_candlestick()
        self._update_info(ohlc_data[-1] if ohlc_data else None)
        
    def _draw_candlestick(self):
        if not self.data:
            return
            
        self.ax.clear()
        
        # Set dark background
        self.ax.set_facecolor('#0a0a0f')
        
        # Extract data
        times = [d.get('time', i) for i, d in enumerate(self.data)]
        opens = [d.get('open', 0) for d in self.data]
        highs = [d.get('high', 0) for d in self.data]
        lows = [d.get('low', 0) for d in self.data]
        closes = [d.get('close', 0) for d in self.data]
        
        x = range(len(opens))
        
        # Draw candlesticks
        for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
            color = '#a6e3a1' if c >= o else '#f38ba8'
            
            # Draw wick
            self.ax.plot([i, i], [l, h], color=color, linewidth=0.8)
            
            # Draw body
            body_bottom = min(o, c)
            body_height = abs(c - o)
            if body_height == 0:
                body_height = 0.1  # Minimum height for doji
                
            self.ax.add_patch(plt.Rectangle(
                (i - 0.35, body_bottom),
                0.7, body_height,
                facecolor=color, edgecolor=color, linewidth=0.5
            ))
        
        # Configure axes
        self.ax.set_xlim(-0.5, len(opens) - 0.5)
        
        if lows and highs:
            y_min = min(lows) * 0.998
            y_max = max(highs) * 1.002
            self.ax.set_ylim(y_min, y_max)
        
        # Add moving average if enough data
        if len(closes) >= 20:
            ma20 = pd.Series(closes).rolling(window=20).mean().values
            self.ax.plot(range(len(ma20)), ma20, color='#89b4fa', 
                         linewidth=1.5, label='MA20', alpha=0.8)
            self.ax.legend(loc='upper left', fontsize=8, facecolor='#0a0a0f', 
                          labelcolor='#89b4fa')
        
        if len(closes) >= 50:
            ma50 = pd.Series(closes).rolling(window=50).mean().values
            self.ax.plot(range(len(ma50)), ma50, color='#fab387', 
                         linewidth=1.5, label='MA50', alpha=0.8)
        
        self.fig.tight_layout()
        self.canvas.draw()
        
    def _update_info(self, latest):
        if not latest:
            return
            
        o = latest.get('open', 0)
        h = latest.get('high', 0)
        l = latest.get('low', 0)
        c = latest.get('close', 0)
        v = latest.get('volume', 0)
        
        self.ohlc_label.configure(
            text=f"O: {o:.2f}  H: {h:.2f}  L: {l:.2f}  C: {c:.2f}  Vol: {v:,.0f}"
        )
        
        if len(self.data) >= 2:
            prev_close = self.data[-2].get('close', c)
            change = ((c - prev_close) / prev_close) * 100
            change_str = f"{change:+.2f}%"
            self.change_label.configure(
                text=change_str,
                text_color="#a6e3a1" if change >= 0 else "#f38ba8"
            )
    
    def add_indicator(self, indicator_type, **params):
        """Add technical indicator overlay"""
        if not self.data:
            return
            
        closes = [d.get('close', 0) for d in self.data]
        
        if indicator_type == 'rsi':
            period = params.get('period', 14)
            rsi = self._calculate_rsi(closes, period)
            self.ax2 = self.ax.twinx()
            self.ax2.set_facecolor('#0a0a0f')
            self.ax2.plot(range(len(rsi)), rsi, color='#f9e2af', linewidth=1.5, alpha=0.8)
            self.ax2.set_ylim(0, 100)
            self.ax2.axhline(30, color='#a6e3a1', linestyle='--', alpha=0.5)
            self.ax2.axhline(70, color='#f38ba8', linestyle='--', alpha=0.5)
            self.ax2.tick_params(colors='#f9e2af')
            self.ax2.set_ylabel('RSI', color='#f9e2af', fontsize=8)
            self.canvas.draw()
            
        elif indicator_type == 'bollinger':
            period = params.get('period', 20)
            std = params.get('std', 2)
            upper, middle, lower = self._calculate_bollinger(closes, period, std)
            self.ax.plot(range(len(upper)), upper, color='#cba6f7', 
                        linewidth=1, linestyle='--', label='BB Upper', alpha=0.7)
            self.ax.plot(range(len(middle)), middle, color='#cba6f7', 
                        linewidth=1, linestyle='-', label='BB Middle', alpha=0.7)
            self.ax.plot(range(len(lower)), lower, color='#cba6f7', 
                        linewidth=1, linestyle='--', label='BB Lower', alpha=0.7)
            self.ax.legend(loc='upper left', fontsize=8, facecolor='#0a0a0f', 
                          labelcolor='#cba6f7')
            self.canvas.draw()
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.convolve(gains, np.ones(period)/period, mode='full')[:len(gains)]
        avg_loss = np.convolve(losses, np.ones(period)/period, mode='full')[:len(losses)]
        
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return [50] * (period - 1) + rsi.tolist()
    
    def _calculate_bollinger(self, prices, period=20, std=2):
        """Calculate Bollinger Bands"""
        prices_series = pd.Series(prices)
        middle = prices_series.rolling(window=period).mean()
        std_dev = prices_series.rolling(window=period).std()
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return upper.values, middle.values, lower.values
    
    def clear(self):
        """Clear the chart"""
        self.data = []
        self.ax.clear()
        self.ax.set_facecolor('#0a0a0f')
        self.fig.tight_layout()
        self.canvas.draw()
        self.symbol_label.configure(text="")
        self.ohlc_label.configure(text="O: --  H: --  L: --  C: --  Vol: --")
        self.change_label.configure(text="--", text_color="#6c7086")


class LineChart(ctk.CTkFrame):
    """Simple line chart for P&L and performance tracking"""
    
    def __init__(self, master, title="", width=400, height=200, **kwargs):
        super().__init__(master, **kwargs)
        
        self.width = width
        self.height = height
        self.title = title
        
        self._setup_ui()
        
    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        ctk.CTkLabel(header, text=f"📊 {self.title}", 
                     font=("Segoe UI", 11, "bold"), text_color="#89b4fa").pack(side=tk.LEFT)
        
        chart_container = ctk.CTkFrame(self, fg_color="#0a0a0f", corner_radius=8)
        chart_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        plt.style.use('dark_background')
        self.fig = Figure(figsize=(4, 2), dpi=80)
        self.fig.patch.set_facecolor('#0a0a0f')
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#0a0a0f')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_container)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def update_data(self, labels, values, color="#a6e3a1"):
        """Update chart with data"""
        self.ax.clear()
        self.ax.set_facecolor('#0a0a0f')
        
        x = range(len(values))
        self.ax.plot(x, values, color=color, linewidth=2, marker='o', markersize=4)
        self.ax.fill_between(x, values, alpha=0.2, color=color)
        
        # Style
        self.ax.tick_params(colors='#cdd6f4', labelsize=8)
        self.ax.spines['bottom'].set_color('#45475a')
        self.ax.spines['top'].set_color('#0a0a0f')
        self.ax.spines['left'].set_color('#45475a')
        self.ax.spines['right'].set_color('#0a0a0f')
        self.ax.grid(True, alpha=0.2, color='#45475a')
        
        if labels:
            self.ax.set_xticks(range(len(labels)))
            self.ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
        
        self.fig.tight_layout()
        self.canvas.draw()


class PieChart(ctk.CTkFrame):
    """Pie chart for portfolio allocation"""
    
    def __init__(self, master, title="", width=300, height=250, **kwargs):
        super().__init__(master, **kwargs)
        
        self.width = width
        self.height = height
        self.title = title
        
        self._setup_ui()
        
    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        ctk.CTkLabel(header, text=f"🥧 {self.title}", 
                     font=("Segoe UI", 11, "bold"), text_color="#89b4fa").pack(side=tk.LEFT)
        
        chart_container = ctk.CTkFrame(self, fg_color="#0a0a0f", corner_radius=8)
        chart_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        plt.style.use('dark_background')
        self.fig = Figure(figsize=(3, 2.5), dpi=80)
        self.fig.patch.set_facecolor('#0a0a0f')
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#0a0a0f')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_container)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def update_data(self, labels, values):
        """Update pie chart"""
        self.ax.clear()
        self.ax.set_facecolor('#0a0a0f')
        
        colors = ['#89b4fa', '#a6e3a1', '#fab387', '#f38ba8', '#cba6f7', '#f9e2af', '#94e2d5']
        
        wedges, texts, autotexts = self.ax.pie(
            values, labels=labels, autopct='%1.1f%%',
            colors=colors[:len(values)],
            textprops={'color': '#cdd6f4', 'fontsize': 8},
            pctdistance=0.75
        )
        
        for autotext in autotexts:
            autotext.set_color('#0a0a0f')
            autotext.set_fontsize(7)
        
        self.fig.tight_layout()
        self.canvas.draw()


class StatCard(ctk.CTkFrame):
    """Enhanced stat card with gradient-like styling"""
    
    def __init__(self, master, title="", value="0", icon="📈", 
                 value_color="#a6e3a1", width=150, height=80, **kwargs):
        super().__init__(master, **kwargs)
        
        self.title_text = title
        self.value_text = value
        self.icon = icon
        self.value_color = value_color
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.configure(fg_color="#11111b", corner_radius=12)
        
        # Icon
        ctk.CTkLabel(self, text=self.icon, font=("Segoe UI", 16)).pack(pady=(10, 0))
        
        # Title
        ctk.CTkLabel(self, text=self.title_text, font=("Segoe UI", 10), 
                     text_color="#6c7086").pack(pady=(5, 0))
        
        # Value
        self.value_label = ctk.CTkLabel(self, text=self.value_text, 
                                         font=("Segoe UI", 18, "bold"), 
                                         text_color=self.value_color)
        self.value_label.pack(pady=(0, 10))
        
    def update_value(self, value, color=None):
        """Update the displayed value"""
        self.value_label.configure(text=value)
        if color:
            self.value_label.configure(text_color=color)


class ThemeToggle(ctk.CTkFrame):
    """Dark/Light theme toggle button"""
    
    def __init__(self, master, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.on_change = on_change
        self.is_dark = True
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.toggle_btn = ctk.CTkButton(
            self, text="🌙", width=40, height=30,
            fg_color="#313244", hover_color="#45475a",
            command=self._toggle_theme
        )
        self.toggle_btn.pack()
        
    def _toggle_theme(self):
        self.is_dark = not self.is_dark
        self.toggle_btn.configure(text="☀️" if not self.is_dark else "🌙")
        
        if self.on_change:
            self.on_change("dark" if self.is_dark else "light")
    
    def get_theme(self):
        return "dark" if self.is_dark else "light"


def create_sample_data(days=30):
    """Generate sample OHLC data for testing"""
    import random
    
    data = []
    base_price = 22000
    base_time = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
    
    for i in range(days):
        minutes_offset = i * 5
        candle_time = base_time + timedelta(minutes=minutes_offset)
        
        open_price = base_price + random.uniform(-100, 100)
        close_price = open_price + random.uniform(-150, 150)
        high_price = max(open_price, close_price) + random.uniform(0, 50)
        low_price = min(open_price, close_price) - random.uniform(0, 50)
        volume = random.randint(100000, 500000)
        
        data.append({
            'time': candle_time,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': volume
        })
        
        base_price = close_price
    
    return data