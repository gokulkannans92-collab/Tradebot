"""
bot_state.py — Shared persistent state for the TradeBot process.

Both the desktop GUI (gui_launcher.py) and the FastAPI web server (api/routes/bot.py)
read and write this same PID file so that:
  - Starting from the GUI  → Browser reflects "Active" instantly
  - Starting from Browser  → GUI can detect it and reflect "Active"
  - Stopping from either   → The other side sees "Idle" on next poll
"""

import os
import sys

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PID_FILE          = os.path.join(_BASE_DIR, ".bot.pid")
STOP_TRIGGER_FILE = os.path.join(_BASE_DIR, ".stop_trigger")
LOG_FILE          = os.path.join(_BASE_DIR, "logs", "bot_output.log")


def write_pid(pid: int):
    """Called right after the bot subprocess is launched."""
    with open(PID_FILE, "w") as f:
        f.write(str(pid))


def clear_pid():
    """Called when the bot process ends."""
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except Exception:
            pass


def read_pid() -> int | None:
    """Return the PID stored on disk, or None if not present."""
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return None


def is_bot_running() -> bool:
    """
    True if the PID file exists AND that process is still alive.
    Works on both Windows and Linux/macOS.
    """
    pid = read_pid()
    if pid is None:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle == 0:
                clear_pid()
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        else:
            os.kill(pid, 0)   # signal 0 = existence check
            return True
    except (ProcessLookupError, PermissionError, OSError):
        clear_pid()           # stale PID — clean up
        return False


def request_stop(preference: str = "keep"):
    """Write the stop trigger file so main.py shuts down gracefully."""
    with open(STOP_TRIGGER_FILE, "w") as f:
        f.write(f"stop:{preference}")
