import tkinter as tk
import customtkinter as ctk
from src.ui.shared import COLORS, IS_DARK, _COLOR_TUPLES
import random
import logging

logger = logging.getLogger("ModernComponents")


class GlassCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        bg = COLORS["bg_card"]
        border = COLORS["border"]
        
        super().__init__(
            master,
            fg_color=bg,
            corner_radius=12,
            border_width=1,
            border_color=border,
            **kwargs
        )
        
        self._add_glass_effect()
    
    def _add_glass_effect(self):
        try:
            from PIL import Image, ImageDraw
            idx = 1 if IS_DARK else 0
            width, height = 200, 100
            image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            
            # Parse hex color string to RGB tuple for PIL
            hex_color = _COLOR_TUPLES["bg_card"][idx].lstrip("#")
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            self.configure(bg_color="transparent")
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to configure card appearance: {e}")


class SkeletonLoader(ctk.CTkFrame):
    def __init__(self, master, width=200, height=20, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.width = width
        self.height = height
        self._animating = False
        
        self._setup_skeleton()
    
    def _setup_skeleton(self):
        bg_color = COLORS["bg_panel"]
        shimmer = COLORS["border"]
        
        self.canvas = tk.Canvas(self, width=self.width, height=self.height, 
                               bg=bg_color, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.rect = self.canvas.create_rectangle(0, 0, self.width, self.height, 
                                                  fill=bg_color, outline="")
        
        self.shimmer_rect = self.canvas.create_rectangle(0, 0, 50, self.height, 
                                                          fill=shimmer, outline="")
        self.canvas.itemconfigure(self.shimmer_rect, state="hidden")
    
    def start_loading(self):
        if not self._animating:
            self._animating = True
            self._animate_shimmer()
    
    def stop_loading(self):
        self._animating = False
        self.canvas.itemconfigure(self.shimmer_rect, state="hidden")
    
    def _animate_shimmer(self):
        if not self._animating:
            return
        
        self.canvas.itemconfigure(self.shimmer_rect, state="normal")
        
        x = -50
        while x < self.width:
            if not self._animating:
                return
            self.canvas.coords(self.shimmer_rect, x, 0, x + 50, self.height)
            self.update()
            self.after(20)
            x += 5
        
        if self._animating:
            self.after(50, self._animate_shimmer)


class SkeletonCard(ctk.CTkFrame):
    def __init__(self, master, title="", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.configure(
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"]
        )
        
        self.title_label = ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                                         text_color=COLORS["text_dim"])
        self.title_label.pack(pady=10)
        
        self.value_skeleton = SkeletonLoader(self, width=100, height=30)
        self.value_skeleton.pack(pady=5)
    
    def show_loading(self):
        self.value_skeleton.start_loading()
    
    def hide_loading(self):
        self.value_skeleton.stop_loading()


class AnimatedButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._hover_animation = True
    
    def _on_enter(self, event=None):
        if self._hover_animation:
            self.configure(cursor="hand")
            if hasattr(self, 'hover_color') and self.hover_color:
                original = self.cget("fg_color")
                self._original_fg = original
                self.configure(fg_color=self.hover_color)
    
    def _on_leave(self, event=None):
        if self._hover_animation and hasattr(self, '_original_fg'):
            self.configure(fg_color=self._original_fg)


class PulseIndicator(ctk.CTkFrame):
    def __init__(self, master, color="#a6e3a1", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.color = color
        self._pulsing = False
        self._dot = None
        
        self._setup_indicator()
    
    def _setup_indicator(self):
        self.canvas = tk.Canvas(self, width=20, height=20, bg="#0a0a0f", highlightthickness=0)
        self.canvas.pack()
        
        self._dot = self.canvas.create_oval(5, 5, 15, 15, fill=self.color, outline="")
    
    def start_pulse(self):
        if not self._pulsing:
            self._pulsing = True
            self._animate_pulse()
    
    def stop_pulse(self):
        self._pulsing = False
    
    def _animate_pulse(self):
        if not self._pulsing:
            return
        
        # COLORS["bg_card"] already returns the resolved hex string — no further indexing
        colors = [self.color, COLORS["bg_card"]]
        current = self.canvas.itemcget(self._dot, "fill")
        idx = colors.index(current) if current in colors else 0
        
        self.canvas.itemconfigure(self._dot, fill=colors[1 - idx])
        self.after(500, self._animate_pulse)


class FadeTransition:
    @staticmethod
    def fade_out(widget, duration=200, callback=None):
        def step(alpha):
            if alpha > 0:
                widget.configure(opacity=alpha)
                widget.after(int(duration/10), lambda: step(alpha - 0.1))
            else:
                widget.configure(opacity=0)
                if callback:
                    callback()
        
        step(1.0)
    
    @staticmethod
    def fade_in(widget, duration=200):
        widget.configure(opacity=0)
        widget.pack()
        
        def step(alpha):
            if alpha < 1:
                widget.configure(opacity=alpha)
                widget.after(int(duration/10), lambda: step(alpha + 0.1))
            else:
                widget.configure(opacity=1)
        
        step(0.1)


class ModernTooltip:
    def __init__(self, widget, text=""):
        self.widget = widget
        self.text = text
        self.tooltip = None
        
        self.widget.bind("<Enter>", self._show)
        self.widget.bind("<Leave>", self._hide)
    
    def _show(self, event=None):
        if self.tooltip:
            return
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{self.widget.winfo_rootx()+10}+{self.widget.winfo_rooty()+30}")
        
        label = tk.Label(self.tooltip, text=self.text, justify=tk.LEFT,
                         bg=COLORS["bg_card"], fg=COLORS["text_main"],
                         font=("Segoe UI", 9), padx=8, pady=4)
        label.pack()
    
    def _hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


def create_modern_card(parent, title="", icon="", value="", subtitle="", 
                       value_color=None, **kwargs):
    card = ctk.CTkFrame(parent, 
                        fg_color=COLORS["bg_card"],
                        corner_radius=12,
                        border_width=1,
                        border_color=COLORS["border"],
                        **kwargs)
    
    if icon:
        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=20)).pack(pady=(10, 0))
    
    if title:
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_dim"]).pack(pady=(5, 0))
    
    if value:
        color = value_color or COLORS["text_main"]
        ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=color).pack(pady=(0, 10))
    
    if subtitle:
        ctk.CTkLabel(card, text=subtitle, font=ctk.CTkFont(size=9),
                    text_color=COLORS["text_dim"]).pack(pady=(0, 10))
    
    return card


def create_modern_section(parent, title, icon="", **kwargs):
    section = ctk.CTkFrame(parent, fg_color="transparent", **kwargs)
    
    header = ctk.CTkFrame(section, fg_color="transparent")
    header.pack(fill=tk.X, pady=(0, 10))
    
    if icon:
        ctk.CTkLabel(header, text=icon, font=ctk.CTkFont(size=14)).pack(side=tk.LEFT)
    
    ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                text_color=COLORS["accent_blue"]).pack(side=tk.LEFT, padx=5)
    
    return section
