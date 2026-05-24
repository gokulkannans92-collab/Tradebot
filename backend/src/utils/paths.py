import os
import sys
import shutil
import logging

logger = logging.getLogger(__name__)

def get_data_dir():
    r"""
    Returns the persistent data directory.
    - If running as a built EXE, ALWAYS use %APPDATA%/TradeBotPro to prevent data loss 
      when the dist/ folder is wiped during rebuilds.
    - If running from source, use the local data/ folder.
    """
    # 1. Handle EXE environment (Safe Persistent Storage)
    if getattr(sys, 'frozen', False):
        base_dir = os.environ.get('APPDATA')
        if not base_dir:
            base_dir = os.path.expanduser('~')
        return os.path.join(base_dir, "TradeBotPro", "data")

    # 2. Check local relative data folder (for development mode running directly)
    # Go up two levels from src/utils/ to root
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    local_dev_data = os.path.join(root_dir, "data")
    if os.path.exists(local_dev_data):
        return local_dev_data

    # 3. Final fallback
    base_dir = os.environ.get('APPDATA')
    if not base_dir:
        base_dir = os.path.expanduser('~')
    return os.path.join(base_dir, "TradeBotPro", "data")


def ensure_paths():
    """
    Creates necessary directories and performs one-time migration from local to persistent storage.
    """
    data_dir = get_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    
    # ── Migration Logic ──
    # If we are in EXE mode, check if there are files in the local dir that need moving
    if getattr(sys, 'frozen', False):
        # 1. Search in EXE dir
        # 2. Search in parent dir (common if running from dist/)
        exe_dir = os.path.dirname(sys.executable)
        parent_dir = os.path.dirname(exe_dir)
        
        # Files/Folders to migrate from local EXE dir to AppData
        migration_targets = [
            ("data/users.json", "users.json"),
            ("trade_bot.log", "trade_bot.log"),
            ("trades_log.csv", "trades_log.csv"),
            ("trades_log_history.csv", "trades_log_history.csv"),
            ("tradebot.db", "tradebot.db"),
            (".session_cache", ".session_cache"),
            (".bot.pid", ".bot.pid"),
            (".stop_trigger", ".stop_trigger"),
            ("data/angel_instruments.json", "angel_instruments.json"),
            (".env", ".env"),
            # Jarvis AI persistent files — must survive EXE rebuilds
            ("data/jarvis_brain.md", "jarvis_brain.md"),
            ("data/jarvis_chat_history.json", "jarvis_chat_history.json"),
        ]
        
        for local_rel, remote_name in migration_targets:
            remote_path = os.path.join(data_dir, remote_name)
            if os.path.exists(remote_path): continue
            
            # Try EXE dir then Parent dir
            for base in [exe_dir, parent_dir]:
                local_path = os.path.join(base, local_rel)
                if os.path.exists(local_path):
                    try:
                        logger.info(f"Migrating {local_path} to {remote_path}...")
                        os.makedirs(os.path.dirname(remote_path), exist_ok=True)
                        shutil.copy2(local_path, remote_path)
                        break # Migrated
                    except Exception as e:
                        logger.error(f"Failed to migrate {local_path}: {e}")

    return data_dir

def get_path(filename):
    """Utility to get a full path for a file in the data directory."""
    return os.path.join(get_data_dir(), filename)
