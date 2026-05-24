import requests
import logging
import threading
import time
import re
import queue
from typing import Callable, Optional
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("TelegramManager")

# Characters that MUST be escaped in MarkdownV2 mode
_MDV2_SPECIAL = [
    '\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
]

def escape_md(text: str) -> str:
    """Escape special characters for Telegram HTML mode."""
    if not isinstance(text, str):
        text = str(text)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

class TelegramManager:
    """
    Handles Telegram notifications and incoming commands.
    
    Optimized for performance:
    - Async message sending via queue
    - Non-blocking listener with shorter timeouts
    - Connection pooling for HTTP requests
    """
    def __init__(self, token: str, chat_id: str, max_workers: int = 2):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0
        self.running = False
        self.commands = {} # {command: callback}
        
        # Async message queue for non-blocking sends
        self._message_queue: Queue = Queue(maxsize=100)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="telegram_")
        self._sender_thread: Optional[threading.Thread] = None
        
        # Connection pool for reuse
        import certifi
        self._session = requests.Session()
        self._session.verify = certifi.where() # Force standard bundle
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=2,
            pool_maxsize=5,
            max_retries=0  # We handle retries manually
        )
        self._session.mount('https://', adapter)
        
    def send_message(self, message: str, blocking: bool = False):
        """
        Send a message to the configured chat.
        
        Args:
            message: Message text to send
            blocking: If True, wait for send to complete. If False, queue for async send.
        """
        if not self.token or not self.chat_id:
            logger.warning("Telegram NOT configured (missing token or chat_id)")
            return
        
        if blocking:
            # Synchronous send (for critical messages)
            self._send_sync(message)
        else:
            # Async send via queue (non-blocking)
            try:
                self._message_queue.put_nowait(message)
            except queue.Full:
                logger.warning("Telegram message queue full, dropping message")
            except Exception as e:
                logger.error(f"Failed to queue Telegram message: {e}")
    
    def _send_sync(self, message: str, max_retries: int = 2) -> bool:
        """
        Synchronous message send with retry logic.
        Uses shorter timeouts to avoid blocking.
        """
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        for attempt in range(max_retries + 1):
            try:
                # Shorter timeout: 5s connect, 10s read
                response = self._session.post(
                    url, 
                    json=payload, 
                    timeout=(5, 10)
                )
                if response.status_code == 200:
                    return True
                else:
                    logger.error(f"Telegram error (Attempt {attempt+1}): {response.text}")
            except (requests.RequestException, TimeoutError, ConnectionError) as e:
                if attempt < max_retries:
                    logger.debug(f"Telegram send failed (Attempt {attempt+1}), retrying: {e}")
                    time.sleep(0.5)  # Short delay between retries
                else:
                    logger.error(f"Failed to send Telegram message after {max_retries+1} attempts: {e}")
        
        return False
    
    def _sender_loop(self):
        """Background thread that processes message queue."""
        while self.running:
            try:
                # Block for up to 1 second waiting for messages
                message = self._message_queue.get(timeout=1.0)
                # Process in thread pool for true async behavior
                self._executor.submit(self._send_sync, message)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in Telegram sender loop: {e}")

    def register_command(self, command: str, callback: Callable):
        """Register a callback for a specific command (e.g., /status)"""
        self.commands[command.lower()] = callback

    def _get_updates(self):
        """
        Fetch new messages from Telegram API.
        Uses shorter timeout to prevent long blocking.
        """
        url = f"{self.base_url}/getUpdates"
        # Shorter long-polling timeout: 5 seconds max
        params = {"offset": self.last_update_id + 1, "timeout": 5}
        try:
            response = self._session.get(url, params=params, timeout=(5, 10))
            if response.status_code == 200:
                return response.json().get("result", [])
        except (requests.RequestException, TimeoutError, ConnectionError) as e:
            logger.debug(f"Error fetching telegram updates: {e}")
        return []

    def _listener_loop(self):
        """
        Background thread loop to listen for commands.
        Optimized to prevent blocking main thread.
        """
        logger.info("Telegram command listener started")
        last_error_time = 0
        error_count = 0
        
        while self.running:
            try:
                updates = self._get_updates()
                
                # Reset error counter on success
                if updates is not None:
                    error_count = 0
                
                for update in updates or []:
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
                            # Run command handler in thread pool to avoid blocking listener
                            self._executor.submit(self._handle_command, cmd, cmd_parts[1:])
                        else:
                            self.send_message(f"Unknown command: <code>{escape_md(text)}</code>\nAvailable: <code>{escape_md(', '.join(self.commands.keys()))}</code>")
                
                # Adaptive sleep based on error rate
                if error_count > 3:
                    # Back off on repeated errors
                    sleep_time = min(30, 2 ** error_count)
                    logger.warning(f"Telegram listener backing off for {sleep_time}s due to errors")
                    time.sleep(sleep_time)
                    error_count = 0
                else:
                    time.sleep(0.5)  # Poll every 500ms normally
                    
            except Exception as e:
                error_count += 1
                current_time = time.time()
                # Log error at most once per minute to avoid spam
                if current_time - last_error_time > 60:
                    logger.error(f"Error in Telegram listener loop: {e}")
                    last_error_time = current_time
                time.sleep(5)  # Wait before retry
    
    def _handle_command(self, cmd: str, args: list):
        """Handle a command in background thread."""
        try:
            if cmd in self.commands:
                self.commands[cmd](self, args)
        except Exception as e:
            logger.error(f"Error handling command {cmd}: {e}")

    def start(self):
        """Start the command listener and message sender in background threads."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram NOT starting: missing credentials")
            return
            
        self.running = True
        
        # Start sender thread
        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True, name="TelegramSender")
        self._sender_thread.start()
        
        # Start listener thread
        self.thread = threading.Thread(target=self._listener_loop, daemon=True, name="TelegramListener")
        self.thread.start()
        
        # Send startup message (blocking to ensure it's sent)
        self.send_message(f"🚀 <b>TradeBot system online</b> and listening for commands.", blocking=True)
        logger.info("Telegram manager started (listener + sender threads)")

    def stop(self):
        """Stop the listener thread and cleanup resources."""
        if not self.running:
            return
            
        logger.info("Telegram manager stopping - flushing message queue...")
        self.running = False
        
        # 1. Flush any pending messages in the queue (Sync send for shutdown)
        while not self._message_queue.empty():
            try:
                message = self._message_queue.get_nowait()
                self._send_sync(message)
            except:
                break
        
        # 2. Stop sender thread
        if self._sender_thread:
            self._sender_thread.join(timeout=2.0)
        
        # 3. Stop listener thread
        if hasattr(self, "thread"):
            self.thread.join(timeout=2.0)
        
        # 4. Shutdown executor
        self._executor.shutdown(wait=True)
        
        # 5. Close session
        self._session.close()
        
        logger.info("Telegram manager stopped")
