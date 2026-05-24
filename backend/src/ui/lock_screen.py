"""Lock Screen UI Component with Anti-Stranger Protections"""
import tkinter as tk
import customtkinter as ctk
from typing import Callable
import logging

from src.ui.shared import COLORS
from src.config import UserManager
from src.utils.security import verify_password

logger = logging.getLogger("LockScreen")


class LockScreen(ctk.CTkFrame):
    """Lock screen for user authentication with anti-bypass security."""
    
    def __init__(self, parent, user_id: str, user_name: str, on_unlock: Callable):
        super().__init__(parent, fg_color=COLORS["bg_panel"])
        self.parent = parent
        self.user_id = user_id
        self.user_name = user_name
        self.on_unlock = on_unlock
        self._recovering_focus = False
        
        # Cover parent window layout
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        
        # Store original window state to restore on unlock
        self.original_fullscreen = self.parent.attributes("-fullscreen")
        self.original_topmost = self.parent.attributes("-topmost")
        
        # Enable extreme secure topmost fullscreen mode (covers Taskbar, Start button)
        self.parent.attributes("-fullscreen", True)
        self.parent.attributes("-topmost", True)
        
        self._setup_ui()
        
        # Block Alt+Space system menu and other bypass combinations
        self.parent.bind("<Alt-space>", lambda e: "break")
        
        # Trap keyboard focus and Tab key traversal to block accessing background widgets
        self.parent.bind("<Tab>", self._handle_tab)
        self.parent.bind("<Shift-Tab>", self._handle_tab)
        
        # Bind focus and key monitoring to defeat Alt+Tab and OS shortcut bypasses
        self.parent.bind("<FocusOut>", self._on_focus_loss)
        self.parent.bind("<FocusIn>", self._on_focus_gain)
        
        # Trap keyboard focus
        self.after(50, self._grab_focus)
        
    def _grab_focus(self):
        """Grabs keyboard input focus safely."""
        try:
            self.password_entry.focus_set()
        except Exception as e:
            logger.debug(f"Failed to grab focus: {e}")

    def _on_focus_loss(self, event=None):
        """Defeats Alt+Tab/App Switching by snapping focus back immediately."""
        # Only handle focus loss of the root window itself, ignore internal widget focus transitions
        if event and event.widget != self.parent:
            return
        if getattr(self, "_recovering_focus", False):
            return
        if getattr(self.parent, "ui_locked_state", 0):
            self._recovering_focus = True
            # Defer slightly to avoid infinite event recursion
            self.after(100, self._force_focus_recovery)

    def _on_focus_gain(self, event=None):
        """Re-grabs input when focus is restored."""
        # Only handle focus gain of the root window itself, ignore internal widget focus transitions
        if event and event.widget != self.parent:
            return
        if getattr(self, "_recovering_focus", False):
            return
        if getattr(self.parent, "ui_locked_state", 0):
            self.after(10, self._grab_focus)

    def _force_focus_recovery(self):
        """Forces window back to topmost and grabs input."""
        try:
            self.parent.attributes("-fullscreen", True)
            self.parent.attributes("-topmost", True)
            self.parent.lift()
            self.parent.focus_force()
            self.password_entry.focus_set()
        except Exception as e:
            logger.debug(f"Focus recovery failed: {e}")
        finally:
            self.after(200, self._reset_recovery_flag)

    def _reset_recovery_flag(self):
        self._recovering_focus = False

    def _setup_ui(self):
        """Setup locked workstation UI with premium styling."""
        fonts = {"title": 22, "normal": 13, "bold": 13}
        
        # Center Card
        card = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_card"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
            width=340,
            height=420
        )
        card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        card.pack_propagate(False)
        
        # Secure Lock Badge / Avatar
        ctk.CTkLabel(card, text="🔒", font=("Segoe UI", 48)).pack(pady=(30, 10))
        
        ctk.CTkLabel(
            card,
            text="Workstation Locked",
            font=("Segoe UI", fonts["title"], "bold"),
            text_color=COLORS["accent_blue"]
        ).pack()
        
        ctk.CTkLabel(
            card,
            text=f"Secure session for {self.user_name}",
            font=("Segoe UI", fonts["normal"]),
            text_color=COLORS["text_dim"]
        ).pack(pady=(2, 12))
        
        # Check if AI mode is active
        ai_active = False
        if hasattr(self.parent, "shared_state"):
            try:
                ai_active = self.parent.shared_state.brain_control.get()
            except Exception:
                pass

        if ai_active:
            ai_badge = ctk.CTkLabel(
                card,
                text="🧠 Jarvis AI Autopilot Active",
                font=("Segoe UI", 11, "bold"),
                text_color=COLORS["accent_blue"],
                fg_color=COLORS["bg_panel"],
                corner_radius=6,
                padx=8,
                pady=4
            )
            ai_badge.pack(pady=(0, 10))
            
        # Password entry field
        self.password_entry = ctk.CTkEntry(
            card,
            placeholder_text="Enter account password",
            show="●",
            width=260,
            height=36,
            fg_color=COLORS["bg_panel"],
            border_color=COLORS["border"]
        )
        self.password_entry.pack(pady=(10, 5))
        self.password_entry.bind("<Return>", lambda e: self.attempt_unlock())
        
        # Password options (Show/Hide)
        self.show_pass_var = tk.BooleanVar(value=False)
        self.show_pass_cb = ctk.CTkCheckBox(
            card,
            text="Show Password",
            variable=self.show_pass_var,
            command=self._toggle_pass,
            font=("Segoe UI", fonts["normal"]),
            text_color=COLORS["text_dim"]
        )
        self.show_pass_cb.pack(pady=(2, 10))
        
        # Dynamic warning label
        self.error_label = ctk.CTkLabel(
            card,
            text="",
            font=("Segoe UI", fonts["normal"]),
            text_color=COLORS["accent_red"]
        )
        self.error_label.pack(pady=(0, 5))
        
        # Unlock button
        self.unlock_btn = ctk.CTkButton(
            card,
            text="UNLOCK WORKSTATION",
            font=("Segoe UI", fonts["bold"], "bold"),
            fg_color=COLORS["accent_blue"],
            hover_color="#74c7ec",
            text_color="white",
            width=260,
            height=38,
            command=self.attempt_unlock
        )
        self.unlock_btn.pack(pady=5)
        
    def _toggle_pass(self):
        """Toggle password visibility."""
        self.password_entry.configure(show="" if self.show_pass_var.get() else "●")
        
    def _handle_tab(self, event):
        """Forces tab cycling to remain strictly within the lock screen widgets."""
        if not getattr(self.parent, "ui_locked_state", 0):
            return
        
        try:
            focused = self.parent.focus_get()
            widgets = [self.password_entry, self.show_pass_cb, self.unlock_btn]
            
            # If focus is somehow outside our lock screen widgets, snap it back to password entry
            if focused not in widgets:
                self.password_entry.focus_set()
                return "break"
                
            # Determine direction
            is_shift = (event.state & 0x0001) != 0 # Shift key state
            
            idx = widgets.index(focused)
            if is_shift:
                # Shift+Tab: move backward
                next_widget = widgets[(idx - 1) % len(widgets)]
            else:
                # Tab: move forward
                next_widget = widgets[(idx + 1) % len(widgets)]
                
            next_widget.focus_set()
        except Exception:
            try:
                self.password_entry.focus_set()
            except Exception:
                pass
        return "break"

    def attempt_unlock(self):
        """Validate password and securely restore window layout."""
        password = self.password_entry.get().strip()
        if not password:
            self.error_label.configure(text="Please enter password")
            return
            
        # Authenticate
        user_profile = UserManager.get_user(self.user_id)
        if user_profile:
            stored_pw = user_profile.get("login_password", "")
            if verify_password(password, stored_pw):
                # Unbind secure event monitors
                self.parent.unbind("<FocusOut>")
                self.parent.unbind("<FocusIn>")
                self.parent.unbind("<Tab>")
                self.parent.unbind("<Shift-Tab>")
                self.parent.unbind("<Alt-space>")
                
                # Restore original window layouts (re-enable normal sizing, taskbar, non-topmost)
                self.parent.attributes("-fullscreen", self.original_fullscreen)
                self.parent.attributes("-topmost", self.original_topmost)
                self.parent.state('normal') # In case window state needs kickstarting
                
                self.destroy()
                
                # Execute parent callback
                if self.on_unlock:
                    self.on_unlock()
            else:
                self.error_label.configure(text="❌ Invalid password")
                self.password_entry.delete(0, tk.END)
        else:
            self.error_label.configure(text="❌ User not found")


def show_lock_screen(parent, user_id: str, user_name: str, on_unlock: Callable) -> LockScreen:
    """Show the lock screen overlay."""
    return LockScreen(parent, user_id, user_name, on_unlock)


def hide_lock_screen(lock_screen: LockScreen):
    """Hide the lock screen overlay."""
    if lock_screen:
        try:
            lock_screen.destroy()
        except Exception:
            pass