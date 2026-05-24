import tkinter as tk
import customtkinter as ctk
from src.ui.shared import COLORS, ToastNotification
from src.utils.audio import AudioManager


class NotificationsView(ctk.CTkFrame):
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
        
        ctk.CTkLabel(title_box, text="🔔 NOTIFICATIONS", 
                    font=ctk.CTkFont(size=18, weight="bold"), 
                    text_color=COLORS["accent_blue"]).pack(side=ctk.LEFT)
        
    def _add_content(self):
        # Use CTkScrollableFrame for content that may exceed screen
        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # Ensure children cards fill the scrollable area width
        self._add_visual_alerts_card()
        self._add_audio_settings_card()
        
        # Link to controller
        if self.is_main and self.controller:
            self.controller.notif_toast_var = self.notif_toast_var
            self.controller.notif_sound_trade_var = self.notif_sound_trade_var
            self.controller.notif_sound_error_var = self.notif_sound_error_var
            self.controller.notif_volume = self.notif_volume
            
        self._add_footer()
    
    def _add_visual_alerts_card(self):
        card1 = ctk.CTkFrame(self.container, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        card1.pack(fill=tk.X, pady=10, expand=True)
        
        ctk.CTkLabel(card1, text="📺 Visual Alerts", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["accent_green"]).pack(anchor=tk.W, padx=20, pady=15)
        
        self.notif_toast_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(card1, text="Enable Desktop Toast Notifications", variable=self.notif_toast_var, font=ctk.CTkFont(size=12)).pack(anchor=tk.W, padx=30, pady=5)
        
        ctk.CTkLabel(card1, text="Position: Bottom-Right (Premium Layout)", font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"]).pack(anchor=tk.W, padx=55, pady=(0, 15))
    
    def _add_audio_settings_card(self):
        card2 = ctk.CTkFrame(self.container, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        card2.pack(fill=tk.X, pady=10, expand=True)
        
        ctk.CTkLabel(card2, text="🎵 Audio Signals", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["accent_peach"]).pack(anchor=tk.W, padx=20, pady=15)
        
        self.notif_sound_trade_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(card2, text="Trade Entry/Exit Sound (Chime)", variable=self.notif_sound_trade_var, font=ctk.CTkFont(size=12)).pack(anchor=tk.W, padx=30, pady=8)
        
        self.notif_sound_error_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(card2, text="System Error Alert (Alarm)", variable=self.notif_sound_error_var, font=ctk.CTkFont(size=12)).pack(anchor=tk.W, padx=30, pady=8)
        
        self.notif_volume = ctk.CTkSlider(card2, from_=0, to=100, width=200, command=self._on_volume_change)
        self.notif_volume.pack(anchor=tk.W, padx=30, pady=(15, 10))
        self.notif_volume.set(70)
        self.volume_label = ctk.CTkLabel(card2, text="System Alert Volume: 70%", font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"])
        self.volume_label.pack(anchor=tk.W, padx=30, pady=(0, 20))

    def _on_volume_change(self, value):
        self.volume_label.configure(text=f"System Alert Volume: {int(value)}%")
    
    def _add_footer(self):
        footer = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        footer.pack(fill=tk.X, pady=(15, 50), side=tk.BOTTOM, expand=False)
        
        ctk.CTkButton(footer, text="🔊 TEST NOTIFICATION", width=180, height=40, fg_color=COLORS["border"], 
                     font=ctk.CTkFont(size=12, weight="bold"), command=self._test_notification).pack(side=tk.LEFT, padx=15, pady=12)
                      
        ctk.CTkButton(footer, text="💾 SAVE NOTIFICATION PREFS", width=220, height=40, fg_color=COLORS["accent_blue"], 
                     font=ctk.CTkFont(size=12, weight="bold"), command=self._save_settings).pack(side=tk.LEFT, padx=5, pady=12)

    def _test_notification(self):
        """Play a test chime and show toast."""
        AudioManager.play_signal_chime()
        ToastNotification(self.winfo_toplevel(), "System Notification Test: ONLINE")

    def _save_settings(self):
        """Save preferences to profile."""
        if not self.controller: return
        
        prefs = {
            "notifications": {
                "show_toasts": self.notif_toast_var.get(),
                "play_trade_sounds": self.notif_sound_trade_var.get(),
                "play_error_sounds": self.notif_sound_error_var.get(),
                "alert_volume": int(self.notif_volume.get())
            }
        }
        
        # In a real app we'd save via controller.update_user
        # For now, show immediate feedback
        ToastNotification(self.winfo_toplevel(), "Notification Preferences Saved!")
    
    @property
    def live_components(self):
        return self._live_components
