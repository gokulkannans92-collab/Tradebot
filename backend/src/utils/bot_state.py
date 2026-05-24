"""
bot_state.py - Shared persistent state for the TradeBot process.

Both the desktop GUI (gui_launcher.py) and the FastAPI web server (api/routes/bot.py)
read and write this same PID file so that:
  - Starting from the GUI  -> Browser reflects "Active" instantly
  - Starting from Browser  -> GUI can detect it and reflect "Active"
  - Stopping from either   -> The other side sees "Idle" on next poll
"""

import os
import sys
import logging

from src.utils.paths import ensure_paths

logger = logging.getLogger(__name__)
_DATA_DIR = ensure_paths()
PID_FILE          = os.path.join(_DATA_DIR, ".bot.pid")
STOP_TRIGGER_FILE = os.path.join(_DATA_DIR, ".stop_trigger")
LOG_FILE          = os.path.join(_DATA_DIR, "trade_bot.log")

import threading

# Thread-safe stop flag for immediate stop signaling
_stop_requested = False
_stop_lock = threading.Lock()

def is_stop_requested() -> bool:
    """Check if stop has been requested (thread-safe flag)."""
    with _stop_lock:
        return _stop_requested

def set_stop_requested(value: bool = True):
    """Set stop requested flag (thread-safe)."""
    global _stop_requested
    with _stop_lock:
        _stop_requested = value
        if value:
            logger.info("🛑 Stop flag set - bot will stop on next iteration")


def write_pid(pid: int):
    """Called right after the bot subprocess is launched."""
    with open(PID_FILE, "w") as f:
        f.write(str(pid))


def clear_pid():
    """Called when the bot process ends."""
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except (OSError, FileNotFoundError) as e:
            logger.debug(f"Could not clear PID file: {e}")


def read_pid() -> int | None:
    """Return the PID stored on disk, or None if not present."""
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError) as e:
        logger.debug(f"Could not read PID file: {e}")
        return None


def is_bot_running() -> bool:
    """
    True if the PID file exists AND that process is still actually running.
    Uses GetExitCodeProcess on Windows for 100% reliability.
    """
    pid = read_pid()
    if pid is None:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            
            # PROCESS_QUERY_LIMITED_INFORMATION (0x1000) is enough to check exit code
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                exit_code = wintypes.DWORD()
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                ctypes.windll.kernel32.CloseHandle(handle)
                if exit_code.value == STILL_ACTIVE:
                    return True
            
            # If handle failed or exit code is not STILL_ACTIVE
            clear_pid()
            return False
        else:
            os.kill(pid, 0)   # signal 0 = existence check
            return True
    except (ProcessLookupError, PermissionError, OSError):
        clear_pid()           # stale PID - clean up
        return False


def request_stop(preference: str = "keep"):
    """Write the stop trigger file AND set flag so main.py shuts down gracefully."""
    # Set flag for immediate response
    set_stop_requested(True)
    # Write file for persistence
    with open(STOP_TRIGGER_FILE, "w") as f:
        f.write(f"stop:{preference}")


def kill_bot_process():
    """Forcefully kill the bot subprocess if it's running"""
    pid = read_pid()
    if pid is None:
        return
    
    try:
        if sys.platform == "win32":
            import subprocess
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                         capture_output=True, timeout=5)
        else:
            os.kill(pid, 9)
    except (ProcessLookupError, OSError) as e:
        logger.debug(f"Could not kill process {pid}: {e}")
    
    clear_pid()


import socket
_lock_socket = None

def acquire_engine_lock(port: int = 28473) -> bool:
    """
    Acquire a localhost TCP socket lock to ensure only one instance of TradeBot runs.
    Returns True if successfully acquired (or if lock bypass env is set), False otherwise.
    """
    global _lock_socket
    # Support bypass env for tests
    if os.environ.get("TRADEBOT_BYPASS_LOCK") == "true":
        logger.info("TRADEBOT_BYPASS_LOCK is active; bypassing TCP instance lock.")
        return True
        
    if _lock_socket is not None:
        logger.warning("acquire_engine_lock was already called in this process.")
        return True
        
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Avoid TIME_WAIT reuse issues only on non-Windows platforms.
        # On Windows, SO_REUSEADDR allows multiple sockets to bind to the same port simultaneously.
        if sys.platform != "win32":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port))
        s.listen(1)
        _lock_socket = s
        logger.info(f"🔑 Successfully acquired single-instance TCP lock on 127.0.0.1:{port}")
        return True
    except socket.error as e:
        logger.error(f"❌ Failed to acquire TCP instance lock on port {port}: {e}")
        logger.error("Another TradeBot instance is already running!")
        return False

def release_engine_lock():
    """Release the localhost TCP socket lock."""
    global _lock_socket
    if _lock_socket is not None:
        try:
            _lock_socket.close()
            logger.info("🔑 Released single-instance TCP lock.")
        except Exception as e:
            logger.debug(f"Failed to close lock socket: {e}")
        finally:
            _lock_socket = None

