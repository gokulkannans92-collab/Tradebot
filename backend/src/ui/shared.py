import os
import sys
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from tkinter import ttk as ttk_orig
import logging

logger = logging.getLogger("UIShared")

# ── Distribution Path Handling ──────────────────────────────────
if getattr(sys, 'frozen', False):
    PROJECT_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, '_MEIPASS', PROJECT_DIR)
else:
    # Use __file__ for accurate directory resolution
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
    # shared.py is in src/ui/, so we go up 2 levels
    PROJECT_DIR = os.path.dirname(os.path.dirname(PROJECT_DIR))
    BUNDLE_DIR = PROJECT_DIR

def set_window_icon(window):
    """Unified helper to set window icon with multiple fallbacks and force-set on Windows"""
    # 1. Determine absolute path to icon
    ico_path = None
    
    # Try multiple possible locations
    test_paths = [
        os.path.join(BUNDLE_DIR, "TradeBot.ico"),
        os.path.join(PROJECT_DIR, "TradeBot.ico"),
        "TradeBot.ico",
        os.path.join(os.getcwd(), "TradeBot.ico")
    ]
    
    for p in test_paths:
        if os.path.exists(p):
            ico_path = p
            break
            
    if not ico_path:
        print(f"[UI] WARNING: TradeBot.ico not found in search paths: {test_paths}")
        return
        
    try:
        # 1. Standard Tkinter Icon bitmap
        if sys.platform == "win32":
            try: window.iconbitmap(ico_path)
            except Exception as e:
                print(f"[UI] iconbitmap failed: {e}")
            
        # 2. Icon photo fallback (Pillow)
        try:
            with Image.open(ico_path) as img:
                photo = ImageTk.PhotoImage(img)
                window.iconphoto(True, photo)
                window._icon_photo_ref = photo # Store ref
        except Exception as e:
             print(f"[UI] iconphoto failed: {e}")
            
        # 3. FORCE SET via Windows API (The "Nuclear" option for Taskbar)
        if sys.platform == "win32":
            try:
                import ctypes
                # LoadIconW / SendMessageW codes
                WM_SETICON = 0x80
                ICON_SMALL = 0
                ICON_BIG = 1
                LR_LOADFROMFILE = 0x00000010
                IMAGE_ICON = 1
                
                # Get the window HWND
                hwnd = window.winfo_id()
                
                # Load the icon handle
                hicon = ctypes.windll.user32.LoadImageW(0, ico_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
                if hicon:
                    ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
                    ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
                else:
                    print(f"[UI] LoadImageW failed to get handle for {ico_path}")
            except Exception as e:
                print(f"[UI] Nuclear Win32 icon set failed: {e}")
                
    except Exception as e:
        print(f"[UI] General icon error: {e}")

# Color palettes (Light, Dark) tuples for dynamic switching
# Light mode values adjusted to be 50% less bright (Slate-based theme)
_COLOR_TUPLES = {
    "bg_root": ("#cbd5e1", "#0a0a0f"), 
    "bg_panel": ("#e2e8f0", "#11111b"), 
    "bg_card": ("#f1f5f9", "#181825"),
    "accent_blue": ("#1e40af", "#89b4fa"), 
    "accent_peach": ("#b45309", "#fab387"), 
    "accent_green": ("#065f46", "#a6e3a1"), 
    "accent_red": ("#991b1b", "#f38ba8"), 
    "text_main": ("#0f172a", "#cdd6f4"), 
    "text_dim": ("#475569", "#6c7086"),
    "border": ("#94a3b8", "#313244")
}

class _Colors(dict):
    """Dict that auto-indexes tuple values based on IS_DARK"""
    def __getitem__(self, key):
        val = _COLOR_TUPLES.get(key, "#ffffff")
        dark_idx = 1 if IS_DARK else 0
        return val[dark_idx] if isinstance(val, (list, tuple)) else val
    
    def __getattr__(self, key):
        return self[key]

COLORS = _Colors()

IS_DARK = True

def apply_theme(dark=True):
    global IS_DARK
    IS_DARK = dark
    ctk.set_appearance_mode("dark" if dark else "light")
    
    style = ttk_orig.Style()
    try:
        if "clam" in style.theme_names():
            style.theme_use('clam')
    except:
        pass
    
    bg_dark = "#11111b"
    fg_dark = "#cdd6f4"
    border_dark = "#313244"
    select_dark = "#89b4fa"
    
    for s in ["Treeview", "Custom.Treeview"]:
        style.configure(s, background=bg_dark, foreground=fg_dark, fieldbackground=bg_dark, rowheight=28)
        style.map(s, background=[('selected', select_dark)], foreground=[('selected', '#ffffff')])

    style.configure("Custom.Treeview.Heading", background=border_dark, foreground=fg_dark)


def setup_treeview_style(tree=None, style_name="Custom.Treeview"):
    """Apply dark mode styling to Treeview."""
    style = ttk_orig.Style()
    try:
        if "clam" in style.theme_names():
            style.theme_use('clam')
    except:
        pass
    
    bg_dark = "#11111b"
    fg_dark = "#cdd6f4"
    
    style.configure(style_name, background=bg_dark, foreground=fg_dark, fieldbackground=bg_dark, rowheight=28)
    style.map(style_name, background=[('selected', '#89b4fa')], foreground=[('selected', '#ffffff')])
    
    # ── NUCLEAR OPTION: Overwrite Treeview.field to prevent white borders/backgrounds on Windows ────
    try:
        if sys.platform == "win32":
            style.element_create("Custom.Treeview.field", "from", "default")
            style.layout(style_name, [
                ('Custom.Treeview.treearea', {'sticky': 'nswe'})
            ])
    except:
        pass
    
    if tree:
        try:
            tree.configure(style=style_name)
            tree.tag_configure('profit', background='#1a2d1a', foreground='#a6e3a1')
            tree.tag_configure('loss', background='#2d1a1a', foreground='#f38ba8')
            tree.tag_configure('even', background=bg_dark, foreground=fg_dark)
            tree.tag_configure('selected', background='#2d3d5a', foreground='#ffffff')
        except Exception as e:
            logger.debug(f"Tree setup error: {e}")

class ModernTimePicker(ctk.CTkFrame):
    def __init__(self, master, default_time="09:30", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        try: h, m = default_time.split(":")
        except: h, m = "09", "30"
        self.hour_var = tk.StringVar(value=h.zfill(2))
        self.min_var = tk.StringVar(value=m.zfill(2))
        inner = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=6, border_width=1, border_color=COLORS["border"])
        inner.pack(side=tk.LEFT)
        self.h_entry = ctk.CTkEntry(inner, textvariable=self.hour_var, width=35, height=28, border_width=0, 
                                     fg_color="transparent", font=ctk.CTkFont(size=13, weight="bold"), justify="center")
        self.h_entry.pack(side=tk.LEFT, padx=(5, 0))
        sep = ctk.CTkLabel(inner, text=":", width=8, font=ctk.CTkFont(size=14, weight="bold"))
        sep.pack(side=tk.LEFT)
        self.m_entry = ctk.CTkEntry(inner, textvariable=self.min_var, width=35, height=28, border_width=0, 
                                     fg_color="transparent", font=ctk.CTkFont(size=13, weight="bold"), justify="center")
        self.m_entry.pack(side=tk.LEFT, padx=(0, 5))
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side=tk.LEFT, padx=6)
        ctk.CTkButton(btn_frame, text="▲", width=22, height=14, font=("Arial", 8, "bold"), 
                      fg_color=COLORS["border"], text_color=COLORS["text_main"], hover_color=COLORS["accent_blue"],
                      command=self._inc).pack(pady=(0, 1))
        ctk.CTkButton(btn_frame, text="▼", width=22, height=14, font=("Arial", 8, "bold"), 
                      fg_color=COLORS["border"], text_color=COLORS["text_main"], hover_color=COLORS["accent_blue"],
                      command=self._dec).pack(pady=(1, 0))

    def _inc(self):
        try: 
            self.hour_var.set(str((int(self.hour_var.get()) + 1) % 24).zfill(2))
        except (ValueError, tk.TclError) as e:
            logger.debug(f"Time increment error: {e}")
    
    def _dec(self):
        try: 
            self.hour_var.set(str((int(self.hour_var.get()) - 1) % 24).zfill(2))
        except (ValueError, tk.TclError) as e:
            logger.debug(f"Time decrement error: {e}")

    def configure(self, **kwargs):
        if "state" in kwargs:
            state = kwargs["state"]
            self.h_entry.configure(state=state)
            self.m_entry.configure(state=state)
            for child in self.winfo_children():
                if isinstance(child, ctk.CTkFrame):
                    for btn in child.winfo_children():
                        if isinstance(btn, ctk.CTkButton):
                            btn.configure(state=state)
        super().configure(**kwargs)
            
    def get(self): return f"{self.hour_var.get().zfill(2)}:{self.min_var.get().zfill(2)}"
    def get_time(self): return self.get()
    
    def set_time(self, time_str: str):
        """Set time from string 'HH:MM'."""
        if not time_str or ":" not in time_str:
            return
        try:
            h, m = time_str.split(":")[:2]
            self.hour_var.set(h.zfill(2))
            self.min_var.set(m.zfill(2))
        except Exception as e:
            logger.debug(f"Failed to set time {time_str}: {e}")

# --- Notification Stacking Manager ---
_active_toasts = []

class ToastNotification:
    def __init__(self, parent, message, success=True):
        bg = ("#cbd5e1", "#1e293b") if success else ("#fee2e2", "#1a1010")
        accent = ("#059669", "#10b981") if success else ("#dc2626", "#ef4444")
        mode_idx = 1 if IS_DARK else 0
        
        # Create frame
        self.frame = ctk.CTkFrame(parent, fg_color=bg[mode_idx], border_width=1, border_color=accent[mode_idx], corner_radius=10)
        
        # Calculate Y offset based on existing toasts
        # Each toast is roughly 50-60px high, we use 65px as a step
        offset_y = 60 + (len(_active_toasts) * 65)
        
        self.frame.place(relx=1.0, rely=1.0, anchor="se", x=-25, y=-offset_y)
        
        label = ctk.CTkLabel(
            self.frame, 
            text=f"• {message}", 
            font=ctk.CTkFont(size=12, weight="normal"), 
            text_color=accent[mode_idx], 
            wraplength=360, 
            justify=tk.LEFT
        )
        label.pack(padx=20, pady=12, anchor=tk.W)
        
        self.frame.lift()
        _active_toasts.append(self)
        
        # Schedule destruction
        self.frame.after(4000, self.destroy)

    def destroy(self):
        """Destroy toast and reposition others."""
        try:
            if self in _active_toasts:
                _active_toasts.remove(self)
                
            if hasattr(self, 'frame') and self.frame.winfo_exists():
                self.frame.destroy()
        except:
            pass
            
        # Reposition remaining toasts
        for i, toast in enumerate(_active_toasts):
            try:
                if hasattr(toast, 'frame') and toast.frame.winfo_exists():
                    new_y = 60 + (i * 65)
                    toast.frame.place(relx=1.0, rely=1.0, anchor="se", x=-25, y=-new_y)
                    toast.frame.lift()
            except:
                pass

class LoadingDialog(ctk.CTkToplevel):
    def __init__(self, parent, message="Processing..."):
        super().__init__(parent)
        self.title("Please Wait")
        self.geometry("380x180")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_panel"])
        self.transient(parent)
        self.attributes("-topmost", True)
        px = parent.winfo_x() + (parent.winfo_width() // 2) - (380 // 2)
        py = parent.winfo_y() + (parent.winfo_height() // 2) - (180 // 2)
        self.geometry(f"380x180+{px}+{py}")
        ctk.CTkLabel(self, text=message, font=ctk.CTkFont(size=13)).pack(pady=(30, 10))
        prog = ctk.CTkProgressBar(self, width=280, mode="indeterminate")
        prog.pack(pady=10)
        prog.start()
        set_window_icon(self)

def save_window_geometry(config_obj, win):
    try:
        geom = f"{win.winfo_x()}x{win.winfo_y()}+{win.winfo_width()}+{win.winfo_height()}"
        # store into config if method exists
        if hasattr(config_obj, 'set'):
            try: 
                config_obj.set('window.geometry', geom)
            except Exception as e:
                logger.debug(f"Could not save geometry to config: {e}")
        else:
            # fallback: write attribute
            setattr(config_obj, 'window_geometry', geom)
    except (tk.TclError, AttributeError) as e:
        logger.debug(f"Failed to save window geometry: {e}")

def restore_window_geometry(config_obj, win):
    try:
        geom = None
        if hasattr(config_obj, 'get'):
            try: 
                geom = config_obj.get('window.geometry')
            except Exception as e:
                logger.debug(f"Could not get geometry from config: {e}")
                geom = None
        else:
            geom = getattr(config_obj, 'window_geometry', None)
        if geom:
            try:
                win.geometry(geom)
            except Exception as e:
                logger.debug(f"Could not restore window geometry: {e}")
    except Exception as e:
        logger.debug(f"Error in restore_window_geometry: {e}")
