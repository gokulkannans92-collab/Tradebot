"""Management View - User management interface for TradeBot.

This module handles:
- User table display and management
- User search and filtering
- Add/Edit/Delete user dialogs
- User statistics cards
"""

import json
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from src.config import UserManager as Config
from src.ui.shared import ToastNotification, COLORS
from src.utils.security import get_password_hash
from src.ui.shared_state import get_shared_state
from src.ui.dashboard.components.charts import StatCard, ModernTable
from src.utils.bot_state import is_bot_running
from src.ui.dashboard.constants import USERS_FILE


class ManagementView(ctk.CTkFrame):
    """User management view with add/edit/delete functionality."""

    def __init__(self, parent, controller=None, is_main=True):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.is_main = is_main
        self._live_components = {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup the complete management view UI."""
        # Header
        if self.is_main:
            self._add_header()
        
        # Use a standard frame because the main dashboard container is already scrollable.
        # This prevents redundant scrollbars and allows full expansion.
        main_scr = ctk.CTkFrame(self, fg_color="transparent")
        main_scr.pack(fill=tk.BOTH, expand=True)

        # Stats Cards
        self._add_stats(main_scr)
        
        # Search and Table Header
        self._add_search_header(main_scr)
        
        # User Table
        self._add_users_table(main_scr)
        
        # Initial data load
        self._refresh_data()

    def _add_header(self):
        """Add tab header with title and close button."""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        ctk.CTkLabel(header_frame, text="👥 Management", 
                    font=ctk.CTkFont(size=18, weight="bold"), 
                    text_color=COLORS["accent_blue"]).pack(side=tk.LEFT)
        
        # Close button for popout
        if not self.is_main:
            ctk.CTkButton(header_frame, text="✕", width=30, height=30, 
                         fg_color="transparent", text_color=COLORS["text_dim"],
                         command=self._close_window).pack(side=tk.RIGHT)

    def _add_stats(self, parent):
        """Add user statistics cards."""
        stats = ctk.CTkFrame(parent, fg_color="transparent")
        stats.pack(fill=tk.X, pady=(0, 15))
        stats.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.total_users_card = StatCard(stats, "Total Users", "0", "👥", COLORS["accent_blue"])
        self.total_users_card.grid(row=0, column=0, padx=5)
        
        self.active_users_card = StatCard(stats, "Active", "0", "✅", COLORS["accent_green"])
        self.active_users_card.grid(row=0, column=1, padx=5)
        
        self.inactive_users_card = StatCard(stats, "Inactive", "0", "❌", COLORS["accent_red"])
        self.inactive_users_card.grid(row=0, column=2, padx=5)

        self.activity_rate_card = StatCard(stats, "Active Rate", "0%", "📊", COLORS["accent_peach"])
        self.activity_rate_card.grid(row=0, column=3, padx=5)
        
        self._live_components["cards"] = [
            self.total_users_card, self.active_users_card, 
            self.inactive_users_card, self.activity_rate_card
        ]

    def _add_search_header(self, parent):
        """Add search bar and add user button."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 8), expand=False)
        ctk.CTkLabel(header, text="👥 USER MANAGEMENT", font=ctk.CTkFont(size=14, weight="bold"), 
                    text_color=COLORS["accent_blue"]).pack(side=tk.LEFT)
        
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side=tk.RIGHT)
        
        self.user_search = ctk.CTkEntry(right, width=150, placeholder_text="Search...")
        self.user_search.pack(side=tk.LEFT, padx=5)
        self.user_search.bind("<KeyRelease>", lambda e: self._search_users())
        
        ctk.CTkButton(right, text="+ Add", fg_color=COLORS["accent_green"], text_color="white", 
                     width=70, height=30, command=self._add_user_dialog).pack(side=tk.LEFT, padx=5)
        
        self._live_components["search_entry"] = self.user_search

    def _add_users_table(self, parent):
        """Add user data table."""
        cols = ["Name", "User ID", "Broker", "Status", "Risk Limit", "Last Login", "Actions"]
        table = ModernTable(parent, columns=cols, height=450, on_select=self._on_user_selected)
        table.pack(fill=tk.BOTH, expand=True, pady=(10, 30))
        
        self._live_components["tree"] = table

    def _add_footer(self, parent):
        """Action buttons (legacy - replaced by row actions)."""
        pass

    def _on_user_selected(self, values):
        """Handle user selection."""
        self.selected_user_data = values

    def _search_users(self):
        """Search and filter users based on query."""
        query = self.user_search.get().strip().lower()
        users = Config.load_users()
        
        table = self._live_components.get("tree")
        if not table or not hasattr(table, "clear"):
            return
            
        table.clear()
        
        active = inactive = 0
        for u in users:
            if query and query not in u.get('name', '').lower() and query not in u.get('user_id', '').lower():
                continue
            is_active = u.get('active', True)
            if is_active:
                active += 1
            else:
                inactive += 1
            
            status = "✅ Active" if is_active else "❌ Inactive"
            try:
                raw_limit = u.get('risk_rules', {}).get('total_capital', 0)
                limit_val = float(raw_limit) if raw_limit else 0
                limit = f"Rs{limit_val:,.0f}"
            except (ValueError, TypeError) as e:
                limit = f"Rs{u.get('risk_rules', {}).get('total_capital', '0')}"
            
            # Actions column content
            u_id = u.get('user_id', '')
            is_admin = (u_id == "admin" or u_id == "user_001")
            bot_on = is_bot_running()
            
            actions = []
            
            # Edit: Only allowed when bot is OFF
            if not bot_on:
                actions.append({"text": "✏️", "command": lambda uid=u_id: self._edit_user_dialog(uid), "color": COLORS["bg_card"], "width": 32})
            
            # Delete: Only allowed when bot is OFF and NOT admin
            if not bot_on and not is_admin:
                actions.append({"text": "🗑️", "command": lambda uid=u_id: self._delete_user(uid), "color": COLORS["accent_peach"], "width": 32})
            
            # If both hidden, show a placeholder or nothing
            if not actions and bot_on:
                # Optional: tooltip or text info handled by ModernTable if it supported it, 
                # but for now we just show an empty list or a "Locked" icon
                pass
            
            values = [
                u.get('name', 'N/A'), u_id,
                u.get('broker_type', 'N/A').upper(), status, limit,
                u.get('last_login', 'Never'),
                actions
            ]
            table.add_row(values)
        
        total = len(users)
        active_rate = (active / total * 100) if total > 0 else 0
        
        cards = self._live_components.get("cards", [])
        if cards:
            cards[0].update_value(str(total))
            cards[1].update_value(str(active))
            cards[2].update_value(str(inactive))
            cards[3].update_value(f"{active_rate:.0f}%")

    def _refresh_data(self):
        """Standard refresh method called by Dashboard GUI."""
        self._search_users()

    def _get_parent_window(self):
        """Get appropriate parent window for dialogs."""
        # In popout mode, use the popout window; otherwise use main window
        if not self.is_main and self.winfo_toplevel() != self.winfo_toplevel().master:
            return self.winfo_toplevel()
        return self.winfo_toplevel()

    def _add_user_dialog(self):
        """Show a premium, simplified dialog to add a new user."""
        parent_ptr = self._get_parent_window()

        dialog = ctk.CTkToplevel(parent_ptr)
        dialog.title("Add New User")
        dialog.geometry("380x480")
        self._apply_window_theme(dialog)
        dialog.transient(parent_ptr)
        dialog.lift()
        
        # Center the window
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (380 // 2)
        y = (dialog.winfo_screenheight() // 2) - (480 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # ─── HEADER ────────────────────────────────────────────────────────
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill=tk.X, padx=24, pady=(25, 10))
        
        ctk.CTkLabel(
            header, text="👤 CREATE USER", 
            font=ctk.CTkFont(size=20, weight="bold"), 
            text_color=COLORS["accent_blue"]
        ).pack(side=tk.LEFT)
        
        ctk.CTkButton(
            header, text="✕", width=28, height=28, 
            fg_color="transparent", text_color=COLORS["text_dim"], 
            hover_color=COLORS["bg_panel"], command=dialog.destroy
        ).pack(side=tk.RIGHT)
        
        desc = ctk.CTkLabel(
            dialog, text="Enter basic details to create a new access profile.",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"]
        )
        desc.pack(anchor=tk.W, padx=24, pady=(0, 20))

        # ─── FORM FIELDS ───────────────────────────────────────────────────
        fields_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=24)

        # 1. Full Name
        ctk.CTkLabel(fields_frame, text="Display Name", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor=tk.W, pady=(5, 2))
        name_entry = ctk.CTkEntry(fields_frame, height=42, placeholder_text="e.g. John Doe")
        name_entry.pack(fill=tk.X, pady=(0, 15))
        
        # 2. User ID
        ctk.CTkLabel(fields_frame, text="User Access ID", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor=tk.W, pady=(5, 2))
        id_entry = ctk.CTkEntry(fields_frame, height=42, placeholder_text="e.g. user_101")
        id_entry.pack(fill=tk.X, pady=(0, 15))
        
        # 3. Password
        ctk.CTkLabel(fields_frame, text="Secure Password", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor=tk.W, pady=(5, 2))
        pass_entry = ctk.CTkEntry(fields_frame, height=42, show="●", placeholder_text="••••••••")
        pass_entry.pack(fill=tk.X, pady=(0, 5))

        def save():
            name = name_entry.get().strip()
            u_id = id_entry.get().strip()
            password = pass_entry.get().strip()

            if not name or not u_id or not password:
                ToastNotification(dialog, "Please fill all fields!", COLORS["accent_red"])
                return

            try:
                # Basic user template - remaining details filled post-login
                new_user = {
                    "user_id": u_id,
                    "name": name,
                    "designation": "Trader", # Default for new users
                    "broker_type": "MOCK", # Default for new users
                    "active": True,
                    "login_password": get_password_hash(password),
                    "credentials": {
                        "api_key": "", "client_id": "", 
                        "api_secret": "", "totp_secret": ""
                    },
                    "risk_rules": {
                        "total_capital": 100000, 
                        "trade_capital": 10000,
                        "max_trades": 2,
                        "stop_loss_pct": 50,
                        "target_pct": 200
                    }
                }
                
                if Config.add_user(new_user):
                    ToastNotification(self.winfo_toplevel(), f"User '{name}' created successfully!")
                    dialog.destroy()
                    self._refresh_data()
                else:
                    messagebox.showerror("Error", f"User ID '{u_id}' already exists.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save user: {e}")
        
        # ─── FOOTER ────────────────────────────────────────────────────────
        btn_save = ctk.CTkButton(
            dialog, text="✨ Create Account", 
            fg_color=COLORS["accent_blue"], height=48, 
            font=ctk.CTkFont(size=14, weight="bold"),
            command=save
        )
        btn_save.pack(fill=tk.X, padx=24, pady=30)

    def _edit_user_dialog(self, target_user_id=None):
        """Show dialog to edit user profile."""
        if is_bot_running():
            messagebox.showwarning("Locked", "Cannot edit users while the bot is running.")
            return

        if target_user_id:
            selected_user_id = target_user_id
        else:
            table = self._live_components.get("tree")
            if not table or table.selected_index == -1:
                messagebox.showwarning("Select", "Please select a user to edit.")
                return
            selected_user_id = self.selected_user_data[1]

        users = Config.load_users()
        user = next((u for u in users if u.get("user_id") == selected_user_id), None)
        
        if not user:
            messagebox.showerror("Error", "User not found")
            return

        parent_ptr = self._get_parent_window()

        dialog = ctk.CTkToplevel(parent_ptr)
        dialog.title(f"Edit Profile: {user.get('name', '')}")
        dialog.geometry("460x580")
        dialog.transient(parent_ptr)
        dialog.lift()
        self._apply_window_theme(dialog)
        
        # Position centered
        dialog.update_idletasks()
        screen_w = dialog.winfo_screenwidth()
        screen_h = dialog.winfo_screenheight()
        x = (screen_w // 2) - (460 // 2)
        y = (screen_h // 2) - (580 // 2) 
        dialog.geometry(f"+{x}+{y}")
        
        # Header
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=(15, 0))
        
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side=tk.LEFT)
        ctk.CTkLabel(title_box, text=f"👤 EDIT PROFILE", 
                    font=ctk.CTkFont(size=18, weight="bold"), 
                    text_color=COLORS["accent_blue"]).pack(side=tk.LEFT)

        # Scrollable Form
        form_scr = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        form_scr.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        entries = {}

        def add_section(title, icon, color):
            s_frame = ctk.CTkFrame(form_scr, fg_color="transparent")
            s_frame.pack(fill=tk.X, pady=(15, 8))
            ctk.CTkLabel(s_frame, text=f"{icon} {title}", font=ctk.CTkFont(size=11, weight="bold"), 
                        text_color=color).pack(side=tk.LEFT)
            ctk.CTkFrame(s_frame, fg_color=COLORS["border"], height=1).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
            return s_frame

        def create_row(container, label_text):
            row = ctk.CTkFrame(container, fg_color="transparent")
            row.pack(fill=tk.X, pady=4)
            ctk.CTkLabel(row, text=label_text, font=ctk.CTkFont(size=11), width=120, 
                        anchor=tk.W, text_color=COLORS["text_dim"]).pack(side=tk.LEFT)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(side=tk.LEFT, fill=tk.X, expand=True)
            return inner

        # Section 1: Core
        add_section("CORE INFORMATION", "📋", COLORS["accent_blue"])
        
        r1 = create_row(form_scr, "Display Name:")
        e_name = ctk.CTkEntry(r1, height=32)
        e_name.pack(fill=tk.X)
        e_name.insert(0, user.get("name", ""))
        entries["name"] = e_name

        r2 = create_row(form_scr, "User ID:")
        e_id = ctk.CTkEntry(r2, height=32, state="normal", fg_color=COLORS["bg_panel"])
        e_id.insert(0, user.get("user_id", ""))
        e_id.configure(state="disabled")
        e_id.pack(fill=tk.X)
        entries["user_id"] = e_id

        r_desig = create_row(form_scr, "Designation:")
        is_master_admin = (user.get("user_id") == "admin" or user.get("user_id") == "user_001")
        if is_master_admin:
            e_desig = ctk.CTkEntry(r_desig, height=32, state="normal", fg_color=COLORS["bg_panel"])
            e_desig.insert(0, "Admin/Owner")
            e_desig.configure(state="disabled")
            e_desig.pack(fill=tk.X)
            entries["designation"] = e_desig
        else:
            current_desig = user.get("designation", "")
            if not current_desig or current_desig not in ["Trader", "Risk Manager", "Analyst", "Viewer"]:
                current_desig = "Trader"
            desig_var = tk.StringVar(value=current_desig)
            desig_menu = ctk.CTkOptionMenu(
                r_desig, 
                variable=desig_var, 
                values=["Trader", "Risk Manager", "Analyst", "Viewer"], 
                height=32
            )
            desig_menu.pack(fill=tk.X)
            entries["designation"] = desig_var

        r3 = create_row(form_scr, "Broker Platform:")
        broker_var = tk.StringVar(value=user.get("broker_type", "MOCK").upper())
        ctk.CTkOptionMenu(r3, variable=broker_var, values=["MOCK", "ZERODHA", "ANGEL", "UPSTOX"], height=32).pack(fill=tk.X)

        r4 = create_row(form_scr, "Account Status:")
        status_var = tk.BooleanVar(value=user.get("active", True))
        ctk.CTkSwitch(r4, text="Account Enabled", variable=status_var, progress_color=COLORS["accent_green"]).pack(side=tk.LEFT)

        # Section 2: API
        add_section("API CREDENTIALS", "🔐", COLORS["accent_peach"])
        creds = user.get("credentials", {})
        
        # Helper to create masked entry with individual eye toggle button
        def create_eye_entry(parent, label_text, value_text):
            r = create_row(parent, label_text)
            f = ctk.CTkFrame(r, fg_color="transparent")
            f.pack(fill=tk.X)
            
            entry = ctk.CTkEntry(f, height=32, show="●")
            entry.insert(0, str(value_text))
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            is_visible = [False]
            def toggle():
                is_visible[0] = not is_visible[0]
                entry.configure(show="" if is_visible[0] else "●")
                btn_eye.configure(text="🔒" if is_visible[0] else "👁️")
                
            btn_eye = ctk.CTkButton(
                f, 
                text="👁️", 
                width=36, 
                height=32,
                fg_color=COLORS["bg_panel"],
                text_color=COLORS["text_dim"],
                hover_color=COLORS["border"],
                command=toggle
            )
            btn_eye.pack(side=tk.RIGHT, padx=(6, 0))
            return entry

        for lbl, key in [
            ("API Key", "api_key"),
            ("Client ID", "client_id"),
            ("API Secret", "api_secret"),
            ("Password", "password"),
            ("TOTP Secret", "totp_secret")
        ]:
            entries[f"cred_{key}"] = create_eye_entry(form_scr, f"{lbl}:", creds.get(key, ""))

        # Section 3: Notifications
        add_section("NOTIFICATIONS", "🔔", COLORS["accent_green"])
        notif = user.get("notifications", {})
        
        # Telegram Bot Token (masked with eye button)
        r_tg_token = create_row(form_scr, "Telegram Bot Token:")
        tg_token_frame = ctk.CTkFrame(r_tg_token, fg_color="transparent")
        tg_token_frame.pack(fill=tk.X)
        
        e_tg_token = ctk.CTkEntry(tg_token_frame, height=32, show="●")
        e_tg_token.insert(0, str(notif.get("telegram_bot_token", "")))
        e_tg_token.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entries["tg_token"] = e_tg_token
        
        is_tg_visible = [False]
        def toggle_tg():
            is_tg_visible[0] = not is_tg_visible[0]
            e_tg_token.configure(show="" if is_tg_visible[0] else "●")
            btn_eye_tg.configure(text="🔒" if is_tg_visible[0] else "👁️")
            
        btn_eye_tg = ctk.CTkButton(
            tg_token_frame, 
            text="👁️", 
            width=36, 
            height=32,
            fg_color=COLORS["bg_panel"],
            text_color=COLORS["text_dim"],
            hover_color=COLORS["border"],
            command=toggle_tg
        )
        btn_eye_tg.pack(side=tk.RIGHT, padx=(6, 0))
        
        r_tg_chat = create_row(form_scr, "Telegram Chat ID:")
        e_tg_chat = ctk.CTkEntry(r_tg_chat, height=32)
        e_tg_chat.insert(0, str(notif.get("telegram_chat_id", "")))
        e_tg_chat.pack(fill=tk.X)
        entries["tg_chat_id"] = e_tg_chat

        # Section 4: AI Credentials
        def test_ai():
            key = entries["gemini_key"].get().strip()
            if not key:
                messagebox.showwarning("Input Required", "Please enter a Gemini API key first.")
                return
            btn_test_ai.configure(text="⏳...", state="disabled")
            
            import threading
            def run_test():
                success, message = self.controller.test_ai_connection("Gemini", key)
                
                def update_ui():
                    try:
                        btn_test_ai.configure(text="⚡ Test Key", state="normal")
                        if success:
                            messagebox.showinfo("AI Connection", f"✅ {message}")
                        else:
                            messagebox.showerror("AI Connection Error", f"❌ {message}")
                    except Exception as e:
                        logger.warning(f"Failed to update AI connection test UI: {e}")
                
                self.after(0, update_ui)
                
            threading.Thread(target=run_test, daemon=True).start()

        add_section("AI CREDENTIALS", "🧠", "#00d2ff")
        ai_intel = user.get("ai_intelligence", {})
        
        r_gemini = create_row(form_scr, "Gemini API Key:")
        gemini_frame = ctk.CTkFrame(r_gemini, fg_color="transparent")
        gemini_frame.pack(fill=tk.X)
        
        e_gemini = ctk.CTkEntry(gemini_frame, height=32, show="●")
        e_gemini.insert(0, str(ai_intel.get("gemini_api_key", "")))
        e_gemini.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entries["gemini_key"] = e_gemini
        
        is_gemini_visible = [False]
        def toggle_gemini():
            is_gemini_visible[0] = not is_gemini_visible[0]
            e_gemini.configure(show="" if is_gemini_visible[0] else "●")
            btn_eye_gemini.configure(text="🔒" if is_gemini_visible[0] else "👁️")
            
        btn_eye_gemini = ctk.CTkButton(
            gemini_frame, 
            text="👁️", 
            width=36, 
            height=32,
            fg_color=COLORS["bg_panel"],
            text_color=COLORS["text_dim"],
            hover_color=COLORS["border"],
            command=toggle_gemini
        )
        btn_eye_gemini.pack(side=tk.LEFT, padx=(6, 0))
        
        btn_test_ai = ctk.CTkButton(
            gemini_frame, 
            text="⚡ Test Key", 
            width=80, 
            height=32,
            fg_color=COLORS["accent_blue"],
            command=test_ai
        )
        btn_test_ai.pack(side=tk.RIGHT, padx=(10, 0))

        # Section 5: Security
        add_section("SECURITY & PASS", "🔑", COLORS["accent_red"])
        r_pass = create_row(form_scr, "New Password:")
        e_pass = ctk.CTkEntry(r_pass, height=32, show="●", placeholder_text="Keep empty to stay unchanged")
        e_pass.pack(fill=tk.X)

        # Breathing room
        ctk.CTkFrame(form_scr, fg_color="transparent", height=60).pack()

        # Footer
        footer = ctk.CTkFrame(dialog, fg_color=COLORS["bg_card"], height=75, corner_radius=0)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        def save_and_close():
            try:
                updates = {
                    "name": entries["name"].get(),
                    "designation": entries["designation"].get().strip(),
                    "broker_type": broker_var.get(),
                    "active": status_var.get()
                }
                
                new_creds = user.get("credentials", {}).copy()
                for k in ["api_key", "client_id", "api_secret", "password", "totp_secret"]:
                    new_creds[k] = entries[f"cred_{k}"].get().strip()
                updates["credentials"] = new_creds

                new_notif = user.get("notifications", {}).copy()
                new_notif["telegram_bot_token"] = entries["tg_token"].get().strip()
                new_notif["telegram_chat_id"] = entries["tg_chat_id"].get().strip()
                updates["notifications"] = new_notif

                new_ai = user.get("ai_intelligence", {}).copy()
                new_ai["gemini_api_key"] = entries["gemini_key"].get().strip()
                updates["ai_intelligence"] = new_ai
                
                new_p = e_pass.get().strip()
                if new_p:
                    updates["login_password"] = get_password_hash(new_p)
                
                if Config.update_user(selected_user_id, updates):
                    ToastNotification(self.winfo_toplevel(), f"Profile '{updates['name']}' Saved!")
                    self._refresh_data()
                    dialog.destroy()
            except Exception as e:
                messagebox.showerror("Save Error", str(e))

        ctk.CTkButton(footer, text="Save Updates", fg_color=COLORS["accent_blue"], width=120, height=35,
                     command=save_and_close).pack(side=tk.RIGHT, padx=20, pady=15)
        ctk.CTkButton(footer, text="Cancel", fg_color="transparent", border_width=1, border_color=COLORS["border"], 
                     text_color=COLORS["text_main"], width=100, height=35, command=dialog.destroy).pack(side=tk.RIGHT, padx=5, pady=15)

    def _delete_user(self, target_user_id=None):
        """Delete selected user."""
        if target_user_id:
            user_id = target_user_id
        else:
            table = self._live_components.get("tree")
            if not table or table.selected_index == -1:
                messagebox.showwarning("Select", "Select a user to delete")
                return
            user_id = self.selected_user_data[1]
        
        # Prevent deleting admin user
        if user_id == "admin" or user_id == "user_001":
            messagebox.showerror("Protected", "Cannot delete admin user!")
            return
        
        # Prevent deleting user if bot is running for that user
        if is_bot_running() and user_id == (self.controller.current_user_id if self.controller else ""):
            messagebox.showerror("Active", "Cannot delete user while bot is running!")
            return
        
        if messagebox.askyesno("Confirm", f"Delete user '{user_id}'?"):
            try:
                users = Config.load_users()
                users = [u for u in users if u.get("user_id") != user_id]
                with open(USERS_FILE, "w", encoding='utf-8') as f:
                    json.dump(users, f, indent=2)
                ToastNotification(self.winfo_toplevel(), f"User '{user_id}' deleted!")
                self._refresh_data()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _apply_window_theme(self, window):
        """Apply theme to toplevel window."""
        pass

    def _close_window(self):
        """Close the popout window."""
        self.winfo_toplevel().destroy()

    @property
    def live_components(self):
        """Return components that need live updates."""
        return self._live_components
