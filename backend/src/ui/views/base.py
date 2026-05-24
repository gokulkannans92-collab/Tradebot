import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional, Dict, Any
from src.ui.shared import COLORS, IS_DARK


class BaseView(ctk.CTkFrame):
    def __init__(self, parent, title: str, icon: str = "📄", 
                 allow_popout: bool = True, is_main: bool = True,
                 controller: Optional[Any] = None):
        super().__init__(parent, fg_color="transparent")
        
        self.parent = parent
        self.title = title
        self.icon = icon
        self.allow_popout = allow_popout
        self.is_main = is_main
        self.controller = controller
        self._live_components: Dict[str, Any] = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        self._add_header()
        self._add_content()
    
    def _add_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side=tk.LEFT)
        
        ctk.CTkLabel(title_box, text=f"{self.icon} {self.title.upper()}", 
                    font=ctk.CTkFont(size=18, weight="bold"), 
                    text_color=COLORS["accent_blue"]).pack(side=tk.LEFT)
        
        if self.allow_popout and self.is_main and self.controller and self.title.upper() == "TRADE HISTORY":
            ctk.CTkButton(self.header_frame, text="↗ Pop Out", width=90, height=28,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         fg_color=COLORS["bg_card"], 
                         border_width=1, border_color=COLORS["border"],
                         text_color=COLORS["text_main"], 
                         hover_color=COLORS["accent_blue"],
                         command=self._pop_out).pack(side=tk.RIGHT)
    
    def _add_content(self):
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill=tk.BOTH, expand=True)
    
    def _pop_out(self):
        if self.controller:
            self.controller._pop_out_window(self.title)
    
    @property
    def live_components(self) -> Dict[str, Any]:
        return self._live_components
    
    @live_components.setter
    def live_components(self, value: Dict[str, Any]):
        self._live_components = value
    
    def refresh(self):
        pass
    
    def set_theme(self, is_dark: bool):
        pass
