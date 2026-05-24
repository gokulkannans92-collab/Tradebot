"""
View Controller Protocol
═══════════════════════════════════════════════════════════════════════════════

Defines the interface that all views use to communicate with the main application.
Views should NOT import or depend directly on TradeBotGUI; instead, they accept
a controller that implements this protocol and call methods on it.

This ensures loose coupling and makes views testable in isolation.
"""

from typing import Protocol, Any, Dict, List, Optional, Callable
import tkinter as tk


class IViewController(Protocol):
    """Protocol defining the interface views use to call back to main app."""
    
    # ─── OVERVIEW VIEW CALLBACKS ───────────────────────────────────────────
    
    def refresh_overview_data(self, force: bool = False) -> None:
        """Refresh overview data (trades, stats). Called by OverviewView._load_data()"""
        ...
    
    def update_overview_charts(self, trades: List[Dict[str, Any]]) -> None:
        """Update charts with trade data. Called by OverviewView after data load."""
        ...
    
    def set_period(self, period: str) -> None:
        """Set active period filter (Today/Week/Month/All). Called by OverviewView period buttons."""
        ...
    
    # ─── TRADES VIEW CALLBACKS ─────────────────────────────────────────────
    
    def refresh_trades_table(self) -> None:
        """Reload active trades list. Called by TradesView refresh button."""
        ...
    
    def close_selected_trade(self, trade_id: str) -> bool:
        """Close a specific trade. Called by TradesView close button. Returns success."""
        ...
    
    def close_all_trades(self) -> bool:
        """Close all active trades. Called by TradesView close-all button. Returns success."""
        ...
    
    def export_trades_csv(self, filepath: str) -> bool:
        """Export trades to CSV. Called by TradesView export button. Returns success."""
        ...
    
    def copy_trade_data(self, trade_index: int) -> str:
        """Get trade data as text for clipboard. Called by TradesView context menu."""
        ...
    
    def show_trade_details(self, trade_data: Dict[str, Any]) -> None:
        """Show detailed view of a trade. Called by TradesView double-click."""
        ...
    
    # ─── MANAGEMENT VIEW CALLBACKS ─────────────────────────────────────────
    
    def refresh_users_table(self) -> None:
        """Reload users list. Called by ManagementView refresh button."""
        ...
    
    def add_user(self, username: str, password: str, api_key: str, api_secret: str, 
                 broker: str) -> bool:
        """Add new user. Called by ManagementView add dialog. Returns success."""
        ...
    
    def edit_user(self, user_id: str, username: str, api_key: str, api_secret: str, 
                  broker: str, password: Optional[str] = None) -> bool:
        """Edit existing user. Called by ManagementView edit dialog. Returns success."""
        ...
    
    def delete_user(self, user_id: str) -> bool:
        """Delete user. Called by ManagementView delete button. Returns success."""
        ...
    
    def search_users(self, query: str) -> List[Dict[str, Any]]:
        """Search users by name/id. Called by ManagementView search field."""
        ...
    
    # ─── CONFIG VIEW CALLBACKS ────────────────────────────────────────────
    
    def save_config(self, config_dict: Dict[str, Any]) -> bool:
        """Save configuration to .env and cache. Called by ConfigView save button. Returns success."""
        ...
    
    def load_config_values(self) -> Dict[str, Any]:
        """Load current config values. Called by ConfigView init. Returns dict."""
        ...
    
    def test_broker(self, broker_name: str) -> str:
        """Test broker connection. Called by ConfigView test button. Returns status message."""
        ...
    
    def backup_data(self, backup_path: str) -> bool:
        """Create backup of data directory. Called by ConfigView backup button. Returns success."""
        ...
    
    def restore_data(self, backup_path: str) -> bool:
        """Restore data from backup. Called by ConfigView restore button. Returns success."""
        ...
    
    # ─── LOGS VIEW CALLBACKS ──────────────────────────────────────────────
    
    def refresh_trade_logs(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Load trade logs for date range. Called by LogsView date filter. Returns list of trades."""
        ...
    
    def update_logs_stats(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics from trades. Called by LogsView after log refresh. Returns stats dict."""
        ...
    
    def export_trade_logs(self, filepath: str, trades: List[Dict[str, Any]]) -> bool:
        """Export logs to CSV. Called by LogsView export button. Returns success."""
        ...
    
    def load_archive_history(self) -> List[str]:
        """Get list of available backup log files. Called by LogsView on init. Returns list of dates."""
        ...
    
    # ─── CONSOLE VIEW CALLBACKS ────────────────────────────────────────────
    
    def append_console(self, text: str, level: str = "INFO") -> None:
        """Add line to console. Called by ConsoleView (_append_console). Level: INFO/WARNING/ERROR."""
        ...
    
    def reload_console(self, view_widget: tk.Text) -> None:
        """Reload entire console text. Called by ConsoleView reload button."""
        ...
    
    def switch_console_log(self, mode: str) -> None:
        """Switch between 'active', 'backup', or 'all' log view. Called by ConsoleView mode buttons."""
        ...
    
    def filter_console(self, filter_type: str) -> None:
        """Apply console filter. Called by ConsoleView filter buttons."""
        ...
    
    # ─── NOTIFICATIONS VIEW CALLBACKS ──────────────────────────────────────
    
    def get_notifications(self) -> List[Dict[str, Any]]:
        """Get list of recent notifications. Called by NotificationsView on init."""
        ...
    
    def clear_notifications(self) -> None:
        """Clear all notifications. Called by NotificationsView clear button."""
        ...
    
    # ─── HELP VIEW CALLBACKS ──────────────────────────────────────────────
    
    def get_help_content(self, section: str) -> str:
        """Get help text for section. Called by HelpView on init. Returns markdown text."""
        ...
    
    # ─── GLOBAL/SHARED CALLBACKS ──────────────────────────────────────────
    
    def export_current(self, view_name: str) -> bool:
        """Export current view data. Called by export button in toolbar. Returns success."""
        ...
    
    def toggle_left_sidebar(self) -> None:
        """Toggle left sidebar visibility. Called by HideLeft button."""
        ...
    
    def toggle_right_sidebar(self) -> None:
        """Toggle right sidebar visibility. Called by HideRight button."""
        ...
    
    def pop_out_view(self, view_name: str) -> None:
        """Open view in standalone window. Called by view 'Pop Out' button."""
        ...
    
    def pop_in_view(self, view_name: str) -> None:
        """Bring popped-out view back to main window. Called by standalone window close."""
        ...
    
    # ─── STATE ACCESS ─────────────────────────────────────────────────────
    
    @property
    def current_user_name(self) -> str:
        """Get logged-in user's display name."""
        ...
    
    @property
    def current_user_id(self) -> str:
        """Get logged-in user's ID."""
        ...
    
    @property
    def bot_running(self) -> bool:
        """Get bot run status."""
        ...
    
    @property
    def selected_period(self) -> str:
        """Get currently selected period filter (Overview view)."""
        ...
