import requests
import logging
import threading
import time
import re
from typing import Callable, Optional

logger = logging.getLogger("TelegramManager")

# Characters that MUST be escaped in MarkdownV2 mode
_MDV2_SPECIAL = [
    '\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
]

def escape_md(text: str) -> str:
    """Escape special MarkdownV2 characters in dynamic text (prices, names, etc.)."""
    if not isinstance(text, str):
        text = str(text)
    for ch in _MDV2_SPECIAL:
        text = text.replace(ch, f'\\{ch}')
    return text

class TelegramManager:
    """
    Handles Telegram notifications and incoming commands.
    """
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0
        self.running = False
        self.commands = {} # {command: callback}
        
    def send_message(self, message: str):
        """Send a message to the configured chat."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram NOT configured (missing token or chat_id)")
            return
            
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "MarkdownV2"
        }
        # Retry loop for reliability (3 attempts)
        for attempt in range(3):
            try:
                # Increased timeout to 20s for slow networks
                response = requests.post(url, json=payload, timeout=20)
                if response.status_code == 200:
                    return
                else:
                    logger.error(f"Telegram error (Attempt {attempt+1}): {response.text}")
            except Exception as e:
                logger.error(f"Failed to send Telegram message (Attempt {attempt+1}): {e}")
            
            if attempt < 2:
                time.sleep(2) # Wait 2s before retry

    def register_command(self, command: str, callback: Callable):
        """Register a callback for a specific command (e.g., /status)"""
        self.commands[command.lower()] = callback

    def _get_updates(self):
        """Fetch new messages from Telegram API"""
        url = f"{self.base_url}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 30}
        try:
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                return response.json().get("result", [])
        except Exception as e:
            logger.debug(f"Error fetching telegram updates: {e}")
        return []

    def _listener_loop(self):
        """Background thread loop to listen for commands"""
        logger.info("Telegram command listener started")
        while self.running:
            updates = self._get_updates()
            for update in updates:
                self.last_update_id = update["update_id"]
                message = update.get("message", {})
                text = message.get("text", "").strip().lower()
                sender_chat_id = str(message.get("chat", {}).get("id", ""))
                
                # Security: Only respond to the configured chat_id
                if sender_chat_id != self.chat_id:
                    logger.warning(f"Ignored telegram message from unknown chat: {sender_chat_id}")
                    logger.info(f"💡 TIP: If this is you, update TELEGRAM_CHAT_ID={sender_chat_id} in your .env file")
                    continue

                if text.startswith("/"):
                    cmd_parts = text.split()
                    cmd = cmd_parts[0]
                    if cmd in self.commands:
                        logger.info(f"Telegram command received: {cmd}")
                        self.commands[cmd](self, cmd_parts[1:])
                    else:
                        self.send_message(fr"Unknown command\: {escape_md(cmd)}\nAvailable\: {escape_md(', '.join(self.commands.keys()))}")
            
            time.sleep(1)

    def start(self):
        """Start the command listener in a background thread"""
        if not self.token or not self.chat_id:
            logger.warning("Telegram NOT starting: missing credentials")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._listener_loop, daemon=True)
        self.thread.start()
        self.send_message(fr"🚀 *TradeBot system online* and listening for commands\.")

    def stop(self):
        """Stop the listener thread"""
        self.running = False
        if hasattr(self, "thread"):
            self.thread.join(timeout=2)
