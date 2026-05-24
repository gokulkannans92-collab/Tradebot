"""
First Run Setup Wizard

Securely collects API keys and configuration on first application launch.
Stores credentials encrypted - never bundles .env in distribution.
"""

import os
import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk
from typing import Optional, Dict, Callable
import logging

from src.utils.security import encrypt_value, set_encryption_key
from src.utils.secure_storage import init_secure_storage, store_credential
from src.ui.responsive import get_optimal_window_size, center_window_geometry, ScreenMetrics, get_adaptive_fonts
from src.ui.shared import COLORS

logger = logging.getLogger(__name__)


class FirstRunWizard:
    """
    First-run configuration wizard for secure API key collection.
    
    Features:
    - Multi-step wizard for broker API keys
    - Telegram configuration
    - Encryption key setup
    - Secure storage to encrypted file (not .env)
    """
    
    SETTINGS_FILE = "data/settings.bin"
    
    def __init__(self, on_complete: Optional[Callable] = None):
        self.root = ctk.CTk()
        self.on_complete = on_complete
        self.current_step = 0
        
        # Collected configuration
        self.config: Dict[str, str] = {}
        
        # Window setup
        self._setup_window()
        
        # Step frames
        self.steps = [
            self._create_welcome_step,
            self._create_encryption_step,
            self._create_broker_step,
            self._create_telegram_step,
            self._create_review_step,
        ]
        
        self.current_frame = None
        self.show_step(0)
        
    def _setup_window(self):
        """Setup responsive wizard window."""
        self.root.title("TradeBot - First Run Setup")
        
        # Responsive sizing
        win_w, win_h = get_optimal_window_size(
            preferred_width=800,
            preferred_height=600,
            min_width=600,
            min_height=500
        )
        
        metrics = ScreenMetrics()
        if metrics.is_large_screen:
            self.root.geometry(f"{win_w}x{win_h}")
        else:
            self.root.geometry(center_window_geometry(win_w, win_h))
        
        self.root.configure(fg_color=COLORS["bg_panel"])
        self.root.resizable(False, False)
        
        # Fonts
        self.fonts = get_adaptive_fonts()
        
    def show_step(self, step_index: int):
        """Show specified wizard step."""
        if self.current_frame:
            self.current_frame.destroy()
        
        self.current_step = step_index
        self.current_frame = self.steps[step_index]()
        self.current_frame.pack(fill="both", expand=True, padx=40, pady=30)
        
    def _create_welcome_step(self):
        """Step 1: Welcome screen."""
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        
        # Title
        ctk.CTkLabel(
            frame,
            text="Welcome to TradeBot",
            font=("Segoe UI", self.fonts["header"], "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(50, 20))
        
        # Description
        ctk.CTkLabel(
            frame,
            text="Let's set up your trading bot securely.",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["text_secondary"]
        ).pack(pady=(0, 30))
        
        # Info box
        info_text = """This wizard will help you:
• Set up master encryption key
• Configure your broker API credentials
• Set up Telegram notifications
• All data will be stored encrypted locally"""
        
        info_box = ctk.CTkTextbox(
            frame,
            width=500,
            height=120,
            font=("Segoe UI", self.fonts["body"]),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_secondary"]
        )
        info_box.pack(pady=20)
        info_box.insert("1.0", info_text)
        info_box.configure(state="disabled")
        
        # Security warning
        ctk.CTkLabel(
            frame,
            text="🔒 Your credentials will never leave this computer",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["accent_green"]
        ).pack(pady=(30, 20))
        
        # Next button
        ctk.CTkButton(
            frame,
            text="Get Started →",
            font=("Segoe UI", self.fonts["body"], "bold"),
            fg_color=COLORS["accent_blue"],
            command=lambda: self.show_step(1),
            width=200,
            height=40
        ).pack(pady=30)
        
        return frame
    
    def _create_encryption_step(self):
        """Step 2: Master encryption key setup."""
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        
        ctk.CTkLabel(
            frame,
            text="Step 1: Master Encryption Key",
            font=("Segoe UI", self.fonts["header"], "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(30, 20))
        
        ctk.CTkLabel(
            frame,
            text="Create a strong master password to encrypt all your credentials.",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["text_secondary"]
        ).pack(pady=(0, 20))
        
        # Password requirements
        ctk.CTkLabel(
            frame,
            text="Requirements:",
            font=("Segoe UI", self.fonts["body"], "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", pady=(20, 5))
        
        reqs = ["• At least 12 characters", "• Mix of uppercase and lowercase", "• Include numbers and symbols"]
        for req in reqs:
            ctk.CTkLabel(
                frame,
                text=req,
                font=("Segoe UI", self.fonts["small"]),
                text_color=COLORS["text_muted"]
            ).pack(anchor="w", padx=20)
        
        # Password entry
        self.encryption_password = ctk.CTkEntry(
            frame,
            placeholder_text="Enter master password",
            show="●",
            width=400,
            font=("Segoe UI", self.fonts["body"])
        )
        self.encryption_password.pack(pady=(30, 10))
        
        self.encryption_confirm = ctk.CTkEntry(
            frame,
            placeholder_text="Confirm master password",
            show="●",
            width=400,
            font=("Segoe UI", self.fonts["body"])
        )
        self.encryption_confirm.pack(pady=(0, 20))
        
        # Warning
        ctk.CTkLabel(
            frame,
            text="⚠️ If you forget this password, all stored credentials will be lost!",
            font=("Segoe UI", self.fonts["small"]),
            text_color=COLORS["warning"]
        ).pack(pady=10)
        
        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=30)
        
        ctk.CTkButton(
            btn_frame,
            text="← Back",
            font=("Segoe UI", self.fonts["body"]),
            fg_color=COLORS["bg_card"],
            command=lambda: self.show_step(0),
            width=120
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame,
            text="Next →",
            font=("Segoe UI", self.fonts["body"], "bold"),
            fg_color=COLORS["accent_blue"],
            command=self._validate_encryption_step,
            width=120
        ).pack(side="left", padx=10)
        
        return frame
    
    def _validate_encryption_step(self):
        """Validate encryption password and proceed."""
        pwd = self.encryption_password.get()
        confirm = self.encryption_confirm.get()
        
        if not pwd or len(pwd) < 12:
            messagebox.showerror("Invalid Password", "Password must be at least 12 characters")
            return
        
        if pwd != confirm:
            messagebox.showerror("Password Mismatch", "Passwords do not match")
            return
        
        # Store temporarily (will be saved at end)
        self.config["_master_key"] = pwd
        self.show_step(2)
    
    def _create_broker_step(self):
        """Step 3: Broker API configuration."""
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        
        ctk.CTkLabel(
            frame,
            text="Step 2: Broker API Configuration",
            font=("Segoe UI", self.fonts["header"], "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(20, 10))
        
        # Broker selection
        ctk.CTkLabel(
            frame,
            text="Select your broker:",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w", pady=(10, 5))
        
        self.broker_var = ctk.StringVar(value="zerodha")
        brokers = ["zerodha", "angel_one", "upstox", "mock"]
        
        broker_frame = ctk.CTkFrame(frame, fg_color="transparent")
        broker_frame.pack(fill="x", pady=10)
        
        for broker in brokers:
            ctk.CTkRadioButton(
                broker_frame,
                text=broker.replace("_", " ").title(),
                variable=self.broker_var,
                value=broker,
                font=("Segoe UI", self.fonts["body"])
            ).pack(anchor="w", pady=5)
        
        # API Key fields frame
        self.api_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.api_frame.pack(fill="x", pady=20)
        
        # API Key
        ctk.CTkLabel(
            self.api_frame,
            text="API Key:",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        self.api_key_entry = ctk.CTkEntry(
            self.api_frame,
            placeholder_text="Enter your broker API key",
            width=500,
            font=("Segoe UI", self.fonts["body"])
        )
        self.api_key_entry.pack(fill="x", pady=(5, 15))
        
        # API Secret
        ctk.CTkLabel(
            self.api_frame,
            text="API Secret:",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        self.api_secret_entry = ctk.CTkEntry(
            self.api_frame,
            placeholder_text="Enter your API secret",
            show="●",
            width=500,
            font=("Segoe UI", self.fonts["body"])
        )
        self.api_secret_entry.pack(fill="x", pady=(5, 15))
        
        # Note
        ctk.CTkLabel(
            frame,
            text="Note: Credentials are encrypted before storage.",
            font=("Segoe UI", self.fonts["small"]),
            text_color=COLORS["accent_green"]
        ).pack(pady=10)
        
        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(
            btn_frame,
            text="← Back",
            font=("Segoe UI", self.fonts["body"]),
            fg_color=COLORS["bg_card"],
            command=lambda: self.show_step(1),
            width=120
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame,
            text="Next →",
            font=("Segoe UI", self.fonts["body"], "bold"),
            fg_color=COLORS["accent_blue"],
            command=self._validate_broker_step,
            width=120
        ).pack(side="left", padx=10)
        
        return frame
    
    def _validate_broker_step(self):
        """Validate broker configuration."""
        broker = self.broker_var.get()
        api_key = self.api_key_entry.get().strip()
        api_secret = self.api_secret_entry.get().strip()
        
        if broker != "mock":
            if not api_key or len(api_key) < 10:
                messagebox.showerror("Invalid API Key", "Please enter a valid API key")
                return
            if not api_secret:
                messagebox.showerror("Invalid API Secret", "Please enter your API secret")
                return
        
        self.config["broker_type"] = broker
        self.config[f"{broker}_api_key"] = api_key
        self.config[f"{broker}_api_secret"] = api_secret
        
        self.show_step(3)
    
    def _create_telegram_step(self):
        """Step 4: Telegram configuration (optional)."""
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        
        ctk.CTkLabel(
            frame,
            text="Step 3: Telegram Notifications (Optional)",
            font=("Segoe UI", self.fonts["header"], "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            frame,
            text="Get trade alerts and status updates via Telegram.",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["text_secondary"]
        ).pack(pady=(0, 20))
        
        # Skip option
        self.skip_telegram = ctk.CTkCheckBox(
            frame,
            text="Skip Telegram setup (you can configure this later)",
            font=("Segoe UI", self.fonts["body"]),
            command=self._toggle_telegram_fields
        )
        self.skip_telegram.pack(anchor="w", pady=10)
        
        # Telegram fields frame
        self.telegram_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.telegram_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            self.telegram_frame,
            text="Bot Token:",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        self.bot_token_entry = ctk.CTkEntry(
            self.telegram_frame,
            placeholder_text="123456789:ABCdefGHIjklMNOpqrSTUvwxyz",
            width=500,
            font=("Segoe UI", self.fonts["body"])
        )
        self.bot_token_entry.pack(fill="x", pady=(5, 15))
        
        ctk.CTkLabel(
            self.telegram_frame,
            text="Chat ID:",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        self.chat_id_entry = ctk.CTkEntry(
            self.telegram_frame,
            placeholder_text="Your Telegram chat ID (e.g., 123456789)",
            width=500,
            font=("Segoe UI", self.fonts["body"])
        )
        self.chat_id_entry.pack(fill="x", pady=(5, 10))
        
        # Help text
        help_text = """How to get these values:
1. Message @BotFather on Telegram to create a bot
2. Copy the bot token provided
3. Message @userinfobot to get your chat ID"""
        
        help_box = ctk.CTkTextbox(
            frame,
            width=500,
            height=80,
            font=("Segoe UI", self.fonts["small"]),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_muted"]
        )
        help_box.pack(pady=10)
        help_box.insert("1.0", help_text)
        help_box.configure(state="disabled")
        
        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(
            btn_frame,
            text="← Back",
            font=("Segoe UI", self.fonts["body"]),
            fg_color=COLORS["bg_card"],
            command=lambda: self.show_step(2),
            width=120
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame,
            text="Next →",
            font=("Segoe UI", self.fonts["body"], "bold"),
            fg_color=COLORS["accent_blue"],
            command=self._validate_telegram_step,
            width=120
        ).pack(side="left", padx=10)
        
        return frame
    
    def _toggle_telegram_fields(self):
        """Toggle visibility of Telegram fields."""
        if self.skip_telegram.get():
            self.telegram_frame.pack_forget()
        else:
            self.telegram_frame.pack(fill="x", pady=10)
    
    def _validate_telegram_step(self):
        """Validate Telegram configuration."""
        if not self.skip_telegram.get():
            token = self.bot_token_entry.get().strip()
            chat_id = self.chat_id_entry.get().strip()
            
            if token:
                if ":" not in token or len(token) < 20:
                    messagebox.showerror("Invalid Token", "Please enter a valid Telegram bot token")
                    return
                
                self.config["telegram_bot_token"] = token
                self.config["telegram_chat_id"] = chat_id
        
        self.show_step(4)
    
    def _create_review_step(self):
        """Step 5: Review and save configuration."""
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        
        ctk.CTkLabel(
            frame,
            text="Review Configuration",
            font=("Segoe UI", self.fonts["header"], "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(20, 20))
        
        # Summary
        summary_text = f"""Broker: {self.config.get('broker_type', 'Not set').upper()}
API Key: {'*' * 10} (encrypted)

Telegram: {'Configured' if 'telegram_bot_token' in self.config else 'Not configured'}
"""
        
        summary_box = ctk.CTkTextbox(
            frame,
            width=500,
            height=100,
            font=("Segoe UI", self.fonts["body"]),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"]
        )
        summary_box.pack(pady=20)
        summary_box.insert("1.0", summary_text)
        summary_box.configure(state="disabled")
        
        # Warning
        ctk.CTkLabel(
            frame,
            text="Click 'Save & Finish' to encrypt and store your credentials.",
            font=("Segoe UI", self.fonts["body"]),
            text_color=COLORS["accent_green"]
        ).pack(pady=20)
        
        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=30)
        
        ctk.CTkButton(
            btn_frame,
            text="← Back",
            font=("Segoe UI", self.fonts["body"]),
            fg_color=COLORS["bg_card"],
            command=lambda: self.show_step(3),
            width=120
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame,
            text="Save & Finish",
            font=("Segoe UI", self.fonts["body"], "bold"),
            fg_color=COLORS["accent_green"],
            command=self._save_configuration,
            width=150
        ).pack(side="left", padx=10)
        
        return frame
    
    def _save_configuration(self):
        """Save all configuration securely."""
        try:
            # Set encryption key
            master_key = self.config.pop("_master_key")
            set_encryption_key(master_key)
            
            # Initialize secure storage
            init_secure_storage(self.SETTINGS_FILE)
            
            # Store each credential
            for key, value in self.config.items():
                if value:
                    store_credential(key, value)
            
            logger.info("First-run configuration saved successfully")
            messagebox.showinfo("Setup Complete", "Your configuration has been saved securely!")
            
            if self.on_complete:
                self.on_complete()
            
            self.root.destroy()
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            messagebox.showerror("Save Failed", f"Could not save configuration: {e}")
    
    def run(self):
        """Run the wizard."""
        self.root.mainloop()


def is_first_run() -> bool:
    """Check if this is the first run (no settings file exists)."""
    return not os.path.exists(FirstRunWizard.SETTINGS_FILE)


def run_first_run_wizard(on_complete: Optional[Callable] = None):
    """
    Run the first-run wizard if needed.
    
    Args:
        on_complete: Callback to run after successful setup
    """
    if is_first_run():
        wizard = FirstRunWizard(on_complete)
        wizard.run()
        return True
    return False


if __name__ == "__main__":
    # Test the wizard
    run_first_run_wizard()
