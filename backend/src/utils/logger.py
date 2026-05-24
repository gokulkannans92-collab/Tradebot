import logging
import logging.handlers
import sys
import os
from typing import Optional

def setup_logging(
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    force_stdout: bool = False,
    clean_existing: bool = True
):
    """
    Centralized logging configuration for TradeBot.
    Ensures handlers are added only once and provides a consistent format.
    """
    root_logger = logging.getLogger()
    
    # Optional: Clear existing handlers to prevent duplication from libraries
    if clean_existing:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
    # Check if handlers already exist (if we didn't just clear them)
    if not clean_existing and root_logger.hasHandlers():
        return root_logger

    root_logger.setLevel(level)
    
    # Standard format: 2026-04-20 07:20:00,123 [Name] INFO - Message
    formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s - %(message)s")

    # Fix for Windows UnicodeEncodeError on console output
    log_stream = sys.stdout
    if sys.platform == 'win32':
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            elif hasattr(sys.stdout, 'buffer'):
                import io
                log_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass

    # 1. Console Handler
    if force_stdout or os.environ.get("LAUNCHED_FROM_DASHBOARD") == "1":
        # If launched from dashboard, we ONLY use stdout so the dashboard can capture it
        # and write it to the central log file itself.
        console_handler = logging.StreamHandler(log_stream)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)
    else:
        # 2. Rotating File Handler (Only if not in dashboard mode to avoid file locking conflicts)
        if log_file:
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            # Cap log file at 5MB, keep 5 backups → max 30MB total disk usage
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,  # 5 MB per file
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            root_logger.addHandler(file_handler)
            
        # Also show to console for manual runs
        console_handler = logging.StreamHandler(log_stream)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)

    # Silence verbose third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("smartapi").setLevel(logging.INFO)
    
    # Silence matplotlib and PIL (very verbose on startup)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    # Silence UI and initialization clutter
    logging.getLogger("src.ui.responsive").setLevel(logging.WARNING)
    logging.getLogger("src.ui.shared_state").setLevel(logging.WARNING)
    logging.getLogger("TradeBotGUI").setLevel(logging.WARNING)
    logging.getLogger("Dashboard").setLevel(logging.INFO)

    return root_logger
